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

The repo is configured for Copilot auto-review on PR open, and that initial trigger fires reliably — no agent or maintainer action is needed when the PR is first created.

**Re-review on follow-up commits is the unreliable case.** Copilot's auto-rereview on push fires only ~20% of the time and frequently posts "Copilot encountered an error and was unable to review" instead of a real review. When that happens (or when the agent confirms head-SHA coverage is missing after a push), **the maintainer must click "Re-request review" next to Copilot's avatar in the PR UI**. Agents must not attempt programmatic re-requests — every public path has been confirmed broken across multiple repos and either fails outright or silently no-ops.

**Do NOT post `@Copilot review` as a PR comment.** That comment triggers the Copilot *coding agent* (`copilot-swe-agent[bot]`), which will make code changes rather than posting a review.

Known non-working programmatic re-request paths — agents have tried these, they fail, do not retry:

- `gh pr edit <N> --add-reviewer Copilot` → `Could not resolve user with login 'copilot'`.
- `POST /requested_reviewers` with `reviewers=[Copilot]` can return 200 but no-op.
- `copilot-pull-request-reviewer` as a requested reviewer slug returns 422.
- `gh api ... -F 'reviewers[]=copilot-pull-request-reviewer'` returns an empty body and never fires a review.
- GraphQL `requestReviews` rejects Copilot's bot node.

The reverse direction — replying on review threads and resolving them via GraphQL (`addPullRequestReviewThreadReply` + `resolveReviewThread`, see "Reply and thread resolution workflow" below) — DOES work reliably and is the agent's responsibility once a review exists.

### Verify review covered current head

Before merging, confirm Copilot reviewed the current PR head SHA. Copilot may respond as either a formal review (carries an exact commit SHA) or an issue comment (no SHA — use the most recent Copilot comment for manual confirmation). Check both.

```sh
PR_HEAD=$(gh pr view <N> --json headRefOid --jq '.headRefOid')

# 1. Formal review — exact SHA match.
gh pr view <N> --json reviews --jq \
  '.reviews[] | select(.author.login=="copilot-pull-request-reviewer") | .commit.oid' \
  | grep -q "$PR_HEAD" && echo "covered via formal review"

# 2. Issue comment — show the most recent Copilot comment for manual confirmation.
gh api repos/<owner>/<repo>/issues/<N>/comments --jq \
  '[.[] | select(.user.login=="copilot-pull-request-reviewer")] | last | {created_at, body: .body[:200]}'
```

Coverage is confirmed when (1) exits 0. For issue comments (path 2), body content is the only reliable signal — `created_at` is not: `git log -1 --format=%cI` is the **commit** timestamp, not the push timestamp, so amended or rebased commits can have an earlier timestamp and an older Copilot comment could satisfy a time check even though Copilot never saw the current head. Treat path (2) as confirmed only when the comment body explicitly refers to the current changes.

To enumerate findings, use the GraphQL unresolved-threads query in the "Reply and thread resolution workflow" section. For issue-level comments (Copilot sometimes posts summaries there), inspect manually:

```sh
gh api repos/<owner>/<repo>/issues/<N>/comments --jq \
  '[.[] | select(.user.login=="copilot-pull-request-reviewer")] | last | {created_at, body}'
```

### Bounded retry workflow

This applies only to follow-up-commit re-review, not the initial PR-open auto-trigger (which is reliable). If after a push the head-SHA-coverage check (above) shows no formal review on the new head, or Copilot posted "encountered an error and was unable to review":

1. Wait briefly and re-check head-SHA coverage in case the rereview is still in flight.
1. If still missing or errored, ask the maintainer to click "Re-request review" next to Copilot's avatar in the PR UI. The agent must not retry via CLI/API — see "Triggering and polling" above.
1. Once the maintainer re-requests, resume polling head-SHA coverage.
1. After two failed maintainer-triggered re-requests on the same head, mark review as blocked and escalate.

### Reply and thread resolution workflow

This path is reliable for agents — unlike review *requesting*, the GraphQL thread mutations work consistently. Triage findings, post replies citing the fixing commit SHA or rationale, and resolve threads as they're addressed.

List unresolved threads. Use `first: 100` with cursor-based pagination; if `hasNextPage` is true, re-run with `after: "<endCursor>"` to retrieve the next page:

```sh
gh api graphql -f query='
{
  repository(owner: "<owner>", name: "<repo>") {
    pullRequest(number: <N>) {
      reviewThreads(first: 100) {
        nodes {
          id isResolved path
          comments(first: 1) { nodes { author { login } body } }
        }
        pageInfo { hasNextPage endCursor }
      }
    }
  }
}' | jq '
  .data.repository.pullRequest.reviewThreads |
  (.pageInfo | "hasNextPage=\(.hasNextPage) endCursor=\(.endCursor)"),
  (.nodes[] | select(.isResolved == false))
'
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

Issue-level Copilot comments (those in `issues/<N>/comments`) have no resolution action — GitHub provides no API or UI to resolve them. Reply if the finding warrants it; no resolution step is needed or possible.

Reply-body conventions:

- Accepted bug/style fix: include fixing commit SHA.
- Declined style comment: cite the AGENTS rule and existing-tree precedent.
- Declined architecture proposal: one-sentence rationale.

After final push, sweep-resolve stale older threads for removed code paths.

## When in doubt

Read [AGENTS.md](../AGENTS.md) for the full picture (release flow, files you must not touch, code style, workflow YAML conventions). Don't restate this file's rules in commit bodies or PR descriptions — keep those focused on the change itself.
