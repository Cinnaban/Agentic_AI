class WorkerRegistry:

    def __init__(self):

        self.workers = {
            "gaming_pc": "online"
        }

    def get_worker_status(
        self,
        worker_name
    ):

        return self.workers.get(
            worker_name,
            "offline"
        )