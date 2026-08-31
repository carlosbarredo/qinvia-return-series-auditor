# GitHub Actions cost control

Status: **disabled by default**

Date: 2026-08-16

## Execution boundary

GitHub is used primarily as a public distribution and archival surface. Routine verification runs
locally; repository-level GitHub Actions remains disabled unless a maintainer explicitly approves a
one-off remote check.

When remote verification is justified, the complete Python 3.12, 3.13, and 3.14 compatibility
matrix can run once for a pull request targeting protected `main`, or by explicit manual dispatch.
Actions should be disabled again immediately after the approved run. Branch pushes and the
post-merge push do not start duplicate matrix runs.

One separate five-minute lint job checks `src/` and `tests/` with Ruff once per workflow run. Keeping
lint outside the compatibility matrix avoids repeating the same version-independent check three
times.

Each pull-request update supersedes and cancels obsolete in-progress jobs. A ten-minute timeout per
job bounds accidental runner consumption. Python package downloads use the setup cache keyed by
`pyproject.toml`.

This opt-in boundary avoids incidental runner use and keeps repository operating costs predictable.

## Quality boundary

Local validation uses Ruff and the complete `unittest` suite. If a remote run is explicitly enabled,
all three supported Python versions and the lint job remain required. The workflow does not change
financial calculations, execute the real-market notebook, download market data, or publish a
package or release.

## Supply-chain boundary

Every external Action is pinned to the exact reviewed commit behind its accepted major release:

| Action | Accepted release | Commit |
|---|---|---|
| `actions/checkout` | `v4` | `11d5960a326750d5838078e36cf38b85af677262` |
| `actions/setup-python` | `v5` | `a26af69be951a213d495a4c3e4e4022e16d87065` |

Checkout credential persistence is disabled. The workflow token is read-only. The workflow has no
secret, environment, deployment, release, package-publication, notebook-execution, or network-data
step.

## Repository governance

Changes to `main` use a pull request and linear history. When required status checks are enforced,
Actions must be enabled only for the bounded verification window and disabled again after merge.
Force pushes and branch deletion remain blocked.

Repository Actions policy admits only the two reviewed official Actions at the commits above.

## Rollback

Restore a branch-push trigger only if validation is explicitly required before a pull request
exists. Revert Action pins only to another reviewed immutable commit, never to a mutable tag. Keep
the complete supported-Python matrix unless the package compatibility contract changes separately.

