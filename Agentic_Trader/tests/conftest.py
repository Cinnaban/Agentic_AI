import os

# keep the suite offline: the trader must never spend real Alpha Vantage requests from a test
os.environ["PAPER_NEWS_SIGNAL"] = "0"
os.environ["PAPER_SIGNAL_RANK"] = "0"
