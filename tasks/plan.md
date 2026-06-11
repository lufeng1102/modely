# Aggregate Governance Implementation Plan

## Context

This plan accompanies `docs/specs/aggregate-governance.md` for the modely-ai aggregate governance feature set. The feature set turns modely-ai from a downloader into a governance-oriented CLI for diagnosing, choosing, gating, verifying, reporting, benchmarking, and monitoring cross-source AI assets.

The current branch already contains the main implementation and documentation. This file records the dependency graph, validation checkpoints, and optional follow-up slices so future work can proceed vertically and safely.

## Current State

Relevant implementation paths:

- CLI wiring: `src/modely/__init__.py`
- Diagnosis and selection: `src/modely/doctor.py`, `src/modely/choose.py`
- Policy and catalog gates: `src/modely/policy.py`, `src/modely/catalog.py`
- Mirror verification: `src/modely/mirror.py`
- Lock/install fallback: `src/modely/manifest.py`
- Cache duplicate reporting: `src/modely/common/cache.py`
- Reports: `src/modely/report.py`
- Benchmark and drift: `src/modely/benchmark.py`, `src/modely/watch.py`
- Focused tests: `tests/test_doctor.py`, `tests/test_choose.py`, `tests/test_policy.py`, `tests/test_manifest.py`, `tests/test_mirror.py`, `tests/test_report.py`, `tests/test_cache.py`, `tests/test_watch.py`

## Dependency Graph

```text
src/modely/__init__.py
  ├─ doctor command ──> doctor_resource
  │                    ├─ resolve_resource
  │                    ├─ score_resource
  │                    ├─ scan_resource
  │                    └─ rank_sources (optional --probe)
  │
  ├─ choose command ──> choose_resource
  │                    ├─ resolve_resource
  │                    ├─ score_resource
  │                    ├─ scan_resource
  │                    └─ rank_sources (fastest strategy)
  │
  ├─ catalog gate ───> read_catalog_report ──> evaluate_catalog_policy
  │                                           └─ print_catalog_policy_result
  │
  ├─ verify-mirror ──> verify_mirror ──> compare_resources
  │
  ├─ lock/install ──> create_lock/read_manifest/install_lock
  │                   ├─ list_repo_files/filter_files
  │                   ├─ lock_summary
  │                   └─ download_resource
  │
  ├─ cache dedupe ──> cache.find_duplicate_files ──> cache.print_dedupe_report
  │
  ├─ report ────────> create_resource_report
  │                   ├─ doctor_resource for remote/query input
  │                   └─ score_path + scan_path for local paths
  │
  ├─ benchmark ─────> benchmark_sources ──> list_source_profiles + requests.get
  │
  └─ watch drift ───> watch.check_drift
                      ├─ load_config/load_state
                      └─ remote fingerprint helpers
```

Dependency order:

1. Foundation signals: resolve, score, scan, compare, sources, cache, and watch fingerprint helpers.
2. Pure governance helpers: doctor, choose, policy, mirror, manifest fallback, report, benchmark, and dedupe.
3. CLI wiring in `src/modely/__init__.py`.
4. Tests and documentation/smoke verification.

## Phase Checkpoints

### Phase 1 — Baseline Verification

Goal: confirm the branch is clean and the aggregate governance spec matches implementation.

Commands:

```bash
git status --short --branch
python -m pytest \
  tests/test_doctor.py \
  tests/test_choose.py \
  tests/test_policy.py \
  tests/test_manifest.py \
  tests/test_mirror.py \
  tests/test_report.py \
  tests/test_cache.py \
  tests/test_watch.py \
  -m "not integration"
python -m pytest tests/ -m "not integration"
```

CLI help smoke checks:

```bash
PYTHONPATH=src modely-ai doctor --help
PYTHONPATH=src modely-ai choose --help
PYTHONPATH=src modely-ai catalog gate --help
PYTHONPATH=src modely-ai verify-mirror --help
PYTHONPATH=src modely-ai report --help
PYTHONPATH=src modely-ai benchmark --help
PYTHONPATH=src modely-ai cache dedupe --help
PYTHONPATH=src modely-ai watch drift --help
```

Checkpoint: continue only if focused tests, full non-integration tests, and CLI help smoke checks pass.

### Phase 2 — Planning Artifacts

Goal: persist this plan and the vertical task list.

Files:

- `tasks/plan.md`
- `tasks/todo.md`

Verification:

```bash
git diff --check
```

### Phase 3 — Optional Follow-Up Slices

These slices map to open questions in `docs/specs/aggregate-governance.md`. They are optional and should be selected explicitly before implementation.

#### Slice A — Local path support for `doctor` and `choose`

Dependency path:

```text
doctor/choose CLI -> doctor_resource/choose_resource -> score_path/scan_path -> report-compatible local output
```

Acceptance criteria:

- `modely-ai doctor ./local-model --json` returns local `score`, `scan`, `recommended`, `warnings`, and `next_steps` without network.
- `modely-ai choose ./local-model --json` either returns a clear local recommendation or a documented warning/error if local choose remains unsupported.
- Existing remote query behavior remains unchanged.

Verification:

```bash
python -m pytest tests/test_doctor.py tests/test_choose.py tests/test_report.py -m "not integration"
python -m pytest tests/ -m "not integration"
```

#### Slice B — Richer `catalog gate` policy semantics

Dependency path:

```text
catalog scan summaries -> read_catalog_report -> evaluate_catalog_policy -> CLI exit status
```

Acceptance criteria:

- Existing summary-only behavior remains supported.
- If richer scan payloads are available in catalog JSON, `catalog gate` honors richer severity/finding/license policy without requiring network.
- CI exit semantics remain: exit `1` on blocked, exit `0` on allowed.

Verification:

```bash
python -m pytest tests/test_policy.py tests/test_catalog.py tests/test_cli.py -m "not integration"
python -m pytest tests/ -m "not integration"
```

#### Slice C — Preserve non-destructive `cache dedupe`

Dependency path:

```text
cache dedupe CLI -> find_duplicate_files -> print_dedupe_report
```

Acceptance criteria:

- `cache dedupe --dry-run --json` reports duplicate groups and reclaimable bytes.
- No command path deletes, hardlinks, or mutates files.
- README/spec frame mutation as future work only.

Verification:

```bash
python -m pytest tests/test_cache.py -m "not integration"
```

## Risks and Mitigations

- Accidental network use in unit tests: monkeypatch score/scan/resolve/download/probe calls and keep network tests marked `integration`.
- CLI examples drifting from argparse flags: include help smoke checks for each public command in documentation verification.
- Changing default source selection order: avoid changing `prefer` defaults unless explicitly approved.
- Destructive cache changes: keep `cache dedupe` report-only; require a new spec and explicit approval for delete/link behavior.
- Policy gates silently passing bad catalog data: keep explicit `ok`, `blocked`, `allowed`, and exit-code tests for failure paths.

## Final Verification Before Commit

```bash
git diff --check
python -m pytest tests/ -m "not integration"
```
