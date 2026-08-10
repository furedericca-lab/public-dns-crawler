# Repository Testing Notes

This file records the repeatable resolver testing workflow for this repository.
It supplements the global operator contract; it does not replace the project
README or the code-level validation rules.

## DoH Runtime Configuration

Use `configs/local-doh.toml` for the local DoH-only workflow. Its important
settings are:

- `validation.doh_trust_env = false`: DoH requests must not inherit a broken or
  unrelated `HTTP(S)_PROXY`.
- `validation.doh_local_address = "0.0.0.0"`: prefer IPv4 on this host.
- `validation.doh_parallelism = 100`: keep unreachable public endpoints from
  blocking the whole candidate set.
- `validation.baseline.resolvers = ["223.5.5.5:53"]`: this is the requested
  DNS baseline, but it is not an independent trust anchor.
- `validation.corpus.path = "configs/doh-probe-corpus.json"`: use the external
  corpus and do not silently fall back to the built-in corpus.

DoH validation uses `httpx` with `trust_env=false` and the explicit IPv4 local
address in both the TLS check and DNS-over-HTTPS POST path. Do not re-enable
environment proxy inheritance for resolver measurements unless the proxy is
the thing being tested.

## Standard DoH Corpus

`configs/doh-probe-corpus.json` currently contains 12 probes, repeated for
three rounds:

- six `positive_exact` A probes for `a` through `f.root-servers.net.`;
- three `positive_consensus` A probes for `a` through `c.root-servers.net.`;
- three generated NXDOMAIN probes under `root-servers.net.`.

Each DoH candidate therefore has 37 results per run: one TLS result plus
`3 * 12` DNS probes. `positive_exact` compares a sorted A RRset against pinned
answers. `positive_consensus` compares the candidate against every configured
baseline resolver and currently requires all baseline answer sets to match;
this is not majority voting. Generated NXDOMAIN probes require the response
rcode to be `NXDOMAIN`; `NOERROR` is reported as `nxdomain_spoofing`.

## Fixed RRset Tests

CDN names should not be tested with `positive_consensus` unless independent
baselines are known to return the same RRset. First query several unrelated
baselines and record the complete answer structure. Only pin a
`positive_exact` RRset after it is stable across multiple rounds and paths.

Example fixed probe for the Pixiv check:

```json
{
  "id": "positive-pixiv-a",
  "kind": "positive_exact",
  "qname": "pixiv.net.",
  "qtype": "A",
  "expected_mode": "exact_rrset",
  "expected_answers": [
    "210.140.139.152",
    "210.140.139.155",
    "210.140.139.158",
    "210.140.139.161"
  ]
}
```

The recorded Pixiv corpus and results are in
`outputs/doh-small-pixiv/pixiv-probe-corpus.json`,
`outputs/doh-small-pixiv/summary.json`, and
`outputs/doh-small-pixiv/validated.json`.

## Repeatable Commands

For the full generated corpus, validate its schema and minimum probe counts:

```bash
uv run resolver-inventory validate-probe-corpus \
  --config configs/local-doh.toml \
  --input configs/doh-probe-corpus.json \
  --schema-version 1
```

The one-probe Pixiv corpus is intentionally a focused runtime probe and does
not meet the default corpus-validator minimums. Validate it by running the
candidate command below and inspecting the per-probe results instead of
raising the global thresholds just for this focused check.

Run the current accepted-plus-candidate small DoH set against that corpus:

```bash
uv run resolver-inventory validate \
  --config configs/local-doh.toml \
  --input outputs/doh-small/doh-small-input.json \
  --probe-corpus outputs/doh-small-pixiv/pixiv-probe-corpus.json \
  --output outputs/doh-small/pollution-pixiv-usable/validated.json \
  --validation-parallelism 100 \
  --progress-every 5
```

The current canonical small input is `outputs/doh-small/doh-small-input.json`.
It is regenerated from the latest 370-endpoint run and includes both
`accepted` and `candidate` records. The previous 15-endpoint snapshot is kept
under `outputs/doh-small/seed-15/`.

To derive it from a fresh full validation without mixing rejected records:

```bash
jq '[.[] | select(.status == "accepted" or .status == "candidate")]
    | sort_by([(.score * -1),
               (if .status == "accepted" then 0 else 1 end),
               .candidate.endpoint_url])
    | map(.candidate)' \
  outputs/doh-370-general/validated.json \
  > outputs/doh-small/doh-small-input.json
```

The clean ranked output is in `outputs/doh-small/clean-ranked/`. Its input is
limited to endpoints that passed all three Pixiv fixed-RRset probes and the
DoH TLS probe. The clean ranking must not be confused with the general small
input: answer-clean candidates with timeout or TLS problems remain in the
diagnostic combined results but are not promoted to the clean usable list.

Run the complete 370-endpoint DoH input with the standard corpus:

```bash
uv run resolver-inventory validate \
  --config configs/local-doh.toml \
  --input outputs/doh-test/doh-test-complete-input.json \
  --probe-corpus configs/doh-probe-corpus.json \
  --output outputs/doh-370-general/validated.json \
  --validation-parallelism 100
```

Before trusting a baseline for a CDN test, compare several resolvers. A
disagreement is evidence to investigate, not a reason to choose the first
answer:

```bash
for resolver in 223.5.5.5 1.1.1.1 8.8.8.8 9.9.9.9; do
  printf '%s: ' "$resolver"
  dig +time=3 +tries=1 +short @"$resolver" pixiv.net A
done
```

## Interpreting Results

- `answer_mismatch`: the candidate returned an RRset different from the
  pinned or baseline answer.
- `nxdomain_spoofing`: a generated nonexistent name did not return NXDOMAIN.
- `unexpected_nxdomain`: an existing positive name returned NXDOMAIN.
- `tls_name_mismatch`: the DoH certificate did not match the expected server
  name.
- `candidate` can mean correctness passed but availability or latency was too
  weak; inspect `reasons` and individual `probes` before treating it as
  polluted.
- A single baseline can itself be polluted. The current code fails closed on
  disagreement between configured baselines, but it does not implement a
  quorum or DNSSEC validation. Fixed RRsets and independent repeated checks
  are required for CDN pollution investigations.

Preserve previous outputs under a separately named directory. Do not overwrite
an older run while comparing counts, answer sets, latency, or reason codes.

## Two-Stage Small-Set Workflow

For a fresh full DoH run, keep both `accepted` and `candidate` records as the
usable small-set input. Exclude `rejected` records. The second-stage corpus
must be independent of the first-stage root probes; for a fixed CDN RRset use
an external `positive_exact` corpus such as the Pixiv corpus above.

Treat the second-stage outcomes separately:

- **Clean RRset**: every repeated fixed-RRset probe passed and no
  `answer_mismatch` was observed. Keep the endpoint's `accepted` or `candidate`
  status and rank it accordingly; a candidate can be answer-clean but too slow
  or have a TLS/availability issue.
- **Polluted or wrong RRset**: a successful response contains an A set other
  than the pinned set. This is an answer mismatch, not merely a low score.
- **Inconclusive**: timeouts, TLS failures, or no usable probes. Do not call
  these clean or polluted without a successful answer comparison.

The recommended ranking order is general-run score descending, then clean
status (`accepted` before `candidate`), then general-run p50 latency ascending,
then endpoint URL ascending. Keep the pollution-stage p50/p95 and probe
counts in the ranked export so a high rank cannot hide slow or sparse data.

## Common Pitfalls

- A `candidate` result is not proof of DNS pollution. Inspect the individual
  probe errors and distinguish `answer_mismatch` from timeout, TLS, and latency
  reasons.
- A baseline disagreement is not a CDN failure by itself. CDN answers can vary
  by resolver location; use a pinned RRset only after checking it across
  independent paths and repeated rounds.
- The current baseline helper requires all configured baseline answer sets to
  be identical. It does not implement quorum voting, DNSSEC validation, or an
  authoritative-server fallback.
- `normalize_answer_set` compares only records of the requested type in the
  DNS answer section. If CNAME chains, TTLs, authority data, or EDNS flags are
  part of the trust decision, capture and compare them separately.
- `validate` with `--probe-corpus` changes the effective corpus to external;
  always inspect the output log and the corpus file path before interpreting
  counts.
- The standalone corpus validator applies global minimum counts (currently six
  exact, three consensus, and three generated-negative probes). A focused
  one-probe corpus can be valid for runtime validation while intentionally
  failing those aggregate thresholds.
- DoH runs can be dominated by unreachable endpoints. Keep explicit
  `trust_env=false`, IPv4 local binding, bounded timeouts, and high DoH
  parallelism; otherwise a proxy or IPv6 failure can look like resolver
  pollution.
- `validated.json` is the raw per-candidate result. Build `input.json`, CSV,
  manifests, and ranked exports from it with deterministic sorting so reruns
  remain comparable.
