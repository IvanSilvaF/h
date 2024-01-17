from h.i18n import TranslationString as _
from pyramid.view import view_config, view_defaults
from h import util, models, storage
import os
from h.models_redis import fetch_all_user_sessions,fetch_all_user_events_by_session
import time

def getPositionViewport(portX,portY,offset_x,offset_y):
    height=""
    width=""
    if (portY/2)> offset_y: height="top"
    else: height="bottom"
    if(portX/2)>offset_x: width="left"
    else: width="rigth"
    return height+" "+width

def getTextbyEvent(event_type,tag_name,text_content,viewPort,offset_x,offset_y,positionText):
    if event_type=="click":
        if positionText=="":
            positionText=getPositionViewport(int(viewPort.split("-")[0]),int(viewPort.split("-")[1]),offset_x,offset_y)
            return "Click on "+ text_content +" at the"+ positionText +" of the page"
        return "Click on "+ text_content
    elif event_type=="scroll":
        print("f")
    elif event_type=="keydown":
        print("f")
    else:
        print(event_type+ " MISS EVENT")
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
            
        return {
            "table_results": table_results,
            "zero_message": _("No annotations matched your search."),
        }
    @view_config(route_name="process_flow", request_method="GET", renderer="h:templates/accounts/kmass-user-process-flow.html.jinja2", is_authenticated=True)
    def processFlow(self):
        #session_id = self.request.params.get("id")
        sessionID="4"

        fetch_result=fetch_all_user_events_by_session(userid=self.request.authenticated_userid, sessionID=sessionID)

        auxTable=[]
        lastEvent=""
        for i in range(len(fetch_result["table_result"])):
            #if not auxTable: auxTable.append(fetch_result["table_result"][i])
            if lastEvent!= fetch_result["table_result"][i]['event_type']:
                auxTable.append(fetch_result["table_result"][i])
                lastEvent = fetch_result["table_result"][i]['event_type']
            elif lastEvent!="scroll" or lastEvent!="keydown":
                auxTable.append(fetch_result["table_result"][i])
                lastEvent = fetch_result["table_result"][i]['event_type']
        print(auxTable)
        #table_results=[]
        #auxText=""
        #positionText=""
        #for i in range(len(fetch_result["table_result"])):
        #    result= fetch_result["table_result"][i]
        #    if not table_results: table_results.append("Log in to your Moodle site")
        #    if result['event_type']!="OPEN" and result['event_type']!="beforeunload":
        #        auxText, positionText=getTextbyEvent(result['event_type'],result['tag_name'],result['text_content'],result['event_source'],result['offset_x'],result['offset_y'],positionText)
        #    print(result['event_type']+" - "+result['tag_name']+" - "+result['text_content']+" - "+result['event_source']+" - "+str(result['offset_x'])+" - "+str(result['offset_y']))
        #for result in fetch_result["table_result"]:
        #    if not table_results: table_results.append("Log in to your Moodle site")
        #    if result['event_type']!="OPEN" and result['event_type']!="beforeunload":
        #        auxText=getTextbyEvent(result['event_type'],result['tag_name'],result['text_content'],result['event_source'],result['offset_x'],result['offset_y'])
        #        print("hola")
            
        
        #    json_item = {'session_id': result['doc_id'], 'task_name': result['interaction_context']}
        #    table_results.append(json_item)
        #print("ER ",table_results)
        print("chao")    
        return {
            "table_results": "PROCCESS FLOW",
            "zero_message": _("No annotations matched your search."),
        }
    
   
