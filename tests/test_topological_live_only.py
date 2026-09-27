import unittest
from unittest.mock import patch

from tradingagents.topological_graph_engine import TopologicalGraphEngine


class TestTopologicalLiveOnly(unittest.TestCase):
    def test_unavailable_live_quote_never_fabricates_coordinates(self):
        engine = TopologicalGraphEngine()
        with patch("tradingagents.topological_graph_engine._live_tick", return_value=None):
            graph = engine.build_market_graph(symbol="XAUUSD", live_price=0)
        self.assertEqual(graph["status"], "LIVE_TOPOLOGY_UNAVAILABLE")
        self.assertIsNone(graph["live_price"])
        self.assertEqual(graph["nodes"], {})
        self.assertEqual(graph["edges"], [])

    def test_explicit_observation_is_preserved_without_fallback_levels(self):
        engine = TopologicalGraphEngine()
        graph = engine.build_market_graph(
            symbol="XAUUSD",
            live_price=2500.0,
            liquidity_data={"session_high": 2510.0, "session_low": 2490.0},
            pivot_data={"pp": 2501.0},
            fvg_matrix={"active_fvgs": [{
                "id": "FVG_TEST",
                "timeframe": "M5",
                "type": "BEARISH",
                "ce": 2505.0,
                "top": 2506.0,
                "bottom": 2504.0,
                "fill_pct": 0.0,
            }]},
        )
        self.assertEqual(graph["status"], "OBSERVATION")
        self.assertIn("SESSION_HIGH", graph["nodes"])
        self.assertIn("SESSION_LOW", graph["nodes"])
        self.assertIn("DAILY_PP", graph["nodes"])
        self.assertIn("FVG_TEST", graph["nodes"])
        prices = [n["price"] for n in graph["nodes"].values() if n.get("price") is not None]
        self.assertNotIn(4285.23, prices)
        self.assertNotIn(4286.66, prices)
        self.assertNotIn(4272.95, prices)

    def test_session_boundaries_are_explicit_and_timezone_aware(self):
        engine = TopologicalGraphEngine()
        graph = engine.build_market_graph(
            symbol="XAUUSD",
            live_price=2500.0,
            session_config={
                "name": "ASIAN_TEST",
                "timezone": "Asia/Tokyo",
                "start": "09:00",
                "end": "15:00",
            },
        )
        self.assertEqual(graph["session"]["name"], "ASIAN_TEST")
        self.assertEqual(graph["session"]["timezone"], "Asia/Tokyo")
        self.assertEqual(graph["session"]["start"], "09:00")
        self.assertEqual(graph["session"]["end"], "15:00")

    def test_edges_are_structural_relationships_not_trade_decisions(self):
        engine = TopologicalGraphEngine()
        graph = engine.build_market_graph(
            symbol="XAUUSD",
            live_price=2500.0,
            liquidity_data={"session_high": 2505.0},
        )
        edge = next(e for e in graph["edges"] if e["to"] == "SESSION_HIGH")
        self.assertEqual(edge["relationship"], "LIQUIDITY_TARGET")
        self.assertIn(edge["state"], {"ACTIVE", "MITIGATED", "RETIRED"})
        self.assertFalse(edge["is_obstacle"])
        self.assertNotIn("rr", " ".join(edge.keys()).lower())

    def test_fully_filled_fvg_retires(self):
        engine = TopologicalGraphEngine()
        graph = engine.build_market_graph(
            symbol="XAUUSD",
            live_price=2500.0,
            fvg_matrix={"active_fvgs": [{
                "id": "FVG_RETIRED",
                "timeframe": "M5",
                "type": "BEARISH",
                "ce": 2505.0,
                "top": 2506.0,
                "bottom": 2504.0,
                "fill_pct": 100.0,
            }]},
        )
        self.assertNotIn("FVG_RETIRED", graph["nodes"])


if __name__ == "__main__":
    unittest.main()
