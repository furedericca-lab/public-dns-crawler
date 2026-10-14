# Upstream Sync 2026-10

## Context

Update `main` from `disposable/public-dns-crawler:main`, preserving the fork's
DoH measurement behavior. The user authorizes integration, commit, and push to
`origin/main`.

## Findings

- Initial local and origin HEAD: `91130b5c16e9a54da5ab8891bc642ba7805819b1`.
- Verified upstream HEAD: `fda6c008bd4a85676446d51574cae0512412ce42`.
- The branches diverged: 28 upstream-only and 3 fork-only commits.
- Existing untracked local configurations, inputs, and outputs are user-owned.

## Outcome

Complete. Upstream integration, local verification, and publication are verified.

## Goals / Non-goals

Preserve fork commits, integrate upstream fixes and transport/source additions,
and verify the merged package. Do not rerun or overwrite historical public
resolver measurements, publish local inputs/configurations, or change services.

## Target files / modules

Upstream changes across `src/resolver_inventory`, `tests`, `configs`, package
metadata, and documentation. Conflict resolution focuses on settings, validation
orchestration, shared DNS helpers, and the README.

## Constraints

Keep DoH `trust_env=false`, explicit IPv4 binding, external probe corpus support,
and prior results. Do not force-push or rewrite existing commits.

## Boundaries

Only upstream integration, necessary compatibility repairs, regression tests,
and this scope record may be committed. Existing untracked files remain excluded.

## Decision Summary

Merge the verified upstream SHA into existing `main` with a merge commit rather
than resetting to upstream. Resolve overlapping code by retaining both upstream
semantics and fork settings.

## Verification surface

1. Back up Git history and hash/archive all pre-existing untracked files.
2. Resolve merge conflicts and test DoH configuration propagation first.
3. Run local unit/integration tests, `make validate`, corpus validation, and build.
4. Verify preserved file hashes, merge ancestry, explicit staged paths, and push.
5. Confirm local HEAD, origin tracking ref, and live remote HEAD match.

## Escalation triggers

Unexpected remote changes, secret-bearing content, or conflicts that require a
new product decision. Ordinary integration conflicts are resolved locally.

## Rollback

Private backup: `/root/.local/state/public-dns-crawler/backups/20261014T134059Z`.
Before committing, `git merge --abort` restores the original tracked tree.
After publication, revert the integration commit rather than rewriting origin.
The backup contains a Git bundle, untracked-file archive, and SHA-256 manifest.

## Open questions

None.

## Execution log / evidence updates

- Live origin and upstream refs verified before integration.
- Backed up Git history and all pre-existing untracked files before the merge.
- Resolved three conflicting files: README, settings, and validation orchestration.
  Retained upstream capability checks and exception-to-probe handling together
  with fork proxy isolation and IPv4 binding.
- Added four pipeline regression cases and a local TLS-fixture IPv4 case with
  deliberately unusable environment proxies. The bound-address case reproduced
  missing TLS-context propagation in both custom HTTP transports. Passing
  `verify`, `trust_env`, and `http2` to those transports fixed the regression.
- Focused verification: 29 tests passed.
- `uv run --locked pytest -q -m 'not network'`: 436 passed, one live-network test
  deselected. Unit tests and local integration fixtures are included.
- `make validate`: formatting, lint, pyright, vulture, and complexity reporting
  passed; pyright reported zero errors and warnings.
- External corpus CLI validation passed: six exact, three consensus, and three
  generated-negative probes, schema version 1.
- `uv build --no-sources`: source distribution and wheel built successfully.
- Local-feed CLI discovery passed: 279 DoH candidates, no DNS/DoT/DoQ candidates.
  Discovery outputs were written under the private backup, not historical outputs.
- All pre-existing untracked file hashes matched the backup manifest; tracked
  historical outputs and local input/configuration paths have no changes.
- Public resolver remeasurement was not run; remote CI results were not inspected.
- Added a local `upstream` remote with `upstream/main` at the verified source SHA.
- Published merge commit `768bc9c1f1953c85377af6eb285bd2b3b3ea2cb2` to
  `origin/main`. Local HEAD, origin tracking ref, and live remote branch SHA
  matched after push. Both the old fork HEAD and upstream SHA are ancestors.
- The only remaining untracked paths are pre-existing user configurations,
  inputs, and outputs; they remain excluded and their hashes are unchanged.
- This closeout updates documentation only. Final publication parity evidence is
  saved as `publication-final.json` in the private backup directory.
