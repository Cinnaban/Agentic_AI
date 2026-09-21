# memory/session_manager.py

class SessionManager:

    def __init__(self):
        self.sessions = {}

    def save_interaction(
        self,
        user_id,
        message,
        response
    ):

        if user_id not in self.sessions:
            self.sessions[user_id] = []

        self.sessions[user_id].append(
            {
                "message": message,
                "response": response
            }
        )

    def get_history(
        self,
        user_id
    ):

        return self.sessions.get(
            user_id,
            []
        )