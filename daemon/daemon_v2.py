"""Daemon v2 engine - dumb alarm bell + AI trader (DAEMON_V2_SPEC.md).

v2 inverts v1's architecture: this process NEVER trades on its own
judgment. It evaluates generic conditions from an AI-authored alert file,
rings once per rule with a full wake prompt, and executes whatever comes
back through data/live/action.json under hard order validation.
"""

import json
import logging
import os
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

from daemon.conditions import EvalContext, evaluate_condition
from daemon.order_router import OrderRouter
from daemon.ring_state import RingStateStore
from daemon.rule_loader import load_rules
from daemon.safety import check_safety
from daemon.wake_prompt import default_banner, build_wake_prompt
from config import (
    DAEMON_V2_GRANGER_SNAPSHOT_PATH,
    DAEMON_V2_MIN_FREE_MARGIN_PCT,
    DAEMON_V2_OPENCODE_CMD,
    DAEMON_V2_POLL_INTERVAL_SECONDS,
    DAEMON_V2_SESSION_ID_FALLBACK,
    DAEMON_V2_TERMINAL_SILENCE_SECONDS,
    DAEMON_V2_WATCH_SYMBOLS,
    INSTRUMENTS,
    MAX_PORTFOLIO_HEAT_PCT,
)

LOG = logging.getLogger("alpha.daemon.v2")

# --- SESSION CONFIGURATION -------------------------------------------------
# The daemon rings the AI by injecting a short pointer message into an
# EXISTING opencode session via `opencode run <msg> -s <session_id>`.
# Session id is read live from data/live/session_id.txt so it can be
# re-pointed without code edits; the constant below is the fallback.
ALPHA_ROOT = Path(__file__).resolve().parent.parent
SESSION_ID_FILE = ALPHA_ROOT / "data" / "live" / "session_id.txt"
AI_SESSION_ID_FALLBACK = "ses_fd796f6e4ffevdglfweo12MmRC"  # active 2026-08-22
OPENCODE_CMD = r"C:\Users\arjun\AppData\Roaming\npm\opencode.cmd"


def resolve_session_id():
    """Session id override from session_id.txt, else the fallback."""
    try:
        sid = SESSION_ID_FILE.read_text(encoding="utf-8-sig").strip()
        if sid:
            return sid
    except OSError:
        pass
    return AI_SESSION_ID_FALLBACK


def _ring_summary_line(payload):
    """Flatten a fire payload into ONE cmd-safe line carrying its core
    context inline.

    Multi-line argv gets mangled through .cmd wrappers (everything past the
    first newline can be dropped -> historically delivered EMPTY messages
    to the session), so every automated fire MUST stay on a single line.
    The complete formatted wake prompt remains on disk at wake_prompt.txt;
    this line guarantees the session always knows WHAT fired and WHY even
    before opening any file.
    """
    p = dict(payload or {})
    market = p.get("market") or {}
    conds = "; ".join(
        "%s=%s(%s)" % (c.get("type"), c.get("fired"), c.get("detail", ""))
        for c in (p.get("conditions") or []))
    parts = [
        "[ALPHA DAEMON RING]",
        "kind=%s" % p.get("kind", "?"),
        "rule=%s" % p.get("id", "?"),
        "sym=%s" % market.get("symbol", "?"),
        "dir=%s" % p.get("direction", "?"),
        "last=%s" % market.get("last"),
        "bid=%s" % market.get("bid"),
        "ask=%s" % market.get("ask"),
        "spread=%s" % market.get("spread"),
        "bal=%s" % market.get("balance"),
        "eq=%s" % market.get("equity"),
        "ts=%s" % p.get("ts", ""),
        "fired=[%s]" % conds,
        "note=%s" % str(p.get("note", ""))[:120],
    ]
    line = " | ".join(parts)
    # hard scrub: never let a stray newline reach a .cmd argv
    return line.replace("\r", " ").replace("\n", " ")[:2000]


def wake_opencode(prompt_path, payload=None):
    """Ping the AI session with a single-line, context-carrying fire notice.

    The message embeds the ring's core facts INLINE (kind, rule id, symbol,
    direction, tick, spread, account balance/equity, timestamp, fired
    conditions) so the session receives FULL CONTEXT with every fire even
    before opening any file; the full formatted prompt remains at
    prompt_path for deep analysis and decisions still land in action.json.

    Empty-message guard: if the summary would somehow be blank, fall back
    to an explicit pointer line instead of sending an empty arg.
    """
    try:
        Path(prompt_path).read_text(encoding="utf-8-sig", errors="replace")
    except (OSError, UnicodeDecodeError):
        pass  # summary is built from the in-memory payload, not the file

    prompt_message = (
        "%s || FULL_CONTEXT_FILE=%s || ACTION: evaluate & write decision "
        "JSON to %s" % (_ring_summary_line(payload), prompt_path,
                        ALPHA_ROOT / "data" / "live" / "action.json"))
    if not prompt_message.strip():
        prompt_message = ("[ALPHA DAEMON RING] (payload unavailable) | Read "
                          "%s for full context" % prompt_path)
    cmd = [OPENCODE_CMD, "run", prompt_message, "-s", resolve_session_id()]
    try:
        subprocess.Popen(
            cmd, cwd=str(ALPHA_ROOT),
            creationflags=(subprocess.CREATE_NEW_PROCESS_GROUP
                           if os.name == "nt" else 0))
        return True
    except Exception as exc:
        LOG.error("opencode wake failed: %s", exc)
        LOG.info("Wake prompt saved to %s - manual intervention needed.",
                 prompt_path)
        return False


def waking_banner(payload, prompt_path):
    """default_banner + opencode session ping (the v2 'ring the bell')."""
    default_banner(payload, prompt_path)
    wake_opencode(prompt_path, payload=payload)

V2_MODULES = [
    "conditions.py", "rule_loader.py", "ring_state.py", "market_data.py",
    "order_router.py", "wake_prompt.py", "safety.py", "daemon_v2.py",
]

DEFAULT_SAFETY_CFG = {
    "max_heat_pct": MAX_PORTFOLIO_HEAT_PCT,
    "min_free_margin_pct": DAEMON_V2_MIN_FREE_MARGIN_PCT,
    "terminal_silence_sec": DAEMON_V2_TERMINAL_SILENCE_SECONDS,
}


def _utcnow():
    return datetime.now(timezone.utc)


def _iso(dt):
    return dt.isoformat()


def _num(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _provider_attr(provider, name, default):
    return getattr(provider, name, default)


def consume_action_file(eng):
    """Consume data/live/action.json if present. Never raises.

    WAIT / REJECT apply reset_rule_ids to rule latches (safety latches that
    are still breaching are protected by Engine.apply_resets).
    ORDER is routed through the engine router; fills land in
    filled_tickets. Every consumed action is archived to the processed
    JSONL and the action file is deleted.
    """
    if not getattr(eng, "action_file", None):
        return None
    if not os.path.exists(eng.action_file):
        return None
    try:
        with open(eng.action_file, "r", encoding="utf-8") as handle:
            action = json.load(handle)
    except (OSError, json.JSONDecodeError):
        _archive_processed(eng,
                           {"raw": "corrupt"},
                           {"success": False, "errors": ["corrupt_json"]})
        LOG.error("action file corrupt; archived and deleted")
        return None

    decision = str(action.get("decision", "")).strip().upper()
    result = {"success": True, "info": ""}
    if decision == "ORDER":
        spec = action.get("spec") or {}
        route_result, route_spec = eng.route_order(spec)
        result = dict(route_result)
        if result.get("success"):
            fill_rec = {
                "symbol": (route_spec or {}).get("symbol")
                          or spec.get("symbol"),
                "ticket": result.get("ticket"),
                "fill_price": result.get("fill_price"),
                "ts": _iso(_utcnow()),
            }
            eng.filled_tickets.append(fill_rec)
            store = getattr(eng, "state_store", None)
            if store is not None:
                store.record_filled(fill_rec)
    elif decision in ("WAIT", "REJECT"):
        resets = action.get("reset_rule_ids") or []
        eng.apply_resets(list(resets))
        result["info"] = "%s recorded; reset %d latch(es)" % (
            decision, len(resets))
    else:
        result = {"success": False,
                  "errors": ["unknown_decision '%s'" % decision]}

    _archive_processed(eng, action, result)
    try:
        os.remove(eng.action_file)
    except OSError as exc:
        LOG.error("could not delete action file: %s", exc)
    return {"decision": decision, "result": result}


def _archive_processed(eng, action, result):
    processed = getattr(eng, "processed_file", None)
    rec = {"processed_at": _iso(_utcnow()),
           "action": action, "result": result}
    if not processed:
        return
    with open(processed, "a", encoding="utf-8") as handle:
        handle.write(json.dumps(rec) + "\n")


class Engine:
    """The v2 alarm bell."""

    def __init__(self, provider, clock=None, banner=None, data_dir=".",
                 dry_run=True, poll_interval=DAEMON_V2_POLL_INTERVAL_SECONDS,
                 safety_cfg=None, watch_symbols=None,
                 granger_snapshot_path="", point_sizes=None):
        self.provider = provider
        self.clock = clock or _utcnow
        self.banner = banner or default_banner
        self.dry_run = dry_run
        self.poll_interval = poll_interval
        self.safety_cfg = dict(DEFAULT_SAFETY_CFG)
        self.safety_cfg.update(safety_cfg or {})
        self.watch_symbols = list(watch_symbols or [])
        self.granger_snapshot_path = granger_snapshot_path
        self.point_sizes = dict(point_sizes or {})

        self.state_store = RingStateStore(os.path.join(data_dir,
                                                       "ring_state.json"))
        self.wake_prompt_file = os.path.join(data_dir, "wake_prompt.txt")
        self.action_file = os.path.join(data_dir, "action.json")
        self.processed_file = os.path.join(data_dir,
                                           "processed_actions.jsonl")

        self.rules = []
        self.monitors = []
        self.router = OrderRouter(dry_run=self.dry_run,
                                  point_sizes=self.point_sizes)

        # authoritative in-memory latch set, mirrored into ring_state.json
        self.latched = set()
        for rid, entry in self.state_store.load()["latches"].items():
            if entry.get("kind") != "expired":
                self.latched.add(rid)

        self.filled_tickets = []
        self._prev_ticks = {}
        self._last_safety_breaches = set()

    # ------------------------------------------------------- loading -----
    def load_rules_object(self, rules):
        self.rules = [dict(r) for r in rules]

    def load_monitors(self, monitors):
        self.monitors = [dict(m) for m in monitors]

    def load_rules_file(self, path):
        res = load_rules(path)
        self.load_rules_object(res.rules)
        self.load_monitors(res.monitors)
        for err in res.errors:
            LOG.error("rules load error: %s", err)
        return res

    # -------------------------------------------------------- resets -----
    def apply_resets(self, rule_ids):
        """Clear rule latches. Safety latches whose breach STILL holds are
        protected - the AI cannot silence an active emergency."""
        cleared = []
        for rid in rule_ids or []:
            if rid.startswith("SAFETY_") and rid in self._last_safety_breaches:
                LOG.warning("reset of %s denied while breach persists", rid)
                continue
            self._unlatch(rid)
            cleared.append(rid)
        if cleared:
            try:
                self.state_store.record({
                    "event": "reset", "rule_ids": list(cleared),
                    "ts": _iso(self.clock())})
            except Exception:
                LOG.exception("failed to record reset event")

    def _unlatch(self, rid):
        self.latched.discard(rid)
        self.state_store.unlatch(rid)

    def _latch(self, rid, kind):
        self.latched.add(rid)
        self.state_store.latch(rid, kind)

    def _latch_kind(self, rid):
        entry = self.state_store.load()["latches"].get(rid) or {}
        return entry.get("kind")

    # -------------------------------------------------------- orders -----
    def route_order(self, spec):
        account = self.provider.get_account()
        symbol = (spec or {}).get("symbol")
        tick = {}
        if symbol:
            try:
                view = self.provider.get_market_view(symbol)
                tick = view.get("tick") or {}
            except Exception as exc:
                LOG.error("no market view for %s: %s", symbol, exc)
        result = self.router.route_order(spec or {}, account, tick)
        return result, dict(spec or {})

    # --------------------------------------------------------- poll ------
    def poll(self):
        """One evaluation cycle. Returns list of fired payloads."""
        rings = []
        try:
            rings.extend(self._poll_safety())
            rings.extend(self._poll_rules())
            rings.extend(self._poll_monitors())
            self._refresh_snapshot_cache()
        except Exception as exc:  # a broken provider must not kill the loop
            LOG.exception("poll cycle failed: %s", exc)
            return []
        consume_action_file(self)
        return rings

    def _load_snapshot(self):
        path = self.granger_snapshot_path
        if path and os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as handle:
                    data = json.load(handle)
                return data if isinstance(data, dict) else {}
            except (OSError, json.JSONDecodeError) as exc:
                LOG.error("granger snapshot unreadable: %s", exc)
        return {}

    def _refresh_snapshot_cache(self):
        self._snapshot_cache = self._load_snapshot()

    def _views_for_poll(self, symbols):
        views = {}
        for sym in sorted(symbols):
            try:
                view = self.provider.get_market_view(sym)
                views[sym] = view
            except Exception as exc:
                LOG.error("market view failed for %s: %s", sym, exc)
        return views

    def _eval_context(self, symbol, view):
        provider = self.provider
        bars = None
        if hasattr(provider, "get_bars"):
            try:
                bars = provider.get_bars(symbol)
            except Exception:
                bars = None
        if bars is None:
            bars = _provider_attr(provider, "bars", [])
        daily_bars = None
        if hasattr(provider, "get_daily_bars"):
            try:
                daily_bars = provider.get_daily_bars(symbol)
            except Exception:
                daily_bars = None
        if daily_bars is None:
            daily_bars = _provider_attr(provider, "daily_bars", [])
        snapshot = getattr(self, "_snapshot_cache", None)
        if snapshot is None:
            snapshot = self._load_snapshot()
        instrument = INSTRUMENTS.get(symbol) or {}
        point_size = (
            _num(self.point_sizes.get(symbol))
            or _num(instrument.get("pip_size"))
            or 0.01
        )
        tick = (view or {}).get("tick") or {}
        return EvalContext(
            symbol=symbol,
            tick=tick,
            prev_tick=self._prev_ticks.get(symbol),
            bars=bars or [],
            daily_bars=daily_bars or [],
            snapshot=snapshot,
            account=_provider_attr(provider, "account", {}) or {},
            positions=provider.get_positions(),
            now_utc=self.clock(),
            point_size=point_size,
        )

    @staticmethod
    def _conditions_fired(rule, ctx):
        results = []
        for cond in rule.get("conditions", []):
            results.append(evaluate_condition(cond, ctx))
        logic = str(rule.get("logic", "ALL")).upper()
        if logic == "ANY":
            ok = any(r.fired for r in results)
        else:
            ok = bool(results) and all(r.fired for r in results)
        detail_list = [{"type": c.get("type"), "fired": r.fired,
                        "detail": r.detail}
                       for c, r in zip(rule.get("conditions", []),
                                       results)]
        return ok, detail_list

    def _rule_expired(self, rule, now):
        expires = rule.get("expires_utc")
        if not expires:
            return False
        try:
            exp_dt = datetime.fromisoformat(str(expires).replace(
                "Z", "+00:00"))
        except ValueError:
            return False
        if exp_dt.tzinfo is None:
            exp_dt = exp_dt.replace(tzinfo=timezone.utc)
        return now >= exp_dt

    def _fire_payload(self, item, kind, ctx, details, view):
        tick = (view or {}).get("tick") or {}
        try:
            account = self.provider.get_account()
        except Exception:
            account = _provider_attr(self.provider, "account", {}) or {}
        account = account or {}
        bid, ask = _num(tick.get("bid")), _num(tick.get("ask"))
        spread_pts = None
        if bid is not None and ask is not None and ctx.point_size > 0:
            spread_pts = (ask - bid) / ctx.point_size
        return {
            "id": item.get("id"),
            "kind": kind,
            "direction": item.get("direction", "any"),
            "note": item.get("note", ""),
            "snapshot_path": self.granger_snapshot_path,
            "detail": "; ".join("%s=%s" % (d["type"], d["fired"])
                                for d in details),
            "conditions": details,
            "ts": _iso(ctx.now_utc),
            "market": {
                "symbol": item.get("symbol") or "",
                "bid": bid, "ask": ask, "spread": spread_pts,
                "last": tick.get("last"), "volume": tick.get("volume"),
                "time": tick.get("time"),
                "balance": account.get("balance"),
                "equity": account.get("equity"),
            },
        }

    def _persist_prompt(self, payload):
        """Write the AI wake prompt to disk BEFORE notifying downstream.
        Banner callbacks may be stubs or fail; the file must always exist."""
        try:
            text = build_wake_prompt(
                payload, snapshot_path=self.granger_snapshot_path)
            tmp = str(self.wake_prompt_file) + ".tmp"
            with open(tmp, "w", encoding="utf-8") as handle:
                handle.write(text)
            os.replace(tmp, self.wake_prompt_file)
        except Exception:
            LOG.exception("failed to persist wake prompt")

    def _evaluate_items(self, items, kind, views, rings):
        now = self.clock()
        for item in items:
            rid = item.get("id")
            if self._rule_expired(item, now):
                latches = self.state_store.load()["latches"]
                if latches.get(rid, {}).get("kind") != "expired":
                    self.state_store.record({
                        "event": "expired", "id": rid, "rule_id": rid,
                        "expires_utc": item.get("expires_utc"),
                        "ts": _iso(now)})
                    self.state_store.latch(rid, "expired")
                    LOG.info("rule %s expired; excluded until re-arm", rid)
                continue
            symbol = item.get("symbol") or item.get("ticket_or_symbol")
            view = views.get(symbol) if symbol else None
            if symbol and view is None:
                continue
            ctx = self._eval_context(symbol, view)
            ctx.rule_direction = item.get("direction", "any")
            fired, details = self._conditions_fired(item, ctx)
            if fired and rid not in self.latched:
                payload = self._fire_payload(item, kind, ctx, details, view)
                event = dict(payload)
                event["event"] = "fired"
                event["rule_id"] = rid
                self.state_store.record(event)
                self._persist_prompt(payload)
                self.banner(payload, self.wake_prompt_file)
                rings.append(payload)
                if item.get("ring_once", True):
                    self._latch(rid, kind)
                LOG.info("RING %s [%s]", rid, kind)
            elif fired and rid in self.latched:
                self.state_store.record({
                    "event": "suppressed_repeat", "id": rid,
                    "rule_id": rid,
                    "kind": self._latch_kind(rid), "ts": _iso(now)})
        for symbol, view in views.items():
            tick = (view or {}).get("tick")
            if tick:
                self._prev_ticks[symbol] = tick

    def _poll_rules(self):
        symbols = set(self.watch_symbols)
        symbols.update(r.get("symbol") for r in self.rules
                       if r.get("symbol"))
        views = self._views_for_poll(symbols)
        rings = []
        self._evaluate_items(self.rules, "entry", views, rings)
        return rings

    def _poll_monitors(self):
        symbols = set()
        for mon in self.monitors:
            sym = mon.get("ticket_or_symbol")
            if sym:
                symbols.add(sym)
        views = self._views_for_poll(symbols)
        rings = []
        self._evaluate_items(self.monitors, "monitor", views, rings)
        return rings

    def _poll_safety(self):
        rings = []
        now_ts = time.time()
        account = _provider_attr(self.provider, "account", {}) or {}
        positions = self.provider.get_positions()
        provider_ts = getattr(self.provider, "last_data_ts", None)
        payloads = check_safety(account, positions, self.safety_cfg,
                                provider_ts=provider_ts, now_ts=now_ts)
        breach_ids = {p["id"] for p in payloads}

        # auto re-arm safety latches whose breach cleared
        for sid in list(self.latched):
            if sid.startswith("SAFETY_") and sid not in breach_ids:
                self._unlatch(sid)
                LOG.info("safety %s cleared; re-armed", sid)

        self._last_safety_breaches = breach_ids
        for payload in payloads:
            sid = payload["id"]
            if sid not in self.latched:
                event = dict(payload)
                event["event"] = "fired"
                event["rule_id"] = sid
                self.state_store.record(event)
                self._persist_prompt(payload)
                self.banner(payload, self.wake_prompt_file)
                rings.append(payload)
                self._latch(sid, "safety")
                LOG.warning("SAFETY RING %s: %s", sid, payload.get("detail"))
            else:
                self.state_store.record({
                    "event": "suppressed_repeat", "id": sid,
                    "rule_id": sid,
                    "kind": "safety", "ts": _iso(self.clock())})
        return rings


def build_engine(cfg):
    """Factory. cfg keys: data_dir, dry_run, poll_interval, safety{},
    watch_symbols, granger_snapshot_path, point_sizes{}, rules_file."""
    cfg = cfg or {}
    data_dir = cfg.get("data_dir", ".")
    engine = Engine(
        provider=cfg.get("provider"),
        clock=cfg.get("clock"),
        banner=cfg.get("banner"),
        data_dir=data_dir,
        dry_run=bool(cfg.get("dry_run", True)),
        poll_interval=int(cfg.get("poll_interval", DAEMON_V2_POLL_INTERVAL_SECONDS)),
        safety_cfg=cfg.get("safety") or {},
        watch_symbols=cfg.get("watch_symbols") or [],
        granger_snapshot_path=cfg.get("granger_snapshot_path", ""),
        point_sizes=cfg.get("point_sizes") or {},
    )
    rules_file = cfg.get("rules_file")
    if rules_file:
        engine.load_rules_file(rules_file)
    return engine


def main():
    """Live entrypoint. ALPHA_DRY_RUN=1 keeps everything simulated."""
    import argparse
    import sys
    parser = argparse.ArgumentParser(description="Alpha Daemon v2")
    parser.add_argument("--data-dir", default=os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "data", "live"))
    parser.add_argument("--dry-run", action="store_true",
                        default=os.environ.get("ALPHA_DRY_RUN",
                                               "").strip() == "1")
    parser.add_argument("--once", action="store_true",
                        help="run a single poll then exit")
    parser.add_argument("--interval", type=int,
                        default=DAEMON_V2_POLL_INTERVAL_SECONDS)
    args = parser.parse_args()

    sys.path.insert(0, os.path.dirname(os.path.dirname(
        os.path.abspath(__file__))))
    from daemon.market_data import LiveMT5Provider, SimulatedProvider

    cfg = {
        "data_dir": args.data_dir,
        "dry_run": args.dry_run,
        "poll_interval": args.interval,
        "watch_symbols": list(DAEMON_V2_WATCH_SYMBOLS),
        "point_sizes": {
            symbol: INSTRUMENTS[symbol]["pip_size"]
            for symbol in DAEMON_V2_WATCH_SYMBOLS
            if symbol in INSTRUMENTS
        },
        # Real 7-layer Granger snapshot written by the orchestrator pull.
        "granger_snapshot_path": str(DAEMON_V2_GRANGER_SNAPSHOT_PATH),
        "rules_file": os.path.join(args.data_dir, "alert_rules.json"),
        "banner": waking_banner,
    }
    if cfg["dry_run"]:
        cfg["provider"] = SimulatedProvider([])
    else:
        cfg["provider"] = LiveMT5Provider(cfg["watch_symbols"])
    engine = build_engine(cfg)
    mode = "DRY-RUN" if engine.dry_run else "LIVE"
    LOG.info("Daemon v2 starting (%s): rules=%d monitors=%d",
             mode, len(engine.rules), len(engine.monitors))
    print("DAEMON V2 UP (%s) - %d rules, %d monitors"
          % (mode, len(engine.rules), len(engine.monitors)))
    try:
        while True:
            for payload in engine.poll():
                prompt_preview = build_wake_prompt(payload).splitlines()[1]
                print(prompt_preview)
            if args.once:
                break
            time.sleep(engine.poll_interval)
    except KeyboardInterrupt:
        print("Daemon v2 stopped cleanly.")


if __name__ == "__main__":
    main()
