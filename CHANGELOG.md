# Changelog

All notable changes to this project are documented in this file.

## [2.4.0] — 2026-06-12

### Added
- `file_move_log.csv` gains a fifth column, `Manual Update Notes`, for hand-written annotations when a file is later moved/renamed manually. `log_file_move()` writes it empty, preserves existing notes, and pads old 4-column rows in place.

### Changed
- `call_claude()` now invokes `claude -p --model sonnet` (was `haiku`) for better classification and date/year extraction accuracy.

### Fixed
- Inbox scan now matches the `.pdf` extension case-insensitively in `main()` — files saved as `.PDF` were silently skipped by the old `glob("*.pdf")`.

## [2.3.0] — 2026-06-12

### Added
- Year-only filenames: when a document identifies only a year (e.g., the tax year on a W-2/1099/1095), the filename is now `YYYY - Description` instead of falling back to the file created date. Prompt, `sanitize_filename()`, and the already-formatted skip check in `main()` all accept the new variant.
- OCR orientation correction in `extract_text_from_pdf()`: each page is checked with tesseract OSD and rotated before OCR, so upside-down/sideways scans no longer extract as gibberish.

### Changed
- `SUBTREE_PICK_PROMPT_TEMPLATE`: tax documents must be filed under the tax year printed on the form — never today's year or a guess; if no tax year is legible, the parent tax folder is used without a year subfolder.

### Fixed
- `parse_root_response()` now ignores trailing dots/spaces when matching root folders, so a response like `Misc.` matches a folder named `Misc. `.

## [2.2.0] — 2026-06-12

### Added
- **Usage-limit aware retries.** `call_claude()` now detects Claude Code's `usage limit reached` response, parses the reset timestamp from it, and raises a new `ClaudeUsageLimitError(reset_at)`.
- **`schedule_retry()`** installs a one-shot macOS LaunchAgent that re-runs the script shortly after the limit resets (survives sleep/logout/reboot, then removes itself). Falls back to a +1 hour retry if no reset time is present in the response.
- `parse_reset_time()` helper to extract the epoch (seconds or milliseconds) from the limit message.

### Changed
- `main()` now catches `ClaudeUsageLimitError`, stops the current run leaving unprocessed files untouched in the inbox, and schedules the automatic retry instead of treating the limit as a fatal error.

## [2.1.0] — 2026-05-28

### Changed
- `call_claude()` now invokes `claude -p --model haiku` to pin classification and filename generation to Claude Haiku, lowering per-call cost/usage for this structured task.

## [2.0.0] — 2026-05-28

Major rewrite: swapped the ChatGPT Apple Shortcut for the locally installed Claude Code CLI, and replaced the hardcoded category taxonomy with live filesystem discovery.

### Added
- **`call_claude()`** wrapper that invokes `claude -p` over stdin. Uses your existing Claude subscription auth — no API key, no per-call billing.
- **Two-stage dynamic classification** in `classify_file_category()`:
  - Stage 1 asks Claude to pick a root folder from the live top-level directories under `DOCUMENTS_BASE_PATH`.
  - Stage 2 asks Claude to pick a destination path from the recursive subtree of the chosen root.
- **Filesystem discovery helpers**: `list_root_folders()`, `build_annotated_tree()`, `detect_subfolder_pattern()`, `validate_destination()`, `find_misc_folder()`, `parse_root_response()`, `parse_path_response()`.
- **Dynamic subfolder auto-create** for two detected patterns:
  - `year-pattern`: parent whose existing children are all 4-digit years → new years allowed (e.g., `Financial/Receipts/2026`).
  - `name-pattern`: parent whose existing children are all single-word proper names → new names allowed (e.g., `Medical/Sophia`).
  - All other "new folder" suggestions from Claude are rejected and the file falls back to `Misc.`.
- **`setup_environment()` extended** to include `~/.local/bin`, `~/.claude/local/bin`, and `~/.npm-global/bin` so the `claude` binary resolves under Apple Shortcuts' minimal PATH.
- **iCloud-aware CSV logging**: `log_file_move()` now nudges iCloud via `brctl download` and retries on `EDEADLK` (errno 11) to ride out transient iCloud coordinator-lock contention.
- **`test_file_sort.py`** with 30 unit tests covering pattern detection, validation, response parsing, tree building, and the end-to-end two-stage flow (with `call_claude` mocked).

### Changed
- **`generate_filename()`** now calls `call_claude()` instead of the ChatGPT shortcut; prompt template unchanged.
- **`classify_file_category()`** now returns an absolute `Path` instead of a `(category, subcategory)` tuple. `main()` updated at both call sites.
- **`README.md`** rewritten: new overview, prerequisites (Claude Code CLI), pattern-detection table, and updated "How It Works" walkthrough.
- Defensive comments in `filter_problematic_content()`, `fallback_filename_from_text()`, and `sanitize_filename()` updated from "ChatGPT" to "the LLM" since the filtering remains useful for any model.

### Removed
- **`CATEGORY_STRUCTURE`** dict (~45 lines) — the filesystem is now the source of truth.
- **`get_folder_path_for_category()`** (~85 lines) — Claude returns the path directly.
- **`get_all_categories_for_prompt()`** (~130 lines) — the descriptive prompt block; replaced by a much shorter inline prompt listing live folder names plus pattern annotations.
- **`extract_text_from_rtf()`** and the `striprtf` dependency — no longer needed; `claude -p` returns plain text.
- **`call_chatgpt_shortcut()`** and the "Ask ChatGPT" Apple Shortcut requirement.
- **"Creating the Ask ChatGPT Shortcut" section** from README.

### Migration Notes
- Install Claude Code locally (`claude` on `PATH`) and authenticate with your Anthropic account before the next script run.
- The folder-watcher Apple Shortcut that triggers `file-sort.py` is unchanged — only the inner AI dependency was swapped.
- No edits to `CATEGORY_STRUCTURE` are needed when you add a new folder in iCloud; the script picks it up on the next run.
- Caveat: a parent folder whose children are all single capitalised words (e.g., `Electric`, `Gas`, `Water`) will be misread as a name-pattern. Include at least one all-caps abbreviation (e.g., `HOA`) or multi-word folder to force strict typing.

### Fixed
- iCloud `EDEADLK` ("Resource deadlock avoided") on CSV writes when `file_move_log.csv` was concurrently held by iCloud's `bird` daemon. File moves themselves were always succeeding; only the audit log row was being dropped. Resolved via `brctl` nudge + bounded retry with backoff (0.5s, 1.0s, 1.5s).
