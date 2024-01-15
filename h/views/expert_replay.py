from h.i18n import TranslationString as _
from pyramid.view import view_config, view_defaults
from h import util, models, storage
import os

@view_defaults(route_name="account_expert_replay", renderer="h:templates/accounts/kmass-user-expert-replay.html.jinja2",is_authenticated=True)
class ExpertController:
    def __init__(self, request):
        self.request = request

    @view_config(request_method="GET")
    def printTEST(self):

        #test = self.request.db.query(models.Test).all()
        #print(test[0].name)


        return {
            "results": "hola expert replay",
            "zero_message": _("No annotations matched your search."),
        }