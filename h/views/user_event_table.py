"""Activity pages views."""

from urllib.parse import urlparse

from jinja2 import Markup
from pyramid import httpexceptions
from pyramid.view import view_config, view_defaults

from h import util
from h.activity import query
from h.i18n import TranslationString as _
from h.links import pretty_link
from h.models.group import ReadableBy
from h.paginator import paginate
from h.presenters.organization_json import OrganizationJSONPresenter
from h.search import parser
from h.security import Permission
from h.util.datetime import utc_us_style_date
from h.util.user import split_user
from h.views.groups import check_slug

PAGE_SIZE = 25


@view_defaults(
    route_name="activity.user_event", renderer="h:templates/activity/kmass-user-event.html.jinja2"
)
class UserEventSearchController:
    """View callables for the "activity.search" route."""

    def __init__(self, request):
        self.request = request
        # Cache a copy of the extracted query params for the child controllers to use if needed.
        self.parsed_query_params = query.extract(self.request)

    @view_config(request_method="GET")
    def user_event_search(self):  # pragma: no cover
        # Make a copy of the query params to be consumed by search.
        query_params = self.parsed_query_params.copy()

        # Check whether a redirect is required.
        query.check_url(self.request, query_params)

        page_size = self.request.params.get("page_size", PAGE_SIZE)
        try:
            page_size = int(page_size)
        except ValueError:
            page_size = PAGE_SIZE

        # Fetch results.
        results = query.execute(self.request, query_params, page_size=page_size)

        groups_suggestions = []

        if self.request.user:
            for group in self.request.user.groups:
                groups_suggestions.append({"name": group.name, "pubid": group.pubid})

        def tag_link(tag):
            tag = parser.unparse({"tag": tag})
            return self.request.route_url("activity.search", _query=[("q", tag)])

        def username_from_id(userid):
            parts = split_user(userid)
            return parts["username"]

        def user_link(userid):
            username = username_from_id(userid)
            return self.request.route_url("activity.user_search", username=username)

        return {
            "search_results": results,
            "groups_suggestions": groups_suggestions,
            "page": paginate(self.request, results.total, page_size=page_size),
            "pretty_link": pretty_link,
            "q": self.request.params.get("q", ""),
            "tag_link": tag_link,
            "user_link": user_link,
            "username_from_id": username_from_id,
            # The message that is shown (only) if there's no search results.
            "zero_message": _("No annotations matched your search."),
        }


def _parsed_query(request):
    """
    Return the parsed (MultiDict) query from the given request.

    Return a copy of the given search page request's search query, parsed from
    a string into a MultiDict.

    """
    return parser.parse(request.params.get("q", ""))


def _username_facets(request, parsed_query=None):
    """
    Return a list of the usernames that the search is faceted by.

    Returns a (possibly empty) list of all the usernames that the given
    search page request's search query is already faceted by.

    """
    return (parsed_query or _parsed_query(request)).getall("user")


def _tag_facets(request, parsed_query=None):
    """
    Return a list of the tags that the search is faceted by.

    Returns a (possibly empty) list of all the tags that the given
    search page request's search query is already faceted by.

    """
    return (parsed_query or _parsed_query(request)).getall("tag")


def _faceted_by_user(request, username, parsed_query=None):
    """
    Return True if the given request is already faceted by the given username.

    Return True if the given search page request's search query already
    contains a user facet for the given username, False otherwise.

    """
    return username in _username_facets(request, parsed_query)


def _faceted_by_tag(request, tag, parsed_query=None):
    """
    Return True if the given request is already faceted by the given tag.

    Return True if the given search page request's search query already
    contains a facet for the given tag, False otherwise.

    """
    return tag in _tag_facets(request, parsed_query)


def _redirect_to_user_or_group_search(request, params):
    if request.matched_route.name == "group_read":
        location = request.route_url(
            "group_read",
            pubid=request.matchdict["pubid"],
            slug=request.matchdict["slug"],
            _query=params,
        )
    elif request.matched_route.name == "activity.user_search":  # pragma: no cover
        location = request.route_url(
            "activity.user_search",
            username=request.matchdict["username"],
            _query=params,
        )
    return httpexceptions.HTTPSeeOther(location=location)


def _back(request):
    """Respond to a click on the ``back`` button."""
    new_params = _copy_params(request)
    del new_params["back"]
    return _redirect_to_user_or_group_search(request, new_params)


def _delete_lozenge(request):
    """
    Redirect to the /search page, keeping the search query intact.

    When on the user or group search page a lozenge for the user or group
    is rendered as the first lozenge in the search bar. The delete button
    on that first lozenge calls this view. Redirect to the general /search
    page, effectively deleting that first user or group lozenge, but
    maintaining any other search terms that have been entered into the
    search box.

    """
    new_params = _copy_params(request)
    del new_params["delete_lozenge"]
    location = request.route_url("activity.search", _query=new_params)
    return httpexceptions.HTTPSeeOther(location=location)


def _toggle_tag_facet(request):
    """
    Toggle the given tag from the search facets.

    If the search is not already faceted by the tag given in the
    "toggle_tag_facet" request param then redirect the browser to the same
    page but with the a facet for this  added to the search query.

    If the search is already faceted by the tag then redirect the browser
    to the same page but with this facet removed from the search query.

    """
    tag = request.params["toggle_tag_facet"]

    new_params = _copy_params(request)

    del new_params["toggle_tag_facet"]

    parsed_query = _parsed_query(request)
    if _faceted_by_tag(request, tag, parsed_query):
        # The search query is already faceted by the given tag,
        # so remove that tag facet.
        tag_facets = _tag_facets(request, parsed_query)
        tag_facets.remove(tag)
        del parsed_query["tag"]
        for tag_facet in tag_facets:
            parsed_query.add("tag", tag_facet)
    else:
        # The search query is not yet faceted by the given tag, so add a facet
        # for the tag.
        parsed_query.add("tag", tag)

    _update_q(new_params, parsed_query)

    return _redirect_to_user_or_group_search(request, new_params)


def _update_q(params, parsed_query):
    """
    Update the given request params based on the given parsed_query.

    Update the value of the 'q' string in the given request params based on the
    given parsed_query.

    If the query parses to an empty string then ensure that there is no 'q' in
    the given request params, to avoid redirecting the browser to a URL with an
    empty trailing ?q=

    """
    query_ = parser.unparse(parsed_query)
    if query_.strip():
        params["q"] = query_
    else:
        params.pop("q", None)


def _copy_params(request, params=None):
    """
    Return a copy of the given request's params.

    If the request contains an empty 'q' param then it is omitted from the
    returned copy of the params, to avoid redirecting the browser to a URL with
    an empty trailing ?q=

    """
    if params is None:
        params = request.params.copy()

    if "q" in params and not params["q"].strip():
        del params["q"]

    return params
