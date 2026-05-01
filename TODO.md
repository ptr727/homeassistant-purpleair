# TODO

## Fix TODO's

- Fix or implement the TODO's in docs and code.

## MD / YANL Format

- Revert the MD / markdown and YAML line shortening done to make the linter happy, line length is not enforced, reformat to follow normal sentence length lines

## Migrate from release-please to NBGV

Release-please is a pita to work with, I wasted half a day and billions of tokens to get it working, giving up.

Use the github actions template pattern for releases and version calculation from [https://github.com/ptr727/ProjectTemplate].\
The current actions files were created from the template, but diverged to use releaase-please, revert the changes back to a simpler nbgv way of versioning.

The desired release process is as follows:

- `main` and `develop` are protected branches, configured in repo, changes must come in using a PR.
- Re-merging `main` to `develop` may occasionally be done or required when there is lots of drift, but should be avoided.
- Typical flow is feature branch cut from develop, open PR from feature to develop, when done PR from develop to main.
- Squash merging is the only allowed method of merging, configured in repo.
- All commits must be signed, configured in repo.
- Meging is blocked until the `Check pull request workflow status` passes, this is configured in repo settings.
- Unlike my typical binary releases that are pulled by users, HACS is a push on update model, and new versions should only be released when really required.
- This means that dependabot updates, or updates to ad new HA versions to the test matrix, should not push new releases, but only update the code and test the code.
- New releases should be a manual run of the release task.
- New beta / pre-releases should be automatically released if users want to test the current version.
- I typically only update the `main` branch using dependabot, but in this case tehre are many pypi requirements that need updating, and re-merging `main` to `develop` to stay in sync can be problematic, so dependabot should update `main` and `develop` to minimize drift and to keep `develop` pre-releases really current.
- The actions should monitor for new HA releases, and update the HA test matrix in code accordingly, take care to update the required child components, i.e. new HA tests are not compatible with old HA versions.
- The actions or dependabot should keep the pypi modules up to date in test and requirements files, folow python and HA best practices for version pinning.
- Note that PR triggers behave different for different gihub tokens, and code chnages or changes that require PR triggers are done using the codemod bot app token.
- Given release-please is being removed, theer will be opportunity to greatly simoplify the actiosn files, and use the inherited github token over the app token, simplify where possible.
- No public relases have been made, so code history, and tags, and versions can all be deleted without consequence.
- Start fresh by deleting all releases and all tags.
- I added nbgv `version.json` file and a new `0.1.0` version as starting point.
- Make whatever chnages are reaquired in the version schema to keep HA and HACS happy with version numbers.
- Delete all the old release-please code and files.
- Update all the agent and contributor instructions to match the new release method, including e.g. `commitMessageGeneration` and `pullRequestDescriptionGeneration`.

Advise or ask questions if any of the objectives are unclear, or if you have better options, or if you see issues.
