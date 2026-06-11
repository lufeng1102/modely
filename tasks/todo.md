# Aggregate Governance TODO

- [x] Task: Verify aggregate governance baseline
  - Acceptance: Focused governance tests and full non-integration test suite pass from a clean branch.
  - Verify: `python -m pytest tests/ -m "not integration"`
  - Files: none expected

- [x] Task: Add planning artifacts
  - Acceptance: `tasks/plan.md` captures dependency graph, phases, checkpoints, and risks; `tasks/todo.md` captures vertical tasks with acceptance and verification.
  - Verify: `git diff --check`
  - Files: `tasks/plan.md`, `tasks/todo.md`

- [x] Task: Confirm CLI/docs alignment
  - Acceptance: README and `docs/specs/aggregate-governance.md` command examples match current parser flags for governance commands.
  - Verify: `PYTHONPATH=src modely-ai <command> --help` for doctor, choose, catalog gate, verify-mirror, report, benchmark, cache dedupe, watch drift.
  - Files: `README.md`, `docs/specs/aggregate-governance.md` if mismatches are found

- [ ] Task: Decide local path behavior for doctor/choose
  - Acceptance: The spec open question is resolved explicitly: either implement local paths or document that local diagnosis stays under report/score/scan.
  - Verify: Review updated spec section and, if code changes are made, run `python -m pytest tests/test_doctor.py tests/test_choose.py tests/test_report.py -m "not integration"`.
  - Files: `docs/specs/aggregate-governance.md`; optionally `src/modely/doctor.py`, `src/modely/choose.py`, `tests/test_doctor.py`, `tests/test_choose.py`

- [ ] Task: Decide catalog gate richness
  - Acceptance: The spec open question is resolved explicitly: summary-only gate semantics remain, or richer offline scan payload evaluation is implemented.
  - Verify: `python -m pytest tests/test_policy.py tests/test_catalog.py -m "not integration"`
  - Files: `docs/specs/aggregate-governance.md`; optionally `src/modely/policy.py`, `src/modely/catalog.py`, `tests/test_policy.py`, `tests/test_catalog.py`

- [ ] Task: Preserve non-destructive cache dedupe
  - Acceptance: Dedupe remains report-only; any destructive hardlink/delete behavior is deferred to a separate approved spec.
  - Verify: `python -m pytest tests/test_cache.py -m "not integration"`
  - Files: `docs/specs/aggregate-governance.md`, `README.md` if wording needs clarification
