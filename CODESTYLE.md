# Code Style and Formatting Rules

This is the single code-style guide for the fleet. The **General** section applies to every language. Each **language section** (.NET, Python, Shell) is self-contained: a repo follows only the section(s) for the languages it ships and ignores the rest. A repo keeps the whole file rather than trimming it. An unused-language section costs nothing, the same whole-file model as [`.editorconfig`][root], whose inert `[*.cs]` block a non-.NET repo keeps.

Cross-cutting *process* rules live in [GOVERNANCE.md][governance] and are not repeated here. They cover PR titles, branching, US English, Markdown style, comments philosophy, workflow YAML, and PR review etiquette. They also cover the verification discipline that defines the pre-push lint gate. This repo's own extensions to them are in [OPERATIONS.md][operations].

## General

These rules apply to every language in the repo.

### Tooling Names and Casing

Use each tool's official casing in task labels, docs, and prose, per the `comment-and-doc-style` Skill at `.agents/skills/comment-and-doc-style/SKILL.md` in the hub. That is not a repo-relative link, since the path is hub-local and not carried into every fleet repo.

### Clean-Compile Verification

Each language defines a **clean-compile** verification: the combination of build, formatter, linter, and code-analysis tools that must report clean before a commit. It is exposed as one or more **named** VS Code tasks (or, where a language ships no tasks, documented commands). Those definitions are the same across the fleet. The concrete names live in each language section below.

- **Run it after every code change, and it is not the whole gate.** The relevant language's clean-compile must pass before you commit. CI runs those same language checks as a backstop **plus everything else its validation workflow runs**. All of it reports into the one required status. A green clean-compile therefore does not predict a green CI. That remainder is at least the doc-lint set (markdownlint, cspell, actionlint, `editorconfig-checker`) and whatever spec, config, and script gates the repo carries. So read the workflow for the full list rather than assuming the previous sentence enumerates it. What has to pass before a push is the repo's **whole** lint gate, per [GOVERNANCE.md "Verification Discipline"][governance-verification-discipline]. Each linter's known-working invocation is in `GOVERNANCE.md` "Running the Linters Locally (Known-Working Invocations)", a hub-only section read in a hub checkout rather than carried into every fleet repo.
- **The named task definition is the canonical spec** - its exact command sequence, arguments, and strictness. You may run it through the VS Code task **or** by invoking the equivalent native commands directly. Either is fine **only if the sequence, arguments, and strictness match exactly**. No shortcuts and no more-lenient options (for example, never drop `--verify-no-changes` or loosen a `--severity`).
- **A working local commit/pre-commit gate is strongly suggested, not the repo's free choice to skip.** The *mechanism* is bounded by the toolchain the repo already keeps rather than by which languages its checks cover, and canonical shapes carry it. Husky.Net runs from a .NET tool manifest declaring it, so a repo that keeps no such manifest uses the `pre-commit` framework instead. Any repo may also wire an equivalent hook of its own at `.husky/pre-commit`, enabled with `core.hooksPath` and sourcing nothing. Canonical shapes for Husky.Net and the `pre-commit` framework live in `catalog/snippets/` in the hub. That is not a repo-relative path, since it is hub-local and not carried into every fleet repo. What that gate must cover, its per-clone enablement steps, and what its absence means for the audit are not restated here. They are in `GOVERNANCE.md` "Running the Linters Locally (Known-Working Invocations)", the same hub-only section. Keeping a working gate is not drift.

### Analyzer Diagnostics and Suppressions

- **A new port is not a license to silence diagnostics.** Brownfield / just-ported status never justifies relaxing analyzer or linter severities or muting newly surfaced warnings. Fix them. (The only brownfield allowance is the one-time git-signing / line-ending migration described in [GOVERNANCE.md][governance] and [README.md][readme], which has nothing to do with code analysis.)
- **Suppress only genuine false-positives or deliberate, documented exceptions**, always at the **narrowest scope that fits**, in this order of preference:
  1. An **in-code annotation on the specific symbol**, with a justification, in the language's attribute/comment form, never a blanket pragma spanning a region.
  2. The **owning project's local config** when the exception is project-wide for one project (e.g. a test project's own `.editorconfig` / `pyproject.toml`).
  3. The **root / shared config** only when the suppression is genuinely applicable to **every** project in the repo.
- **Never blanket-relax a batch of rules project-wide** to get a port to build. The per-language mechanics (which attribute, which config key) are in each language section.

### Operations and Failure Messages

- **Let the real operation be the check, not a prediction of it.** Attempt the read, the write, or the call itself, and turn its failure into a clean refusal. Do not probe first with an existence, type, or permission test. Where the operation could block or succeed on the wrong kind of target, judge what it opened instead. A probe is a second model of the operation. It misjudges each case its author did not foresee, such as a dangling link, a link loop, or a platform's own permission model. The operation cannot disagree with itself.
- **Classify a subprocess failure by which command failed and the status code it reports, never by the prose of its message.** That prose varies by tool version and locale, and a status code's value does not, even one printed inside the message. A printed code is read by the notation that marks it, and a match finding none counts as an unexpected failure. Where one command's status code cannot separate the failures its caller handles differently, give each expected failure its own real operation. Where no such operation exists, treat the failure as unexpected. A test asserting a script's output, such as the refusal "Command-Line Arguments" requires, verifies that output rather than classifying a failure.
- **A failure message states the error, the path or other target, and the remedy, and claims nothing about the state the failure left.** The error the operation raised is the one fact the code holds at that point. A description of what the failure left behind is a prediction. It reads false once an unforeseen state reaches the message, such as a file written in full that then fails to close. A remedy such as "fix what it names, then re-run" needs no such claim.

### Parsing Structured Formats

- **A program reading a structured format uses a maintained parser rather than a hand-written one, where a field-tested parser exists for the runtime in use.** That covers YAML, Markdown, TOML, JSON, a programming language's comments or strings, and a shell command line. The standard library's own parsers count, such as Python's `json`, `tomllib`, `ast`, `tokenize`, and `html.parser`. A hand-written reader converges on the format's full grammar one review finding at a time, and every script that grows one pays that cost again.

### Command-Line Arguments

A command-line script is one a person or an agent runs by name. A hook its host runs, taking its input from that host rather than from a command line, is not one.

- **Every command-line script answers `--help` and `-h`** with the same text on stdout, then exits 0, changing nothing. That text opens on a usage line naming the script. An agent learns a script's interface by asking it, so a script that reads `--help` as an input acts in a way nobody predicted. A PowerShell script declaring its own parameters answers `-Help` and `-h` instead, from a `-Help` switch carrying an `h` alias. That form follows PowerShell's own parameter convention, so such a script owes no answer to a literal `--help`. A wrapper that forwards its arguments to another script answers whatever that script answers.
- **An argument the script does not recognize is refused**, with a non-zero exit before any read or write. The refusal names it as an unknown or unrecognized option, argument, flag, or parameter, and PowerShell's own refusal of a parameter it cannot bind counts. So a PowerShell script declaring its own parameters refuses a literal `--help` like any other unrecognized argument. Where no parameter takes the remaining arguments, the binder's refusal does that. A script with such a parameter refuses a dash-prefixed leftover itself. An unrecognized first argument is never taken as a default mode or as a target.

### Script and Utility File Names

| Type | Rule | Basis |
| --- | --- | --- |
| Python `.py` | lowercase snake_case | [PEP 8][pep8-names-link] module naming. A hyphenated module also cannot be named in an `import` statement |
| Shell `.sh` and PowerShell `.ps1` | lowercase-hyphenated | The Linux command convention. A cross-platform pair keeps one name, `sync-tools.sh` beside `sync-tools.ps1` |
| Windows batch `.cmd` and `.bat` | lowercase-hyphenated | The same convention as shell and PowerShell. A shim that puts a command on `PATH` takes the name of the command it provides, `sync-tools.cmd` launching `sync-tools.ps1` |
| PowerShell functions inside a `.ps1` | Verb-Noun with an approved verb (`Get-Verb`) | PSScriptAnalyzer `PSUseApprovedVerbs`. This is a command rule, not a file rule |
| Env and secret files, tracked or not | lowercase fields joined by `_`, with no dot but the extension | `mail_relay.env`, `db_root_password`, `app_web-01_prod.env` |
| Env variable names and CI secret names | UPPER_SNAKE_CASE | The POSIX and GitHub convention |

- **Installed commands.** An executable or launcher on `PATH` or in a system slot (systemd, cron, run-parts, motd) is named as a command, whatever its language. That name is lowercase-hyphenated. It carries no extension unless the platform needs one to run it, such as `.cmd` or `.ps1` on Windows.
- **Wrapper exemption.** A thin launcher whose only job is to run a Python tool keeps that tool's stem, so `fetch_report.py`, `fetch_report.sh`, and `fetch_report.ps1` stay grouped together. It covers only a launcher run by its path. A launcher installed onto `PATH` or into a system slot is an installed command instead, such as `fetch-report` rather than `fetch_report`.
- **Env and secret file names reach every file a repository names.** That covers a tracked file or template and a secret file mounted into a container. It also covers a host-side file the repository's docs or scripts name, such as an `ENV_FILE` path or a compose `env_file`.
- **`_` joins the fields of an env or secret file name, and each field keeps its own valid form.** A host name field stays verbatim, hyphens included, so `app_web-01_prod.env` is right and `app_web_01_prod.env` and `app.web-01.prod.env` are not. That field is a short name, the host's first DNS label (`web-01`) or a logical role name (`vps-staging`), and never a fully qualified one. Either way it takes the DNS label form, so its own words join with `-`. A repository name field takes the repository's name in lower case, hyphens kept, as in `github_example-repo_codecov_token`. GitHub allows `_` and `.` in a repository name too. A repository whose name carries either cannot form this field, so it may name no env or secret file that needs one. In every other field a hyphen never joins words, since that is the job of `_`. A host name label can carry `-` and never `_`, so every `_` is a separator and the name splits back into its fields. The name is lowercase, carries no dot but its extension, and starts and ends with a letter or digit. A tracked template's `.example` suffix is not counted as a dot.
- **A variable name converts separately.** An env variable or CI secret name allows only `A-Z`, `0-9`, and `_`. Where a field becomes one, the hyphen becomes `_` there, as in `APP_WEB_01_PROD_TOKEN`, and never in the file name.
- **Some consumers set limits of their own.** A name used as a Docker secret stays within the 64 characters Docker allows. A name that maps to an env variable or CI secret does not start with a digit, which POSIX and GitHub both forbid.
- **Externally fixed names are exempt.** That covers Git hook names, `__init__.py`, `conftest.py`, and Pester's `.Tests.ps1` suffix, whose stem mirrors the script under test. It covers a PowerShell data file (`.psd1`) whose name a tool fixes, such as a module manifest named for its module. `PSScriptAnalyzerSettings.psd1` is another, since PSScriptAnalyzer finds it by that name. So is an env file a tool reads by a fixed name, such as `.env`, `.env.local`, or `.env.production`. An env or secret file in a `.secrets/` directory is never one, since it is read by a path the repository configures. The exemption also covers any name a platform defines.
- **Directories are out of scope.** That means directory names. How a repository splits its Python across directories is a profile rule, stated in the "Python" section below.

Departures, stated on purpose so a reader does not "fix" them back:

- The [Google Shell Style Guide][google-shell-link] asks for underscores in shell file names. The fleet uses hyphens instead, matching installed Linux commands.
- Microsoft's [approved verbs][ps-approved-verbs-link] govern command names. A `.ps1` run by path is a file rather than an exported command, so the file takes the shell convention and its functions take Verb-Noun.

### Markdown and Spelling

These rules apply repo-wide, in every directory. Markdown lints clean via `markdownlint-cli2` against the shared config. Spelling is US English via CSpell against the shared `cspell.json`, and the CI spelling gate covers `README.md` and `HISTORY.md` only. `HISTORY.md` mirrors the README's opening, and "Markdown" is a proper noun in prose. A repo excluding a subtree of its own that it does not treat as authored prose puts a `.markdownlint-cli2.jsonc` beside that content. That file carries its own `ignores`, instead of the repo editing the shared root config, whose contents are fleet-fixed. A committed data archive, a vendored theme, and a hand-maintained record each count as such a subtree. Those `ignores` patterns resolve against the directory holding them rather than against the repo root. So a repo-root-relative entry there matches nothing and reports no error saying so. Excluding through the CI workflow's own negated Markdown glob input instead is a CI-only fix. It leaves the same files flagged for anyone running the linter locally. The full rules are in the `comment-and-doc-style` Skill referenced above.

## .NET

*This section applies only to the .NET side. A repo with no .NET projects still carries it (the file is carried whole) and ignores it.*

The style guide for any .NET projects in this repo covers the zero-warnings build policy and its clean-compile task chain. It covers central `Directory.Build.props`/`Directory.Packages.props` configuration, C# language and naming conventions, XML documentation, and analyzer suppression scope. It covers the library-versus-application logging split, async and error-handling patterns, and xUnit v3 + AwesomeAssertions testing conventions. It covers the runner declaration, package references and version floor that an MTP-based test project needs. With them it covers the local diagnostic for a run that reports no tests. It also covers AOT-compatible project configuration.

This is packaged as the `dotnet-codestyle` Skill at `.agents/skills/dotnet-codestyle/SKILL.md` in the hub. That is not a repo-relative link, since the path is hub-local and not carried into every fleet repo. The summary above sketches the scope. Read the skill for the full rules, code examples, and mechanics.

## Python

*This section is the style guide for the Python code this repo ships.*

The style guide for any Python project(s) in this repo covers the build-versus-lint-only profile split, the uv/ruff/pyright/mypy/pytest toolchain, and `src` layout. It covers formatting and linting, comment and docstring conventions, type hints, naming, imports, and patterns to avoid. It covers test conventions, including the `pytest-cov` dependency and coverage selector a Python directory running pytest owes. It also covers versioning.

A profile belongs to a declared directory, not to the repository. Each deliverable takes one build-profile directory of its own, except that a uv workspace is declared once, by its root. A repository declaring no Python directory has its root gated only where it tracks a root `pyproject.toml`. Lint-only Python may sit beside the component it serves. Only a split by purpose alone, within one place, is forbidden, since the file name carries the purpose. One place means directories serving the same component, or serving none.

This is packaged as the `python-codestyle` Skill at `.agents/skills/python-codestyle/SKILL.md` in the hub. That is not a repo-relative link, since the path is hub-local and not carried into every fleet repo. The summary above sketches the scope. Read the skill for the full rules and the profile-adaptation guidance.

The rest of this section adapts that skill to this repo.

This repo ships a **Home Assistant custom integration** (`custom_components/purpleair/`), not an installable package or wheel. The dev environment is a `uv`-managed `.venv` (`scripts/setup` runs `uv venv` + `uv pip install` from `requirements*.txt`), but there is no `uv.lock`, no build backend, and no `src/` layout - deal in the actual integration tree and the `scripts/*` dev loop described below.

Use each tool's official casing in prose: `ruff`, `mypy`, `pyright`, `pytest`, `hassfest`, `HACS` (not `Hacs`), `NBGV`.

### Tests and Script Dependencies

- **A test lives in a `tests/` directory, never inside the production file it tests.** A deployed script may keep a `--selftest` that runs a small smoke check in seconds, and the case matrix lives in `tests/`. A self-test shipped inside the file it tests grows the file every reviewer reads, and its cases can come to outweigh the code they test.
- **A hub-hosted standalone script that needs a third-party library declares it in PEP 723 inline script metadata, and runs as `uv run --no-project --script <path>`.** The block opens on `# /// script`, closes on `# ///`, and carries `dependencies` and `requires-python`. The fleet already installs uv on hosts and in CI. `--no-project` keeps uv from syncing the project around a script that has no block yet, where it would write a lockfile and a virtual environment. A script with no such block runs under `python3` and uv alike. A hook an agent harness runs on every tool call stays standard-library only, since it runs before any toolchain is guaranteed.

### Toolchain

| Tool | Role | Config |
|---|---|---|
| [uv](https://docs.astral.sh/uv/) | dependency install into the dev `.venv` (CI uses pip) | `requirements.txt`, `requirements-test.txt` |
| [ruff](https://docs.astral.sh/ruff/) | lint + format + import sort | `.ruff.toml` (repo root) |
| [mypy](https://mypy-lang.org/) | strict type gate | `[tool.mypy]` in `pyproject.toml` (`strict`, `follow_imports = "silent"`) |
| [pyright](https://microsoft.github.io/pyright/) | type checker | `pyrightconfig.json` |
| [pytest](https://docs.pytest.org/) | test runner | `pyproject.toml` `[tool.pytest.ini_options]` |

Two type checkers run, and **both are gates**. A strict `mypy` run over `custom_components/purpleair/` is required by the platinum quality-scale `strict-typing` rule. Its scope and strictness live in `pyproject.toml`'s `[tool.mypy]` section, so `scripts/lint` and the `pre-commit` hook run a bare `mypy`. `pyright` runs directly, configured by `pyrightconfig.json` at `typeCheckingMode: basic`. It is also the engine behind VS Code's **Pylance** extension, so the in-editor and CI experience stay in sync. Both run in `scripts/lint` and in CI.

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

The Python clean-compile (see [Clean-Compile Verification](#clean-compile-verification)) is exactly what `scripts/lint` runs: `ruff format . --check` + `ruff check .` + `mypy` + `pyright`. Run it (plus `pytest`) before committing. These commands are also wired as VS Code tasks (`Fix:`, `Lint:`, `Test:`, `Develop:`) in [`.vscode/tasks.json`](./.vscode/tasks.json) for convenience. CI runs the same checks as the authoritative backstop. A `pre-commit` hook runs the four checks on every commit, from [`.pre-commit-config.yaml`][pre-commit-config], and `scripts/setup` enables it. The hook does not run `pytest`, so the suite still runs by hand before a push, per [OPERATIONS.md][operations-local-verification].

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
- The `pre-commit` hook runs the four `scripts/lint` linters plus the prose and line-ending gates on every commit. `pytest` and the Docs lint set still run by hand before a push, per [`OPERATIONS.md`][operations] "Local Verification".
- CI runs the same checks as `scripts/lint` (`ruff format --check` + `ruff check` + `mypy --strict` + `pyright`) plus `pytest`, as separate workflow steps (not by invoking the script) - the authoritative gate.
- Markdown in this directory follows the repo-wide [Markdown and Spelling](#markdown-and-spelling) rules.

## Shell

Bash, and only where a program cannot be Python: a bootstrap that installs the interpreter cannot be written in it. Nor can a host tool that must run before a development toolchain exists depend on Python. Everything else is Python, with a test under its own scripts tree's `tests/` directory. The `shell-codestyle` Skill packages the mandatory `set -Eeuo pipefail` header, the pipefail-versus-early-reader pitfall, and self-recursive command shims. It also packages self-locating scripts, the `shellcheck`-plus-`shfmt` clean-compile, and the why-not-what comment rule. It is at `.agents/skills/shell-codestyle/SKILL.md` in the hub, not a repo-relative link since that path is hub-local and not carried into every fleet repo. Read the skill for the full rules. A script's own arguments follow "Command-Line Arguments" under General, which the Skill carries whole. Run the clean-compile check itself per `GOVERNANCE.md` "Running the Linters Locally (Known-Working Invocations)", not by probing `command -v shellcheck`. That section is hub-only, read in a hub checkout rather than carried into every fleet repo.

<!-- Repo -->

[governance]: ./GOVERNANCE.md
[operations]: ./OPERATIONS.md
[operations-local-verification]: ./OPERATIONS.md#local-verification
[governance-verification-discipline]: ./GOVERNANCE.md#verification-discipline
[pre-commit-config]: ./.pre-commit-config.yaml
[readme]: ./README.md
[root]: ./.editorconfig

<!-- External -->

[google-shell-link]: https://google.github.io/styleguide/shellguide.html
[pep8-names-link]: https://peps.python.org/pep-0008/#package-and-module-names
[ps-approved-verbs-link]: https://learn.microsoft.com/en-us/powershell/scripting/developer/cmdlet/approved-verbs-for-windows-powershell-commands
