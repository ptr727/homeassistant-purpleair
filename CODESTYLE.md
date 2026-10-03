# Code Style and Formatting Rules

This is the single code-style guide for the fleet. The **General** section applies to every language. Each **language section** (.NET, Python, Shell) is self-contained: a repo follows only the section(s) for the languages it ships and ignores the rest. A repo keeps the whole file rather than trimming it. An unused-language section costs nothing, the same whole-file model as [`.editorconfig`][root], whose inert `[*.cs]` block a non-.NET repo keeps.

Cross-cutting *process* rules (PR titles, branching, US English, Markdown style, comments philosophy, workflow YAML, PR review etiquette, and the verification discipline that defines the pre-push lint gate) live in [GOVERNANCE.md][governance] and are not repeated here. This repo's own extensions to them are in [OPERATIONS.md][operations].

## General

These rules apply to every language in the repo.

### Tooling Names and Casing

Use each tool's official casing in task labels, docs, and prose, per the `comment-and-doc-style` Skill at `.agents/skills/comment-and-doc-style/SKILL.md` in the hub (not a repo-relative link, that path is hub-local and not carried into every fleet repo).

### Clean-Compile Verification

Each language defines a **clean-compile** verification: the combination of build, formatter, linter, and code-analysis tools that must report clean before a commit. It is exposed as one or more **named** VS Code tasks (or, where a language ships no tasks, documented commands), and those definitions are the same across the fleet. The concrete names live in each language section below.

- **Run it after every code change, and it is not the whole gate.** The relevant language's clean-compile must pass before you commit. CI runs those same language checks as a backstop **plus everything else its validation workflow runs**, and all of it reports into the one required status, so a green clean-compile does not predict a green CI. That remainder is at least the doc-lint set (markdownlint, cspell, actionlint, `editorconfig-checker`) and whatever spec, config, and script gates the repo carries, so read the workflow for the full list rather than assuming this sentence enumerates it. What has to pass before a push is the repo's **whole** lint gate, per [GOVERNANCE.md "Verification Discipline"][governance-verification-discipline]. Each linter's known-working invocation is in `GOVERNANCE.md` "Running the Linters Locally (Known-Working Invocations)", a hub-only section read in a hub checkout rather than carried into every fleet repo.
- **The named task definition is the canonical spec** - its exact command sequence, arguments, and strictness. You may run it through the VS Code task **or** by invoking the equivalent native commands directly, and either is fine **only if the sequence, arguments, and strictness match exactly**. No shortcuts and no more-lenient options (for example, never drop `--verify-no-changes` or loosen a `--severity`).
- **A working local commit/pre-commit gate is strongly suggested, not the repo's free choice to skip.** The *mechanism* is bounded by the toolchain the repo already keeps rather than by which languages its checks cover, and two canonical shapes carry it. Husky.Net runs from a .NET tool manifest declaring it, so a repo that keeps no such manifest uses the `pre-commit` framework instead. Any repo may also wire an equivalent hook of its own at `.husky/pre-commit`, enabled with `core.hooksPath` and sourcing nothing. Canonical shapes for both live in `catalog/snippets/` in the hub, not a repo-relative path since it is hub-local and not carried into every fleet repo. What that gate must cover, its per-clone enablement steps, and what its absence means for the audit, is `GOVERNANCE.md` "Running the Linters Locally (Known-Working Invocations)", the same hub-only section, not restated here. Keeping a working gate is not drift.

### Analyzer Diagnostics and Suppressions

- **A new port is not a license to silence diagnostics.** Brownfield / just-ported status never justifies relaxing analyzer or linter severities or muting newly surfaced warnings. Fix them. (The only brownfield allowance is the one-time git-signing / line-ending migration described in [GOVERNANCE.md][governance] and [README.md][readme], which has nothing to do with code analysis.)
- **Suppress only genuine false-positives or deliberate, documented exceptions**, always at the **narrowest scope that fits**, in this order of preference:
  1. An **in-code annotation on the specific symbol**, with a justification, in the language's attribute/comment form, never a blanket pragma spanning a region.
  2. The **owning project's local config** when the exception is project-wide for one project (e.g. a test project's own `.editorconfig` / `pyproject.toml`).
  3. The **root / shared config** only when the suppression is genuinely applicable to **every** project in the repo.
- **Never blanket-relax a batch of rules project-wide** to get a port to build. The per-language mechanics (which attribute, which config key) are in each language section.

### Markdown and Spelling

These apply repo-wide, in every directory: Markdown lints clean via `markdownlint-cli2` against the shared config, spelling is US English via CSpell against the shared `cspell.json`, the CI spelling gate covers `README.md` and `HISTORY.md` only, `HISTORY.md` mirrors the README's opening, and "Markdown" is a proper noun in prose. A repo excluding a subtree of its own that it does not treat as authored prose, a committed data archive, a vendored theme, or a hand-maintained record, puts a `.markdownlint-cli2.jsonc` carrying its own `ignores` beside that content rather than editing the shared root config, whose contents are fleet-fixed. Those `ignores` patterns resolve against the directory holding them rather than against the repo root, so a repo-root-relative entry there matches nothing and reports no error saying so, and excluding through the CI workflow's own negated Markdown glob input instead is a CI-only fix that leaves the same files flagged for anyone running the linter locally. The full rules are in the `comment-and-doc-style` Skill referenced above.

## .NET

*This section applies only to the .NET side. A repo with no .NET projects still carries it (the file is carried whole) and ignores it.*

The style guide for any .NET projects in this repo: the zero-warnings build policy and its three-task clean-compile chain, central `Directory.Build.props`/`Directory.Packages.props` configuration, C# language and naming conventions, XML documentation, analyzer suppression scope, the library-versus-application logging split, async and error-handling patterns, xUnit v3 + AwesomeAssertions testing conventions, the runner declaration, package references and version floor that an MTP-based test project needs under `WORKFLOW.md` D1.6, with the local diagnostic for a run that reports no tests, and AOT-compatible project configuration.

This is packaged as the `dotnet-codestyle` Skill at `.agents/skills/dotnet-codestyle/SKILL.md` in the hub, not a repo-relative link since that path is hub-local and not carried into every fleet repo. The summary above sketches the scope. Read the skill for the full rules, code examples, and mechanics.

## Python

*This section is the style guide for the Python code this repo ships.*

The style guide for any Python project(s) in this repo: the build-versus-lint-only profile split, the uv/ruff/pyright/mypy/pytest toolchain, `src` layout, formatting and linting, comment and docstring conventions, type hints, naming, imports, patterns to avoid, test conventions including the `pytest-cov` dependency and coverage selector a Python directory running pytest owes under `WORKFLOW.md` D1.6, and versioning.

This is packaged as the `python-codestyle` Skill at `.agents/skills/python-codestyle/SKILL.md` in the hub, not a repo-relative link since that path is hub-local and not carried into every fleet repo. The summary above sketches the scope. Read the skill for the full rules and the profile-adaptation guidance.

The rest of this section adapts that skill to this repo.

This repo ships a **Home Assistant custom integration** (`custom_components/purpleair/`), not an installable package or wheel. The dev environment is a `uv`-managed `.venv` (`scripts/setup` runs `uv venv` + `uv pip install` from `requirements*.txt`), but there is no `uv.lock`, no build backend, and no `src/` layout - deal in the actual integration tree and the `scripts/*` dev loop described below.

Use each tool's official casing in prose: `ruff`, `mypy`, `pyright`, `pytest`, `hassfest`, `HACS` (not `Hacs`), `NBGV`.

### Toolchain

| Tool | Role | Config |
|---|---|---|
| [uv](https://docs.astral.sh/uv/) | dependency install into the dev `.venv` (CI uses pip) | `requirements.txt`, `requirements-test.txt` |
| [ruff](https://docs.astral.sh/ruff/) | lint + format + import sort | `.ruff.toml` (repo root) |
| [mypy](https://mypy-lang.org/) | strict type gate | CLI flags in `scripts/lint` (`--strict --follow-imports=silent`) |
| [pyright](https://microsoft.github.io/pyright/) | type checker | `pyrightconfig.json` |
| [pytest](https://docs.pytest.org/) | test runner | `pyproject.toml` `[tool.pytest.ini_options]` |

Two type checkers run, and **both are gates**. `mypy --strict --follow-imports=silent` over `custom_components/purpleair/` is required by the platinum quality-scale `strict-typing` rule. `pyright` runs directly (`pyright`, configured by `pyrightconfig.json` at `typeCheckingMode: basic`) and is also the engine behind VS Code's **Pylance** extension, so the in-editor and CI experience stay in sync. Both run in `scripts/lint` and in CI.

### Local Development Loop

Development targets **Linux only**: native Linux, WSL2, or the devcontainer. Home Assistant Core doesn't run on Windows natively, so there is no Windows-native dev path, and these `scripts/*` are bash. See [OPERATIONS.md](OPERATIONS.md#supported-platforms).

The dev loop is a set of bash scripts under `scripts/`, run from the repo root:

```sh
scripts/setup       # uv venv + uv pip install requirements*.txt (and editable aiopurpleair)
scripts/fix         # ruff format . && ruff check . --fix   (apply auto-fixes)
scripts/lint        # verify-only: ruff format --check, ruff check, mypy --strict, pyright
pytest              # run tests (after scripts/setup, in the uv .venv)
scripts/develop     # launch Home Assistant against ./config with the integration loaded
```

The Python clean-compile (see [Clean-Compile Verification](#clean-compile-verification)) is exactly what `scripts/lint` runs: `ruff format . --check` + `ruff check .` + `mypy --strict --follow-imports=silent custom_components/purpleair/` + `pyright`. Run it (plus `pytest`) before committing. These commands are also wired as VS Code tasks (`Fix:`, `Lint:`, `Test:`, `Develop:`) in [`.vscode/tasks.json`](./.vscode/tasks.json) for convenience. CI runs the same checks as the authoritative backstop. No local commit gate is wired yet (#385), so local enforcement is the manual pre-push run below.

### Layout

Home Assistant integration layout - the integration lives under `custom_components/purpleair/` and is loaded by Home Assistant from there; it is never built into a wheel:

```text
custom_components/purpleair/
    manifest.json          # domain, requirements, version (NBGV-stamped at build)
    __init__.py            # integration setup/teardown
    config_flow.py
    coordinator.py
    sensor.py
    entity.py
    const.py
    diagnostics.py
    py.typed
    quality_scale.yaml
    strings.json / translations/ / icons.json
tests/
    conftest.py
    components/purpleair/
        test_<module>.py
        conftest.py
        fixtures/ / snapshots/
```

### Code Style

#### Formatting and Linting

- **`ruff format` is authoritative.** Don't argue with the formatter; if it reformats your code, that's the final form. Configure (target version, formatter behavior) in `.ruff.toml`, not via inline `# fmt:` directives.
- **Run `scripts/fix` (`ruff format .` + `ruff check . --fix`) before committing.** Most ruff lint rules have safe autofixes; let the tool handle them. The configured rule families are listed under `[lint]` `select` in `.ruff.toml`. Add new rule families project-wide rather than scattering inline `# noqa` markers.
- **`# noqa` is a last resort.** When you must use one, scope it narrowly (`# noqa: E501`, not bare `# noqa`) and add a short comment on the same line explaining why. False-positive patterns that recur across the codebase belong in `[lint]` `ignore` or `[lint.per-file-ignores]` in `.ruff.toml`, with a comment. Porting an existing codebase is not a license to add `ignore` / `per-file-ignores` blocks to mute newly surfaced lint - fix it (see [Analyzer Diagnostics and Suppressions](#analyzer-diagnostics-and-suppressions)).

#### Comments

- **Inline `#` comments**: keep tight and local. One line is preferred, but multi-line is fine when you need to document a non-obvious implementation constraint, a local trade-off, or coupling that future edits could easily break. Keep that rationale next to the affected block so the reviewer/maintainer sees it at edit-time.
- **Don't explain *what* the code does** - well-named identifiers handle that. Don't reference the current task ("added for X", "used by Y"); that belongs in the PR description.

#### Docstrings

- Follow [PEP 257](https://peps.python.org/pep-0257/). Focus docstrings primarily on the **behavior contract** (what callers and tests can rely on), public semantics, and edge-case expectations. Implementation-local rationale belongs in inline `#` comments, not docstrings.
- A short one-liner is fine for trivial functions and tests with self-documenting names.
- For non-trivial behavior - non-obvious test scenarios, contracts a test pins, edge cases callers must know about, design trade-offs that are load-bearing for future maintainers - write a one-line summary, blank line, then a details paragraph. Multi-paragraph docstrings are fine when the contract earns it.
- Design notes belong **in the code** (docstrings or inline comments). They do NOT belong in [`HISTORY.md`](./HISTORY.md) - that file is end-user release notes, not a design log.

#### Type Hints

- **Everything is typed.** `mypy --strict` over `custom_components/purpleair/` is a CI gate (the platinum `strict-typing` rule), and `pyright` runs alongside it at `typeCheckingMode: basic` over `custom_components/purpleair` and `tests` (see `pyrightconfig.json`). Both must be clean.
- **Use modern syntax**: `list[int]` not `List[int]`, `dict[str, X]` not `Dict[str, X]`, `X | None` not `Optional[X]`, `from __future__ import annotations` only when needed for forward references.
- **Pyright framework warts get a narrow, explained ignore.** When pyright flags a Home Assistant typing wart, such as `DataUpdateCoordinator.data` typed as the generic `_DataT` but `None` until the first refresh, or `Entity.*` declared as `cached_property` while `CoordinatorEntity` re-declares them as plain `@property`, prefer a narrow `# pyright: ignore[<rule>]` with a why-comment over disabling the rule. For high-volume false positives in a single test file, a per-file `# pyright: <rule>=false` directive at the top with a rationale comment is acceptable, as in [`tests/components/purpleair/test_config_flow.py`](./tests/components/purpleair/test_config_flow.py). `pyrightconfig.json` escalates `reportUnnecessaryComparison` and `reportIncompatibleVariableOverride` to errors.
- **`Final` annotation form.** Declare module-level constants with `Final`, never a plain assignment. Use `FOO: Final[<type>] = <value>` when the type is broader than the value, such as `API_KEY: Final[str] = "placeholder-key"` or `THRESHOLD: Final[timedelta] = timedelta(...)`, which is the form for production constants and most test fixtures. Use bare `FOO: Final = "<value>"` **only** when the constant is a TypedDict key and pyright's structural match needs the literal type preserved, such as `context={CONF_SOURCE: CONF_SOURCE_USER}` against Home Assistant's `ConfigFlowContext`, since `Final[str]` widens to `str` and breaks that match. Document the bare form with a comment so a later cleanup does not "fix" it. Never write `FOO: Final[Literal["x"]] = "x"`, which ruff PYI064 flags as redundant.
- **Don't add `# type: ignore` to silence type errors without a comment** explaining the constraint. If a recurring false positive needs suppression, configure it project-wide in `pyrightconfig.json` (pyright) or via the `scripts/lint` mypy flags. A new port doesn't change this - fix freshly surfaced type errors rather than muting them (see [Analyzer Diagnostics and Suppressions](#analyzer-diagnostics-and-suppressions)).

#### Naming

- `snake_case` for functions, methods, variables, modules, package directories.
- `PascalCase` for classes, type aliases, type vars, enum members.
- `UPPER_SNAKE_CASE` for module-level constants.
- Single leading underscore for module-private; double leading underscore for name-mangled (rare - usually means rethink the design).

#### Imports

- **Let ruff sort imports.** `[lint]` `select` in `.ruff.toml` includes the `I` rule family (isort-equivalent), with Home Assistant's import conventions (`[lint.isort]`: `force-sort-within-sections`, `known-first-party = ["custom_components", "homeassistant", "tests"]`). Don't hand-sort.
- Standard library first, then third-party, then first-party (the integration and `homeassistant`), separated per the configured isort sections - ruff enforces this automatically.
- Avoid wildcard imports (`from x import *`) outside `__init__.py` re-exports.

#### Patterns to Avoid

- **Don't add backward-compat shims, `# removed` markers, or rename-to-`_` for unused vars** - just delete. Git history is the audit trail.
- **Don't add error handling for impossible cases.** Trust internal code; only validate at boundaries (user input, parsed config, external APIs).
- **Don't repeat a dict-key string literal.** When the same literal is a dict key in more than one place, such as `flow["handler"]` or `result["type"]`, promote it to a named constant. Reuse Home Assistant's canonical constants where they exist, such as `SOURCE_REAUTH` from `homeassistant.config_entries`. Production constants live in [`const.py`](./custom_components/purpleair/const.py) and test-only ones in [`tests/components/purpleair/const.py`](./tests/components/purpleair/const.py).
- **Don't diverge from an established codebase pattern for a local improvement.** Before adopting a reviewer-suggested pattern in one file, sweep the codebase for the same construct. Where a convention already exists at several sites, match it, and adopt the new form only by migrating every site in the same pull request. A "better" idiom in one spot that creates a third style beside two existing ones is worse than the local imperfection.
- **Don't use exceptions for expected control flow.** Exceptions are for *unexpected* states.
- **Don't suppress errors silently** (`except Exception: pass`). Either handle the specific exception and document why it's safe, or let it propagate.

### Tests

- `pytest` with the configuration in `pyproject.toml` `[tool.pytest.ini_options]` (`asyncio_mode = "auto"`, `testpaths = ["tests"]`). Install `requirements-test.txt` first, then invoke `pytest`. Tests build on `pytest-homeassistant-custom-component`.
- Tests live under `tests/components/purpleair/`, one test file per module under test, named `test_<module>.py`.
- Test functions named `test_<scenario>_<expected_behavior>` - descriptive, not numbered.
- Use fixtures (defined in `conftest.py` for shared ones, or per-test for narrowly-scoped) instead of setup/teardown methods.
- **Avoid mocking when fakes work.** Hand-rolled fakes that implement the protocol you depend on are usually clearer and break less than `unittest.mock` magic.
- **Test edge cases that the docstring promises**, not implementation details. If the test breaks when you refactor *without changing behavior*, the test is asserting on an implementation detail.

### Versioning

The integration's shipped version lives in `custom_components/purpleair/manifest.json`. The checked-in value is the all-zero placeholder version; at build time NBGV computes the real version from `version.json` (major.minor floor `1.0` plus git height, adjusted by `versionHeightOffset`) and **stamps `manifest.json` on the runner only** - no commit, no `_version.py`, no `hatch-vcs`. See [WORKFLOW.md](./WORKFLOW.md) for the full version model. Don't hand-edit the placeholder.

### Linter Cleanliness

Before pushing or opening a PR:

- VS Code's **Problems** pane should be quiet for the files you touched. The relevant linters are ruff (via the `charliermarsh.ruff` extension) and pyright (via the `ms-python.python` extension's bundled Pylance).
- No local commit gate is wired yet (#385), so run the full gate set in [`OPERATIONS.md`][operations] "Local Verification" yourself before a push. `scripts/lint` covers only the Python linters within it.
- CI runs the same checks as `scripts/lint` (`ruff format --check` + `ruff check` + `mypy --strict` + `pyright`) plus `pytest`, as separate workflow steps (not by invoking the script) - the authoritative gate.
- Markdown in this directory follows the repo-wide [Markdown and Spelling](#markdown-and-spelling) rules.

## Shell

Bash, and only where a program cannot be Python: a bootstrap that installs the interpreter cannot be written in it, and a host tool that must run before a development toolchain exists cannot depend on Python either. Everything else is Python, with a test under its own scripts tree's `tests/` directory. The mandatory `set -Eeuo pipefail` header, the pipefail-versus-early-reader pitfall, self-recursive command shims, self-locating scripts, the `shellcheck`-plus-`shfmt` clean-compile, and the why-not-what comment rule are packaged as the `shell-codestyle` Skill at `.agents/skills/shell-codestyle/SKILL.md` in the hub, not a repo-relative link since that path is hub-local and not carried into every fleet repo. Read the skill for the full rules. Run the clean-compile check itself per `GOVERNANCE.md` "Running the Linters Locally (Known-Working Invocations)", a hub-only section read in a hub checkout rather than carried into every fleet repo, not by probing `command -v shellcheck`.

<!-- Repo -->

[governance]: ./GOVERNANCE.md
[operations]: ./OPERATIONS.md
[governance-verification-discipline]: ./GOVERNANCE.md#verification-discipline
[readme]: ./README.md
[root]: ./.editorconfig
