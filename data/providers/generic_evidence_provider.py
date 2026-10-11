import re
from datetime import datetime, timezone
from urllib.parse import (
    urlsplit,
    urlunsplit
)

import requests

from data.providers.live.public_web_backend import (
    PublicWebBackend
)

from data.providers.live.public_topic_news_backend import (
    PublicTopicNewsBackend
)

from data.providers.live.firecrawl_backend import (
    FirecrawlBackend
)

from data.providers.social.social_evidence_provider import (
    SocialEvidenceProvider
)

from data.providers.social.social_summary_builder import (
    SocialSummaryBuilder
)

class GenericEvidenceProvider:

    def __init__(
        self
    ):

        self.web = (
            PublicWebBackend()
        )

        self.news = (
            PublicTopicNewsBackend()
        )

        self.firecrawl = (
            FirecrawlBackend()
        )

        self.social = (
            SocialEvidenceProvider()
        )
        
        self.social_summary_builder = (
            SocialSummaryBuilder()
        )

        self.max_pages = 15
        self.max_search_queries = 5

    @staticmethod
    def _subject_terms(subject):
        stop_words = {
            "about", "company", "corporation", "corp", "inc", "incorporated",
            "limited", "llc", "ltd", "organization", "what", "who"
        }
        return [
            term
            for term in re.findall(
                r"[a-z0-9]+",
                str(subject or "").lower()
            )
            if term not in stop_words
        ]

    @classmethod
    def _is_relevant_to_subject(cls, result, subject):
        terms = cls._subject_terms(subject)
        if not terms:
            return True

        title = str(result.get("title") or "")
        summary = str(result.get("summary") or "")
        url = str(result.get("url") or "")
        text = " ".join((title, summary, url)).lower()
        matched = sum(term in text for term in terms)
        required = 1 if len(terms) == 1 else max(
            2,
            (len(terms) + 1) // 2
        )
        return matched >= min(required, len(terms))

    @staticmethod
    def _source_details(url, search_query, subject):
        try:
            host = urlsplit(url).hostname or ""
        except (TypeError, ValueError):
            host = ""
        host = host.lower().removeprefix("www.")
        search_normalized = str(search_query or "").lower()
        subject_terms = GenericEvidenceProvider._subject_terms(
            subject
        )
        host_matches_subject = bool(
            subject_terms
            and all(term in host for term in subject_terms)
        )

        if host.endswith("wikipedia.org"):
            role = "reference"
        elif host.endswith(".gov") or host.endswith(".edu"):
            role = "government_or_academic"
        elif (
            "official website" in search_normalized
            and (
                "official" in str(url).lower()
                or host_matches_subject
            )
        ):
            role = "official_candidate"
        else:
            role = "independent_or_other"

        return host, role

    @classmethod
    def _rank_and_filter_results(cls, results, subject):
        social_hosts = (
            "reddit.com",
            "x.com",
            "twitter.com",
            "facebook.com",
            "instagram.com",
            "tiktok.com"
        )
        ranked = []
        for result in results:
            if not isinstance(result, dict):
                continue
            url = result.get("url")
            if not isinstance(url, str) or not cls._is_relevant_to_subject(
                result,
                subject
            ):
                continue
            host, role = cls._source_details(
                url,
                result.get("search_query"),
                subject
            )
            result.setdefault("evidence_level", "search_snippet")
            if any(
                host == social_host
                or host.endswith("." + social_host)
                for social_host in social_hosts
            ):
                continue
            result["source"] = host or "Unknown publisher"
            result["source_host"] = host
            result["source_role"] = role
            ranked.append(result)

        role_order = {
            "official_candidate": 0,
            "government_or_academic": 1,
            "reference": 2,
            "independent_or_other": 3
        }
        ranked.sort(
            key=lambda result: (
                role_order.get(result.get("source_role"), 3),
                result.get("source_host", "")
            )
        )
        return ranked

    def _build_factual_queries(
        self,
        query,
        search_queries,
        subject
    ):
        target = str(subject or query or "").strip()
        candidates = []
        target_terms = set(self._subject_terms(target))
        is_game_related = bool(target_terms.intersection({
            "game",
            "games",
            "developer",
            "developers",
            "studio",
            "studios"
        }))
        if target:
            candidates.extend([
                f'"{target}" official website',
                f'"{target}" Wikipedia',
                f'"{target}"',
                f'"{target}" current projects upcoming in development'
            ])
            if is_game_related:
                candidates.append(
                    f'"{target}" video game franchise projects history'
                )

        if isinstance(search_queries, list):
            candidates.extend(search_queries)

        cleaned = []
        target_terms = self._subject_terms(target)
        for candidate in candidates:
            if not isinstance(candidate, str):
                continue
            candidate = candidate.strip()
            if not candidate or candidate in cleaned:
                continue
            if subject and target_terms:
                query_terms = self._subject_terms(candidate)
                if not all(term in query_terms for term in target_terms):
                    continue
            cleaned.append(candidate)
            query_limit = self.max_search_queries + (
                2 if is_game_related else 1
            )
            if len(cleaned) >= query_limit:
                break
        return cleaned

    def _normalize_url(
        self,
        url
    ):

        if not isinstance(
            url,
            str
        ):

            return None


        url = url.strip()


        if not url:

            return None


        try:

            parsed = urlsplit(
                url
            )


            normalized = (
                urlunsplit(
                    (
                        parsed.scheme.lower(),
                        parsed.netloc.lower(),
                        parsed.path.rstrip("/"),
                        "",
                        ""
                    )
                )
            )


        except Exception:

            return url


        return normalized

    def get_context(
        self,
        query,
        search_queries=None,
        research_plan=None,
        subject=None,
        include_social=None
    ):

        if not isinstance(
            research_plan,
            dict
        ):

            research_plan = {}


        evidence_depth = (
            research_plan.get(
                "evidence_depth",
                "standard"
            )
        )


        if evidence_depth not in {
            "summary",
            "standard",
            "deep"
        }:

            evidence_depth = (
                "standard"
            )


        if evidence_depth == "summary":

            page_limit = 2


        elif evidence_depth == "deep":

            page_limit = (
                self.max_pages
            )


        else:

            page_limit = min(
                6,
                self.max_pages
            )


        if include_social is None:
            include_social = bool(
                re.search(
                    r"\b(subreddit|social discussion|social media reaction|"
                    r"public discussion|community reaction|reddit posts|"
                    r"tweets?|x posts?)\b|r/",
                    str(query or ""),
                    re.IGNORECASE
                )
            )

        cleaned_queries = self._build_factual_queries(
            query=query,
            search_queries=search_queries,
            subject=subject
        )

        wikipedia_result = None
        wikipedia_status = {
            "status": "not_requested"
        }
        if subject:
            wikipedia_result, wikipedia_status = (
                self._get_wikipedia_evidence(subject)
            )

        results = []
        if wikipedia_result:
            results.append(wikipedia_result)


        for search_query in (
            cleaned_queries
        ):

            web_results = (
                self.web.search(
                    company={},
                    query=search_query
                )
            )


            for result in web_results:

                if isinstance(
                    result,
                    dict
                ):

                    result[
                        "search_query"
                    ] = search_query


            results.extend(
                web_results
            )


        deduplicated = []

        seen = set()


        for result in results:

            if not isinstance(
                result,
                dict
            ):

                continue


            url = result.get(
                "url"
            )


            normalized_url = (
                self._normalize_url(
                    url
                )
            )


            key = (
                normalized_url
                or result.get(
                    "title"
                )
            )


            if not key:

                continue


            if key in seen:

                continue


            seen.add(
                key
            )


            deduplicated.append(
                result
            )

        deduplicated = self._rank_and_filter_results(
            deduplicated,
            subject
        )
        deduplicated = self._select_diverse_sources(
            deduplicated,
            limit=8
        )

        enriched = (
            self._enrich(
                deduplicated,
                page_limit=page_limit
            )
        )
        social_context = {
            "results": [],
            "sources": []
        }
        social_summary = {}
        if include_social:
            social_context = self.social.get_context(
                query=query,
                search_queries=cleaned_queries
            )
            social_summary = self.social_summary_builder.build(
                social_context.get("results", [])
            )


        for index, result in enumerate(enriched, start=1):
            result["source_id"] = f"S{index}"

        return {
            "available":
                bool(
                    enriched
                    or social_context.get(
                        "results"
                    )
                ),

            "query":
                query,

            "subject":
                subject,

            "results":
                enriched,
                
            "social_results":
            social_context.get("results", []),
                
            "social_summary":
                social_summary,

            "search_queries":
                cleaned_queries,

            "research_plan":
                research_plan,

            "wikipedia_status":
                wikipedia_status,

            "evidence_depth":
                evidence_depth,

            "page_limit":
                page_limit,

            "sources":
                [
                    {
                        "source_id": result.get("source_id"),
                        "title": result.get("title"),
                        "publisher": result.get("source"),
                        "url": result.get("url"),
                        "source_role": result.get("source_role"),
                        "evidence_level": result.get(
                            "evidence_level",
                            "search_snippet"
                        )
                    }
                    for result in enriched
                ],

            "retrieved_at":
                datetime.now(timezone.utc).isoformat()
        }

    @classmethod
    def _get_wikipedia_evidence(cls, subject):
        try:
            search_response = requests.get(
                "https://en.wikipedia.org/w/api.php",
                params={
                    "action": "query",
                    "list": "search",
                    "srsearch": subject,
                    "srlimit": 5,
                    "format": "json"
                },
                headers={
                    "User-Agent": (
                        "AgenticAIResearchBot/1.0 "
                        "(factual source retrieval)"
                    )
                },
                timeout=(3, 10)
            )
            search_response.raise_for_status()
            search_payload = search_response.json()
            matches = (
                search_payload.get("query", {}).get("search", [])
                if isinstance(search_payload, dict)
                else []
            )
            terms = cls._subject_terms(subject)
            page_title = None
            for match in matches:
                if not isinstance(match, dict):
                    continue
                title = str(match.get("title") or "")
                title_terms = cls._subject_terms(title)
                if terms and sum(
                    term in title_terms
                    for term in terms
                ) < min(2, len(terms)):
                    continue
                page_title = title
                break
            if not page_title:
                return None, {
                    "status": "not_found",
                    "source": "Wikipedia"
                }

            page_response = requests.get(
                "https://en.wikipedia.org/w/api.php",
                params={
                    "action": "query",
                    "prop": "extracts|info",
                    "explaintext": 1,
                    "exchars": 12000,
                    "inprop": "url",
                    "redirects": 1,
                    "titles": page_title,
                    "format": "json"
                },
                headers={
                    "User-Agent": (
                        "AgenticAIResearchBot/1.0 "
                        "(factual source retrieval)"
                    )
                },
                timeout=(3, 10)
            )
            page_response.raise_for_status()
            page_payload = page_response.json()
            pages = (
                page_payload.get("query", {}).get("pages", {})
                if isinstance(page_payload, dict)
                else {}
            )
            page = next(
                (
                    item
                    for item in pages.values()
                    if isinstance(item, dict)
                ),
                None
            )
            extract = (
                page.get("extract", "").strip()
                if isinstance(page, dict)
                else ""
            )
            if not extract:
                return None, {
                    "status": "unavailable",
                    "source": "Wikipedia",
                    "error": "The matching page had no readable article text."
                }

            return {
                "source_id": None,
                "title": page.get("title", page_title),
                "published_at": None,
                "source": "en.wikipedia.org",
                "source_host": "en.wikipedia.org",
                "source_role": "reference",
                "source_type": "encyclopedia",
                "evidence_level": "retrieved_reference",
                "summary": "",
                "content": extract,
                "url": page.get(
                    "fullurl",
                    (
                        "https://en.wikipedia.org/wiki/"
                        + page_title.replace(" ", "_")
                    )
                ),
                "search_query": "Direct Wikipedia article lookup"
            }, {
                "status": "available",
                "source": "Wikipedia",
                "title": page.get("title", page_title)
            }
        except (
            requests.RequestException,
            ValueError,
            TypeError,
            AttributeError
        ) as exc:
            return None, {
                "status": "unavailable",
                "source": "Wikipedia",
                "error": str(exc)
            }

    @staticmethod
    def _select_diverse_sources(results, limit):
        selected = []
        seen_hosts = set()
        deferred = []
        for result in results:
            host = result.get("source_host")
            if host and host not in seen_hosts:
                selected.append(result)
                seen_hosts.add(host)
            else:
                deferred.append(result)
            if len(selected) >= limit:
                break
        if len(selected) < limit:
            selected.extend(deferred[:limit - len(selected)])
        for index, result in enumerate(selected, start=1):
            result["source_id"] = f"S{index}"
        return selected

    def _enrich(
        self,
        results,
        page_limit=None
    ):


        if not isinstance(
            page_limit,
            int
        ):

            page_limit = (
                self.max_pages
            )

        if page_limit < 0:

            page_limit = 0
            
        if not self.firecrawl.health_check():

            return results


        results_by_query = {}


        for result in results:

            if not isinstance(
                result,
                dict
            ):

                continue


            search_query = result.get(
                "search_query",
                "default"
            )


            results_by_query.setdefault(
                search_query,
                []
            ).append(
                result
            )


        enriched_count = 0

        index = 0


        while (
            enriched_count
            < page_limit
        ):

            found_candidate = False


            for query_results in (
                results_by_query.values()
            ):

                if index >= len(
                    query_results
                ):

                    continue


                result = query_results[
                    index
                ]


                url = result.get(
                    "url"
                )


                if not url:

                    continue


                found_candidate = True


                scraped = (
                    self.firecrawl.retrieve(
                        url
                    )
                )


                if not scraped:

                    continue


                markdown = scraped.get(
                    "markdown"
                )


                if not markdown:

                    continue


                result[
                    "content"
                ] = markdown


                result[
                    "content_retrieved_by"
                ] = "Firecrawl"
                result["evidence_level"] = "retrieved_webpage"
                metadata = scraped.get("metadata")
                if isinstance(metadata, dict):
                    scraped_title = metadata.get("title")
                    if (
                        isinstance(scraped_title, str)
                        and scraped_title.strip()
                    ):
                        result["title"] = scraped_title.strip()


                enriched_count += 1


                if enriched_count >= (
                    page_limit
                ):

                    break


            if not found_candidate:

                break


            index += 1


        return results