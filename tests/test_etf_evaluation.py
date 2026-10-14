import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from agents.company_detection_agent import CompanyDetectionAgent
from data.providers.etf_fund_provider import ETFFundProvider
from orchestrator.financial_metric_builder import FinancialMetricBuilder
from orchestrator.evidence_provenance import EvidenceProvenance
from orchestrator.hermes import Hermes
from orchestrator.portfolio_request_parser import PortfolioRequestParser
from job_queue.job_factory import JobFactory
from workers.agent_executor import AgentExecutor
from workers.gaming_pc_bridge import GamingPCBridge


class FakeFrame:

    def __init__(self, values):
        self.values = values

    def to_dict(self, orient):
        if orient != "index":
            raise AssertionError("Expected index-oriented row data")
        return self.values


class AssignmentAgent:

    def analyze(self, companies, message):
        return {
            "research": False,
            "sentiment": False,
            "quant": False,
            "risk": False
        }


class ExplicitETFProvider:

    def resolve(self, ticker, message):
        return {
            "entity_type": "etf",
            "classification_status": "resolved",
            "classification_source": "test",
            "etf_context": {"status": "available"}
        }


class ETFEvaluationTests(unittest.TestCase):

    def test_ticker_metadata_distinguishes_etf_and_equity(self):
        etf_fund_data = SimpleNamespace(
            quote_type="ETF",
            fund_overview={
                "categoryName": "Technology",
                "family": "Example Funds",
                "legalType": "Exchange Traded Fund"
            },
            fund_operations=FakeFrame({
                "Annual Report Expense Ratio": {
                    "SOXX": 0.0035,
                    "Category Average": 0.004
                }
            }),
            top_holdings=FakeFrame({
                "NVDA": {
                    "Name": "NVIDIA",
                    "Holding Percent": 0.08
                }
            }),
            asset_classes={"stockPosition": 1.0},
            sector_weightings={"technology": 0.95},
            equity_holdings=FakeFrame({}),
            bond_holdings=FakeFrame({}),
            bond_ratings={}
        )
        etf_ticker = SimpleNamespace(
            info={"quoteType": "ETF"},
            funds_data=etf_fund_data
        )
        equity_ticker = SimpleNamespace(
            info={"quoteType": "EQUITY"}
        )

        with patch(
            "data.providers.etf_fund_provider.yf.Ticker",
            side_effect=[etf_ticker, equity_ticker]
        ):
            provider = ETFFundProvider()
            etf = provider.resolve("SOXX", "Evaluate SOXX")
            stock = provider.resolve("NVDA", "Evaluate NVDA")

        self.assertEqual(etf["entity_type"], "etf")
        self.assertEqual(etf["etf_context"]["status"], "available")
        self.assertEqual(
            etf["etf_context"]["top_holdings"][0]["key"],
            "NVDA"
        )
        self.assertEqual(stock["entity_type"], "stock")
        self.assertNotIn("etf_context", stock)

    def test_explicit_etf_cue_is_used_when_metadata_lookup_fails(self):
        provider = ETFFundProvider()
        ticker = SimpleNamespace()
        with patch(
            "data.providers.etf_fund_provider.yf.Ticker",
            return_value=ticker
        ), patch.object(
            provider,
            "get_fund_context",
            return_value={"status": "available"}
        ) as get_context:
            result = provider.resolve("NOQUOTE", "Evaluate the ETF NOQUOTE")

        self.assertEqual(result["entity_type"], "etf")
        self.assertEqual(
            result["classification_status"],
            "unverified"
        )
        get_context.assert_called_once_with("NOQUOTE", yf_ticker=ticker)

    def test_quote_type_overrides_conflicting_user_label(self):
        ticker = SimpleNamespace(
            info={
                "quoteType": "EQUITY",
                "sector": "Technology",
                "industry": "Semiconductors"
            }
        )
        with patch(
            "data.providers.etf_fund_provider.yf.Ticker",
            return_value=ticker
        ):
            result = ETFFundProvider().resolve(
                "NVDA",
                "Evaluate the ETF NVDA"
            )

        self.assertEqual(result["entity_type"], "stock")
        self.assertEqual(result["classification_status"], "resolved")
        self.assertEqual(result["sector"], "Technology")
        self.assertEqual(result["industry"], "Semiconductors")

    def test_unavailable_quote_type_is_reported_as_unresolved(self):
        ticker = SimpleNamespace(
            info={}
        )
        with patch(
            "data.providers.etf_fund_provider.yf.Ticker",
            return_value=ticker
        ):
            result = ETFFundProvider().resolve(
                "NOQUOTE",
                "Evaluate NOQUOTE"
            )

        self.assertEqual(result["entity_type"], "security")
        self.assertEqual(
            result["classification_status"],
            "unresolved"
        )

    def test_known_etf_is_recognized_when_quote_metadata_is_empty(self):
        ticker = SimpleNamespace(info={})
        provider = ETFFundProvider()
        fund_context = {
            "status": "unavailable",
            "quote_type": None,
            "sector_weightings": {"financialServices": 0.40}
        }
        with patch(
            "data.providers.etf_fund_provider.yf.Ticker",
            return_value=ticker
        ), patch.object(
            provider,
            "get_fund_context",
            return_value=fund_context
        ):
            result = provider.resolve("SCHD", "Evaluate my portfolio")

        self.assertEqual(result["entity_type"], "etf")
        self.assertEqual(result["classification_status"], "resolved")
        self.assertEqual(
            result["classification_source"],
            "curated ETF ticker registry"
        )
        self.assertEqual(result["etf_context"], fund_context)

    def test_empty_detector_response_preserves_explicit_ticker(self):
        agent = CompanyDetectionAgent.__new__(CompanyDetectionAgent)
        agent.ollama = SimpleNamespace(
            generate=lambda *args, **kwargs: {
                "response": ""
            }
        )

        result = agent.analyze("Evaluate SOXX")

        self.assertTrue(result["is_company_request"])
        self.assertEqual(result["companies"][0]["ticker"], "SOXX")

    def test_empty_detector_response_does_not_route_etf_to_portfolio(self):
        detector = CompanyDetectionAgent.__new__(CompanyDetectionAgent)
        detector.ollama = SimpleNamespace(
            generate=lambda *args, **kwargs: {
                "response": ""
            }
        )
        hermes = Hermes.__new__(Hermes)
        hermes.portfolio_request_parser = PortfolioRequestParser()
        hermes.job_factory = JobFactory()
        hermes.company_agent = detector
        hermes.assignment_agent = AssignmentAgent()
        hermes.etf_fund_provider = ExplicitETFProvider()

        workflow = hermes.build_workflow("Evaluate the ETF SOXX")

        self.assertEqual(workflow.companies[0]["entity_type"], "etf")
        self.assertTrue(workflow.required_agents["quant"])
        self.assertTrue(workflow.required_agents["research"])
        self.assertTrue(workflow.required_agents["risk"])

    def test_etf_context_reaches_research_and_provenance(self):
        executor = AgentExecutor.__new__(AgentExecutor)
        executor.freshness_detector = SimpleNamespace(
            requires_live_data=lambda message: False
        )
        executor.quant_agent = SimpleNamespace(
            analyze=lambda work_package: {}
        )
        executor.market_context_provider = SimpleNamespace(
            get_context=lambda *args, **kwargs: {
                "company": args[0] if args else kwargs["company"],
                "source_status": {}
            }
        )
        executor.research_agent = Mock(return_value="ETF analysis")
        executor.sentiment_agent = Mock()
        executor.risk_agent = Mock()
        executor.signal_reconciliation_agent = Mock()

        fund_context = {
            "status": "available",
            "source": "Yahoo Finance",
            "fund_overview": {"categoryName": "Semiconductors"},
            "fund_operations": [],
            "top_holdings": [],
            "sector_weightings": {"technology": 0.95}
        }
        work_package = SimpleNamespace(
            companies=[{
                "name": "iShares Semiconductor ETF",
                "ticker": "SOXX",
                "entity_type": "etf",
                "etf_context": fund_context
            }],
            required_agents={
                "quant": True,
                "research": True,
                "sentiment": False,
                "risk": False
            },
            original_message="Evaluate the ETF SOXX"
        )

        result = executor.execute(work_package)

        context = result["market_context"]
        self.assertEqual(context["etf_fund_data"], fund_context)
        self.assertEqual(
            context["source_status"]["etf_fund_data"],
            "available"
        )
        self.assertEqual(
            executor.research_agent.analyze.call_args.kwargs[
                "market_context"
            ]["etf_fund_data"],
            fund_context
        )
        provenance = EvidenceProvenance.format_note(context)
        self.assertIn("ETF fund profile and holdings", provenance)

    def test_company_response_shows_fund_profile_and_holdings(self):
        hermes = Hermes.__new__(Hermes)
        output = hermes._build_etf_fund_section({
            "company": {
                "ticker": "SOXX",
                "entity_type": "etf"
            },
            "etf_fund_data": {
                "status": "available",
                "fund_overview": {
                    "categoryName": "Semiconductors"
                },
                "fund_operations": [{
                    "key": "Annual Report Expense Ratio",
                    "SOXX": 0.0035
                }],
                "top_holdings": [{
                    "key": "NVDA",
                    "Name": "NVIDIA",
                    "Holding Percent": 0.08
                }],
                "sector_weightings": {
                    "technology": 0.95
                }
            }
        })

        self.assertIn("ETF Fund Profile", output)
        self.assertIn("Expense ratio: 0.35%", output)
        self.assertIn("NVIDIA (NVDA): 8.00%", output)
        self.assertIn("technology: 95.00%", output)

    def test_etf_does_not_display_issuer_sec_financials(self):
        metrics = FinancialMetricBuilder().build({
            "risk": {},
            "market_context": {
                "company": {
                    "ticker": "SOXX",
                    "entity_type": "etf"
                },
                "sec_facts": {
                    "facts": {
                        "revenue": {"value": 1000000}
                    }
                }
            }
        })

        self.assertNotIn("revenue", metrics)

    def test_quant_only_metrics_do_not_require_risk_results(self):
        metrics = FinancialMetricBuilder().build({
            "quant": {
                "results": [{
                    "analysis": {
                        "predictive_rating": "positive"
                    }
                }]
            },
            "risk": None
        })

        self.assertEqual(metrics["predictive_rating"]["value"], "positive")
        self.assertNotIn("overall_risk", metrics)
        self.assertNotIn("risk_score", metrics)
        self.assertNotIn("signal_uncertainty", metrics)

    def test_gaming_pc_payload_preserves_instrument_type(self):
        bridge = GamingPCBridge()
        bridge.session = Mock()
        response = Mock()
        response.json.return_value = {"results": []}
        bridge.session.post.return_value = response
        work_package = SimpleNamespace(
            job_id="job-1",
            companies=[{
                "name": "iShares Semiconductor ETF",
                "ticker": "SOXX",
                "entity_type": "etf",
                "etf_context": {
                    "status": "available"
                }
            }],
            required_agents={"quant": True},
            original_message="Evaluate the ETF SOXX",
            source="test"
        )

        result = bridge.submit_job(work_package)
        payload = bridge.session.post.call_args.kwargs["json"]

        self.assertEqual(result["status"], "failed")
        self.assertIn(
            "no quant results",
            result["failed_companies"][0]["error"]
        )
        self.assertEqual(payload["companies"][0]["entity_type"], "etf")
        self.assertEqual(
            payload["companies"][0]["etf_context"]["status"],
            "available"
        )


if __name__ == "__main__":
    unittest.main()
