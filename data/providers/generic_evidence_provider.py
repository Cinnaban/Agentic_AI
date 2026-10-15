import re
from datetime import datetime, timezone
from urllib.parse import (
    urlsplit,
    urlunsplit
)

from configs.config import Config

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
from orchestrator.freshness_detector import FreshnessDetector
from shared_storage.reference_archive import PublicReferenceArchive

class GenericEvidenceProvider:
    SEARCH_STOP_WORDS = {
        "a", "about", "above", "after", "against", "all", "also", "an",
        "and", "any", "are", "as", "at", "be", "because", "been", "before",
        "being", "between", "both", "but", "by", "can", "could", "did",
        "do", "does", "doing", "down", "during", "each", "explain", "for",
        "from", "further", "get", "give", "had", "has", "have", "he", "her",
        "here", "hers", "him", "his", "how", "i", "if", "in", "into", "is",
        "it", "its", "itself", "just", "me", "more", "most", "my", "no",
        "nor", "not", "of", "off", "on", "once", "only", "or", "other",
        "our", "out", "over", "own", "please", "same", "she", "should",
        "so", "some", "such", "than", "that", "the", "their", "them",
        "then", "there", "these", "they", "this", "those", "through", "to",
        "too", "under", "until", "up", "us", "very", "was", "we", "were",
        "what", "when", "where", "which", "while", "who", "why", "will",
        "with", "would", "you", "your", "compare", "comparison", "different",
        "difference", "differences", "versus", "vs"
    }

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

        self.reference_archive = PublicReferenceArchive()
        self.freshness_detector = FreshnessDetector()
        self.max_pages = 15
        self.max_search_queries = 5

    @staticmethod
    def _subject_terms(subject):
        stop_words = {
            "about", "company", "corporation", "corp", "inc", "incorporated",
            "limited", "llc", "ltd", "organization", "what", "who",
            "and", "between", "compare", "comparison", "difference",
            "differences", "explain", "versus"
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
    def _search_terms(cls, text):
        terms = set()
        for term in re.findall(r"[a-z0-9]+", str(text or "").casefold()):
            if term in cls.SEARCH_STOP_WORDS or len(term) < 2:
                continue
            if term.endswith("ies") and len(term) > 4:
                term = term[:-3] + "y"
            elif term.endswith("s") and not term.endswith(("ss", "us")):
                term = term[:-1]
            terms.add(term)
        return terms

    @classmethod
    def _relevance_score(cls, result, query, search_queries, subject):
        primary_terms = cls._search_terms(
            " ".join((str(query or ""), str(subject or "")))
        )
        result_text = " ".join(
            str(result.get(key) or "")
            for key in ("title", "summary", "url")
        )
        result_terms = cls._search_terms(result_text)
        primary_matches = len(primary_terms & result_terms)
        if primary_matches:
            return primary_matches

        planned_terms = cls._search_terms(
            " ".join(
                item for item in search_queries
                if isinstance(item, str)
            )
        )
        planned_matches = len(planned_terms & result_terms)
        return planned_matches if planned_matches >= 2 else 0

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
    def _rank_and_filter_results(
        cls,
        results,
        subject=None,
        query=None,
        search_queries=None
    ):
        if not isinstance(search_queries, list):
            search_queries = []

        topic_terms = cls._search_terms(
            " ".join((str(query or ""), str(subject or "")))
        )
        planned_terms = cls._search_terms(" ".join(search_queries))
        should_filter_by_relevance = bool(topic_terms or planned_terms)

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
            if not isinstance(url, str):
                continue
            relevance = cls._relevance_score(
                result,
                query,
                (
                    [result["search_query"]]
                    if result.get("search_query")
                    else search_queries
                ),
                subject
            )
            if should_filter_by_relevance and relevance == 0:
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
            ranked.append((relevance, result))

        role_order = {
            "official_candidate": 0,
            "government_or_academic": 1,
            "reference": 2,
            "independent_or_other": 3
        }
        ranked.sort(
            key=lambda item: (
                -item[0],
                role_order.get(item[1].get("source_role"), 3),
                item[1].get("source_host", "")
            )
        )
        return [result for _, result in ranked]

    def _build_factual_queries(
        self,
        query,
        search_queries,
        subject
    ):
        target = str(subject or query or "").strip()
        candidates = []
        if subject:
            candidates.extend([
                f'"{target}" official website',
                str(query or "").strip(),
                f'"{target}" overview'
            ])
        else:
            candidates.append(str(query or "").strip())
        if isinstance(search_queries, list):
            candidates.extend(search_queries)

        cleaned = []
        for candidate in candidates:
            if not isinstance(candidate, str):
                continue
            candidate = candidate.strip()
            if not candidate or candidate in cleaned:
                continue
            cleaned.append(candidate)
            query_limit = self.max_search_queries + 1
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

        requires_live_data = self.freshness_detector.requires_live_data(
            str(query or "")
        )
        archived_query = None
        if not requires_live_data and not include_social:
            archived_query = self.reference_archive.get_query(
                query,
                subject,
                evidence_depth
            )
            if (
                archived_query
                and self.reference_archive.is_recent(
                    archived_query,
                    Config.PUBLIC_REFERENCE_REUSE_TTL_DAYS
                )
            ):
                return self._build_archived_context(
                    query,
                    subject,
                    research_plan,
                    evidence_depth,
                    page_limit,
                    archived_query
                )

        wikipedia_result = None
        wikipedia_status = {
            "status": "not_requested"
        }
        if subject:
            wikipedia_result, wikipedia_status = (
                self._get_wikipedia_evidence(subject)
            )
            if wikipedia_result and not requires_live_data:
                self.reference_archive.store_page(wikipedia_result)

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
            subject=subject,
            query=query,
            search_queries=cleaned_queries
        )
        deduplicated = self._add_official_homepage_candidate(
            deduplicated
        )
        deduplicated = self._select_diverse_sources(
            deduplicated,
            limit=8
        )

        enriched = (
            self._enrich(
                deduplicated,
                page_limit=page_limit,
                subject=subject,
                use_archive=not requires_live_data
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

        if (
            not requires_live_data
            and not include_social
            and any(
                isinstance(result, dict)
                and isinstance(result.get("content"), str)
                and result["content"].strip()
                for result in enriched
            )
        ):
            self.reference_archive.store_query(
                query,
                subject,
                evidence_depth,
                enriched
            )

        if (
            not requires_live_data
            and not include_social
            and archived_query
            and not any(
                isinstance(result, dict)
                and isinstance(result.get("content"), str)
                and result["content"].strip()
                for result in enriched
            )
        ):
            return self._build_archived_context(
                query,
                subject,
                research_plan,
                evidence_depth,
                page_limit,
                archived_query
            )

        archived_results = [
            result
            for result in enriched
            if isinstance(result, dict)
            and result.get("archive_status") == "reused"
        ]
        archive_as_of = max(
            (
                str(result.get("archived_at") or "")
                for result in archived_results
            ),
            default=None
        )

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

            "archive_reused":
                bool(archived_results),

            "archive_as_of":
                archive_as_of,

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
                        "page_kind": result.get("page_kind"),
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

    @staticmethod
    def _build_archived_context(
        query,
        subject,
        research_plan,
        evidence_depth,
        page_limit,
        archived_query
    ):
        results = archived_query["results"]
        for index, result in enumerate(results, start=1):
            result["source_id"] = f"S{index}"
            result.pop("search_query", None)
        sources = [
            {
                "source_id": result.get("source_id"),
                "title": result.get("title"),
                "publisher": result.get("source"),
                "url": result.get("url"),
                "source_role": result.get("source_role"),
                "page_kind": result.get("page_kind"),
                "evidence_level": result.get("evidence_level")
            }
            for result in results
        ]
        archive_as_of = max(
            (
                str(result.get("archived_at") or "")
                for result in results
            ),
            default=archived_query.get("archived_at")
        )
        return {
            "available": bool(results),
            "query": query,
            "subject": subject,
            "results": results,
            "social_results": [],
            "social_summary": {},
            "search_queries": [],
            "research_plan": research_plan,
            "wikipedia_status": {"status": "archived"},
            "evidence_depth": evidence_depth,
            "page_limit": page_limit,
            "sources": sources,
            "archive_mode": "offline_reuse",
            "archive_reused": True,
            "archive_as_of": archive_as_of
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

    def _add_official_homepage_candidate(self, results):
        for result in results:
            if result.get("source_role") != "official_candidate":
                continue
            try:
                parsed = urlsplit(result.get("url", ""))
            except (TypeError, ValueError):
                continue
            if (
                parsed.scheme not in {"http", "https"}
                or not parsed.hostname
            ):
                continue

            homepage_url = urlunsplit((
                parsed.scheme,
                parsed.netloc,
                "/",
                "",
                ""
            ))
            normalized_homepage = self._normalize_url(homepage_url)
            for existing in results:
                if self._normalize_url(existing.get("url")) == normalized_homepage:
                    existing["page_kind"] = "official_homepage"
                    return results

            homepage = dict(result)
            homepage.update({
                "url": homepage_url,
                "page_kind": "official_homepage",
                "search_query": "Official website homepage"
            })
            return [homepage] + results
        return results

    def _enrich(
        self,
        results,
        page_limit=None,
        subject=None,
        use_archive=True
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
            
        firecrawl_available = self.firecrawl.health_check()
        reference_archive = getattr(
            self,
            "reference_archive",
            None
        )


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

                if result.get("evidence_level") == "retrieved_reference":
                    if (
                        use_archive
                        and reference_archive is not None
                        and isinstance(result.get("content"), str)
                        and result["content"].strip()
                    ):
                        reference_archive.store_page(result)
                    continue

                if not url:

                    continue

                if use_archive and reference_archive is not None:
                    archived_page = reference_archive.get_page(url)
                    if (
                        archived_page
                        and reference_archive.is_recent(
                            archived_page,
                            Config.PUBLIC_REFERENCE_REUSE_TTL_DAYS
                        )
                    ):
                        found_candidate = True
                        result.update(archived_page)
                        result["evidence_level"] = (
                            "retrieved_webpage"
                        )
                        enriched_count += 1
                        if enriched_count >= page_limit:
                            break
                        continue

                if not firecrawl_available:
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

                metadata = scraped.get("metadata")
                if not isinstance(metadata, dict):
                    metadata = {}
                scraped_title = metadata.get("title")
                original_title_terms = set(
                    self._subject_terms(result.get("title"))
                )
                scraped_title_terms = set(
                    self._subject_terms(scraped_title)
                )
                title_matches_result = (
                    not original_title_terms
                    or not scraped_title_terms
                    or bool(original_title_terms & scraped_title_terms)
                )
                content_matches_subject = (
                    not subject
                    or self._is_relevant_to_subject(
                        {
                            "title": scraped_title or "",
                            "summary": markdown
                        },
                        subject
                    )
                )
                if not title_matches_result or not content_matches_subject:
                    result.pop("content", None)
                    result["evidence_level"] = "search_snippet"
                    continue


                result[
                    "content"
                ] = markdown


                result[
                    "content_retrieved_by"
                ] = "Firecrawl"
                result["evidence_level"] = "retrieved_webpage"
                result["content_retrieved_by"] = (
                    scraped.get("retrieved_by", "Firecrawl")
                )
                result["content_retrieved_at"] = (
                    datetime.now(timezone.utc).isoformat()
                )
                result["page_title"] = (
                    scraped_title.strip()
                    if isinstance(scraped_title, str)
                    else ""
                )
                if isinstance(scraped_title, str) and scraped_title.strip():
                    result["title"] = scraped_title.strip()

                if use_archive and reference_archive is not None:
                    reference_archive.store_page(result)

                enriched_count += 1


                if enriched_count >= (
                    page_limit
                ):

                    break


            if not found_candidate:

                break


            index += 1


        return results