"""Wake prompt builder + default banner (DAEMON_V2_SPEC.md section 8).

The banner is the ONLY thing Daemon v2 says to the AI. It must carry
everything needed for a from-scratch decision: rule identity, condition
detail, market snapshot, Granger pointer, reset protocol.
"""

import json
import os

BANNER_HEADER = "=" * 74


def build_wake_prompt(payload, snapshot_path=""):
    """Compose the full wake prompt text for one fired event payload."""
    payload = payload if isinstance(payload, dict) else {}
    rule_id = payload.get("id", "<unknown>")
    kind = str(payload.get("kind", "entry"))
    direction = payload.get("direction", "any")
    detail = payload.get("detail") or ""
    conditions = payload.get("conditions") or []
    market = payload.get("market") or {}
    note = payload.get("note") or ""
    snapshot_path = snapshot_path or payload.get("snapshot_path", "")

    lines = [
        BANNER_HEADER,
        "DAEMON V2 WAKE - %s [%s] direction=%s" % (rule_id, kind, direction),
        BANNER_HEADER,
        "",
        "TRIGGERED CONDITIONS:",
    ]
    for cond in conditions:
        if isinstance(cond, dict):
            lines.append("  - type=%s fired=%s | %s"
                         % (cond.get("type"), cond.get("fired"),
                            cond.get("detail")))
        else:
            lines.append("  - %s" % cond)
    lines += [
        "",
        "MARKET SNAPSHOT:",
        "  bid=%s ask=%s spread=%s last=%s volume=%s time=%s"
        % (market.get("bid"), market.get("ask"), market.get("spread"),
           market.get("last"), market.get("volume"), market.get("time")),
        "",
        "ACCOUNT:",
        "  balance=%s equity=%s" % (market.get("balance"),
                                   market.get("equity")),
        "",
        "FUNDAMENTALS:",
        "  Granger snapshot: %s" % (snapshot_path or "(none configured)"),
        "  Read it BEFORE answering. No fundamentals -> say so explicitly.",
    ]
    if note:
        lines += ["", "RULE NOTE: %s" % note]
    lines += [
        "",
        "DECISION PROTOCOL (answer as JSON only):",
        '  {"decision": "WAIT|ORDER|REJECT", ...}',
        "  - WAIT: conditions ambiguous; state what would change your mind.",
        "  - ORDER: include symbol/side/volume/sl/tp. SL+TP mandatory.",
        "  - REJECT: setup is a trap; explain which retail trap applies.",
        "  - To re-arm ring_once rules you consumed, list them under",
        "    \"reset_rule_ids\": [...] - safety latches CANNOT be reset.",
        "  - You have NO memory of previous wakes. Judge FROM SCRATCH.",
        BANNER_HEADER,
    ]
    return "\n".join(lines)


def default_banner(payload, prompt_path):
    """Default engine banner: persist the prompt atomically and echo it."""
    prompt_text = build_wake_prompt(payload)
    tmp_path = prompt_path + ".tmp"
    with open(tmp_path, "w", encoding="utf-8") as handle:
        handle.write(prompt_text)
    os.replace(tmp_path, prompt_path)
    print(BANNER_HEADER)
    print("WAKE PROMPT WRITTEN: %s" % prompt_path)
    print(BANNER_HEADER)
    print(json.dumps({"id": payload.get("id"),
                      "kind": payload.get("kind"),
                      "direction": payload.get("direction")},
                     indent=2))
