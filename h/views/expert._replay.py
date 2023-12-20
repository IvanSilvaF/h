

@view_defaults(route_name="expert_replay", renderer="h:templates/expert_replay/expert_replay.html.jinja2")
class TestController:
    def __init__(self, request):
        self.request = request

    @view_config(request_method="GET")
    def printTEST(self):

        test = self.request.db.query(models.Test).all()
        print(test[0].name)

        return {
            "results": test,
            "zero_message": _("No annotations matched your search."),
        }