from h.i18n import TranslationString as _
from pyramid.view import view_config, view_defaults
from h import util, models, storage
import os
from h.models_redis import fetch_all_user_sessions


@view_defaults(route_name="account_expert_replay", renderer="h:templates/accounts/kmass-user-expert-replay.html.jinja2",is_authenticated=True)
class ExpertController:
    def __init__(self, request):
        self.request = request

    @view_config(request_method="GET")
    def get(self):

        fetch_result=fetch_all_user_sessions(userid=self.request.authenticated_userid)

        table_results=[]
        for result in fetch_result["table_result"]:
            json_item = {'session_id': result['doc_id'], 'task_name': result['interaction_context']}
            table_results.append(json_item)

        return {
            "table_results": table_results,
            "zero_message": _("No annotations matched your search."),
        }