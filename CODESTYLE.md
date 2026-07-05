# Code Style and Formatting Rules

This is the single code-style guide for the repo. The **General** section applies to every language. The **Python** language section is self-contained: it is the style guide for the Python code this repo ships.

Cross-cutting *process* rules (PR titles, branching, US English, markdown style, comments philosophy, workflow YAML, PR review etiquette) live in [AGENTS.md](./AGENTS.md) and are not repeated here.

## General

These rules apply to every language in the repo.

### Tooling Names and Casing

Use each tool's official casing in task labels, docs, and prose - `ruff`, `mypy`, `pyright`, `pytest`, `hassfest`, `HACS` (not `Hacs`), `NBGV`. Don't invent personal variants.

### Clean-Compile Verification

Each language defines a **clean-compile** verification - the combination of build, formatter, linter, and code-analysis tools that must report clean before a commit. It is exposed as one or more **named** VS Code tasks (or, where a language ships no tasks, documented commands), and those definitions are **carried verbatim** across derived repos. The concrete names live in each language section below.

- **Run it after every code change.** The relevant language's clean-compile must pass before you commit; CI runs the same checks as a backstop.
- **The named task definition is the canonical spec** - its exact command sequence, arguments, and strictness. You may run it through the VS Code task **or** by invoking the equivalent native commands directly; either is fine **only if the sequence, arguments, and strictness match exactly**. No shortcuts and no more-lenient options (for example, never drop `ruff format --check`'s verify mode or loosen a lint/type-check severity).
- **A local commit/pre-commit gate is the repo's choice.** No single hook runner fits every project, so none is mandated - but that is **not** a recommendation against commit gates. CI is the authoritative backstop regardless; a local gate (for example, `pre-commit` running `ruff`, `mypy`, and `pyright`) is an additive convenience a repo may wire and keep - this repo wires none today. Keeping a working gate is not drift.

### Analyzer Diagnostics and Suppressions

- **A new port is not a license to silence diagnostics.** Brownfield / just-ported status never justifies relaxing analyzer or linter severities or muting newly surfaced warnings - fix them. (The only brownfield allowance in this template is the one-time git-signing / line-ending migration described in [AGENTS.md](./AGENTS.md) and [README.md](./README.md), which has nothing to do with code analysis.)
- **Suppress only genuine false-positives or deliberate, documented exceptions**, always at the **narrowest scope that fits**, in this order of preference:
  1. An **in-code annotation on the specific symbol**, with a justification - the language's attribute/comment form, never a blanket pragma spanning a region.
  2. The **owning project's local config** when the exception is project-wide for one project (e.g. a test project's own `.editorconfig` / `pyproject.toml`).
  3. The **root / shared config** only when the suppression is genuinely applicable to **every** project in the repo.
- **Never blanket-relax a batch of rules project-wide** to get a port to build. The per-language mechanics (which attribute, which config key) are in each language section.

### Markdown and Spelling

These apply repo-wide, in every directory:

1. **Markdown linting**: All `.md` files must be lint-clean (error and warning free) via the VS Code `markdownlint` extension. [`.markdownlint-cli2.jsonc`](./.markdownlint-cli2.jsonc) at the repo root is the single source of truth - the davidanson `markdownlint` extension and a command-line `markdownlint-cli2` run both read it, so the IDE and CLI stay in lock-step. Rules it deliberately disables (e.g. `MD013` line-length, `MD033` inline HTML) are **intentional** - do not "fix" them. Fix violations at the source rather than disabling rules.
2. **Spelling**: All spelling must be clean via the CSpell VS Code integration; words must be correctly spelled in **US English** (the repo-wide convention - see [AGENTS.md](./AGENTS.md)). Project-specific terms go in the workspace CSpell config.

## Python

*This section is the style guide for the Python code this repo ships.*

This repo ships a **Home Assistant custom integration** (`custom_components/purpleair/`), not an installable package or wheel. There is no `uv`, no `uv.lock`, no build backend, and no `src/` layout - deal in the actual integration tree and the `scripts/*` dev loop described below.

### Toolchain

| Tool | Role | Config |
|---|---|---|
| [pip](https://pip.pypa.io/) | dependency install | `requirements.txt`, `requirements-test.txt` |
| [ruff](https://docs.astral.sh/ruff/) | lint + format + import sort | `.ruff.toml` (repo root) |
| [mypy](https://mypy-lang.org/) | strict type gate | CLI flags in `scripts/lint` (`--strict --follow-imports=silent`) |
| [pyright](https://microsoft.github.io/pyright/) | type checker | `pyrightconfig.json` |
| [pytest](https://docs.pytest.org/) | test runner | `pyproject.toml` `[tool.pytest.ini_options]` |

Two type checkers run, and **both are gates**. `mypy --strict --follow-imports=silent` over `custom_components/purpleair/` is required by the platinum quality-scale `strict-typing` rule. `pyright` runs directly (`pyright`, configured by `pyrightconfig.json` at `typeCheckingMode: basic`) and is also the engine behind VS Code's **Pylance** extension, so the in-editor and CI experience stay in sync. Both run in `scripts/lint` and in CI.

### Local Development Loop

Development targets **Linux only** - native Linux, WSL2, or the devcontainer. Home Assistant Core doesn't run on Windows natively, so there is no Windows-native dev path (these `scripts/*` are bash); see [AGENTS.md](AGENTS.md#supported-development-platforms).

The dev loop is a set of bash scripts under `scripts/`, run from the repo root:

```sh
scripts/setup       # pip install requirements.txt + requirements-test.txt (and editable aiopurpleair)
scripts/fix         # ruff format . && ruff check . --fix   (apply auto-fixes)
scripts/lint        # verify-only: ruff format --check, ruff check, mypy --strict, pyright
pytest              # run tests (install requirements-test.txt first)
scripts/develop     # launch Home Assistant against ./config with the integration loaded
```

The Python clean-compile (see [Clean-Compile Verification](#clean-compile-verification)) is exactly what `scripts/lint` runs: `ruff format . --check` + `ruff check .` + `mypy --strict --follow-imports=silent custom_components/purpleair/` + `pyright`. Run it (plus `pytest`) before committing. These commands are also wired as VS Code tasks (`Fix:`, `Lint:`, `Test:`, `Develop:`) in [`.vscode/tasks.json`](./.vscode/tasks.json) for convenience. CI runs the same checks as the authoritative backstop. Git hooks are opt-in; wire `pre-commit` for `ruff`, `mypy`, and `pyright` yourself if you want local enforcement.

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

The integration's shipped version lives in `custom_components/purpleair/manifest.json`. The checked-in value is the placeholder `"version": "0.0.0"`; at build time NBGV computes the real version from `version.json` (major.minor floor `1.0` plus git height, adjusted by `versionHeightOffset`) and **stamps `manifest.json` on the runner only** - no commit, no `_version.py`, no `hatch-vcs`. See [WORKFLOW.md](./WORKFLOW.md) for the full version model. Don't hand-edit the placeholder.

### Linter Cleanliness

Before pushing or opening a PR:

- VS Code's **Problems** pane should be quiet for the files you touched. The relevant linters are ruff (via the `charliermarsh.ruff` extension) and pyright (via the `ms-python.python` extension's bundled Pylance).
- CI runs the same checks as `scripts/lint` (`ruff format --check` + `ruff check` + `mypy --strict` + `pyright`) plus `pytest`, as separate workflow steps (not by invoking the script) - the authoritative gate.
- Markdown in this directory follows the repo-wide [Markdown and Spelling](#markdown-and-spelling) rules.
