"""TLS trust helpers for integration endpoints with incomplete cert chains.

op.flynava.ai (and possibly other future integrations) only sends its leaf
certificate, not the intermediate that signs it — `openssl s_client
-showcerts` against it shows just `*.flynava.ai`, issued by "Go Daddy Secure
Certificate Authority - G2". Windows' SChannel silently fetches missing
intermediates via the cert's AIA extension and caches them, which is why this
"just works" on a Windows dev machine — but Linux/OpenSSL (Render's
container) does not do that fetch, so the same request fails there with
"unable to get local issuer certificate" even though verification is
otherwise working correctly. Verification stays ON either way; this only
completes the chain, it doesn't disable checking it.
"""
from __future__ import annotations

import tempfile
from pathlib import Path

_CERTS_DIR = Path(__file__).parent / "certs"
_bundle_cache: dict[tuple[str, ...], str] = {}


def combined_ca_bundle(*extra_pem_files: str) -> str:
    """certifi's default CA bundle plus repo-local extra PEM cert(s) appended
    — for servers missing an intermediate from their handshake, which neither
    certifi's public roots nor a Linux OS trust store can complete on their
    own (only Windows does automatic AIA chain-fetching). Returns a path
    suitable for httpx's `verify=`. Cached per unique set of extra files.
    """
    key = tuple(sorted(extra_pem_files))
    if key in _bundle_cache and Path(_bundle_cache[key]).exists():
        return _bundle_cache[key]

    import certifi

    parts = [Path(certifi.where()).read_text()]
    for name in extra_pem_files:
        parts.append((_CERTS_DIR / name).read_text())

    fd, path = tempfile.mkstemp(suffix=".pem", prefix="io_ca_bundle_")
    with open(fd, "w", encoding="utf-8") as f:
        f.write("\n".join(parts))
    _bundle_cache[key] = path
    return path
