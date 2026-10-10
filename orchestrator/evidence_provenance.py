from datetime import datetime, timezone


class EvidenceProvenance:

    @staticmethod
    def _format_timestamp(value):
        if not isinstance(value, str) or not value.strip():
            return None

        try:
            parsed = datetime.fromisoformat(
                value.strip().replace("Z", "+00:00")
            )
        except ValueError:
            return None

        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)

        return parsed.astimezone(timezone.utc).strftime(
            "%Y-%m-%d %H:%M UTC"
        )

    @staticmethod
    def _format_publication_date(value):
        if not isinstance(value, str) or not value.strip():
            return None

        normalized = value.strip()
        try:
            parsed = datetime.fromisoformat(
                normalized.replace("Z", "+00:00")
            )
        except ValueError:
            try:
                parsed = datetime.strptime(normalized, "%Y-%m-%d")
            except ValueError:
                return None

        return parsed.date().isoformat()

    @classmethod
    def _latest_date_for_keys(cls, value, keys):
        found = []

        if isinstance(value, dict):
            for key, item in value.items():
                if key in keys:
                    date_value = cls._format_publication_date(item)
                    if date_value:
                        found.append(date_value)
                else:
                    found.extend(
                        cls._latest_date_for_keys(item, keys)
                    )
        elif isinstance(value, list):
            for item in value:
                found.extend(
                    cls._latest_date_for_keys(item, keys)
                )

        return max(found) if found else None

    @classmethod
    def format_note(cls, evidence, requires_current=False):
        if not isinstance(evidence, dict):
            evidence = {}
        requires_current = (
            requires_current
            or bool(evidence.get("requires_live_data"))
        )

        live_context = evidence.get("live_market_context")
        if not isinstance(live_context, dict):
            live_context = {}

        is_company_context = isinstance(
            evidence.get("source_status"),
            dict
        )
        results = evidence.get("results", [])
        if is_company_context:
            results = live_context.get("results", [])
        elif isinstance(results, list):
            social_results = evidence.get("social_results", [])
            if isinstance(social_results, list):
                results = results + social_results

        if not isinstance(results, list):
            results = []

        publishers = {}
        for result in results:
            if not isinstance(result, dict):
                continue

            source = result.get("source")
            if not isinstance(source, str) or not source.strip():
                continue

            publisher = source.strip()
            publishers.setdefault(publisher, set())
            publication_date = cls._format_publication_date(
                result.get("published_at")
            )
            if publication_date:
                publishers[publisher].add(publication_date)

        lines = ["Evidence and freshness:"]

        retrieved_at = cls._format_timestamp(
            evidence.get("retrieved_at")
            or live_context.get("retrieved_at")
        )
        if retrieved_at:
            lines.append(f"Retrieved: {retrieved_at}")

        unavailable = []
        if is_company_context:
            source_status = evidence["source_status"]
            source_names = {
                "financial_data": "Gaming PC quantitative analysis",
                "sec_facts": "SEC company facts",
                "sec_filings": "SEC filings",
                "macro": "FRED macroeconomic data",
                "live_market_context": "current news sources",
                "news": "company news feeds",
                "social": "public social discussion"
            }

            available = []
            for key, label in source_names.items():
                status = source_status.get(key)
                if status == "available":
                    if key in {"sec_facts", "sec_filings"}:
                        if "SEC facts/filings" not in available:
                            available.append("SEC facts/filings")
                    elif key == "live_market_context":
                        available.extend(
                            publisher
                            for publisher in publishers
                            if publisher not in available
                        )
                        if not publishers:
                            available.append(label)
                    elif key == "news":
                        news_sources = cls._sources_from_results(
                            evidence.get("news", [])
                        )
                        available.extend(
                            source
                            for source in news_sources
                            if source not in available
                        )
                        if not news_sources:
                            available.append(label)
                    elif key == "social":
                        social_context = evidence.get(
                            "social_context",
                            {}
                        )
                        social_sources = (
                            social_context.get("sources", [])
                            if isinstance(social_context, dict)
                            else []
                        )
                        if not isinstance(social_sources, list):
                            social_sources = []
                        available.extend(
                            source
                            for source in social_sources
                            if isinstance(source, str)
                            and source not in available
                        )
                        if not social_sources:
                            available.append(label)
                    else:
                        available.append(label)
                elif status == "unavailable":
                    unavailable.append(label)

            if available:
                lines.append("Sources: " + "; ".join(available))
            elif results:
                lines.append(
                    "Sources: " + "; ".join(publishers)
                )

            if requires_current and (
                source_status.get("live_market_context") != "available"
            ):
                lines.append(
                    "Current information could not be verified "
                    "from the configured live sources."
                )

            if unavailable:
                lines.append(
                    "Unavailable evidence: "
                    + "; ".join(unavailable)
                )

            data_dates = []
            filings_date = cls._latest_date_for_keys(
                evidence.get("sec_filings", []),
                {"filing_date"}
            )
            if filings_date:
                data_dates.append(f"SEC filing: {filings_date}")

            facts_date = cls._latest_date_for_keys(
                evidence.get("sec_facts", {}),
                {"filed"}
            )
            if facts_date and facts_date != filings_date:
                data_dates.append(f"SEC facts filed: {facts_date}")

            macro_date = cls._latest_date_for_keys(
                evidence.get("macro_facts", {}),
                {"observation_date"}
            )
            if macro_date:
                data_dates.append(f"FRED observation: {macro_date}")

            if data_dates:
                lines.append("Data dates: " + "; ".join(data_dates))
        elif publishers:
            lines.append("Sources: " + "; ".join(publishers))
        else:
            sources = evidence.get("sources", [])
            if isinstance(sources, list) and sources:
                lines.append(
                    "Sources: "
                    + "; ".join(
                        str(source)
                        for source in sources
                        if isinstance(source, str) and source.strip()
                    )
                )

        publication_dates = []
        for publisher, dates in publishers.items():
            if dates:
                publication_dates.append(
                    f"{publisher} (latest supplied publication: "
                    f"{max(dates)})"
                )
        if publication_dates:
            lines.append(
                "Publication dates: " + "; ".join(publication_dates)
            )

        if not is_company_context and not publishers:
            if requires_current:
                lines.append(
                    "Current information could not be verified "
                    "from the configured live sources."
                )
            elif results:
                lines.append(
                    "Could not verify: retrieved evidence did not "
                    "include an attributable publisher."
                )
            else:
                lines.append(
                    "Could not verify: no attributable public evidence "
                    "was retrieved."
                )

        return "\n".join(lines)

    @staticmethod
    def _sources_from_results(results):
        if not isinstance(results, list):
            return []

        sources = []
        for result in results:
            if not isinstance(result, dict):
                continue
            source = result.get("source")
            if (
                isinstance(source, str)
                and source.strip()
                and source not in sources
            ):
                sources.append(source.strip())
        return sources

    @classmethod
    def add_to_result(cls, result, evidence, requires_current=False):
        if not isinstance(result, dict):
            return result

        updated = dict(result)
        response = updated.get("response")
        note = cls.format_note(
            evidence,
            requires_current=requires_current
        )

        if isinstance(response, str) and response.strip():
            updated["response"] = response.rstrip() + "\n\n" + note
        else:
            updated["response"] = note

        return updated
