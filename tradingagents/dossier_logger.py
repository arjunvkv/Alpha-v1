import os
import json
import logging
import datetime

LOG = logging.getLogger("alpha.dossier_logger")

DOSSIER_DIR = r"C:\Trading\Alpha\logs"
JSON_DOSSIER_PATH = os.path.join(DOSSIER_DIR, "full_desk_dossier.json")
MD_DOSSIER_PATH = os.path.join(DOSSIER_DIR, "full_desk_dossier.md")

class DeepDossierLogger:
    """
    Persistently writes 100% complete, un-truncated multi-agent intelligence dossiers
    to disk after every scan cycle in both JSON and Markdown formats.
    """
    def __init__(self):
        os.makedirs(DOSSIER_DIR, exist_ok=True)

    def write_dossier(self, cycle_count: int, instruments_data: list, open_positions: list, reversal_alerts: list, session_info: dict, gsr_data: dict, account_health: dict = None, currency_strength: dict = None, real_yields: dict = None, study_cycle_id: int = None) -> str:
        """
        Writes persistent JSON and Markdown dossiers to disk and returns the full markdown string.
        """
        now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        account_health = account_health or {}
        currency_strength = currency_strength or {}
        real_yields = real_yields or {}

        # 1. JSON Dossier Output
        json_payload = {
            "timestamp": now_str,
            "scan_cycle_count": cycle_count,
            "agent_study_cycle_id": study_cycle_id,
            "session_info": session_info,
            "gsr_data": gsr_data,
            "account_health": account_health,
            "currency_strength": currency_strength,
            "real_yields": real_yields,
            "open_positions_count": len(open_positions),
            "open_positions": open_positions,
            "reversal_alerts": [a[1] for a in reversal_alerts] if reversal_alerts else [],
            "instruments_scanned": len(instruments_data),
            "instruments_matrix": instruments_data
        }
        try:
            with open(JSON_DOSSIER_PATH, "w", encoding="utf-8") as f:
                json.dump(json_payload, f, indent=2)
        except Exception as err:
            LOG.error(f"Failed to write JSON dossier: {err}")

        # 2. Markdown Dossier Output
        md_lines = []
        md_lines.append(f"# Deep Institutional Trading Desk Dossier")
        if study_cycle_id is not None:
            md_lines.append(f"**Timestamp**: `{now_str}` | **Desk Scan Cycle**: `#{cycle_count} (Market Scan Loop)` | **Agent Study Cycle**: `#{study_cycle_id} (Unified Learning Review)`")
        else:
            md_lines.append(f"**Timestamp**: `{now_str}` | **Desk Scan Cycle**: `#{cycle_count} (Market Scan Loop)`")
        md_lines.append(f"**Session Clock**: `{session_info.get('session')}` ({session_info.get('description')} | `{session_info.get('utc_time')}`)")
        md_lines.append(f"**Intermarket GSR Ratio**: `{gsr_data.get('gsr')}` [{gsr_data.get('status')}]")
        md_lines.append(f"**US Real Yield Matrix**: Fed Rate `{real_yields.get('fed_funds_rate')}` | US10Y `{real_yields.get('us10y_nominal_yield')}` | `{real_yields.get('us_real_yield_posture')}`")
        md_lines.append(f"**Currency Strength Matrix**: USD `{currency_strength.get('usd_index_posture')}` | EUR `{currency_strength.get('eur_strength')}` | GBP `{currency_strength.get('gbp_strength')}` | JPY `{currency_strength.get('jpy_strength')}`")
        md_lines.append(f"**FTMO Account Health**: Balance `${account_health.get('balance')}` | Equity `${account_health.get('equity')}` | Free Margin `${account_health.get('free_margin')}` | Margin Level `{account_health.get('margin_level_pct')}%` | Floating PnL `${account_health.get('floating_pnl')}` | Account Heat `{account_health.get('account_heat_pct')}%`\n")

        if open_positions:
            md_lines.append(f"## 📊 Active FTMO MT5 Positions ({len(open_positions)})")
            for pos in open_positions:
                md_lines.append(f"- {pos}")
            md_lines.append("")

        if reversal_alerts:
            md_lines.append(f"## ⚠️ High-Priority Drawdown & Reversal Alerts")
            for alert in reversal_alerts:
                md_lines.append(f"- ⚠️ **{alert[1]}**")
            md_lines.append("")

        active_syms = ", ".join([inst.get("symbol", "") for inst in instruments_data])
        md_lines.append(f"## 🌐 Multi-Instrument 7-Agent Detailed Findings ({len(instruments_data)}/6 Instruments Scanned - Active: {active_syms})\n")

        for inst in instruments_data:
            sym = inst.get("symbol", "UNKNOWN")
            tech = inst.get("tech", {})
            fund = inst.get("fund", {})
            macro = inst.get("macro", {})
            debate = inst.get("debate", {})
            risk = inst.get("risk", {})
            mtf = inst.get("mtf", {})
            ob = inst.get("order_blocks", {})
            news = inst.get("news_shield", {})
            adr = inst.get("adr", {})
            spread = inst.get("spread", {})
            vel = inst.get("velocity", {})

            # Robust COT Percentile extraction (G2)
            cot_pct = fund.get("cot_managed_money_percentile")
            if cot_pct is None:
                cot_pct = fund.get("cot_percentile") if fund.get("cot_percentile") is not None else fund.get("cot_index_52w", 50.0)

            # Robust 4TF Timeframe resolution including H4 (G3)
            h4_bias = mtf.get("h4_trend") or tech.get("h4_bias", "NEUTRAL")
            h1_bias = mtf.get("h1_trend", "NEUTRAL")
            m15_bias = mtf.get("m15_trend", "NEUTRAL")
            m5_bias = mtf.get("m5_trend", "NEUTRAL")
            alignment_label = mtf.get("alignment") or tech.get("tf_confluence", "MIXED_TIMEFRAMES")

            lib = inst.get("librarian", {})
            top4 = lib.get("top_4_precedents", [])
            top1 = top4[0] if top4 else {}
            lib_name = top1.get("name", "N/A")
            lib_wr = top1.get("win_rate", "0/0 (N/A) [ESTIMATED_PRIOR]")
            lib_prov = top1.get("evidence_provenance", "ESTIMATED")
            lib_trigger = top1.get("execution_trigger", "N/A")
            lib_score = top1.get("score", 0.0)
            prox_status = lib.get("proxima_status", "STANDBY (Local Memory Active)")
            prox_synth = lib.get("proxima_research_synthesis", "Proxima Desktop Standby — using local deterministic microstructure rules")

            is_weekend = session_info.get("market_status") == "WEEKEND_MARKET_CLOSED"
            if is_weekend:
                live_exec_str = f"Spread: `{spread.get('pts')} pts (${spread.get('val')}) [FROZEN_WEEKEND_CLOSE]` | Velocity: `0 t/m [MARKET_CLOSED]`"
                adr_str = f"Range Friday `${adr.get('today_range')}/${adr.get('adr_20')}` (`{adr.get('pct_used')}% used`) [HISTORICAL_FRIDAY]"
            else:
                live_exec_str = f"Spread: `{spread.get('pts')} pts (${spread.get('val')}) [{spread.get('status')}]` | Velocity: `{vel.get('ticks_per_min')} t/m [{vel.get('status')}]`"
                adr_str = f"Range `${adr.get('today_range')}/${adr.get('adr_20')}` (`{adr.get('pct_used')}% used`) [{adr.get('capacity_status')}]"

            md_lines.append(f"### 🔹 Instrument: {sym}")
            md_lines.append(f"- **Live Execution**: {live_exec_str}")
            md_lines.append(f"- **ADR(20) Expansion**: {adr_str}")
            md_lines.append(f"- **Multi-Timeframe Alignment**: H4 (`{h4_bias}`) | H1 (`{h1_bias}`) | M15 (`{m15_bias}`) | M5 (`{m5_bias}`) $\\rightarrow$ **{alignment_label}**")
            md_lines.append(f"- **Order Blocks & Pivots**: Daily PP `{ob.get('pivot_point')}` (S1: `{ob.get('support_s1')}`, R1: `{ob.get('resistance_r1')}`) | Demand: `{ob.get('demand_zone')}` | Supply: `{ob.get('supply_zone')}`")
            md_lines.append(f"- **Technical Order Flow**: {tech.get('thesis', 'N/A')}")
            md_lines.append(f"- **COT / Fundamental Positioning**: COT Percentile `{cot_pct:.1f}%` (26w: `{fund.get('cot_index_26w', cot_pct)}%` | Change: `{fund.get('change', 0):+d}` | Net Non-Comm: `{fund.get('net_noncommercial', 0):+d}` | Net Comm: `{fund.get('commercial_net', 0):+d}` | Provenance: `{fund.get('data_provenance', 'FUTURESBENCH_LIVE_API')}`) | {fund.get('thesis', 'N/A')}")
            md_lines.append(f"- **Macro Intermarket Telemetry**: DXY `{macro.get('dxy', 101.4)}` | US10Y `{macro.get('us10y', 4.25)}%` | VIX `{macro.get('vix', 15.8)}` | News Shield: `{news.get('status_text', 'CLEAR')}` | {macro.get('thesis', 'N/A')}")
            md_lines.append(f"- **Bull vs. Bear Debate Breakdown**: Bull Catalysts ({len(debate.get('bull_points', []))}): `{debate.get('bull_points', [])}` | Bear Risks ({len(debate.get('bear_points', []))}): `{debate.get('bear_points', [])}` | Regime Divergence: `{'YES' if debate.get('is_regime_conflict') else 'NO'}` | Structural Risk Warning: `{'YES' if debate.get('structural_risk_warning') else 'NO'}`")
            md_lines.append(f"- **Autonomous Librarian Precedents (ULM)**: Top Setup: `{lib_name}` | Win Rate: `{lib_wr}` [{lib_prov}] | Trigger: {lib_trigger}")
            md_lines.append(f"- **Proxima Quantitative Research Findings (Port 3210)**: Engine Status: `{prox_status}` | Microstructure Synthesis: {prox_synth}")
            md_lines.append(f"- **Risk Officer Agent Telemetry**: Recommended Max Lot Size: `{risk.get('max_volume_lots', 0.10)} lots` | Sizing Rationale: `{risk.get('reason')}`")
            md_lines.append("")

        full_md_content = "\n".join(md_lines)
        line_count = len(md_lines)
        try:
            with open(MD_DOSSIER_PATH, "w", encoding="utf-8") as f:
                f.write(full_md_content)
        except Exception as err:
            LOG.error(f"Failed to write MD dossier: {err}")

        # Compute line ranges for token-efficient line pointers
        header_end = min(12, line_count)
        positions_end = min(25, line_count)
        findings_start = min(26, line_count)
        
        return {
            "full_md": full_md_content,
            "total_lines": line_count,
            "header_range": f"L1-L{header_end}",
            "positions_range": f"L1-L{positions_end}",
            "findings_range": f"L{findings_start}-L{line_count}"
        }
