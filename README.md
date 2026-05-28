# Apple File Sorter

An automated document organization system for macOS that uses Claude (via the locally installed Claude Code CLI) to classify, rename, and sort PDF files into organized folder structures. It's recommended to call this script via an Apple Shortcut that automatically runs when files are added to the directory, enabling fully automatic document sorting.

> See [CHANGELOG.md](CHANGELOG.md) for the version history and migration notes (notably the **v2.0.0** swap from ChatGPT to Claude Code + dynamic folder discovery).

## Overview

This project automatically processes PDF files from a scan inbox folder, extracts their text content, asks Claude to classify and rename them, and moves them to appropriate folders based on the **live structure of your iCloud Documents directory**. There is no hardcoded taxonomy — adding a new folder in iCloud is all that's needed for Claude to start using it.

Classification happens in two stages per document to keep Claude's prompt small:
1. **Pick a root folder** (e.g., `Financial`, `Medical`, `Misc.`) from the actual top-level directories.
2. **Pick a destination path** within that root from the annotated subtree.

Two dynamic exceptions auto-create folders on the fly:
- **Year-pattern parents** — if every existing child of a parent is a 4-digit year (e.g., `Financial/Receipts/2023, 2024, 2025`), Claude may propose a new year (e.g., `2026`) and the script creates it.
- **Name-pattern parents** — if every existing child is a single-word proper name (e.g., `Medical/Anthony, Hannah, Oliver, Roman`), Claude may propose a new name (e.g., a relative) and the script creates it.

Any other "new" folder Claude proposes is rejected and the file falls back to `Misc.`.

## Features

- **Automatic Text Extraction**: Extracts text from PDFs using multiple methods (PyPDF2, pdfplumber, OCR with Tesseract)
- **AI-Powered Classification**: Uses Claude via the locally installed `claude` CLI — no API key required, uses your existing Claude subscription auth
- **Live Folder Discovery**: Reads your real iCloud folder tree at runtime; no taxonomy hardcoded in the script
- **Dynamic Year/Name Subfolders**: Auto-creates year-stamped (e.g., `Financial/Receipts/2026`) or person-name (e.g., `Medical/Sophia`) subfolders when the surrounding pattern is detected
- **Smart Filenaming**: Generates descriptive filenames in the format `YYYY-MM-DD - Description.pdf` using document content
- **iCloud Drive Support**: Handles iCloud Drive files, ensuring they're downloaded before processing
- **Comprehensive Logging**: Creates detailed debug logs and CSV logs of all file movements

## Requirements

### Python Dependencies
- `PyPDF2` - PDF text extraction
- `pdfplumber` - Alternative PDF text extraction
- `pytesseract` - OCR for scanned documents
- `pdf2image` - Convert PDF pages to images for OCR
- `striprtf` (optional) - Better RTF text extraction

### System Dependencies
- **Tesseract OCR**: `brew install tesseract`
- **Poppler**: `brew install poppler` (for pdf2image)
- **Claude Code CLI**: The `claude` command must be on `PATH` and already authenticated with your Anthropic account (see [Claude Code installation](https://docs.claude.com/en/docs/claude-code/quickstart)). The script invokes `claude -p` non-interactively and uses your existing subscription auth — no API key needed.

### Installation

```bash
# Install Python dependencies
pip install PyPDF2 pdfplumber pytesseract pdf2image

# Install system dependencies (macOS)
brew install tesseract poppler

# Verify Claude Code is installed and you're logged in
claude --version
claude -p "ready" --output-format text >/dev/null && echo "Claude is reachable"
```

## Usage

### Main Script: `file-sort.py`

Processes all PDF files in the scan inbox folder:

```bash
python file-sort.py
```

The script will:
1. Find all PDF files in the configured scan inbox folder
2. Extract text from each PDF
3. Ask Claude (Stage 1) to pick a root folder from your live iCloud Documents tree
4. Ask Claude (Stage 2) to pick the destination subfolder from the annotated subtree
5. Ask Claude to generate a descriptive filename
6. Move the file to the chosen destination (creating year/name subfolders on the fly when the pattern allows)
7. Log all operations to debug logs and a CSV file

### Utility Script: `view-ocr.py`

View the extracted text from PDF files for debugging:

```bash
# View text from all PDFs in default folder
python view-ocr.py

# View text from a specific PDF
python view-ocr.py /path/to/file.pdf

# View text from PDFs in a specific folder
python view-ocr.py /path/to/folder

# Save extracted text to a .txt file
python view-ocr.py /path/to/file.pdf --save
```

## Configuration

### Folder Paths

The script uses hardcoded paths that you'll need to customize:

- **Scan Inbox**: `/Users/anthonywheeler/Library/Mobile Documents/com~apple~CloudDocs/Documents/00 - Scan Inbox`
- **Documents Base**: `/Users/anthonywheeler/Library/Mobile Documents/com~apple~CloudDocs/Documents`

### Categories

There is **no hardcoded category list** — Claude sees whatever root folders currently exist under `Documents Base` (minus hidden folders and the scan inbox). Create or rename folders in iCloud and the script picks them up on the next run.

For Claude to recognise that a parent folder accepts dynamic subfolders, the script inspects the *existing children* of each parent:

| Existing children look like              | Pattern detected | Claude may propose                          |
|------------------------------------------|------------------|---------------------------------------------|
| `2023`, `2024`, `2025`                   | year             | A new 4-digit year (e.g., `2026`)           |
| `Anthony`, `Hannah`, `Oliver`, `Roman`   | name             | A new single-word proper name (e.g., `Sophia`) |
| Anything else / mixed / <2 children      | strict           | Only an existing child folder               |

The detector requires at least 2 sibling folders to declare a pattern — that prevents a single one-off folder being misread.

## Automation Setup

For fully automatic document sorting, create an Apple Shortcut that monitors the scan inbox folder and runs the script when new PDFs are added.

### Creating the Automation Shortcut

Follow these exact steps to create the automation shortcut:

1. **Create a new Shortcut** in the Shortcuts app

2. **Add "Receive folder change summary as input"** action:
   - This is the trigger that receives folder change events
   - Configure it to monitor your scan inbox folder

3. **Add "Set variable"** action:
   - Variable name: `AddedFiles`
   - Set to: `Added files` (from the folder change summary input)

4. **Add "Text"** action:
   - Enter: `No`

5. **Add "Set variable"** action:
   - Variable name: `RunScript`
   - Set to: `Text` (from the previous Text action)

6. **Add "Repeat with each item"** action:
   - Repeat with: `AddedFiles` variable
   - Inside the loop, add:
     - **"If"** action:
       - Condition: `File Extension` `is` `pdf`
       - Inside the "If" block:
         - **"Text"** action: Enter `Yes`
         - **"Set variable"** action:
           - Variable name: `RunScript`
           - Set to: `Text` (from the "Yes" text)
       - **"Otherwise"** block: Leave empty
       - **"End If"** action

7. **Add "End Repeat"** action

8. **Add "If"** action:
   - Condition: `RunScript` variable `is` `Yes`
   - Inside the "If" block:
     - **"Run Shell Script"** action:
       - Shell: `/bin/zsh` (or your preferred shell)
       - Input: `as arguments`
       - Script: 
         ```bash
         python3 /Users/anthonywheeler/Documents/Development/Personal/apple-file-sorter/file-sort.py
         ```
         (Update the path to match your script location)
   - **"End If"** action

### How It Works

The shortcut workflow:
1. Receives folder change notifications when files are added
2. Extracts the list of added files into the `AddedFiles` variable
3. Loops through each added file to check if any are PDFs
4. Sets `RunScript` to "Yes" if at least one PDF is found
5. Only runs the Python script if `RunScript` is "Yes"

This ensures the script only runs when PDF files are added, preventing unnecessary processing for other file types. The script itself then shells out to the locally installed `claude` CLI for classification and filename generation.

### Important Notes

- **PDF Filter Required**: The shortcut must check for PDF files before running the script. Without this filter, the shortcut will trigger for every file type added to the folder, which can cause unnecessary processing and errors.
- **iCloud Drive Considerations**: If using iCloud Drive, allow time for files to fully download before processing. The script includes iCloud download handling, but the automation may need a slight delay.
- **Testing**: Test the automation with a single PDF file first to ensure it works correctly before relying on it for automatic processing.
- **Update Path**: Make sure to update the Python script path in the "Run Shell Script" action to match your actual file location.
- **Claude must be on PATH for the Shortcut shell**: Apple Shortcuts launches shell scripts with a minimal `PATH`. The script's `setup_environment()` prepends common locations (`/opt/homebrew/bin`, `/usr/local/bin`, `~/.local/bin`, `~/.claude/local/bin`, `~/.npm-global/bin`) so that `claude` resolves. If your install is elsewhere, add it to that list or symlink the binary into one of those directories.
- **Claude subscription rate limits**: Each PDF triggers ~3 `claude -p` calls (root pick, subtree pick, filename). Heavy batch runs can hit your 5-hour usage cap.

## How It Works

1. **Text Extraction**: Tries multiple methods to extract text:
   - Direct text extraction (PyPDF2, pdfplumber)
   - OCR fallback for scanned/image-based PDFs

2. **Classification (Stage 1 — root pick)**: Sends the document text plus the live list of root folders in your iCloud Documents tree to `claude -p`. Claude returns one folder name.

3. **Classification (Stage 2 — destination pick)**: Walks the chosen root recursively, tags each parent with `[year-pattern]` or `[name-pattern]` if its existing children fit that shape, and sends the annotated tree to Claude. Claude returns a full relative path. The script validates the path exists (or is a permitted dynamic year/name extension) before accepting it.

4. **Filename Generation**: Asks Claude to generate a descriptive filename following the format `YYYY-MM-DD - Description`, prioritizing dates found in the document.

5. **File Organization**: Moves the file to the chosen destination, creating year/name subfolders on the fly when allowed. If Claude proposes an invalid folder, falls back to `Misc.` with a loud warning in the debug log.

6. **Logging**: Creates timestamped debug logs and maintains a CSV log of all file movements.

## Log Files

- **Debug Logs**: Created in the scan inbox folder as `file_sort_debug_YYYYMMDD_HHMMSS.log`
- **CSV Log**: `file_move_log.csv` in the scan inbox folder, tracking all file movements with timestamps

## Notes

- Files that already follow the `YYYY-MM-DD - Description.pdf` format are treated as manual overrides and skip renaming
- The script handles iCloud Drive files by forcing downloads before processing
- All operations are logged for debugging and audit purposes
