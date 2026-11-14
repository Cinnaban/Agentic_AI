import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock

from workers.etf_portfolio_insights import (
    enrich_daily_news,
    format_daily_news_sections,
    replace_daily_news_sections,
    select_daily_news,
)


class DailyArticleContextTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 11, 11, 12, tzinfo=timezone.utc)
        self.holdings = [{"ticker": "AMZN", "name": "Amazon"}]
        self.market = [{
            "title": "Markets retreat after inflation data",
            "url": "https://news.example/market",
            "source": "Example News",
            "published_at": (self.now - timedelta(hours=2)).isoformat(),
        }]
        self.watch = {"AMZN": [{
            "title": "Amazon reports cloud growth",
            "url": "https://news.example/amazon",
            "source": "Example News",
            "published_at": (self.now - timedelta(hours=1)).isoformat(),
        }]}
        self.backend = Mock()
        self.backend._is_public_http_url.return_value = True

    def test_selected_articles_enriched_and_rendered_in_both_sections(self):
        market, watch = select_daily_news(
            self.holdings, self.market, self.watch, now=self.now
        )
        pages = {
            "https://news.example/market": {"title": "Markets retreat after inflation data", "markdown":
             "# Markets retreat after inflation data\n"
             "Shares fell as inflation data exceeded economists' forecasts. "
             "Investors reassessed the timing of future interest rate cuts. "
             "A third sentence about markets should not appear."},
            "https://news.example/amazon": {"title": "Amazon reports cloud growth", "markdown":
             "# Amazon reports cloud growth\n"
             "Amazon reported a rise in cloud revenue during the latest quarter. "
             "The company said demand from its customers continued to increase."},
        }
        self.backend.retrieve_page.side_effect = lambda url: pages[url]
        enrich_daily_news(market, watch, self.backend)
        market_text, watch_text = format_daily_news_sections(market, watch, self.holdings)
        self.assertIn("Shares fell as inflation data", market_text)
        self.assertIn("Investors reassessed", market_text)
        self.assertNotIn("A third sentence", market_text)
        self.assertIn("article excerpt", market_text)
        self.assertIn("https://news.example/market", market_text)
        self.assertIn("AMZN: Amazon reports cloud growth", watch_text)
        self.assertIn("Amazon reported a rise", watch_text)
        self.assertIn("Example News", watch_text)

    def test_no_article_text_uses_labelled_snippet_or_explicit_limitation(self):
        self.market[0]["summary"] = (
            "Investors assessed new inflation data ahead of the next policy meeting."
        )
        market, watch = select_daily_news(self.holdings, self.market, self.watch, now=self.now)
        self.backend.retrieve_page.return_value = None
        enrich_daily_news(market, watch, self.backend)
        market_text, watch_text = format_daily_news_sections(market, watch, self.holdings)
        self.assertIn("search snippet; article text unavailable", market_text)
        self.assertIn("Investors assessed", market_text)
        self.assertIn("Article details unavailable.", watch_text)

    def test_rejects_mismatched_page_and_boilerplate(self):
        market, _ = select_daily_news(self.holdings, self.market, {}, now=self.now)
        self.backend.retrieve_page.return_value = {
            "title": "Sports championship results",
            "markdown": "The visiting team won the championship after a long final match.",
        }
        enrich_daily_news(market, [], self.backend)
        self.assertEqual(market[0]["brief"], "")

    def test_stale_stories_and_unapproved_tickers_are_not_selected(self):
        self.market.append({
            "title": "Old market report", "url": "https://news.example/old",
            "published_at": (self.now - timedelta(days=4)).isoformat(),
        })
        self.watch["AMZN"].append({
            "title": "NVDA news", "url": "https://news.example/other",
            "published_at": self.now.isoformat(),
        })
        market, watch = select_daily_news(self.holdings, self.market, self.watch, now=self.now)
        self.assertEqual(len(market), 1)
        self.assertEqual(len(watch), 1)

    def test_generic_fund_profile_is_not_a_news_story(self):
        holdings = [{"ticker": "VTEB", "name": "Vanguard Tax-Exempt Bond ETF"}]
        news = {"VTEB": [
            {"title": "Vanguard Tax-Exempt Bond ETF", "url": "https://news.example/fund",
             "published_at": self.now.isoformat()},
            {"title": "Vanguard fund reports new municipal bond strategy",
             "url": "https://news.example/strategy",
             "published_at": self.now.isoformat()},
        ]}
        _, watch = select_daily_news(holdings, [], news, now=self.now)
        self.assertEqual([item["url"] for _, item in watch], ["https://news.example/strategy"])

    def test_replaces_both_model_and_fallback_sections_without_touching_others(self):
        brief = (
            "# Daily Portfolio Update\n\n## Current Market Context\nOld headline\n\n"
            "## Risk Watch\nRisk remains.\n\n## Short-Term Watch\nOld watch\n\n"
            "## Appendix\nKeep this.\n"
        )
        result = replace_daily_news_sections(
            brief, "## Current Market Context\nNew market.",
            "## Short-Term Watch\nNew watch."
        )
        self.assertIn("New market.", result)
        self.assertIn("New watch.", result)
        self.assertIn("Risk remains.", result)
        self.assertIn("## Appendix\nKeep this.", result)
        self.assertNotIn("Old headline", result)

    def test_duplicate_urls_are_fetched_once_and_unsafe_urls_rejected(self):
        market, watch = select_daily_news(self.holdings, self.market, self.watch, now=self.now)
        watch[0][1]["url"] = market[0]["url"]
        self.backend._is_public_http_url.return_value = False
        enrich_daily_news(market, watch, self.backend)
        self.backend._is_public_http_url.assert_called_once()
        self.backend.retrieve_page.assert_not_called()
        self.assertEqual(market[0]["brief_source"], "article details unavailable")


if __name__ == "__main__":
    unittest.main()
