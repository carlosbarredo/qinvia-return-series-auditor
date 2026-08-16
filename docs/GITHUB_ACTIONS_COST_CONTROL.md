# GitHub Actions cost control

Status: **GAO-1 governance applied**

Date: 2026-08-16

## Execution boundary

The complete Python 3.12, 3.13, and 3.14 compatibility matrix runs once for pull requests targeting
protected `main`. An explicit manual dispatch is retained for recovery and governance verification.
Branch pushes and the post-merge push do not start duplicate matrix runs.

Each pull-request update supersedes and cancels obsolete in-progress jobs. A ten-minute timeout per
job bounds accidental runner consumption. Python package downloads use the setup cache keyed by
`pyproject.toml`.

The repository is public, so standard GitHub-hosted runner minutes do not currently create a direct
Actions charge. These controls still reduce unnecessary execution and preserve a zero-cost posture
if repository visibility or billing conditions change.

## Quality boundary

All three supported Python versions remain required. GAO-1 does not narrow compatibility coverage,
change financial calculations, execute the real-market notebook, download market data, or publish a
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

Changes to `main` require a pull request, all three Python matrix checks, current-branch validation,
resolved conversations, and linear history. Administrators are subject to the same controls;
force pushes and branch deletion are blocked.

Repository Actions policy admits only the two reviewed official Actions at the commits above.

## Rollback

Restore a branch-push trigger only if validation is explicitly required before a pull request
exists. Revert Action pins only to another reviewed immutable commit, never to a mutable tag. Keep
the complete supported-Python matrix unless the package compatibility contract changes separately.
