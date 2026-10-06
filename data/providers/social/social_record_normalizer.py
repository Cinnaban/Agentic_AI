class SocialRecordNormalizer:

    def normalize_reddit(
        self,
        record
    ):
        if not isinstance(
            record,
            dict
        ):
            return None

        return {
            "platform": "reddit",
            "source_type": "social",

            "title":
                record.get(
                    "title"
                ),

            "content":
                record.get(
                    "content"
                ),

            "author":
                record.get(
                    "author"
                ),

            "timestamp":
                record.get(
                    "timestamp"
                ),

            "url":
                record.get(
                    "url"
                ),

            "engagement": {
                "score":
                    record.get(
                        "score"
                    ),

                "comments":
                    record.get(
                        "comments"
                    )
            },

            "query":
                record.get(
                    "query"
                ),

            "metadata": {}
        }

    def normalize_x(
        self,
        record
    ):
        if not isinstance(
            record,
            dict
        ):
            return None

        return {
            "platform": "x",
            "source_type": "social",

            "title": None,

            "content":
                record.get(
                    "content"
                ),

            "author":
                record.get(
                    "author"
                ),

            "timestamp":
                record.get(
                    "timestamp"
                ),

            "url":
                record.get(
                    "url"
                ),

            "engagement": {
                "likes":
                    record.get(
                        "likes"
                    ),

                "reposts":
                    record.get(
                        "reposts"
                    ),

                "replies":
                    record.get(
                        "replies"
                    )
            },

            "query":
                record.get(
                    "query"
                ),

            "metadata": {}
        }