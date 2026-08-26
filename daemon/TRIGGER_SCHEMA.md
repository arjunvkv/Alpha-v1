# Trigger JSON Schema — what the daemon writes before waking me

# TEMPLATE FILLER: The daemon populates this from live data

{
  # --- HEADER (always present) ---
  "template": "zone_approach",        # which wakeup template to use
  "timestamp": "2026-08-21T14:30:00", # ISO format
  "session": "london",                 # asian/london/ny/off
  "symbol": "XAGUSD",                 # primary symbol affected
  
  # --- MARKET STATE (daemon fills from MT5 + Granger) ---
  "price": {
    "last": 68.25,
    "bid": 68.23,
    "ask": 68.27,
    "spread_pips": 4,
    "change_1d_pct": 3.93,
    "change_5d_pct": 5.31
  },
  
  # --- TRIGGER DETAILS (what caused the wake-up) ---
  "trigger": {
    "type": "zone_approach",           # zone_approach/regime_shift/position_management/daily_scan/emergency/thesis_validation
    "reason": "Price within 0.36% of SMA20 support at $68.50",
    "zone": {
      "level": 68.50,
      "type": "SMA20",
      "distance_pct": 0.36,
      "significance": "First test of SMA20 since breakout. Held 3 times in past month."
    }
  },
  
  # --- REGIME (daemon fills from L3/L7) ---
  "regime": {
    "composite": "bullish_metals",     # from L7 macro_regime
    "dxy": 98.84,
    "dxy_trend": "weakening",          # weakening/stable/strengthening
    "dxy_change_1d_pct": -0.1,
    "vix": 16.0,
    "vix_regime": "normal",            # complacency/normal/elevated/fear/panic
    "us10y": 4.70,
    "yield_curve_spread": 0.993,
    "risk_regime": "mixed"             # risk_on/risk_off/mixed
  },
  
  # --- GRANGER 7-LAYER SUMMARY (daemon fills from snapshot) ---
  "granger": {
    "snapshot_path": "C:/Trading/data/all_layers_snapshot.json",
    "age_hours": 2.5,
    "stale": false,                     # true if > 6 hours old
    "summary": {
      "L1_prices": {"silver": 68.25, "gold": 4586, "dxy": 98.84},
      "L2_COT": {"silver": "elevated_speculative", "copper": "elevated_long"},
      "L2_ETF": {"SLV": "inflow_2.9B", "GLD": "inflow_10.5B"},
      "L4_sentiment": {"overall": "neutral_0.023", "silver": "neutral_-0.036"},
      "L6_technical": {"silver": {"rsi": 66, "macd_h": 0.71, "trend": "neutral", "signal": "HOLD"}},
      "L7_signals": {"options_pc": 0.311, "macro_regime": "bullish_metals", "yield_curve": "normal"}
    }
  },
  
  # --- POSITIONS (daemon fills from MT5) ---
  "positions": [
    {
      "ticket": 12345678,
      "symbol": "XAGUSD",
      "direction": "LONG",
      "lots": 0.15,
      "entry_price": 67.50,
      "current_price": 68.25,
      "sl": 66.80,
      "tp": 70.00,
      "pnl_dollars": 112.50,
      "pnl_r": 1.07,
      "duration_hours": 48,
      "thesis": "Granger 8.5/10. Bullish metals regime. DXY weakening. Options P/C 0.311. Entry at SMA50 support."
    }
  ],
  
  # --- ACCOUNT (daemon fills from MT5) ---
  "account": {
    "balance": 100000,
    "equity": 100500,
    "margin_used": 5000,
    "free_margin": 95500,
    "heat_pct": 1.8,                    # current risk as % of account
    "max_heat_pct": 6.0,
    "monthly_pnl_pct": 2.3,
    "monthly_drawdown_pct": -1.2,
    "max_drawdown_limit_pct": -10.0
  },
  
  # --- CALENDAR (daemon fills from ForexFactory) ---
  "calendar": {
    "next_event": "Flash PMIs",
    "event_currency": "USD",
    "event_impact": "HIGH",
    "event_time": "2026-08-21T13:45:00",
    "minutes_until": 45,
    "recent_events": [
      {"name": "Initial Jobless Claims", "impact": "MEDIUM", "actual": "206K", "forecast": "215K"}
    ]
  },
  
  # --- ACTIONS I MUST TAKE ---
  "required_actions": [
    "1. Read trigger.json — understand why you were woken",
    "2. Read or pull Granger snapshot — get fresh intelligence",
    "3. Analyze: Is thesis still valid at this price/zone?",
    "4. Check calendar: Any news in next 30 min?",
    "5. Check regime: DXY reversing? VIX spiking?",
    "6. Decide: ENTER / WAIT / MODIFY / EXIT / HOLD",
    "7. Write decision to C:/Trading/Alpha/data/live/action.json",
    "8. If entering: calculate size from conviction × account × risk"
  ],
  
  # --- OUTPUT ---
  "action_file": "C:/Trading/Alpha/data/live/action.json"
}
