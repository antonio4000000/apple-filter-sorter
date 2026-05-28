# Project Guidance for Claude

## Changelog hygiene

This project keeps a human-readable changelog at [`CHANGELOG.md`](CHANGELOG.md) (Keep a Changelog format).

### Before making changes

**Read `CHANGELOG.md` first.** It captures recent behavior shifts, removed APIs, and migration notes that aren't always obvious from the code alone — for example, the v2.0.0 swap from the "Ask ChatGPT" Apple Shortcut to the local `claude -p` CLI, and why the hardcoded `CATEGORY_STRUCTURE` was deleted in favor of live filesystem discovery. Skip this and you risk reintroducing patterns the user has already moved away from.

### After making changes

**Append a new entry to `CHANGELOG.md` when the change is user-visible or behavior-altering.** Specifically:

- Append when the change is in any of these buckets: new feature, removed feature, behavior change, breaking change, bug fix that a user would notice, dependency change, prompt or model swap, public-script invocation change.
- Skip the changelog for purely internal cleanups: comment fixes, whitespace, renaming a local variable, test-only refactors, dead-code removal that didn't affect runtime behavior.

### How to append

1. Add a new version block at the top of `CHANGELOG.md` under the existing header. Use `## [X.Y.Z] — YYYY-MM-DD`.
2. Bump the version using semver intent:
   - **Major** (X.0.0): breaking change — script invocation, required dependencies, output format, or removed public behavior.
   - **Minor** (x.Y.0): new capability that's backward-compatible.
   - **Patch** (x.y.Z): bug fix or small enhancement with no behavior change for existing users.
3. Use the existing section headings as needed: **Added**, **Changed**, **Removed**, **Fixed**, **Migration Notes**. Omit any section that has no entries.
4. Keep entries terse — one line each, reference file paths or function names where useful. The user can `git log` for the full story; the changelog is the curated highlight reel.
5. If the change requires the user to do something (install a tool, edit config, migrate data), add a **Migration Notes** bullet.

### Don't

- Don't create a changelog entry for every commit. Group related work under one version bump.
- Don't include emojis (project convention).
- Don't reference issue numbers or PRs that don't exist in this repo.
- Don't write planning or design docs into the changelog — that belongs in conversation or a Plan, not the audit trail.
