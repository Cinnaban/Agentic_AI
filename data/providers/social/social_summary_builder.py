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
        
        platform_counts = Counter()

        for record in records:

            if not isinstance(
                record,
                dict
            ):
                continue

            platform = record.get(
                "platform"
            )
            content = (
                record.get("content")
                or ""
            )

            words = re.findall(
                r"\b[a-zA-Z]{4,}\b",
                content.lower()
            )

            stop_words = {
                "this",
                "that",
                "with",
                "from",
                "have",
                "been",
                "will",
                "would",
                "their",
                "about",
                "stock",
                "reddit",
                "discussion"
            }

            for word in words:
                if word not in stop_words:
                    keywords[word] += 1

            
            if (
                len(
                    summary[
                        "sample_posts"
                    ]
                )
                < 5
            ):
                content = (
                    record.get("content")
                    or ""
                ).strip()

                if (
                    content
                    and len(
                        summary["sample_posts"]
                    ) < 5
                ):
                    summary["sample_posts"].append(
                        content[:500]
                    )

            if platform:
                platform_counts[platform] += 1
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


        volume = len(summary["records"]) 
        
        summary["discussion_volume"] = volume 
        
        summary["available"] = volume > 0

        if volume >= 10:
            status = "available"
        elif volume > 0:
            status = "limited"
        else:
            status = "unavailable"
        summary["status"] = status
            
        summary[
            "platforms"
        ] = sorted(
            platforms
        )
        
        summary[
            "top_keywords"
        ] = dict(
            keywords.most_common(
                50
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