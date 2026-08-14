---
name: sync-simonw-til-upstream
description: Review and selectively import application code, dependency, template, and workflow changes from the original simonw/til repository without importing its TIL content. Use when checking upstream, syncing the fork, reviewing upstream package updates, or cherry-picking useful changes from simonw/til.
---

# Sync code from simonw/til

Treat `simonw/til` as a source of selectively adopted patches, not as a branch to merge wholesale. This fork has independent branding, styles, deployment settings, and embedding infrastructure, and its content diverges from upstream.

Upstream history through commit `a16711f2157fb5908b003a16792538ed9c9bcb00` (2026-07-29) is already fully incorporated into the fork's history, including upstream content from before the divergence. The review process in this skill applies only to upstream commits after that point.

Never merge or rebase the fork onto upstream `main`; that would import upstream content. Never cherry-pick every candidate automatically.

## Expected remotes

The desired setup is:

- `origin`: the user's fork
- `upstream`: `https://github.com/simonw/til.git`

Inspect before changing anything:

```bash
git remote -v
git status --short
git branch --show-current
```

If `origin` still points to `simonw/til`, the user may not have configured their fork yet. Ask for or confirm the fork URL before renaming remotes or pushing. A typical setup is:

```bash
git remote rename origin upstream
git remote add origin git@github.com:OWNER/til.git
git push -u origin main
```

If the fork already has an `origin`, add upstream with:

```bash
git remote add upstream https://github.com/simonw/til.git
```

Do not alter remotes without user confirmation. Never push to `upstream`.

## Safety rules

1. Preserve all existing user changes. Never reset, restore, clean, or stash them without explicit permission.
2. Require a clean worktree before cherry-picking. If it is dirty, ask the user to commit or approve a stash first.
3. Fetching and reviewing are safe with a dirty worktree; cherry-picking is not.
4. Apply commits one at a time, oldest first, using `-x` for provenance.
5. Inspect the full commit because a code candidate may also contain upstream content.
6. Do not automatically advance the review checkpoint after an error or unresolved candidate.
7. Do not treat upstream deployment, domains, analytics, credentials, object storage, screenshots, or embedding choices as portable by default.

## Fetch and establish the review range

Fetch without merging:

```bash
git fetch upstream main
```

Use a local Git config value as the last-reviewed upstream commit:

```bash
baseline=$(git config --get til.upstreamCodeReviewed || true)
target=$(git rev-parse upstream/main)
```

If `baseline` is empty, infer the original fork point:

```bash
baseline=$(git merge-base HEAD upstream/main)
```

Validate an existing checkpoint before using it:

```bash
git merge-base --is-ancestor "$baseline" "$target"
```

If validation fails, stop and investigate a force-push, incorrect remote, or invalid checkpoint. Do not silently replace it.

The config checkpoint is intentionally local. On a new clone, the first review may include old commits again; use `git cherry -v HEAD upstream/main` and the `-x` provenance lines to identify patches already adopted.

## Find code candidates

Review changes to these maintained paths while excluding Markdown TIL content and the generated `README.md`:

```bash
git log --reverse --date=short \
  --format='%H%x09%ad%x09%s' "$baseline..$target" -- \
  .github plugins script static templates \
  build_database.py generate_screenshots.py update_readme.py \
  metadata.yaml requirements.txt
```

`templates/pages/tools/` contains standalone personal tools and is usually content rather than reusable site code. Deprioritize those commits unless the user explicitly wants the tool. A commit touching both a tool and core paths still needs inspection.

For each candidate, inspect both its summary and complete patch:

```bash
git show --stat --summary COMMIT
git show --find-renames COMMIT
```

Classify it as one of:

- **Adopt**: portable bug fix, security fix, useful application behavior, or compatible package update.
- **Adapt**: useful intent, but paths/configuration conflict with this fork.
- **Skip**: upstream content, branding, hosting, analytics, secrets, domain, S3/Fly, screenshot, or embedding behavior that does not apply.
- **Ask**: product or infrastructure choice requiring the user's decision.

Present a concise review table with commit, date, subject, classification, reason, and likely conflict paths before making changes.

## Package updates

`requirements.txt` and `.github/workflows/build.yml` are coupled: a package may be installed for local builds, at Datasette publish time, or both. For every dependency candidate:

1. Inspect changes to both files.
2. Determine whether the fork uses that plugin or deployment path.
3. Check compatibility with the fork's Python and Datasette versions.
4. Preserve fork-specific OpenRouter embedding steps and production verification.
5. Prefer the smallest applicable patch; do not copy unrelated upstream deployment edits.

Do not describe a minimum-version constraint as a lock-file update—this project has no dependency lock file.

## Apply an adopted commit

Confirm the worktree is clean immediately before applying:

```bash
test -z "$(git status --porcelain --untracked-files=no)"
```

Untracked files are acceptable unless the patch being applied creates the same paths.

For a clean, fully applicable commit:

```bash
git cherry-pick -x COMMIT
```

For a mixed or partially applicable commit:

```bash
git cherry-pick -n COMMIT
```

Then remove unwanted changes from the pending patch by editing only affected files, preserve the fork's customizations, inspect `git diff` and `git diff --cached`, and commit with the upstream hash in the message. Do not use destructive blanket commands to remove mixed content.

If conflicts occur, manually integrate the upstream intent. In particular, never resolve `templates/til_base.html`, `metadata.yaml`, `requirements.txt`, or `.github/workflows/build.yml` wholesale with `--ours` or `--theirs`. If the patch is unsuitable:

```bash
git cherry-pick --abort
```

For a `-n` application, carefully restore only the commit's affected paths or use a temporary branch/worktree; never discard pre-existing user changes.

## Verify

Choose checks based on changed files. At minimum:

```bash
python -m compileall -q \
  build_database.py generate_screenshots.py update_readme.py plugins
```

When dependencies changed, install and test in the project's virtual environment rather than modifying the system Python. When database generation or templates changed, run the relevant build in a disposable worktree or with a backed-up generated database, then inspect the homepage and a TIL page. The repository's broad build entry point is:

```bash
./script/build
```

It can modify generated files, call external services, and generate screenshots, so do not run it blindly. Preserve the OpenRouter embeddings/similarities production invariant when workflow changes are involved.

Before finishing, inspect:

```bash
git status --short
git log --oneline --decorate -10
```

Report adopted, adapted, and skipped commits plus checks run and any remaining risks.

## Mark the range reviewed

Only after every candidate through `target` has been deliberately classified and all selected patches have succeeded, record the upstream target:

```bash
git config --local til.upstreamCodeReviewed "$target"
```

Advancing the checkpoint means skipped commits were intentionally reviewed and should not be offered again. Show the user the new checkpoint. Do not advance it if review stopped early.

If the checkpoint is unset and the fork is already up to date with upstream (no code candidates in the range), initialize it to the current `upstream/main` tip so future reviews only surface new commits.

## Cadence

Recommend checking monthly or every two to three months. Upstream core changes are infrequent: historically roughly 7–15 core/site-code commits per year, often with none for months at a time. Security and directly relevant dependency fixes can be handled sooner.
