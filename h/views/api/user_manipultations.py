"""
HTTP/REST API for storage and retrieval of annotation data.

This module contains the views which implement our REST API, mounted by default
at ``/api``. Currently, the endpoints are limited to:

- basic CRUD (create, read, update, delete) operations on annotations
- annotation search
- a handful of authentication related endpoints

It is worth noting up front that in general, authorization for requests made to
each endpoint is handled outside of the body of the view functions. In
particular, requests to the CRUD API endpoints are protected by the Pyramid
authorization system. You can find the mapping between annotation "permissions"
objects and Pyramid ACLs in :mod:`h.traversal`.
"""
import copy
import json
import os
import re
import requests
import shutil
from redis_om import get_redis_connection
from urllib.parse import urljoin, urlparse

from h.exceptions import InvalidUserId
from h.security import Permission
from h.views.api.config import api_config
from h.models_redis import UserEvent

def split_user(userid):
    """
    Return the user and domain parts from the given user id as a dict.

    For example if userid is u'acct:seanh@hypothes.is' then return
    {'username': u'seanh', 'domain': u'hypothes.is'}'

    :raises InvalidUserId: if the given userid isn't a valid userid

    """
    match = re.match(r"^acct:([^@]+)@(.*)$", userid)
    if match:
        return {"username": match.groups()[0], "domain": match.groups()[1]}
    raise InvalidUserId(userid)


@api_config(
    versions=["v1", "v2"],
    route_name="api.upload",
    request_method="POST",
    permission=Permission.Annotation.CREATE,
    link_name="upload",
    description="Upload files to the cloud",
)
def upload(request):
    username = split_user(request.authenticated_userid)["username"]
    settings = request.registry.settings

    if request.POST["file-upload"] is None:
        return {"error": "no file"}

    root_dir = os.path.join(settings.get("user_root"), username)
    input_file = request.POST["file-upload"].file

    meta = json.loads(request.POST["meta"])
    filetype = meta["type"]

    if not os.path.exists(root_dir):
        os.mkdir(root_dir)

    if filetype == "html":
        print("meta", meta)
        parsed_url = urlparse(meta["link"])
        host_name = parsed_url.netloc
        name = meta["name"]
        if name == "":
            name = host_name + parsed_url.path.split("/")[-1]
        if not name.endswith(".html"):
            name = name + ".html"
        try:
            filepath = os.path.join(root_dir, name)
            if os.path.exists(filepath):
                return {"error": name + " already exists"}
            with open(filepath, "wb") as output_file:
                shutil.copyfileobj(input_file, output_file)
        except Exception as e:
            return {"error": repr(e)}

        relavtive_path = os.path.relpath(filepath, settings.get("user_root"))
        return {"succ": {
            "depth": 0,
            "id": root_dir,
            "link": os.path.join(settings.get("user_root_url"), "static", relavtive_path),
            "name": name,
            "path": filepath,
            "type": "file"
        }}

    parent_path = meta["id"]
    file_path = meta["path"]
    depth = int(meta["depth"])
    name = meta["name"]
    relavtive_path = os.path.relpath(file_path, settings.get("user_root"))
    print("filepath", file_path)

    if not os.path.exists(root_dir):
        os.mkdir(root_dir)

    try:
        # check the user directory
        if not os.path.exists(parent_path):
            os.mkdir(parent_path)

        if os.path.exists(file_path):
            return {"error": name + " already exists"}

        with open(file_path, "wb") as output_file:
            shutil.copyfileobj(input_file, output_file)
    except Exception as e:
        return {"error": repr(e)}

    # transfer to TA B
    local_file = open(file_path, "rb")
    files = {"myFile": (name, local_file)}
    url = urljoin(request.registry.settings.get("query_url"), "upload")
    data = {"url": os.path.join(settings.get("user_root_url"), "static", relavtive_path)}

    succ_response = {"succ": {
        "depth": depth,
        "id": parent_path,
        "link": os.path.join(settings.get("user_root_url"), "static", relavtive_path),
        "name": name,
        "path": file_path,
        "type": "file"
    }}

    try:
        response = requests.post(url, files=files, data=data)
        # result = response.json()
    except Exception as e:
        return {"error": repr(e)}
    else:
        if response.status_code != 200:
            return {"error": "TA B proxy error"}
    try:
        result = response.json()
    except Exception as e:
        return {"error": repr(e)}
    else:
        # check the ingesting is succ?
        if "error" in result:
            if "[the ingestion failed]" in result["error"]:
                succ_response["tab"] = result["error"]
            else:
                return result

    local_file.close()
    return succ_response


@api_config(
    versions=["v1", "v2"],
    route_name="api.delete",
    request_method="DELETE",
    permission=Permission.Annotation.CREATE,
    link_name="delete",
    description="Delete files from the cloud",
)
def delete(request):
    username = split_user(request.authenticated_userid)["username"]
    settings = request.registry.settings

    file_path = request.GET.get('file')

    try:

        if not os.path.exists(file_path):
            return {'error': 'could not find the file in user repository'}
        else:
            os.remove(file_path)
            return {'succ': {
                "filepath": file_path,
                "parent_filepath": os.path.dirname(file_path),
                }}
    except Exception as e:
        return {"error": repr(e)}


def iterate_directory(dir, name, url, depth):
    current_path = os.path.join(url, name)
    directory_node = {
        'path': dir,
        'id': dir,
        'name': name,
        'type': 'dir', # dir | file
        'link': current_path,
        'children': [],
        'depth': depth,
    }
    with os.scandir(dir) as it:
        for entry in it:
            if entry.is_file():
                file_node = {
                    'path': os.path.join(dir, entry.name),
                    'id': dir,
                    'name': entry.name,
                    'type': 'file',
                    'link': os.path.join(current_path, entry.name),
                    'children': [],
                    'depth': depth,
                }
                directory_node['children'].append(file_node)
            elif entry.is_dir():
                directory_node['children'].append(iterate_directory(os.path.join(dir, entry.name), entry.name, current_path, depth + 1))

    return directory_node


@api_config(
    versions=["v1", "v2"],
    route_name="api.repository",
    request_method="GET",
    permission=Permission.Annotation.CREATE,
    link_name="repository",
    description="Get user cloud repository",
)
def repository(request):
    username = split_user(request.authenticated_userid)["username"]
    settings = request.registry.settings
    url = os.path.join(settings.get("user_root_url"), "static", username)

    dir = os.path.join(settings.get("user_root"), username)
    if not os.path.exists(dir):
            os.mkdir(dir)
    return iterate_directory(dir, username, os.path.join(settings.get("user_root_url"), "static"), 0)


@api_config(
    versions=["v1", "v2"],
    route_name="api.client_url",
    request_method="GET",
    link_name="client",
    description="Get the Client location",
)
def client_url(request):
    return {
        "base_url": request.registry.settings.get("homepage_url"),
        "url_string": "",
    }


@api_config(
    versions=["v1", "v2"],
    route_name="api.recommendation",
    request_method="POST",
    permission=Permission.Annotation.CREATE,
    link_name="push_recommendation",
    description="Post the Recommendation",
)
def push_recommendation(request):
    username = split_user(request.authenticated_userid)["username"]
    data = request.json_body

    key = "h:Recommendation:" + username + ":" + data["url"]
    get_redis_connection().set(key, json.dumps(data))

    expiration_time = 120
    get_redis_connection().expire(key, expiration_time)

    return {
        "succ": data["url"] + "has been saved"
    }


@api_config(
    versions=["v1", "v2"],
    route_name="api.recommendation",
    request_method="GET",
    permission=Permission.Annotation.CREATE,
    link_name="pull_recommendation",
    description="Get the Recommendation",
)
def pull_recommendation(request):
    username = split_user(request.authenticated_userid)["username"]
    encoded_url = request.GET.get("url")

    key_pattern = "h:Recommendation:" + username + ":" + encoded_url
    keys = get_redis_connection().keys(key_pattern)

    if len(keys) > 0:
        ret = get_redis_connection().getdel(keys[0])
        print("ret", ret)
        return json.loads(ret)

    return {
        "id": "",
        "url": "",
        "type": "",
        "title": "",
        "context": "",
    }


@api_config(
    versions=["v1", "v2"],
    route_name="api.event",
    request_method="POST",
    permission=Permission.Annotation.CREATE,
    link_name="event",
    description="Create an user interaction",
)
def event(request):
    user = request.user
    event = json.loads(request.body)

    user_event = UserEvent(**event)
    user_event.save()


    return {
        "succ": "event has been saved",
    }
