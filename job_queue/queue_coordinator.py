class QueueCoordinator:

    def __init__(
        self,
        router,
        job_factory,
        job_queue
    ):
        self.router = router
        self.job_factory = job_factory
        self.job_queue = job_queue

    def submit(
        self,
        source,
        original_message,
        companies=None,
        required_agents=None
    ):
        companies = (
            companies
            if companies is not None
            else []
        )

        required_agents = (
            required_agents
            if required_agents is not None
            else {}
        )

        priority = (
            self.router.get_priority(
                source
            )
        )

        work_package = (
            self.job_factory.create_work_package(
                companies=companies,
                required_agents=required_agents,
                original_message=original_message,
                source=source,
                priority=priority
            )
        )

        self.job_queue.put(
            work_package
        )

        return work_package

    def get_next(
        self
    ):
        return (
            self.job_queue.get()
        )

    def has_work(
        self
    ):
        return (
            not self.job_queue.empty()
        )

    def queue_size(
        self
    ):
        return (
            self.job_queue.size()
        )