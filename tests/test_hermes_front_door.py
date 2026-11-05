import unittest

from agents.company_detection_agent import CompanyDetectionAgent
from integrations import hermes_mcp_server as bridge


class GenericCategoryTests(unittest.TestCase):
    def test_asset_class_words_are_not_company_names(self):
        for query in ("mutual funds", "ETFs", "the stocks", "exchange traded funds"):
            self.assertTrue(CompanyDetectionAgent._is_generic_category(query), query)

    def test_named_entities_are_kept(self):
        for query in ("Vanguard funds", "SPY", "Intel B770"):
            self.assertFalse(CompanyDetectionAgent._is_generic_category(query), query)


class CommandBridgeTests(unittest.TestCase):
    def test_help_and_unknown(self):
        self.assertIn("/portfolio", bridge.run_command("/help_rh", "1"))
        with self.assertRaises(ValueError):
            bridge.run_command("/shutdown", "1")

    def test_tools_listed(self):
        names = {tool["name"] for tool in bridge.TOOLS}
        self.assertEqual(names, {"research_question", "paper_trader_status"})


class WatchdogClassTests(unittest.TestCase):
    def test_general_vs_company(self):
        for q in ("What's the latest on Pokemon?", "Explain the roll mass plays in physics", "FPS vs RTS gaming"):
            self.assertFalse(bridge._is_company_question(q), q)
        for q in ("Analyze AAPL", "Compare NVDA and AAPL", "Mutual Funds vs ETFs", "Evaluate SCHD"):
            self.assertTrue(bridge._is_company_question(q), q)


class ArchiveStallTests(unittest.TestCase):
    def test_stalled_share_disables_archive_instead_of_hanging(self):
        import tempfile
        import threading
        import time
        from shared_storage.reference_archive import PublicReferenceArchive

        archive = PublicReferenceArchive(tempfile.mkdtemp())
        archive.IO_TIMEOUT_SECONDS = 0.2
        release = threading.Event()
        archive._get_page = lambda url: release.wait(5)
        started = time.time()
        self.assertIsNone(archive.get_page("https://example.com"))
        release.set()
        self.assertLess(time.time() - started, 2)
        self.assertFalse(archive._available)


if __name__ == "__main__":
    unittest.main()
