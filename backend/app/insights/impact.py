"""Bug impact classification — independent of the human-set `priority` field.

`priority` reflects what someone judged urgent that day (a demo on the
calendar makes a logo color bug "High"); it doesn't tell you whether a bug
actually breaks a critical flow. This computes a second signal, `impact`,
from the bug's own title via keyword rules — no LLM call, no cost, instant,
fully auditable (you can see exactly which keyword fired). A bug with no
keyword match either way is left unclassified — it falls back to whatever
its `priority` field says, no override.

Used by `detectors_ops._critical_bug_aging` to catch bugs that are dangerous
but under-labeled (low/normal priority, high real impact) as well as the
reverse (over-labeled: high priority, cosmetic-only).

You own these lists — extend them as real incidents teach you what
"critical" actually means for this product.
"""
from __future__ import annotations

CRITICAL_AREA_KEYWORDS = [
    "payment", "checkout", "refund", "booking", "book now", "fare", "price",
    "pricing", "login", "log in", "signin", "sign in", "auth", "check-in",
    "checkin", "boarding pass", "pnr", "ticket", "wallet", "invoice",
    "cancellation", "reschedule", "crash", "data loss", "security",
]
COSMETIC_KEYWORDS = [
    "logo", "color", "colour", "font", "spacing", "alignment", "padding",
    "margin", "icon", "typo", "wording", "copy", "label text", "css",
    "ui polish", "styling", "tooltip text",
]


def classify_impact(title: str) -> str | None:
    """'high' (critical-area keyword matched), 'low' (cosmetic keyword
    matched), or None (no keyword match — no override, defer to priority)."""
    t = (title or "").lower()
    if any(kw in t for kw in CRITICAL_AREA_KEYWORDS):
        return "high"
    if any(kw in t for kw in COSMETIC_KEYWORDS):
        return "low"
    return None
