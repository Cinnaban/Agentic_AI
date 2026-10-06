import re

from collections import Counter

class SocialSummaryBuilder:

    def build(
        self,
        records
    ):
        if not isinstance(
            records,
            list
        ):
            records = []

        summary = {
            "discussion_volume":
                len(
                    records
                ),

            "platforms": [],

            "records": [],

            "available":
                bool(
                    records
                ),
                
            "sample_posts": [],

            "top_keywords": {},

            "discussion_themes": []
        }
        
        platforms = set()
        
        keywords = Counter()

        for record in records:

            if not isinstance(
                record,
                dict
            ):
                continue

            platform = record.get(
                "platform"
            )
            
            if (
                len(
                    summary[
                        "sample_posts"
                    ]
                )
                < 5
            ):
                summary[
                    "sample_posts"
                ].append(
                    record.get(
                        "content"
                    )
                )

            if platform:
                platforms.add(
                    platform
                )

            summary[
                "records"
            ].append(
                {
                    "platform":
                        platform,

                    "author":
                        record.get(
                            "author"
                        ),

                    "content":
                        record.get(
                            "content"
                        ),
                        
                    "url":
                        record.get(
                            "url"
                        )
                }
            )

        summary[
            "platforms"
        ] = sorted(
            platforms
        )
        
        summary[
            "top_keywords"
        ] = dict(
            keywords.most_common(
                20
            )
        )
        
        summary[
            "discussion_themes"
        ] = list(
            summary[
                "top_keywords"
            ].keys()
        )[:10]

        return summary