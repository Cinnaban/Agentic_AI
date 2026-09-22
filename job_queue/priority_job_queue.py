import heapq
import itertools


class PriorityJobQueue:

    def __init__(
        self
    ):
        self._queue = []
        self._sequence = itertools.count()

    def put(
        self,
        job
    ):
        priority = getattr(
            job,
            "priority",
            100
        )

        sequence = next(
            self._sequence
        )

        heapq.heappush(
            self._queue,
            (
                priority,
                sequence,
                job
            )
        )

    def get(
        self
    ):
        if not self._queue:
            return None

        priority, sequence, job = (
            heapq.heappop(
                self._queue
            )
        )

        return job

    def empty(
        self
    ):
        return (
            len(self._queue) == 0
        )

    def size(
        self
    ):
        return len(
            self._queue
        )