"""
GRAPHIFY GPS — LIVE STRUCTURAL TOPOLOGY ENGINE

Graphify describes observable market structure. It does not predict price and does
not make trading decisions. Runtime coordinates must come from a verified live
quote or explicit replay/test observations; there are no fabricated price seeds.
"""

from __future__ import annotations

import logging
import math
import time
from datetime import datetime, time as dt_time, timezone
from typing import Any, Dict, List, Optional
from zoneinfo import ZoneInfo

LOG = logging.getLogger("alpha.topological_graph")

ACTIVE = "ACTIVE"
MITIGATED = "MITIGATED"
RETIRED = "RETIRED"


def _valid_price(value: Any) -> Optional[float]:
    try:
        value = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(value) or value <= 0.0 or value > 50000.0:
        return None
    return value


def _number(value: Any, default: Optional[float] = None) -> Optional[float]:
    try:
        value = float(value)
    except (TypeError, ValueError):
        return default
    return value if math.isfinite(value) else default


def _session_contains(hour_minute: tuple[int, int], start: dt_time, end: dt_time) -> bool:
    current = dt_time(*hour_minute)
    if start <= end:
        return start <= current < end
    return current >= start or current < end


def _session_bounds(config: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    cfg = config or {}
    tz_name = str(cfg.get("timezone") or "UTC")
    try:
        tz = ZoneInfo(tz_name)
    except Exception:
        LOG.warning("Invalid topology session timezone %s; using UTC", tz_name)
        tz_name, tz = "UTC", timezone.utc

    def parse_clock(value: Any, fallback: str) -> dt_time:
        raw = str(value or fallback)
        try:
            hour, minute = [int(x) for x in raw.split(":")[:2]]
            return dt_time(hour, minute)
        except Exception:
            hour, minute = [int(x) for x in fallback.split(":")]
            return dt_time(hour, minute)

    return {
        "name": str(cfg.get("name") or "ASIAN"),
        "timezone": tz_name,
        "timezone_obj": tz,
        "start": parse_clock(cfg.get("start"), "00:00"),
        "end": parse_clock(cfg.get("end"), "07:00"),
    }


def _live_tick(symbol: str) -> Optional[Dict[str, float]]:
    try:
        import MetaTrader5 as mt5
        tick = mt5.symbol_info_tick(symbol)
        if not tick:
            return None
        bid = _valid_price(getattr(tick, "bid", None))
        ask = _valid_price(getattr(tick, "ask", None))
        if bid is None and ask is None:
            return None
        if bid is None:
            bid = ask
        if ask is None:
            ask = bid
        return {
            "bid": bid,
            "ask": ask,
            "mid": (bid + ask) / 2.0,
            "spread_price": max(0.0, ask - bid),
        }
    except Exception:
        return None


def _live_liquidity_data(symbol: str, session_config: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Derive previous-day and configured-session extremes from MT5 bars."""
    out: Dict[str, Any] = {}
    try:
        import MetaTrader5 as mt5
        import pandas as pd  # type: ignore
        from datetime import timedelta

        d1 = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_D1, 1, 1)
        if d1 is not None and len(d1):
            row = d1[0]
            out["yest_high"] = _valid_price(row["high"])
            out["yest_low"] = _valid_price(row["low"])
            out["yest_close"] = _valid_price(row["close"])

        session = _session_bounds(session_config)
        now_utc = datetime.now(timezone.utc)
        local_now = now_utc.astimezone(session["timezone_obj"])
        session_date = local_now.date()
        if local_now.time() < session["start"]:
            session_date = session_date
            if session["start"] > session["end"]:
                session_date = session_date - timedelta(days=1)

        start_local = datetime.combine(session_date, session["start"], tzinfo=session["timezone_obj"])
        end_local = datetime.combine(session_date, session["end"], tzinfo=session["timezone_obj"])
        if session["start"] >= session["end"]:
            if local_now.time() < session["end"]:
                start_local -= timedelta(days=1)
            end_local += timedelta(days=1)

        rates = mt5.copy_rates_range(
            symbol,
            mt5.TIMEFRAME_H1,
            start_local.astimezone(timezone.utc),
            end_local.astimezone(timezone.utc),
        )
        if rates is not None and len(rates):
            frame = pd.DataFrame(rates)
            out["session_high"] = _valid_price(frame["high"].max())
            out["session_low"] = _valid_price(frame["low"].min())
            out["session_name"] = session["name"]
            out["session_timezone"] = session["timezone"]
            out["session_start"] = start_local.isoformat()
            out["session_end"] = end_local.isoformat()
    except Exception as exc:
        LOG.debug("Live liquidity derivation unavailable: %s", exc)
    return out


def _live_pivot_data(symbol: str) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    try:
        import MetaTrader5 as mt5
        rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_D1, 1, 1)
        if rates is not None and len(rates):
            row = rates[0]
            high = _valid_price(row["high"])
            low = _valid_price(row["low"])
            close = _valid_price(row["close"])
            if high and low and close:
                out["pp"] = (high + low + close) / 3.0
    except Exception:
        pass
    return out


def _node_state(node: Dict[str, Any], cursor: float) -> str:
    if node.get("fill_pct") is not None and _number(node.get("fill_pct"), 0.0) >= 100.0:
        return RETIRED
    if node.get("swept") is True:
        return MITIGATED
    return ACTIVE



class TopologicalGraphEngine:
    """Builds and queries a live structural market graph only."""

    def __init__(self) -> None:
        self._last_build_time = 0.0
        self._cached_graph: Dict[str, Any] = {}
        self._node_history: Dict[str, str] = {}

    def build_market_graph(
        self,
        symbol: str = "XAUUSD",
        live_price: float = 0.0,
        spread_pts: float = 0.0,
        cvd_10b_pressure: float = 0.0,
        velocity_tpm: float = 0.0,
        dfii10: Optional[float] = None,
        us10y: Optional[float] = None,
        dxy: Optional[float] = None,
        cot_percentile: Optional[float] = None,
        fvg_matrix: Optional[Dict[str, Any]] = None,
        liquidity_data: Optional[Dict[str, Any]] = None,
        pivot_data: Optional[Dict[str, Any]] = None,
        rates_m5: Optional[List[Dict[str, Any]]] = None,
        session_config: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        sym = str(symbol or "XAUUSD").strip().upper()
        built_at = time.time()

        explicit_price = _valid_price(live_price)
        tick = _live_tick(sym) if explicit_price is None else None
        price = explicit_price or (tick["mid"] if tick else None)
        if price is None:
            graph = {
                "symbol": sym,
                "status": "LIVE_TOPOLOGY_UNAVAILABLE",
                "reason": "No verified live quote and no explicit observation supplied",
                "live_price": None,
                "spread_pts": None,
                "nodes": {},
                "edges": [],
                "macro_leash": {},
                "order_flow": {},
                "session": {k: v for k, v in _session_bounds(session_config).items() if k != "timezone_obj"},
                "built_at": built_at,
            }
            self._cached_graph = graph
            self._last_build_time = graph["built_at"]
            return graph

        if tick:
            spread = tick["spread_price"] * 100.0
        else:
            spread = _number(spread_pts)
            if spread is None or spread < 0:
                spread = None

        nodes: Dict[str, Dict[str, Any]] = {
            "CURSOR": {
                "id": "CURSOR",
                "type": "PRICE_CURSOR",
                "price": price,
                "tf": "TICK",
                "lifecycle_state": ACTIVE,
                "label": f"Price Cursor ({price:.2f})",
            }
        }

        # Explicit observations are isolated from live MT5 structure so replay/test
        # coordinates cannot be contaminated by the current market.
        liq = dict(_live_liquidity_data(sym, session_config)) if tick else {}
        if liquidity_data:
            liq.update({k: v for k, v in liquidity_data.items() if v is not None})
            if "session_high" not in liq and liquidity_data.get("asian_high") is not None:
                liq["session_high"] = liquidity_data["asian_high"]
            if "session_low" not in liq and liquidity_data.get("asian_low") is not None:
                liq["session_low"] = liquidity_data["asian_low"]

        level_specs = [
            ("SESSION_HIGH", "SESSION_EXTREME_BSL", "session_high", "M15", price > (_valid_price(liq.get("session_high")) or math.inf)),
            ("SESSION_LOW", "SESSION_EXTREME_SSL", "session_low", "M15", price < (_valid_price(liq.get("session_low")) or -math.inf)),
            ("PDH", "PREV_DAY_HIGH_BSL", "yest_high", "D1", price > (_valid_price(liq.get("yest_high")) or math.inf)),
            ("PDL", "PREV_DAY_LOW_SSL", "yest_low", "D1", price < (_valid_price(liq.get("yest_low")) or -math.inf)),
        ]
        for nid, ntype, key, tf, swept in level_specs:
            value = _valid_price(liq.get(key))
            if value is not None:
                nodes[nid] = {
                    "id": nid, "type": ntype, "price": value, "tf": tf,
                    "swept": bool(swept), "lifecycle_state": MITIGATED if swept else ACTIVE,
                    "source": "live_mt5" if key not in liq or key not in (liquidity_data or {}) else "explicit_observation",
                    "label": f"{nid} ({value:.2f})",
                }

        pivot = dict(_live_pivot_data(sym)) if tick else {}
        if pivot_data:
            pivot.update({k: v for k, v in pivot_data.items() if v is not None})

        pp = _valid_price(pivot.get("pp"))
        if pp is not None:
            nodes["DAILY_PP"] = {
                "id": "DAILY_PP", "type": "VALUE_AREA_EQUILIBRIUM",
                "price": pp, "tf": "D1", "lifecycle_state": ACTIVE,
                "source": "live_mt5" if not pivot_data else "explicit_observation",
                "label": f"Daily PP ({pp:.2f})",
            }

        for nid, ntype, lo_key, hi_key in (
            ("DEMAND_SHELF", "INSTITUTIONAL_DEMAND", "demand_low", "demand_high"),
            ("SUPPLY_SHELF", "INSTITUTIONAL_SUPPLY", "supply_low", "supply_high"),
        ):
            lo, hi = _valid_price(pivot.get(lo_key)), _valid_price(pivot.get(hi_key))
            if lo is not None and hi is not None and lo <= hi:
                nodes[nid] = {
                    "id": nid, "type": ntype, "price": (lo + hi) / 2.0,
                    "bottom": lo, "top": hi, "tf": "H1",
                    "lifecycle_state": ACTIVE, "source": "explicit_observation",
                    "label": f"{nid.replace('_', ' ').title()} ({lo:.2f}-{hi:.2f})",
                }

        active_fvgs = []
        retired_node_ids: List[str] = []
        if fvg_matrix and isinstance(fvg_matrix, dict):
            active_fvgs = fvg_matrix.get("active_fvgs", []) or []
        for idx, fvg in enumerate(active_fvgs):
            if not isinstance(fvg, dict):
                continue
            ce = _valid_price(fvg.get("ce"))
            top, bottom = _valid_price(fvg.get("top")), _valid_price(fvg.get("bottom"))
            fill = _number(fvg.get("fill_pct"), 0.0)
            tf = str(fvg.get("timeframe") or "M5").upper()
            side = str(fvg.get("type") or "UNKNOWN").upper()
            nid = str(fvg.get("id") or f"FVG_{tf}_{side}_{idx}")
            if ce is None or top is None or bottom is None or fill is None:
                continue
            if fill >= 100.0:
                retired_node_ids.append(nid)
                self._node_history[nid] = RETIRED
                continue
            nodes[nid] = {
                "id": nid, "type": f"FVG_{side}", "price": ce, "tf": tf,
                "top": top, "bottom": bottom, "fill_pct": max(0.0, min(100.0, fill)),
                "lifecycle_state": ACTIVE, "source": "explicit_observation",
                "label": f"{tf} {side} FVG (CE: {ce:.2f}, {fill:.0f}% fill)",
            }

        edges: List[Dict[str, Any]] = []
        relationship_by_type = {
            "SESSION_EXTREME_BSL": "LIQUIDITY_TARGET",
            "SESSION_EXTREME_SSL": "LIQUIDITY_TARGET",
            "PREV_DAY_HIGH_BSL": "LIQUIDITY_TARGET",
            "PREV_DAY_LOW_SSL": "LIQUIDITY_TARGET",
            "VALUE_AREA_EQUILIBRIUM": "VALUE_REFERENCE",
            "INSTITUTIONAL_DEMAND": "STRUCTURAL_ZONE",
            "INSTITUTIONAL_SUPPLY": "STRUCTURAL_ZONE",
        }
        for nid, node in nodes.items():
            if nid == "CURSOR":
                continue
            distance = round(node["price"] - price, 6)
            direction = "ABOVE" if distance > 0 else ("BELOW" if distance < 0 else "AT")
            relationship = relationship_by_type.get(node["type"], "IMBALANCE_WAYPOINT" if node["type"].startswith("FVG_") else "STRUCTURAL_REFERENCE")
            state = node.get("lifecycle_state", ACTIVE)
            edges.append({
                "from": "CURSOR",
                "to": nid,
                "relationship": relationship,
                "distance_pts": distance,
                "abs_distance_pts": abs(distance),
                "direction": direction,
                "state": state,
                "level_type": node["type"],
                "target_price": node["price"],
                "is_obstacle": False,
                "is_uncompleted_sweep_hazard": (
                    node["type"] in {"SESSION_EXTREME_BSL", "SESSION_EXTREME_SSL", "PREV_DAY_HIGH_BSL", "PREV_DAY_LOW_SSL"}
                    and state == ACTIVE and abs(distance) < 3.0
                ),
            })
        # Keep the radial cursor relations for compatibility, but also materialize
        # explicit directional paths. A path is an ordered sequence of structural
        # targets that price would encounter moving in one direction from CURSOR.
        # This turns the graph from a nearest-level inventory into a traversable
        # market roadway without making a directional trading decision.
        above_edges = sorted(
            [e for e in edges if e["direction"] == "ABOVE"],
            key=lambda e: e["target_price"],
        )
        below_edges = sorted(
            [e for e in edges if e["direction"] == "BELOW"],
            key=lambda e: e["target_price"],
            reverse=True,
        )

        def _build_directional_path(
            source_edges: List[Dict[str, Any]],
            direction: str,
        ) -> Dict[str, Any]:
            steps: List[Dict[str, Any]] = []
            previous_node = "CURSOR"
            previous_price = price
            cumulative = 0.0
            path_state = "CLEAR"
            for index, edge in enumerate(source_edges, start=1):
                step_distance = round(abs(edge["target_price"] - previous_price), 6)
                cumulative = round(cumulative + step_distance, 6)
                node_id = edge["to"]
                node = nodes[node_id]
                hazard = bool(edge.get("is_uncompleted_sweep_hazard"))
                if hazard and path_state == "CLEAR":
                    path_state = "HAZARD"
                steps.append({
                    "index": index,
                    "from": previous_node,
                    "to": node_id,
                    "direction": direction,
                    "from_price": previous_price,
                    "to_price": node["price"],
                    "step_distance_pts": step_distance,
                    "cumulative_distance_pts": cumulative,
                    "relationship": edge["relationship"],
                    "state": edge["state"],
                    "target_type": node["type"],
                    "target_label": node["label"],
                    "is_uncompleted_sweep_hazard": hazard,
                })
                previous_node = node_id
                previous_price = node["price"]

            return {
                "direction": direction,
                "origin": "CURSOR",
                "nodes": [step["to"] for step in steps],
                "steps": steps,
                "terminal_node": steps[-1]["to"] if steps else None,
                "terminal_price": steps[-1]["to_price"] if steps else None,
                "runway_pts": cumulative if steps else 0.0,
                "path_state": path_state,
            }

        directional_paths = {
            "UP": _build_directional_path(above_edges, "UP"),
            "DOWN": _build_directional_path(below_edges, "DOWN"),
        }

        # Explicit path edges are graph-native relationships between successive
        # targets. Radial CURSOR edges remain available as direct spatial facts.
        path_edges: List[Dict[str, Any]] = []
        for path in directional_paths.values():
            for step in path["steps"]:
                path_edges.append({
                    "from": step["from"],
                    "to": step["to"],
                    "relationship": "DIRECTIONAL_PATH_STEP",
                    "direction": step["direction"],
                    "distance_pts": step["step_distance_pts"],
                    "abs_distance_pts": step["step_distance_pts"],
                    "cumulative_distance_pts": step["cumulative_distance_pts"],
                    "state": step["state"],
                    "level_type": step["target_type"],
                    "target_price": step["to_price"],
                    "is_path_edge": True,
                    "is_uncompleted_sweep_hazard": step["is_uncompleted_sweep_hazard"],
                })

        edges.sort(key=lambda e: e["abs_distance_pts"])

        macro = {}
        for key, value in (("dfii10", dfii10), ("us10y", us10y), ("dxy", dxy), ("cot_percentile", cot_percentile)):
            if value is not None and _number(value) is not None:
                macro[key] = float(value)

        session = _session_bounds(session_config)        now_local = datetime.now(timezone.utc).astimezone(session["timezone_obj"])
        session_active = _session_contains(
            (now_local.hour, now_local.minute), session["start"], session["end"]
        )
        graph = {
            "symbol": sym,
            "status": "LIVE" if tick else "OBSERVATION",
            "input_mode": "MT5_LIVE_QUOTE" if tick else "EXPLICIT_OBSERVATION",
            "live_price": price,
            "spread_pts": spread,
            "nodes": nodes,
            "edges": edges,
            "path_edges": path_edges,
            "directional_paths": directional_paths,
            "macro_observations": macro,
            "order_flow_observations": {
                "cvd_10b_pressure": _number(cvd_10b_pressure, 0.0),
                "velocity_tpm": _number(velocity_tpm, 0.0),
            },
            "session": {
                "name": session["name"],
                "timezone": session["timezone"],
                "start": session["start"].strftime("%H:%M"),
                "end": session["end"].strftime("%H:%M"),
                "state": "ACTIVE" if session_active else "OUTSIDE",
            },
            "retired_node_ids": retired_node_ids,
            "built_at": built_at,
        }

        for nid, node in nodes.items():
            previous = self._node_history.get(nid)
            current = node.get("lifecycle_state", ACTIVE)
            if current == ACTIVE and previous == MITIGATED:
                node["lifecycle_state"] = ACTIVE
            self._node_history[nid] = node.get("lifecycle_state", ACTIVE)

        self._cached_graph = graph
        self._last_build_time = graph["built_at"]
        return graph

    def get_localized_ego_graph(self, symbol: str = "XAUUSD", k_hops: int = 1) -> Dict[str, Any]:
        if not self._cached_graph or self._cached_graph.get("symbol") != symbol.upper():
            graph = self.build_market_graph(symbol=symbol)
        else:
            graph = self._cached_graph

        if graph.get("status") == "LIVE_TOPOLOGY_UNAVAILABLE":
            return {
                "symbol": symbol.upper(),
                "status": graph["status"],
                "live_price": None,
                "nearest_ceiling": None,
                "nearest_floor": None,
                "downward_cascade_chain": [],
                "upward_cascade_chain": [],
                "hazard_edges": [],
                "uncompleted_sweeps": [],
                "macro_observations": {},
                "order_flow_observations": {},
            }

        price = graph["live_price"]
        edges = graph["edges"]
        nodes = graph["nodes"]
        ceilings = [e for e in edges if e["direction"] == "ABOVE"]
        floors = [e for e in edges if e["direction"] == "BELOW"]

        nearest_ceiling = ceilings[0] if ceilings else None
        nearest_floor = floors[0] if floors else None

        def chain(source: List[Dict[str, Any]], allowed: set[str]) -> List[Dict[str, Any]]:
            return [
                {"label": nodes[e["to"]]["label"], "price": nodes[e["to"]]["price"], "distance_pts": e["abs_distance_pts"], "relationship": e["relationship"], "state": e["state"]}
                for e in source if nodes.get(e["to"], {}).get("type") in allowed
            ][:3]

        downward = chain(floors, {"SESSION_EXTREME_SSL", "PREV_DAY_LOW_SSL", "INSTITUTIONAL_DEMAND", "VALUE_AREA_EQUILIBRIUM", "FVG_BEARISH"})
        upward = chain(ceilings, {"SESSION_EXTREME_BSL", "PREV_DAY_HIGH_BSL", "INSTITUTIONAL_SUPPLY", "FVG_BULLISH"})
        hazards = [e for e in edges if e["is_uncompleted_sweep_hazard"]]

        return {
            "symbol": symbol.upper(),
            "status": graph.get("status"),
            "live_price": price,
            "nearest_ceiling": nearest_ceiling,
            "nearest_floor": nearest_floor,
            "downward_cascade_chain": downward,
            "upward_cascade_chain": upward,
            "downward_path": graph.get("directional_paths", {}).get("DOWN", {}),
            "upward_path": graph.get("directional_paths", {}).get("UP", {}),
            "path_edges": graph.get("path_edges", []),
            "hazard_edges": hazards,
            "uncompleted_sweeps": hazards,
            "macro_observations": graph.get("macro_observations", {}),
            "order_flow_observations": graph.get("order_flow_observations", {}),
            "session": graph.get("session", {}),
        }

    def format_ego_graph_card(self, symbol: str = "XAUUSD", detailed: bool = False) -> str:
        if detailed:
            return self.format_detailed_graph_card(symbol)
        ego = self.get_localized_ego_graph(symbol)
        if ego.get("status") == "LIVE_TOPOLOGY_UNAVAILABLE":
            return f"=== TOPOLOGICAL MARKET MAP ({symbol.upper()}) ===\n• Status: LIVE_TOPOLOGY_UNAVAILABLE"
        p = ego["live_price"]
        nc, nf = ego["nearest_ceiling"], ego["nearest_floor"]
        nc_str = f"+{nc['abs_distance_pts']:.2f} pts [{nc['to']}]" if nc else "None"
        nf_str = f"-{nf['abs_distance_pts']:.2f} pts [{nf['to']}]" if nf else "None"
        down = " -> ".join(f"{x['price']:.1f}" for x in ego["downward_cascade_chain"]) or "None"
        up = " -> ".join(f"{x['price']:.1f}" for x in ego["upward_cascade_chain"]) or "None"
        down_path = " -> ".join(str(x["to"]) for x in ego.get("downward_path", {}).get("steps", [])) or "None"
        up_path = " -> ".join(str(x["to"]) for x in ego.get("upward_path", {}).get("steps", [])) or "None"
        card = (
            f"=== TOPOLOGICAL MARKET MAP ({symbol.upper()} @ {p:.2f}) ===\n"
            f"• Spatial Relations: Ceiling {nc_str} | Floor {nf_str}\n"
            f"• Directional Roadway: DOWN [{down_path}] | UP [{up_path}]\n"
            f"• Structural Cascades: Down [{down}] | Up [{up}]\n"
            f"• Session: {ego['session'].get('name')} {ego['session'].get('start')}-{ego['session'].get('end')} {ego['session'].get('timezone')}\n"
        )
        if ego["uncompleted_sweeps"]:
            hazard = ego["uncompleted_sweeps"][0]
            card += f"• Uncompleted Sweep Hazard: {hazard['to']} at {hazard['abs_distance_pts']:.2f} pts\n"
        return card.strip()

    def format_detailed_graph_card(self, symbol: str = "XAUUSD") -> str:
        ego = self.get_localized_ego_graph(symbol)
        if ego.get("status") == "LIVE_TOPOLOGY_UNAVAILABLE":
            return f"=== TOPOLOGICAL MARKET MAP ({symbol.upper()}) ===\nStatus: LIVE_TOPOLOGY_UNAVAILABLE"
        graph = self._cached_graph
        lines = [
            f"=== TOPOLOGICAL MARKET MAP — STRUCTURAL INVENTORY ({symbol.upper()} @ {ego['live_price']:.2f}) ===",
            f"Session: {ego['session'].get('name')} {ego['session'].get('start')}-{ego['session'].get('end')} {ego['session'].get('timezone')}",
            "--- ABOVE PRICE ---",
        ]
        for e in [x for x in graph["edges"] if x["direction"] == "ABOVE"]:
            n = graph["nodes"][e["to"]]
            lines.append(f"  +{e['abs_distance_pts']:.2f} | {n['label']} | {e['relationship']} | {e['state']}")
        lines.append("--- BELOW PRICE ---")
        for e in [x for x in graph["edges"] if x["direction"] == "BELOW"]:
            n = graph["nodes"][e["to"]]
            lines.append(f"  -{e['abs_distance_pts']:.2f} | {n['label']} | {e['relationship']} | {e['state']}")
        return "\n".join(lines)

    def format_dossier_compact_vector(self, symbol: str = "XAUUSD") -> str:
        # Every dossier vector is a fresh structural observation. Never carry the
        # previous cycle's topology forward as if it were the current auction.
        self.build_market_graph(symbol=symbol)
        ego = self.get_localized_ego_graph(symbol)
        if ego.get("status") == "LIVE_TOPOLOGY_UNAVAILABLE":
            return f"[TOPOLOGICAL GPS {symbol.upper()}]: UNAVAILABLE"
        down_path = ego.get("downward_path", {})
        up_path = ego.get("upward_path", {})
        nc, nf = ego["nearest_ceiling"], ego["nearest_floor"]
        down_path = ego.get("downward_path", {})
        up_path = ego.get("upward_path", {})
        down_terminal = down_path.get("terminal_node") or "None"
        up_terminal = up_path.get("terminal_node") or "None"
        return (
            f"[TOPOLOGICAL GPS @ {ego['live_price']:.2f}]: "
            f"Ceiling: {nc['abs_distance_pts']:.1f}pt ({nc['to']}) | "
            f"Floor: {nf['abs_distance_pts']:.1f}pt ({nf['to']}) | "
            f"UP_PATH: {up_terminal} ({up_path.get('runway_pts', 0.0):.1f}pt) | "
            f"DOWN_PATH: {down_terminal} ({down_path.get('runway_pts', 0.0):.1f}pt)"
            if nc and nf else
            f"[TOPOLOGICAL GPS @ {ego['live_price']:.2f}]: "
            f"Ceiling: {nc['abs_distance_pts']:.1f}pt ({nc['to']}) | "
            f"Floor: {'None' if not nf else str(nf['abs_distance_pts']) + 'pt'}"
        )


_topological_engine: Optional[TopologicalGraphEngine] = None


def get_topological_engine() -> TopologicalGraphEngine:
    global _topological_engine
    if _topological_engine is None:
        _topological_engine = TopologicalGraphEngine()
    return _topological_engine
