from agentic_trader.robinhood.data import RobinhoodData


def test_inactive_symbol_is_dropped_and_batch_retried():
    d = RobinhoodData.__new__(RobinhoodData)
    calls = []

    def fake(tool, args, ttl):
        calls.append(list(args["symbols"]))
        if "KVUE" in args["symbols"]:
            raise RuntimeError('API error 400: {"inactive_instruments":["KVUE"]}')
        return {"results": [{"symbol": s, "bars": [{"begins_at": "2026-11-02T14:30:00Z", "open_price": "1", "high_price": "1",
                                                     "low_price": "1", "close_price": "1", "volume": 1}]} for s in args["symbols"]]}

    d._call = fake
    out = d.bars(["F", "KVUE", "T"], "day", 5)
    assert set(out) == {"F", "T"}
    assert len(calls) == 2
    d.bars(["F", "KVUE"], "day", 5)
    assert all("KVUE" not in c for c in calls[2:])
