"""Regression tests for fork DoH settings in the merged validation pipeline."""

from __future__ import annotations

import dns.message
import httpx
import pytest

from resolver_inventory.models import Candidate, ProbeResult
from resolver_inventory.settings import Settings
from resolver_inventory.validate import validate_candidates
from resolver_inventory.validate.capabilities import capability_check_names


@pytest.mark.parametrize("trust_env", [False, True])
@pytest.mark.parametrize("capabilities_enabled", [False, True])
def test_doh_pipeline_preserves_network_settings(
    monkeypatch: pytest.MonkeyPatch, trust_env: bool, capabilities_enabled: bool
) -> None:
    settings = Settings()
    settings.validation.rounds = 1
    settings.validation.corpus.mode = "controlled"
    settings.validation.corpus.zone = "test.local"
    settings.validation.doh_trust_env = trust_env
    settings.validation.doh_local_address = "0.0.0.0"
    settings.validation.capabilities.enabled = capabilities_enabled
    candidate = Candidate(
        provider=None,
        source="test",
        transport="doh",
        endpoint_url="https://resolver.test/dns-query",
        host="resolver.test",
        port=443,
        path="/dns-query",
    )
    client_calls: list[dict[str, object]] = []
    tls_calls: list[dict[str, object]] = []
    capability_calls: list[str] = []

    def fake_client(**kwargs: object) -> httpx.AsyncClient:
        client_calls.append(kwargs)
        return httpx.AsyncClient(transport=httpx.MockTransport(lambda request: httpx.Response(200)))

    async def fake_tls(*args: object, **kwargs: object) -> ProbeResult:
        tls_calls.append(kwargs)
        return ProbeResult(ok=True, probe="doh:tls", latency_ms=1.0)

    async def fake_positive(entry, *args: object, **kwargs: object) -> ProbeResult:
        return ProbeResult(ok=True, probe=f"doh:positive:{entry.label}", latency_ms=1.0)

    async def fake_negative(entry, *args: object, **kwargs: object) -> ProbeResult:
        return ProbeResult(ok=True, probe=f"doh:nxdomain:{entry.label}", latency_ms=1.0)

    async def fake_post(*args: object, **kwargs: object) -> tuple[dns.message.Message, float]:
        return dns.message.make_response(dns.message.make_query("test.local.", "A")), 1.0

    async def fake_capability(name, send, config, **kwargs: object) -> ProbeResult:
        assert config is settings.validation.capabilities
        capability_calls.append(name)
        return ProbeResult(ok=True, probe=f"capability:{name}", latency_ms=1.0)

    monkeypatch.setattr("resolver_inventory.validate.build_doh_client", fake_client)
    monkeypatch.setattr("resolver_inventory.validate._probe_tls", fake_tls)
    monkeypatch.setattr("resolver_inventory.validate._probe_positive_doh", fake_positive)
    monkeypatch.setattr("resolver_inventory.validate._probe_nxdomain_doh", fake_negative)
    monkeypatch.setattr("resolver_inventory.validate._doh_post", fake_post)
    monkeypatch.setattr("resolver_inventory.validate.run_capability_check", fake_capability)

    results = validate_candidates([candidate], settings)

    assert client_calls == [{"timeout_s": 2.0, "trust_env": trust_env, "local_address": "0.0.0.0"}]
    assert tls_calls == [{"trust_env": trust_env, "local_address": "0.0.0.0"}]
    assert sorted(capability_calls) == sorted(
        capability_check_names(settings.validation.capabilities)
    )
    assert len(results) == 1
    assert len(results[0].probes) == 6
    assert all(probe.ok for probe in results[0].probes)
