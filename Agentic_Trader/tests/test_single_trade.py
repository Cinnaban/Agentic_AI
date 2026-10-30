from datetime import datetime
from zoneinfo import ZoneInfo

import numpy as np


ET = ZoneInfo("America/New_York")


def test_scoring_pillars():
    from agentic_trader import single_trade as st
    up, down = list(np.linspace(100, 130, 120)), list(np.linspace(130, 100, 120))
    assert st.trend_score(up, up[-1]) > 0.3 > -0.3 > st.trend_score(down, down[-1])
    s, cov = st.composite({"prediction": 0.5, "sentiment": None, "financials": None, "trend": 0.5})
    assert abs(s - 0.5) < 1e-9 and abs(cov - 0.6) < 1e-9
    assert (st.financial_score({"pe_ratio": "15", "market_cap": "2e11"})
            > st.financial_score({"pe_ratio": "-3", "market_cap": "2e8"}))
