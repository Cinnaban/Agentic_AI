# orchestrator/router.py

class Router:

    def route(self, company_result):

        if company_result.get(
            "is_company_request",
            False
        ):

            return {
                "destination": "gaming_pc"
            }

        return {
            "destination": "local"
        }