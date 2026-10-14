"""HTTP client helpers for DoH requests."""

from __future__ import annotations

import ssl

import httpx


def build_doh_client(
    *,
    timeout_s: float = 5.0,
    verify: bool | str | ssl.SSLContext = True,
    trust_env: bool = False,
    local_address: str | None = None,
) -> httpx.AsyncClient:
    """Return an async httpx client configured for DoH use."""
    transport = (
        httpx.AsyncHTTPTransport(
            verify=verify,
            trust_env=trust_env,
            http2=True,
            local_address=local_address,
            retries=0,
        )
        if local_address is not None
        else None
    )
    return httpx.AsyncClient(
        http2=True,
        timeout=httpx.Timeout(timeout_s),
        verify=verify,
        follow_redirects=False,
        trust_env=trust_env,
        transport=transport,
        headers={"Accept": "application/dns-message"},
    )
