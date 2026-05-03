# Copilot instructions

Repository conventions for GitHub Copilot (and any other agent reading this file).

The **canonical guide is [AGENTS.md](../AGENTS.md)** at the repo root — read it first. It covers project layout, branch flow, code style, the release pipeline, and what NOT to touch (e.g. the placeholder `manifest.json` `version` and the HA test matrix). Treat AGENTS.md as the source of truth; this file just summarizes the commit/PR-title rules so the VS Code AI commit-message and PR-title generators get them without an extra fetch.

## Commit messages and pull request titles

Feature → develop PRs squash-merge — the PR title becomes the single commit on develop. Develop → main PRs merge-commit — main's history shows one merge commit per release with develop's tip as the second parent. Titles are descriptive and have no versioning effect — versioning is handled by [Nerdbank.GitVersioning](https://github.com/dotnet/Nerdbank.GitVersioning) reading [version.json](../version.json) and git history, not by parsing commit messages.

### Format

- Imperative subject summarizing the change, ≤ 72 characters, no trailing period. ("Add 24-hour PM2.5 average sensor", not "Added X" or "Adds X".)
- Optional body, blank-line separated, explaining *why* the change is being made when that's non-obvious. The diff shows *what*.

### Rules

- Don't write `update stuff`, `wip`, or other vague titles. (Dependabot's default `Bump X from Y to Z` titles are fine — keep them.)
- Don't add `Co-Authored-By:` lines unless the user explicitly asks.
- Don't put release-bump magnitude in the title — no "minor", "patch", "release v0.2.0", etc. NBGV computes the next release version from `version.json` + git history. Dependency versions in dependency-bump titles are fine and expected.
- Use US English spelling and match the existing heading style of the file you're editing: title case with lowercase short bind words (a, an, the, and, but, or, of, in, on, at, to, by, for, from); hyphenated compounds capitalize both parts unless the second is a short preposition (*Built-in*, *EPA-Corrected*, *24-Hour*).

### Examples

```text
Surface 24-hour PM2.5 average as a separate sensor
Skip empty PurpleAir API responses during polling
Drop support for Home Assistant < 2026.4
Bump aiopurpleair from 2025.08.1 to 2025.09.0
Clarify HACS install steps in README
```

## GitHub Copilot Review Runbook

Use this section for provider-specific mechanics. The expected review loop contract is defined in [AGENTS.md](../AGENTS.md); this section only describes how to make GitHub Copilot reliably execute it.

### Triggering and polling

Copilot auto-review on push is configured, but it sometimes misses pushes. The reliable manual trigger is:

```sh
gh pr comment <N> --body "@Copilot review"
```

Copilot may reply as either an issue comment (`repos/.../issues/<N>/comments`) or a formal review (`repos/.../pulls/<N>/reviews`). Check both.

Known non-working request paths (don't rely on them):

- `POST /requested_reviewers` with `reviewers=[Copilot]` can return 200 but no-op.
- `copilot-pull-request-reviewer` as a requested reviewer slug returns 422.
- GraphQL `requestReviews` rejects Copilot's bot node.

### Verify review covered current head

Before merging, confirm Copilot reviewed the current PR head SHA. Copilot may respond as either a formal review (carries an exact commit SHA) or an issue comment (no SHA — use the commit's push timestamp as a proxy). Check both.

```sh
PR_HEAD=$(gh pr view <N> --json headRefOid --jq '.headRefOid')
PUSHED_AT=$(gh api repos/<owner>/<repo>/commits/"$PR_HEAD" --jq '.commit.committer.date')

# 1. Formal review — exact SHA match.
gh pr view <N> --json reviews --jq \
  '.reviews[] | select(.author.login=="copilot-pull-request-reviewer") | .commit.oid' \
  | grep -q "$PR_HEAD" && echo "covered via formal review"

# 2. Issue comment — posted on or after the head commit was pushed.
gh api repos/<owner>/<repo>/issues/<N>/comments --jq \
  "[.[] | select(.user.login==\"copilot-pull-request-reviewer\" and .created_at >= \"$PUSHED_AT\")] | length"
```

Coverage is confirmed when either (1) exits 0 or (2) returns a count ≥ 1.

Then inspect all Copilot comments at-or-after the latest response timestamp:

```sh
LATEST=$(gh pr view <N> --json reviews --jq \
  '[.reviews[] | select(.author.login=="copilot-pull-request-reviewer")] | last | .submittedAt // "1970-01-01T00:00:00Z"')

# Inline review comments (thread replies on diff hunks).
gh api repos/<owner>/<repo>/pulls/<N>/comments --jq \
  "[.[] | select(.created_at >= \"$LATEST\")]"

# Issue-level comments (Copilot sometimes posts findings here instead).
gh api repos/<owner>/<repo>/issues/<N>/comments --jq \
  "[.[] | select(.user.login==\"copilot-pull-request-reviewer\" and .created_at >= \"$LATEST\")]"
```

### Bounded retry workflow

If a review did not run on the current head, retry with bounded attempts:

1. Trigger with `@Copilot review`.
1. Wait briefly and re-check head-SHA coverage.
1. Retry up to three attempts.
1. If still missing, mark review as blocked and escalate to the user/maintainer with what was attempted.

### Reply and thread resolution workflow

List unresolved threads:

```sh
gh api graphql -f query='
{
  repository(owner: "<owner>", name: "<repo>") {
    pullRequest(number: <N>) {
      reviewThreads(last: 100) {
        nodes {
          id isResolved path
          comments(first: 1) { nodes { author { login } body } }
        }
      }
    }
  }
}' | jq '.data.repository.pullRequest.reviewThreads.nodes[] | select(.isResolved == false)'
```

Reply on a thread, then resolve it:

```sh
gh api graphql -f query='
mutation($threadId: ID!, $body: String!) {
  addPullRequestReviewThreadReply(input: { pullRequestReviewThreadId: $threadId, body: $body }) {
    comment { id }
  }
}' -F threadId="PRRT_..." -F body="Fixed in <SHA>: <one-line summary>."

gh api graphql -f query='
mutation($threadId: ID!) {
  resolveReviewThread(input: { threadId: $threadId }) { thread { id isResolved } }
}' -F threadId="PRRT_..."
```

Reply-body conventions:

- Accepted bug/style fix: include fixing commit SHA.
- Declined style comment: cite the AGENTS rule and existing-tree precedent.
- Declined architecture proposal: one-sentence rationale.

After final push, sweep-resolve stale older threads for removed code paths.

## When in doubt

Read [AGENTS.md](../AGENTS.md) for the full picture (release flow, files you must not touch, code style, workflow YAML conventions). Don't restate this file's rules in commit bodies or PR descriptions — keep those focused on the change itself.
