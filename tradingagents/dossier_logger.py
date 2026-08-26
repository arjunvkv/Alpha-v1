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

    def write_dossier(self, cycle_count: int, instruments_data: list, open_positions: list, reversal_alerts: list, session_info: dict, gsr_data: dict) -> str:
        """
        Writes persistent JSON and Markdown dossiers to disk and returns the full markdown string.
        """
        now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # 1. JSON Dossier Output
        json_payload = {
            "timestamp": now_str,
            "cycle_count": cycle_count,
            "session_info": session_info,
            "gsr_data": gsr_data,
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
        md_lines.append(f"**Timestamp**: `{now_str}` | **Scan Cycle**: `{cycle_count}`")
        md_lines.append(f"**Session Clock**: `{session_info.get('session')}` ({session_info.get('description')} | `{session_info.get('utc_time')}`)")
        md_lines.append(f"**Intermarket Gold/Silver Ratio (GSR)**: `{gsr_data.get('gsr')}` [{gsr_data.get('status')}]\n")

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

        md_lines.append(f"## 🌐 Multi-Instrument 7-Agent Detailed Findings ({len(instruments_data)} Instruments Scanned)\n")

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

            md_lines.append(f"### 🔹 Instrument: {sym}")
            md_lines.append(f"- **Live Execution**: Ask `{tech.get('rsi', 50.0):.1f} RSI` | Spread: `{spread.get('pts')} pts (${spread.get('val')}) [{spread.get('status')}]` | Velocity: `{vel.get('ticks_per_min')} t/m [{vel.get('status')}]`")
            md_lines.append(f"- **ADR(20) Expansion**: Range `${adr.get('today_range')}/${adr.get('adr_20')}` (`{adr.get('pct_used')}% used`) [{adr.get('capacity_status')}]")
            md_lines.append(f"- **Multi-Timeframe Alignment**: H1 (`{mtf.get('h1_trend')}`) | M15 (`{mtf.get('m15_trend')}`) | M5 (`{mtf.get('m5_trend')}`) $\\rightarrow$ **{mtf.get('alignment')}**")
            md_lines.append(f"- **Order Blocks & Pivots**: Daily PP `{ob.get('pivot_point')}` (S1: `{ob.get('support_s1')}`, R1: `{ob.get('resistance_r1')}`) | Demand: `{ob.get('demand_zone')}` | Supply: `{ob.get('supply_zone')}`")
            md_lines.append(f"- **Technical Agent Internal Reasoning**: {tech.get('thesis', 'N/A')}")
            md_lines.append(f"- **COT / Fundamental Agent Internal Reasoning**: COT Percentile `{fund.get('cot_percentile', 50.0):.1f}%` | {fund.get('thesis', 'N/A')}")
            md_lines.append(f"- **Macro / News Agent Internal Reasoning**: DXY `{macro.get('dxy', 101.4)}`, VIX `{macro.get('vix', 15.8)}` | News Shield: `{news.get('status_text', 'CLEAR')}` | {macro.get('thesis', 'N/A')}")
            md_lines.append(f"- **Bull vs. Bear Debate Agent Internal Reasoning**: Consensus Score `{debate.get('consensus_score', 5.0)}/10` | Conviction `{debate.get('conviction', 'LOW')}` | Retail Trap Warning: `{'YES' if debate.get('retail_trap_warning') else 'NO'}`")
            md_lines.append(f"- **Risk Officer Agent Decision**: Approved: `{risk.get('approved')}` | Recommended Max Lot Size: `{risk.get('max_volume_lots', 0.10)} lots` | Rationale: `{risk.get('reason')}`")
            md_lines.append("")

        full_md_content = "\n".join(md_lines)
        try:
            with open(MD_DOSSIER_PATH, "w", encoding="utf-8") as f:
                f.write(full_md_content)
        except Exception as err:
            LOG.error(f"Failed to write MD dossier: {err}")

        return full_md_content
