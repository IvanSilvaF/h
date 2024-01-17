from h.i18n import TranslationString as _
from pyramid.view import view_config, view_defaults
from h import util, models, storage
import os
from h.models_redis import fetch_all_user_sessions
import time

class ExpertController:
    def __init__(self, request):
        self.request = request

    @view_config(route_name="account_expert_replay", request_method="GET", renderer="h:templates/accounts/kmass-user-expert-replay.html.jinja2", is_authenticated=True)
    def getSessionUser(self):

        fetch_result=fetch_all_user_sessions(userid=self.request.authenticated_userid)

        table_results=[]
        for result in fetch_result["table_result"]:
            json_item = {'session_id': result['doc_id'], 'task_name': result['interaction_context']}
            table_results.append(json_item)
        print("ER ",table_results)
        return {
            "table_results": table_results,
            "zero_message": _("No annotations matched your search."),
        }
    @view_config(route_name="process_flow", request_method="GET", renderer="h:templates/accounts/kmass-user-process-flow.html.jinja2", is_authenticated=True)
    def processFlow(self):
        print("hola")
        session_id = self.request.params.get("id")
        #task_name = self.request.params.get("name")
        print(str(session_id))
        #order = self.request.params.get("order", ORDER)
        #recevived the tast name and session ID
        #get all the events 
        #process the event
        #Send the result
        #fetch_result=fetch_all_user_sessions(userid=self.request.authenticated_userid)

        #table_results=[]
        #for result in fetch_result["table_result"]:
        #    json_item = {'session_id': result['doc_id'], 'task_name': result['interaction_context']}
        #    table_results.append(json_item)
        #print("ER ",table_results)
        return {
            "table_results": "PROCCESS FLOW",
            "zero_message": _("No annotations matched your search."),
        }