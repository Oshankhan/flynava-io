"""Use the operating-system trust store for TLS verification.

Some integration endpoints (e.g. OpenProject behind certain proxies) don't send
a complete certificate chain, so the bundled `certifi` roots can't verify them —
but the OS trust store can (it's what `curl` uses). `truststore` makes Python's
default SSL context read the OS store. Verification stays ON.
"""
from __future__ import annotations

_injected = False


def use_os_trust_store() -> None:
    global _injected
    if _injected:
        return
    try:
        import truststore

        truststore.inject_into_ssl()
        _injected = True
    except Exception:  # noqa: BLE001 - fall back to certifi if unavailable
        pass
