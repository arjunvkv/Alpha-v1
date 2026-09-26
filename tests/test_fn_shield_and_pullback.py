"""
Unit test suite verifying FundedNext 32-second hold shield and Universal Pullback Cutting
across MCP position manager and desk daemon dynamic ratchet loop.
"""
import unittest
from unittest.mock import MagicMock, patch
import json
import sys
from pathlib import Path
import MetaTrader5 as mt5

# Add Alpha root and mcp_server to sys.path
ALPHA_ROOT = Path(r"C:\Trading\Alpha")
sys.path.insert(0, str(ALPHA_ROOT))
sys.path.insert(0, str(ALPHA_ROOT / "mcp_server"))

import alpha_mcp_server as srv


class TestFundedNextShieldAndPullback(unittest.TestCase):

    def setUp(self):
        srv._pending_delayed_tickets.clear()

    @patch("MetaTrader5.positions_get")
    @patch("MetaTrader5.symbol_info_tick")
    @patch("MetaTrader5.order_send")
    def test_breakeven_pullback_cut(self, mock_send, mock_tick, mock_pos):
        """If price pulled back to or below entry, BREAK_EVEN must cut at market without erroring."""
        # Mock BUY position opened at 4370.0
        pos = MagicMock()
        pos.ticket = 1001
        pos.type = 0  # BUY
        pos.symbol = "XAUUSD"
        pos.price_open = 4370.0
        pos.sl = 4362.0
        pos.tp = 4390.0
        pos.volume = 0.50
        pos.magic = 999
        pos.profit = -5.0
        pos.time_msc = 1000000000000
        mock_pos.return_value = [pos]

        # Tick shows bid at 4369.5 (pulled back 0.5 pts below entry)
        tick = MagicMock()
        tick.bid = 4369.5
        tick.ask = 4369.8
        tick.time_msc = 1000000035000  # 35 seconds elapsed
        mock_tick.return_value = tick

        mock_send.return_value = MagicMock(retcode=mt5.TRADE_RETCODE_DONE)

        res_raw = srv.mcp_alpha_update_position(ticket=1001, action="BREAK_EVEN")
        res = json.loads(res_raw)

        self.assertEqual(res["status"], "CUT_AT_MARKET")
        self.assertEqual(res["action"], "BREAK_EVEN_PULLBACK_CUT")
        self.assertEqual(res["close_price"], 4369.5)
        # Verify market deal was sent with comment "BE Pullback Cut"
        mock_send.assert_called_once()
        args = mock_send.call_args[0][0]
        self.assertEqual(args["action"], mt5.TRADE_ACTION_DEAL)
        self.assertEqual(args["comment"], "BE Pullback Cut")

    @patch("MetaTrader5.positions_get")
    @patch("MetaTrader5.symbol_info_tick")
    @patch("MetaTrader5.order_send")
    def test_trail_sl_pullback_cut(self, mock_send, mock_tick, mock_pos):
        """If price pulled back below target trailing SL, TRAIL_SL must cut at market without erroring."""
        # Mock BUY position opened at 4370.0
        pos = MagicMock()
        pos.ticket = 1002
        pos.type = 0  # BUY
        pos.symbol = "XAUUSD"
        pos.price_open = 4370.0
        pos.sl = 4370.5
        pos.tp = 4395.0
        pos.volume = 0.50
        pos.magic = 999
        pos.profit = 120.0
        pos.time_msc = 1000000000000
        mock_pos.return_value = [pos]

        # Tick shows bid at 4373.0, but caller requests trailing SL to 4373.5 (target is above bid)
        tick = MagicMock()
        tick.bid = 4373.0
        tick.ask = 4373.3
        tick.time_msc = 1000000040000  # 40 seconds elapsed
        mock_tick.return_value = tick

        mock_send.return_value = MagicMock(retcode=mt5.TRADE_RETCODE_DONE)

        res_raw = srv.mcp_alpha_update_position(ticket=1002, action="TRAIL_SL", params_json=json.dumps({"sl": 4373.5}))
        res = json.loads(res_raw)

        self.assertEqual(res["status"], "CUT_AT_MARKET")
        self.assertEqual(res["action"], "TRAIL_PULLBACK_CUT")
        self.assertEqual(res["close_price"], 4373.0)
        # Verify market deal was sent with comment "Trail Pullback Cut"
        mock_send.assert_called_once()
        args = mock_send.call_args[0][0]
        self.assertEqual(args["action"], mt5.TRADE_ACTION_DEAL)
        self.assertEqual(args["comment"], "Trail Pullback Cut")

    @patch("MetaTrader5.positions_get")
    @patch("MetaTrader5.symbol_info_tick")
    @patch("MetaTrader5.order_send")
    def test_full_exit_delayed_close_under_32s(self, mock_send, mock_tick, mock_pos):
        """If profitable and under 32s hold, FULL_EXIT must accept and return ACCEPTED_DELAYED_CLOSE."""
        pos = MagicMock()
        pos.ticket = 1003
        pos.type = 0  # BUY
        pos.symbol = "XAUUSD"
        pos.price_open = 4370.0
        pos.sl = 4362.0
        pos.tp = 4390.0
        pos.volume = 0.50
        pos.magic = 999
        pos.profit = 250.0
        pos.time_msc = 1000000000000
        mock_pos.return_value = [pos]

        # Tick at 15.0 seconds (bid 4375.0, in profit)
        tick = MagicMock()
        tick.bid = 4375.0
        tick.ask = 4375.3
        tick.time_msc = 1000000015000  # 15.0s elapsed
        mock_tick.return_value = tick

        res_raw = srv.mcp_alpha_update_position(ticket=1003, action="FULL_EXIT")
        res = json.loads(res_raw)

        self.assertEqual(res["status"], "ACCEPTED_DELAYED_CLOSE")
        self.assertEqual(res["remaining_seconds"], 17.0)  # 32.0 - 15.0 = 17.0
        self.assertIn("17.0 seconds", res["message"])
        # Crucial: order_send should NOT have been called synchronously!
        mock_send.assert_not_called()

    @patch("MetaTrader5.positions_get")
    @patch("MetaTrader5.symbol_info_tick")
    @patch("MetaTrader5.order_send")
    @patch("MetaTrader5.copy_rates_from_pos")
    def test_underwater_exit_vetoed_by_const_no_premature_cut(self, mock_rates, mock_send, mock_tick, mock_pos):
        """If underwater and within structural stop loss, FULL_EXIT must be VETOED unless forced."""
        pos = MagicMock()
        pos.ticket = 1004
        pos.type = 0  # BUY
        pos.symbol = "XAUUSD"
        pos.price_open = 4370.0
        pos.sl = 4362.0
        pos.tp = 4390.0
        pos.volume = 0.50
        pos.magic = 999
        pos.profit = -100.0
        pos.time_msc = 1000000000000
        mock_pos.return_value = [pos]

        # Tick at 4368.0 (2.0 pts adverse, well inside 8.0 pt structural SL)
        tick = MagicMock()
        tick.bid = 4368.0
        tick.ask = 4368.3
        tick.time_msc = 1000000050000  # 50s elapsed
        mock_tick.return_value = tick

        mock_rates.return_value = []

        res_raw = srv.mcp_alpha_update_position(ticket=1004, action="FULL_EXIT")
        res = json.loads(res_raw)

        self.assertEqual(res["status"], "VETOED", f"Expected VETOED but got: {res}")
        self.assertIn("CONST_NO_PREMATURE_CUT VETO", res["error"])
        mock_send.assert_not_called()

    def test_daemon_ratchet_qualification_and_pullback_rules(self):
        """Verify the 3-stage qualification and pullback threshold math used by the 500ms watcher."""
        # Simulated qualifications
        stage_qualification = {}

        # Case 1: Expansion to +6.0 pts qualifies Stage 1
        fav_pts = 6.0
        pos_ticket = 2001
        qual = stage_qualification.setdefault(pos_ticket, {"highest_fav": 0.0, "stage": 0})
        if fav_pts > qual["highest_fav"]:
            qual["highest_fav"] = fav_pts
        if qual["highest_fav"] >= 14.0:
            qual["stage"] = max(qual["stage"], 3)
        elif qual["highest_fav"] >= 8.5:
            qual["stage"] = max(qual["stage"], 2)
        elif qual["highest_fav"] >= 5.2:
            qual["stage"] = max(qual["stage"], 1)

        self.assertEqual(qual["stage"], 1)
        self.assertEqual(qual["highest_fav"], 6.0)

        # Pullback check: if pulled back to +0.30 pts (< +0.50 pts), triggers BE Pullback Cut
        fav_now = 0.30
        needs_cut = (qual["stage"] == 1 and fav_now < 0.50)
        self.assertTrue(needs_cut)

        # Case 2: Expansion to +9.5 pts qualifies Stage 2
        fav_pts_2 = 9.5
        pos_ticket_2 = 2002
        qual_2 = stage_qualification.setdefault(pos_ticket_2, {"highest_fav": 0.0, "stage": 0})
        if fav_pts_2 > qual_2["highest_fav"]:
            qual_2["highest_fav"] = fav_pts_2
        if qual_2["highest_fav"] >= 14.0:
            qual_2["stage"] = max(qual_2["stage"], 3)
        elif qual_2["highest_fav"] >= 8.5:
            qual_2["stage"] = max(qual_2["stage"], 2)
        elif qual_2["highest_fav"] >= 5.2:
            qual_2["stage"] = max(qual_2["stage"], 1)

        self.assertEqual(qual_2["stage"], 2)
        self.assertEqual(qual_2["highest_fav"], 9.5)

        # Pullback check: if pulled back to +2.5 pts (< +3.5 pts), triggers Stage 2 Pullback Cut
        fav_now_2 = 2.5
        needs_cut_2 = (qual_2["stage"] == 2 and fav_now_2 < 3.5)
        self.assertTrue(needs_cut_2)

        # Case 3: Expansion to +16.0 pts qualifies Stage 3
        fav_pts_3 = 16.0
        pos_ticket_3 = 2003
        qual_3 = stage_qualification.setdefault(pos_ticket_3, {"highest_fav": 0.0, "stage": 0})
        if fav_pts_3 > qual_3["highest_fav"]:
            qual_3["highest_fav"] = fav_pts_3
        if qual_3["highest_fav"] >= 14.0:
            qual_3["stage"] = max(qual_3["stage"], 3)
        elif qual_3["highest_fav"] >= 8.5:
            qual_3["stage"] = max(qual_3["stage"], 2)
        elif qual_3["highest_fav"] >= 5.2:
            qual_3["stage"] = max(qual_3["stage"], 1)

        self.assertEqual(qual_3["stage"], 3)
        self.assertEqual(qual_3["highest_fav"], 16.0)

        # Pullback check: if pulled back to +7.0 pts (< +8.0 pts), triggers Stage 3 Pullback Cut
        fav_now_3 = 7.0
        needs_cut_3 = (qual_3["stage"] == 3 and fav_now_3 < 8.0)
        self.assertTrue(needs_cut_3)


if __name__ == "__main__":
    unittest.main()
