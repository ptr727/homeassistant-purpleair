# AUDIT.md

How an agent audits **this repository** against the fleet ground truth and reports drift. The audit is **read-only**: it produces a report (an issue, a pull request comment, or a scratch file) and never edits the repository. Converging is a separate phase, in section 6.

The verdict vocabulary is fixed in section 5 below: **operational / not operational**, **N/A**, and **defect**, each judged against the applicable/absent rule. Do not invent a parallel scheme.

**The deterministic half is mechanized, and it is hub-hosted rather than carried here.** Run it from a checkout of the hub, `github.com/ptr727/ProjectTemplate`, fetched immediately before it is read, per [`GOVERNANCE.md`][governance] "Hub-Hosted Tooling". Verify the host first, since a tool below its floor answers `--version`, looks healthy, and produces a wrong answer.

```shell
python3 scripts/host_gate.py --repo <path-to-this-checkout>   # from a hub checkout
python3 spec/audit.py homeassistant-purpleair                 # the deterministic findings, read at main
python3 spec/audit.py --issue homeassistant-purpleair         # audits again and renders that run as an issue
```

A finding is a snapshot. Quote the run stamp (`audit run <UTC> | hub <sha>`) in anything derived from it, and re-run before acting on a finding written earlier.

## 1. Scope and Ground-Truth Branch

Read the **`main` branch** as ground truth: `main` is the released, gated state. Read `develop` only to detect divergence, and treat a stale or diverged `develop` as a **drift finding** rather than as the truth.

## 2. Profile

This repository's profile is fixed, so no classification step is needed:

- **`python` + `homeassistant`**, `workflowModel: release`, `consumerModel: push`, `releaseTrigger: dispatch-only`. The release is a single HACS `purpleair.zip` attached to a GitHub Release, and a release is always a deliberate `workflow_dispatch` of the publisher, per [`OPERATIONS.md`][operations] "Release Flow".
- Checks governing absent constructs (a .NET build, a package registry, an image registry) are **N/A**. Record them as N/A and exclude them from the verdict. N/A is never a defect.

## 3. Dimensions

Evaluate each applicable check at two tiers: **letter** (the exact file, section, or config is present) and **intent** (an equivalent outcome holds even where the form differs).

- **python** - ruff, mypy, and pyright present and gating. `mypy --strict` over the integration is required by the platinum quality-scale `strict-typing` rule.
- **homeassistant** - `hassfest` and HACS validation run in CI, the HA test matrix in [`.github/ha-test-versions.json`][ha-test-versions] gates every slot equally, and `hacs.json`'s minimum Home Assistant version matches the matrix `minimum`, per [`OPERATIONS.md`][operations] "HA Test Matrix".
- **branch-model** - `main` and `develop` both exist and are protected, and the live rulesets match the **hub's** ruleset payloads by normalized diff, which is what the section 4 command compares against.
- **repo-setup** - every required secret is configured and no forbidden secret is present. The required set is `CODEGEN_APP_CLIENT_ID`, `CODEGEN_APP_PRIVATE_KEY`, and `CODECOV_TOKEN`, each in **both** the Actions and Dependabot stores, since a Dependabot-triggered run reads the Dependabot store rather than Actions secrets.
- **linter-parity** - one config per linter ([`.markdownlint-cli2.jsonc`][markdownlint], [`cspell.json`][cspell], [`.editorconfig`][editorconfig], and the Python linter configs) drives the editor extension, the CLI, and CI alike, and CI runs each.
- **recurring-violations** (always run), covering comments concise and non-narrative, US spelling, and line endings per [`.editorconfig`][editorconfig], verified with `git ls-files --eol`. Each is a grep-able check.
- **workflows** - run [`WORKFLOW.md`][workflow]'s methodology against [`.github/workflows/`][workflows]: the static audit of each applicable guarantee with `file:line` citations, plus the trace scenarios. The release-train invariants in [`OPERATIONS.md`][operations] are part of this dimension, not separate from it.

## 4. Validate Settings, Rulesets, and Secrets

Settings, labels, and the ruleset payloads are the hub's, applied by its `repo-config/configure.sh` against its own payloads. Run the command from a hub checkout at `main`, passing this repository and its model as arguments:

```shell
# cwd is a hub checkout of github.com/ptr727/ProjectTemplate, at main
repo-config/configure.sh check ptr727/homeassistant-purpleair release
```

`check` reads and never writes, which is what makes it usable here. Its `apply` counterpart writes to the live repository, so it is a converge action rather than a measurement and belongs to section 6.

That command checks the rulesets, the general settings and the registry description, the security features, the labels, and the link to the fleet project the hub declares. The token needs project access as well as the admin the ruleset endpoints require, since a token without it cannot read the project link and the command reports that group as failing rather than as clean. **It does not check secrets**, so the secret check below is part of this section rather than an optional extra.

Confirm secret **names** directly, since values are not readable:

```shell
gh api --paginate repos/ptr727/homeassistant-purpleair/actions/secrets --jq '.secrets[].name'
gh api --paginate repos/ptr727/homeassistant-purpleair/dependabot/secrets --jq '.secrets[].name'
```

Expect `CODEGEN_APP_CLIENT_ID`, `CODEGEN_APP_PRIVATE_KEY`, and `CODECOV_TOKEN` in **both** stores, and not `CODEGEN_APP_ID`, the deprecated App input. `spec/audit.py homeassistant-purpleair`, run from the same hub checkout, asserts the set from the hub's `spec/secrets.json`, so a disagreement between this paragraph and that run is a defect in this paragraph.

`bypass_actors` sits deliberately outside any compared subset: who may bypass a ruleset is a human decision taken in the UI, no payload declares one, and comparing it would report a finding against every ruleset that has any bypass actor at all.

## 5. Verdict Model

Per dimension, record `operational | not-operational | N/A`, each with a letter and an intent verdict:

- A letter miss with intent satisfied is a **drift finding**: an equivalent outcome in a non-standard form, worth fixing but not a break.
- A letter and intent miss together is a **defect**, and the repository is not operational.

The repository is **operational** only if every applicable check passes. A single applicable defect makes it not operational. N/A items are excluded and never counted as failures.

## 6. Converge, and Apply the Fixes

The audit is read-only. Converging is the follow-on phase, and the hub's `RESYNC.md` owns the order the remedies are applied in.

- Apply fixes via a **pull request** per the branch model (feature branch into `develop`, promotion into `main`) as described in [`GOVERNANCE.md`][governance-branching-model], never a direct push to a protected branch.
- Drive the review loop to green, addressing and resolving every thread, per [`GOVERNANCE.md`][governance-pr-review] "PR Review Etiquette".
- **Merge only with explicit maintainer permission.** The agent drives to green and stops.
- One focused pull request per drift class, cross-referencing the finding it closes.
- Settings, labels, and rulesets are the exception to the pull-request rule, since they are live configuration rather than tracked files. Converge them by running `repo-config/configure.sh apply ptr727/homeassistant-purpleair release` from a hub checkout at `main`, then re-run the `check` in section 4 to confirm the drift is gone. This writes to the live repository, which is why it appears here and not in the measurement section.

<!-- Repo -->

[cspell]: ./cspell.json
[editorconfig]: ./.editorconfig
[governance]: ./GOVERNANCE.md
[governance-branching-model]: ./GOVERNANCE.md#branching-model
[governance-pr-review]: ./GOVERNANCE.md#pr-review-etiquette
[ha-test-versions]: ./.github/ha-test-versions.json
[markdownlint]: ./.markdownlint-cli2.jsonc
[operations]: ./OPERATIONS.md
[workflow]: ./WORKFLOW.md
[workflows]: ./.github/workflows/
