import uuid

from job_queue.work_package import (
    WorkPackage
)


class JobFactory:

    def create_work_package(
        self,
        companies,
        required_agents,
        original_message,
        source="discord",
        priority=100
    ):
        return WorkPackage(
            job_id=str(
                uuid.uuid4()
            ),
            companies=companies,
            required_agents=required_agents,
            original_message=original_message,
            source=source,
            priority=priority
        )