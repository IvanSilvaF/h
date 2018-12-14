# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from jinja2 import Markup
from pyramid.view import view_config, view_defaults
from pyramid.httpexceptions import HTTPFound
from sqlalchemy import func

from h import form  # noqa F401
from h import i18n
from h import models
from h import paginator
from h.models.annotation import Annotation
from h.models.group_scope import GroupScope
from h.models.organization import Organization
from h.schemas.forms.admin.group import CreateAdminGroupSchema

_ = i18n.TranslationString


@view_config(
    route_name="admin.groups",
    request_method="GET",
    renderer="h:templates/admin/groups.html.jinja2",
    permission="admin_groups",
)
@paginator.paginate_query
def groups_index(context, request):
    q = request.params.get("q")

    filter_terms = []
    if q:
        name = models.Group.name
        filter_terms.append(func.lower(name).like("%{}%".format(q.lower())))

    return (
        request.db.query(models.Group)
        .filter(*filter_terms)
        .order_by(models.Group.created.desc())
    )


@view_defaults(
    route_name="admin.groups_create",
    renderer="h:templates/admin/groups_create.html.jinja2",
    permission="admin_groups",
)
class GroupCreateViews(object):
    """Views for admin create-group forms"""

    def __init__(self, request):
        self.request = request

        self.user_svc = self.request.find_service(name="user")
        self.list_org_svc = self.request.find_service(name="list_organizations")
        self.group_create_svc = self.request.find_service(name="group_create")
        self.group_members_svc = self.request.find_service(name="group_members")

        self.organizations = {o.pubid: o for o in self.list_org_svc.organizations()}
        self.default_org_id = Organization.default(self.request.db).pubid

        self.schema = CreateAdminGroupSchema().bind(
            request=request, organizations=self.organizations, user_svc=self.user_svc
        )
        self.form = _create_form(self.request, self.schema, (_("Create New Group"),))

    @view_config(request_method="GET")
    def get(self):
        """Render the admin create-group form"""
        self.form.set_appstruct(
            {
                "creator": self.request.user.username,
                "organization": self.default_org_id,
                "enforce_scope": True,
            }
        )
        return self._template_context()

    @view_config(request_method="POST")
    def post(self):
        def on_success(appstruct):
            """Create a group on successful validation of POSTed form data"""

            organization = self.organizations[appstruct["organization"]]
            # We know this user exists because it is checked during schema validation
            creator_userid = self.user_svc.fetch(
                appstruct["creator"], organization.authority
            ).userid

            create_fns = {
                "open": self.group_create_svc.create_open_group,
                "restricted": self.group_create_svc.create_restricted_group,
            }

            type_ = appstruct["group_type"]
            if type_ not in ["open", "restricted"]:
                raise Exception("Unsupported group type {}".format(type_))

            group = create_fns[type_](
                name=appstruct["name"],
                userid=creator_userid,
                origins=appstruct["origins"],
                description=appstruct["description"],
                organization=organization,
                enforce_scope=appstruct["enforce_scope"],
            )

            # Add members to the group. We know that these users exist
            # because that check is part of form schema validation.
            member_userids = []
            for username in appstruct["members"]:
                member_userids.append(
                    self.user_svc.fetch(username, organization.authority).userid
                )

            self.group_members_svc.add_members(group, member_userids)

            self.request.session.flash(
                Markup('Created new group "{name}"'.format(name=group.name)),
                queue="success",
            )

            # Direct the user back to the admin page.
            return HTTPFound(location=self.request.route_url("admin.groups"))

        return form.handle_form_submission(
            self.request,
            self.form,
            on_success=on_success,
            on_failure=self._template_context,
        )

    def _template_context(self):
        return {"form": self.form.render()}


@view_defaults(
    route_name="admin.groups_edit",
    permission="admin",
    renderer="h:templates/admin/groups_edit.html.jinja2",
)
class GroupEditViews(object):
    def __init__(self, context, request):
        self.group = context
        self.request = request

        self.list_org_svc = request.find_service(name="list_organizations")
        self.user_svc = request.find_service(name="user")
        self.group_update_svc = self.request.find_service(name="group_update")
        self.group_members_svc = self.request.find_service(name="group_members")

        self.organizations = {
            o.pubid: o for o in self.list_org_svc.organizations(self.group.authority)
        }

        self.schema = CreateAdminGroupSchema().bind(
            request=self.request,
            group=self.group,
            organizations=self.organizations,
            user_svc=self.user_svc,
        )
        self.form = _create_form(self.request, self.schema, (_("Save"),))

    @view_config(request_method="GET")
    def read(self):
        self._update_appstruct()
        return self._template_context()

    @view_config(request_method="POST", route_name="admin.groups_delete")
    def delete(self):
        group = self.group
        svc = self.request.find_service(name="delete_group")

        svc.delete(group)
        self.request.session.flash(
            _("Successfully deleted group %s" % (group.name), "success")
        )

        return HTTPFound(location=self.request.route_path("admin.groups"))

    @view_config(request_method="POST")
    def update(self):
        group = self.group

        def on_success(appstruct):
            """Update the group resource on successful form validation"""

            organization = self.organizations[appstruct["organization"]]
            scopes = [GroupScope(origin=o) for o in appstruct["origins"]]

            self.group_update_svc.update(
                group,
                organization=organization,
                creator=self.user_svc.fetch(appstruct["creator"], group.authority),
                description=appstruct["description"],
                name=appstruct["name"],
                scopes=scopes,
                enforce_scope=appstruct["enforce_scope"],
            )

            memberids = []
            for username in appstruct["members"]:
                memberids.append(self.user_svc.fetch(username, group.authority))

            self.group_members_svc.update_members(group, memberids)

            self.form = _create_form(self.request, self.schema, (_("Save"),))
            self._update_appstruct()

            return self._template_context()

        return form.handle_form_submission(
            self.request,
            self.form,
            on_success=on_success,
            on_failure=self._template_context,
        )

    def _update_appstruct(self):
        group = self.group
        self.form.set_appstruct(
            {
                # `group.creator` is nullable but "Creator" is currently a required
                # field, so the user will have to pick one when editing the group.
                "creator": group.creator.username if group.creator else "",
                "description": group.description or "",
                "group_type": group.type,
                "name": group.name,
                "members": [m.username for m in group.members],
                "organization": group.organization.pubid,
                "origins": [s.origin for s in group.scopes],
                "enforce_scope": group.enforce_scope,
            }
        )

    def _template_context(self):
        num_annotations = (
            self.request.db.query(Annotation)
            .filter_by(groupid=self.group.pubid)
            .count()
        )
        return {
            "form": self.form.render(),
            "pubid": self.group.pubid,
            "group_name": self.group.name,
            "annotation_count": num_annotations,
            "member_count": len(self.group.members),
        }


def _userid(username, authority):
    return models.User(username=username, authority=authority).userid


def _create_form(request, schema, buttons):
    # `deform.Form` throws an exception when rendering if `validate` was earlier called
    # on the same `Form` and the number of items in a list field when validating does not
    # match the number of items when rendering.
    # This can happen here if a user enters the same username multiple times and clicks "Save".
    # Re-creating the form before rendering after a _successful_ save resolves the problem.
    return request.create_form(schema, buttons=buttons)
