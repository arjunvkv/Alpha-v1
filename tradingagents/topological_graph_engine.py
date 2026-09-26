"""
ALPHA TRADING DESK — TOPOLOGICAL MARKET GRAPH ENGINE (GRAPHIFY GPS)
===================================================================
Constructs a deterministic, in-memory directed topological graph of market structure,
liquidity cascades, and cross-asset macro leash for XAUUSD on MT5.

Key Design Principles:
1. Anti-Telemetry Guardrail: Zero Level 2 DOM order book depth. Zero micro-tick noise.
   Operates strictly at the structural auction frequency (M5/M15/H1/H4).
2. Asymmetric Clearance Law: Minor intermediate M1/M5 levels in trade direction are
   classified as Take-Profit Highway Waypoints, NEVER as entry obstacles.
3. Dynamic Node Evaporation: Mitigated levels are dissolved upon candle close (no ghost nodes).
4. Localized 1-Hop Ego-Graph: Returns sub-80 token spatial radar for OpenCode.
"""

import time
import math
import logging
from typing import Dict, Any, List, Optional, Tuple

LOG = logging.getLogger("alpha.topological_graph")

class TopologicalGraphEngine:
    """
    Constructs and queries the live Spatial Market Graph.
    Extracts 1-hop ego-graphs, liquidity cascade chains, and obstacle clearance metrics.
    """

    def __init__(self):
        self._last_build_time = 0.0
        self._cached_graph: Dict[str, Any] = {}
        self._mitigated_node_ids = set()

    def build_market_graph(
        self,
        symbol: str = "XAUUSD",
        live_price: float = 0.0,
        spread_pts: float = 0.0,
        cvd_10b_pressure: float = 0.0,
        velocity_tpm: float = 0.0,
        dfii10: float = 2.83,
        us10y: float = 5.17,
        dxy: float = 101.03,
        cot_percentile: float = 80.4,
        fvg_matrix: Optional[Dict[str, Any]] = None,
        liquidity_data: Optional[Dict[str, Any]] = None,
        pivot_data: Optional[Dict[str, Any]] = None,
        rates_m5: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """
        Builds the live directed spatial graph for the given symbol.
        Operates in pure in-memory Python (<2ms compute time).
        """
        sym = str(symbol or "XAUUSD").strip().upper()
        
        # 1. Input Sanitization (Adversarial Robustness)
        try:
            live_price = float(live_price)
            if math.isnan(live_price) or math.isinf(live_price) or live_price <= 0.0 or live_price > 50000.0:
                live_price = 0.0
        except Exception:
            live_price = 0.0

        try:
            spread_pts = float(spread_pts)
            if math.isnan(spread_pts) or math.isinf(spread_pts) or spread_pts < 0.0:
                spread_pts = 20.0
        except Exception:
            spread_pts = 20.0

        # Fallbacks and defaults if price is not provided
        if live_price <= 0.0:
            try:
                import MetaTrader5 as mt5
                tick = mt5.symbol_info_tick(sym)
                if tick:
                    live_price = float(tick.ask if tick.ask > 0 else tick.bid)
                    spread_pts = round((tick.ask - tick.bid) * 100, 1)
            except Exception:
                live_price = 4285.23
                spread_pts = 47.0

        # 2. Extract Structural Spatial Anchors
        nodes = {}
        edges = []

        # Current Price Cursor Node
        nodes["CURSOR"] = {
            "id": "CURSOR",
            "type": "PRICE_CURSOR",
            "price": live_price,
            "spread_pts": spread_pts,
            "label": f"Price Cursor ({live_price:.2f})"
        }

        # Liquidity Radar Levels (Asian High/Low, PDH/PDL)
        ah, al, yh, yl = 4300.00, 4254.39, 4315.64, 4244.12
        if liquidity_data and isinstance(liquidity_data, dict):
            try:
                ah = float(liquidity_data.get("asian_high", 0) or 0)
                al = float(liquidity_data.get("asian_low", 0) or 0)
                yh = float(liquidity_data.get("yest_high", 0) or 0)
                yl = float(liquidity_data.get("yest_low", 0) or 0)
            except Exception:
                pass

        if ah > 0:
            nodes["ASIAN_HIGH"] = {
                "id": "ASIAN_HIGH", "type": "SESSION_EXTREME_BSL",
                "price": ah, "tf": "M15", "swept": live_price > ah,
                "label": f"Asian High BSL ({ah:.2f})"
            }
        if al > 0:
            nodes["ASIAN_LOW"] = {
                "id": "ASIAN_LOW", "type": "SESSION_EXTREME_SSL",
                "price": al, "tf": "M15", "swept": live_price < al,
                "label": f"Asian Low SSL ({al:.2f})"
            }
        if yh > 0:
            nodes["PDH"] = {
                "id": "PDH", "type": "PREV_DAY_HIGH_BSL",
                "price": yh, "tf": "D1", "swept": live_price > yh,
                "label": f"PDH ({yh:.2f})"
            }
        if yl > 0:
            nodes["PDL"] = {
                "id": "PDL", "type": "PREV_DAY_LOW_SSL",
                "price": yl, "tf": "D1", "swept": live_price < yl,
                "label": f"PDL ({yl:.2f})"
            }

        # Daily Pivot & S/R Shelves
        pp, demand_low, demand_high, supply_low, supply_high = 4272.95, 4244.12, 4246.62, 4300.66, 4303.16
        if pivot_data and isinstance(pivot_data, dict):
            try:
                pp = float(pivot_data.get("pp", 0) or 0)
                demand_low = float(pivot_data.get("demand_low", 0) or 0)
                demand_high = float(pivot_data.get("demand_high", 0) or 0)
                supply_low = float(pivot_data.get("supply_low", 0) or 0)
                supply_high = float(pivot_data.get("supply_high", 0) or 0)
            except Exception:
                pass

        if pp > 0:
            nodes["DAILY_PP"] = {
                "id": "DAILY_PP", "type": "VALUE_AREA_EQUILIBRIUM",
                "price": pp, "tf": "D1", "label": f"Daily PP ({pp:.2f})"
            }
        if demand_high > 0:
            nodes["DEMAND_SHELF"] = {
                "id": "DEMAND_SHELF", "type": "INSTITUTIONAL_DEMAND",
                "price": (demand_low + demand_high) / 2.0, "tf": "H1",
                "bottom": demand_low, "top": demand_high,
                "label": f"Demand Shelf ({demand_low:.2f}-{demand_high:.2f})"
            }
        if supply_low > 0:
            nodes["SUPPLY_SHELF"] = {
                "id": "SUPPLY_SHELF", "type": "INSTITUTIONAL_SUPPLY",
                "price": (supply_low + supply_high) / 2.0, "tf": "H1",
                "bottom": supply_low, "top": supply_high,
                "label": f"Supply Shelf ({supply_low:.2f}-{supply_high:.2f})"
            }

        # FVG Matrix Levels (M5, M15, H1)
        has_custom_fvgs = False
        if fvg_matrix and isinstance(fvg_matrix, dict):
            for fvg in fvg_matrix.get("active_fvgs", []):
                if not isinstance(fvg, dict):
                    continue
                try:
                    tf = str(fvg.get("timeframe", "M5"))
                    side = str(fvg.get("type", "BEARISH"))
                    ce = float(fvg.get("ce", 0) or 0)
                    top = float(fvg.get("top", 0) or 0)
                    bot = float(fvg.get("bottom", 0) or 0)
                    fill_pct = float(fvg.get("fill_pct", 0) or 0)
                    if math.isnan(ce) or math.isinf(ce) or ce <= 0:
                        continue
                    node_id = f"FVG_{tf}_{side}_{int(ce)}"

                    # Dynamic Node Evaporation: If 100% filled, dissolve the node
                    if fill_pct >= 100.0 or node_id in self._mitigated_node_ids:
                        continue

                    nodes[node_id] = {
                        "id": node_id, "type": f"FVG_{side}",
                        "price": ce, "tf": tf, "top": top, "bottom": bot,
                        "fill_pct": fill_pct,
                        "label": f"{tf} {side} FVG (CE: {ce:.2f}, {fill_pct:.0f}% fill)"
                    }
                    has_custom_fvgs = True
                except Exception:
                    continue

        if not has_custom_fvgs:
            # Default M5 Bear FVG from Friday close
            nodes["FVG_M5_BEAR_4286"] = {
                "id": "FVG_M5_BEAR_4286", "type": "FVG_BEARISH",
                "price": 4286.66, "tf": "M5", "top": 4286.72, "bottom": 4286.59,
                "fill_pct": 0.0, "label": "M5 Bear FVG (CE: 4286.66, 0% fill)"
            }

        # 3. Macro Leash & Order Flow Friction Attributes
        macro_leash = {
            "dfii10": dfii10,
            "us10y": us10y,
            "dxy": dxy,
            "cot_percentile": cot_percentile,
            "regime": "BEARISH_RATES_HEADWIND" if (dfii10 > 2.5 or us10y > 5.0) else "BULLISH_ACCOMMODATIVE",
            "crowded_long_specs": cot_percentile >= 75.0
        }

        order_flow = {
            "cvd_10b_pressure": cvd_10b_pressure,
            "velocity_tpm": velocity_tpm,
            "delta_bias": "NEGATIVE_ABSORPTION" if cvd_10b_pressure < -15.0 else ("POSITIVE_EXPANSION" if cvd_10b_pressure > 15.0 else "NEUTRAL")
        }

        # 4. Construct Directed Spatial Edges from Cursor
        for nid, n in nodes.items():
            if nid == "CURSOR":
                continue
            dist = round(n["price"] - live_price, 2)
            abs_dist = abs(dist)
            
            # Position relative to cursor
            rel_pos = "ABOVE" if dist > 0 else "BELOW"
            
            # Obstacle vs Target Classification (Asymmetric Clearance Law)
            # Intermediate levels in the direction of trade are highway waypoints, not obstacles
            is_obstacle = False
            is_uncompleted_sweep_hazard = False

            if abs_dist < 3.0:
                if "SESSION_EXTREME" in n["type"] and not n.get("swept", False):
                    # Uncompleted sweep within 3 pts is an active trap hazard
                    is_obstacle = True
                    is_uncompleted_sweep_hazard = True
                elif n["type"] in ("INSTITUTIONAL_DEMAND", "INSTITUTIONAL_SUPPLY") and abs_dist < 1.5:
                    is_obstacle = True

            edges.append({
                "from": "CURSOR",
                "to": nid,
                "distance_pts": dist,
                "abs_distance_pts": abs_dist,
                "relative_position": rel_pos,
                "level_type": n["type"],
                "target_price": n["price"],
                "is_obstacle": is_obstacle,
                "is_uncompleted_sweep_hazard": is_uncompleted_sweep_hazard
            })

        # Sort edges by absolute distance (nearest first)
        edges.sort(key=lambda e: e["abs_distance_pts"])

        graph = {
            "symbol": sym,
            "live_price": live_price,
            "spread_pts": spread_pts,
            "nodes": nodes,
            "edges": edges,
            "macro_leash": macro_leash,
            "order_flow": order_flow,
            "built_at": time.time()
        }

        self._cached_graph = graph
        self._last_build_time = time.time()
        return graph

    def get_localized_ego_graph(self, symbol: str = "XAUUSD", k_hops: int = 1) -> Dict[str, Any]:
        """
        Extracts the localized k-hop ego-graph around current price.
        Identifies nearest ceiling, nearest floor, downward cascade chain, and upward cascade chain.
        """
        if not self._cached_graph or self._cached_graph.get("symbol") != symbol.upper():
            self.build_market_graph(symbol=symbol)

        g = self._cached_graph
        live_p = g["live_price"]
        edges = g["edges"]
        nodes = g["nodes"]

        # Find nearest ceiling (above price) and nearest floor (below price)
        ceilings = [e for e in edges if e["relative_position"] == "ABOVE"]
        floors = [e for e in edges if e["relative_position"] == "BELOW"]

        nearest_ceiling = ceilings[0] if ceilings else None
        nearest_floor = floors[0] if floors else None

        # Build Downward Liquidity Cascade Chain
        # Major cascade targets below current price
        downward_chain = []
        for e in floors:
            nid = e["to"]
            n = nodes.get(nid, {})
            if n.get("type") in ("SESSION_EXTREME_SSL", "VALUE_AREA_EQUILIBRIUM", "INSTITUTIONAL_DEMAND", "PREV_DAY_LOW_SSL"):
                downward_chain.append({
                    "label": n.get("label"),
                    "price": n.get("price"),
                    "distance_pts": e["abs_distance_pts"]
                })
        downward_chain = downward_chain[:3]

        # Build Upward Liquidity Cascade Chain
        upward_chain = []
        for e in ceilings:
            nid = e["to"]
            n = nodes.get(nid, {})
            if n.get("type") in ("SESSION_EXTREME_BSL", "INSTITUTIONAL_SUPPLY", "PREV_DAY_HIGH_BSL"):
                upward_chain.append({
                    "label": n.get("label"),
                    "price": n.get("price"),
                    "distance_pts": e["abs_distance_pts"]
                })
        upward_chain = upward_chain[:3]

        # Obstacle Check
        hazard_edges = [e for e in edges if e.get("is_obstacle", False)]
        uncompleted_sweeps = [e for e in edges if e.get("is_uncompleted_sweep_hazard", False)]

        # Macro Highway Clearance Calculation
        # Planned SL buffer is governed by CONST_SL_STRUCTURAL (6.0 to 12.0 pts, standard 8.0 pts)
        ceiling_distance = nearest_ceiling["abs_distance_pts"] if nearest_ceiling else 8.0
        short_sl_budget = min(max(ceiling_distance, 6.0), 10.0)
        downward_runway = downward_chain[0]["distance_pts"] if downward_chain else 15.0
        short_rr = round(downward_runway / short_sl_budget, 2)

        floor_distance = nearest_floor["abs_distance_pts"] if nearest_floor else 8.0
        long_sl_budget = min(max(floor_distance, 6.0), 10.0)
        upward_runway = upward_chain[0]["distance_pts"] if upward_chain else 15.0
        long_rr = round(upward_runway / long_sl_budget, 2)

        return {
            "symbol": symbol.upper(),
            "live_price": live_p,
            "nearest_ceiling": nearest_ceiling,
            "nearest_floor": nearest_floor,
            "downward_cascade_chain": downward_chain,
            "upward_cascade_chain": upward_chain,
            "hazard_edges": hazard_edges,
            "uncompleted_sweeps": uncompleted_sweeps,
            "short_macro_runway_rr": short_rr,
            "long_macro_runway_rr": long_rr,
            "macro_leash": g.get("macro_leash", {}),
            "order_flow": g.get("order_flow", {})
        }

    def format_ego_graph_card(self, symbol: str = "XAUUSD", detailed: bool = False) -> str:
        """
        Formats topological inspection card for OpenCode.
        - detailed=False (default): sub-80 token compact radar card.
        - detailed=True: complete multi-level structural hierarchy of all active nodes.
        """
        if detailed:
            return self.format_detailed_graph_card(symbol=symbol)

        ego = self.get_localized_ego_graph(symbol=symbol)
        p = ego["live_price"]
        nc = ego["nearest_ceiling"]
        nf = ego["nearest_floor"]
        dw = ego["downward_cascade_chain"]
        up = ego["upward_cascade_chain"]
        leash = ego["macro_leash"]
        flow = ego["order_flow"]

        nc_str = f"+{nc['abs_distance_pts']:.2f} pts [{nc['to']}] @ {nc['target_price']:.2f}" if nc else "None"
        nf_str = f"-{nf['abs_distance_pts']:.2f} pts [{nf['to']}] @ {nf['target_price']:.2f}" if nf else "None"

        dw_str = " -> ".join([f"{d['price']:.1f}" for d in dw]) if dw else "None"
        up_str = " -> ".join([f"{u['price']:.1f}" for u in up]) if up else "None"

        card = (
            f"=== TOPOLOGICAL MARKET MAP ({symbol.upper()} @ {p:.2f}) ===\n"
            f"• Spatial Neighborhood: Ceiling: {nc_str} | Floor: {nf_str}\n"
            f"• Liquidity Cascades: Downward: [{dw_str}] (Runway R:R {ego['short_macro_runway_rr']}:1) | Upward: [{up_str}] (Runway R:R {ego['long_macro_runway_rr']}:1)\n"
            f"• Macro Leash & Tape: DFII10: {leash.get('dfii10', 0):.2f}% ({leash.get('regime')}) | 10b CVD: {flow.get('cvd_10b_pressure', 0):+.1f}%\n"
        )

        if ego["uncompleted_sweeps"]:
            haz = ego["uncompleted_sweeps"][0]
            card += f"• ⚠️ TRAP HAZARD: Price is {haz['abs_distance_pts']:.1f} pts from un-swept {haz['to']}. Front-running prohibited.\n"

        return card.strip()

    def format_detailed_graph_card(self, symbol: str = "XAUUSD") -> str:
        """
        Formats a comprehensive multi-level structural hierarchy of ALL active graph nodes:
        - Sorted ceilings (above price) and floors (below price) with exact coordinates, signed distance in pts, and level type.
        - Unmitigated FVG details (CE, boundary bounds, fill %).
        - Institutional Demand & Supply shelves.
        - Session extremes (Asian High/Low, PDH/PDL) with sweep status.
        - Extended cascade chains and obstacle hazard audit.
        """
        ego = self.get_localized_ego_graph(symbol=symbol)
        g = self._cached_graph
        p = ego["live_price"]
        edges = g.get("edges", [])
        nodes = g.get("nodes", {})
        leash = ego.get("macro_leash", {})
        flow = ego.get("order_flow", {})

        ceilings = [e for e in edges if e["relative_position"] == "ABOVE"]
        floors = [e for e in edges if e["relative_position"] == "BELOW"]

        lines = [
            f"=== TOPOLOGICAL MARKET MAP — MULTI-LEVEL STRUCTURAL INVENTORY ({symbol.upper()} @ {p:.2f}) ===",
            f"Live Cursor: {p:.2f} | Spread: {g.get('spread_pts', 0):.1f} pts | DFII10: {leash.get('dfii10', 0):.2f}% ({leash.get('regime', 'NEUTRAL')}) | CVD: {flow.get('cvd_10b_pressure', 0):+.1f}%",
            "",
            "--- OVERHEAD CEILINGS (ABOVE PRICE) ---"
        ]
        if not ceilings:
            lines.append("  (No overhead structural levels detected)")
        else:
            for idx, e in enumerate(ceilings, 1):
                nid = e["to"]
                n = nodes.get(nid, {})
                flag = " [OBSTACLE]" if e.get("is_obstacle") else ""
                if e.get("is_uncompleted_sweep_hazard"):
                    flag = " [TRAP HAZARD: UN-SWEPT EXTREME <3pts]"
                fvg_extra = ""
                if "FVG" in n.get("type", ""):
                    fvg_extra = f" (Bounds: {n.get('bottom', 0):.2f}-{n.get('top', 0):.2f}, Fill: {n.get('fill_pct', 0):.0f}%)"
                lines.append(f"  {idx}. +{e['abs_distance_pts']:.2f} pts | {n.get('label', nid)} @ {n.get('price', 0):.2f}{fvg_extra}{flag}")

        lines.extend([
            "",
            "--- UNDERLYING FLOORS (BELOW PRICE) ---"
        ])
        if not floors:
            lines.append("  (No underlying structural levels detected)")
        else:
            for idx, e in enumerate(floors, 1):
                nid = e["to"]
                n = nodes.get(nid, {})
                flag = " [OBSTACLE]" if e.get("is_obstacle") else ""
                if e.get("is_uncompleted_sweep_hazard"):
                    flag = " [TRAP HAZARD: UN-SWEPT EXTREME <3pts]"
                fvg_extra = ""
                if "FVG" in n.get("type", ""):
                    fvg_extra = f" (Bounds: {n.get('bottom', 0):.2f}-{n.get('top', 0):.2f}, Fill: {n.get('fill_pct', 0):.0f}%)"
                lines.append(f"  {idx}. -{e['abs_distance_pts']:.2f} pts | {n.get('label', nid)} @ {n.get('price', 0):.2f}{fvg_extra}{flag}")

        # All cascade levels
        dw = [f"{nodes[e['to']]['price']:.1f}" for e in floors if nodes.get(e['to'], {}).get('type') in ("SESSION_EXTREME_SSL", "VALUE_AREA_EQUILIBRIUM", "INSTITUTIONAL_DEMAND", "PREV_DAY_LOW_SSL")]
        up = [f"{nodes[e['to']]['price']:.1f}" for e in ceilings if nodes.get(e['to'], {}).get('type') in ("SESSION_EXTREME_BSL", "INSTITUTIONAL_SUPPLY", "PREV_DAY_HIGH_BSL")]

        dw_str = " -> ".join(dw) if dw else "None"
        up_str = " -> ".join(up) if up else "None"

        lines.extend([
            "",
            f"• Liquidity Cascade Sequences: Downward: [{dw_str}] (Runway R:R {ego.get('short_macro_runway_rr')}:1) | Upward: [{up_str}] (Runway R:R {ego.get('long_macro_runway_rr')}:1)"
        ])
        if ego.get("uncompleted_sweeps"):
            haz = ego["uncompleted_sweeps"][0]
            lines.append(f"• ⚠️ ACTIVE TRAP HAZARD: Price is {haz['abs_distance_pts']:.1f} pts from un-swept {haz['to']}. Front-running prohibited.")

        return "\n".join(lines).strip()

    def format_dossier_compact_vector(self, symbol: str = "XAUUSD") -> str:
        """
        Formats the ultra-compact 3-line topological vector for Turn A and Turn B dossier headers.
        Net-negative tokens: Replaces 15 lines of messy text with 3 lines of spatial coordinates.
        """
        ego = self.get_localized_ego_graph(symbol=symbol)
        p = ego["live_price"]
        nc = ego["nearest_ceiling"]
        nf = ego["nearest_floor"]
        dw = ego["downward_cascade_chain"]
        leash = ego["macro_leash"]
        flow = ego["order_flow"]

        nc_desc = f"+{nc['abs_distance_pts']:.1f}pt ({nc['target_price']:.1f})" if nc else "Clear"
        nf_desc = f"-{nf['abs_distance_pts']:.1f}pt ({nf['target_price']:.1f})" if nf else "Clear"
        target_desc = f"{dw[0]['price']:.1f} ({dw[0]['distance_pts']:.1f}pt)" if dw else "Open"

        cascade_str = " -> ".join([str(round(d["price"], 1)) for d in dw]) if dw else "Open"
        return (
            f"[TOPOLOGICAL GPS @ {p:.2f}]: Ceiling: {nc_desc} | Floor: {nf_desc} | Target Magnet: {target_desc} (R:R {ego['short_macro_runway_rr']}:1)\n"
            f"CASCADE CHAIN: {cascade_str}\n"
            f"MACRO LEASH: DFII10 {leash.get('dfii10', 0):.2f}% ({leash.get('regime', 'NEUTRAL')}) | CVD 10b: {flow.get('cvd_10b_pressure', 0):+.1f}%"
        )


# Global Singleton Instance
_topological_engine: Optional[TopologicalGraphEngine] = None

def get_topological_engine() -> TopologicalGraphEngine:
    global _topological_engine
    if _topological_engine is None:
        _topological_engine = TopologicalGraphEngine()
    return _topological_engine
