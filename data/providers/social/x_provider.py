import sys
import traceback
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.append(str(ROOT_DIR))

from data.providers.social.social_record_normalizer import (
    SocialRecordNormalizer
)

from data.providers.live.firecrawl_backend import (
    FirecrawlBackend
)

from configs.config import (
    Config
)


class XProvider:

    def __init__(
        self
    ):
        self.normalizer = (
            SocialRecordNormalizer()
        )

        self.firecrawl = (
            FirecrawlBackend()
        )

    def search(
        self,
        query,
        limit=None
    ):
        if not Config.ENABLE_SOCIAL:
            return []

        if not Config.ENABLE_X:
            return []

        if limit is None:
            limit = (
                Config.SOCIAL_RESULT_LIMIT
            )

        raw_results = (
            self._fetch_results(
                query,
                limit
            )
        )

        records = []

        for result in raw_results:

            normalized = (
                self.normalizer
                .normalize_x(
                    result
                )
            )

            if normalized:
                records.append(
                    normalized
                )

        return records

    def _fetch_results(
        self,
        query,
        limit
    ):
        return []