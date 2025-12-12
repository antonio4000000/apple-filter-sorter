# Apple File Sorter

An automated document organization system for macOS that uses AI to classify, rename, and sort PDF files into organized folder structures. It's recommended to call this script via an Apple Shortcut that automatically runs when files are added to the directory, enabling fully automatic document sorting.

## Overview

This project automatically processes PDF files from a scan inbox folder, extracts their text content, uses ChatGPT to intelligently classify and rename them, and moves them to appropriate folders based on category and subcategory.

## Features

- **Automatic Text Extraction**: Extracts text from PDFs using multiple methods (PyPDF2, pdfplumber, OCR with Tesseract)
- **AI-Powered Classification**: Uses ChatGPT via Apple Shortcuts to classify documents into predefined categories
- **Smart Filenaming**: Generates descriptive filenames in the format `YYYY-MM-DD - Description.pdf` using document content
- **iCloud Drive Support**: Handles iCloud Drive files, ensuring they're downloaded before processing
- **Comprehensive Logging**: Creates detailed debug logs and CSV logs of all file movements
- **Category Organization**: Organizes files into a structured folder hierarchy (Medical, Financial, Career, Cars, etc.)

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
- **Apple Shortcuts**: Requires a shortcut named "Ask ChatGPT" that accepts text input

### Installation

```bash
# Install Python dependencies
pip install PyPDF2 pdfplumber pytesseract pdf2image striprtf

# Install system dependencies (macOS)
brew install tesseract poppler
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
3. Classify the document using ChatGPT
4. Generate a descriptive filename
5. Move the file to the appropriate category folder
6. Log all operations to debug logs and a CSV file

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

The system supports a wide range of categories including:

- **Medical** (with patient name subcategories)
- **Financial** (Bills, Cards, Checks, Insurance, Taxes, Receipts, etc.)
- **Career** (Certifications, Resumes, Business Cards)
- **Cars** (vehicle-specific subcategories)
- **Kids/School**
- **Personal** (Government Documents, Letters, Spiritual)
- **Purchases** (Tickets, Product Manuals, Other)
- **Sheet Music**, **Recipes**, **User Manuals**, **Misc**

See `CATEGORY_STRUCTURE` in `file-sort.py` for the complete list and folder mappings.

### Apple Shortcuts Setup

The script requires an Apple Shortcut named "Ask ChatGPT" that:
- Accepts text input via stdin (`--input-path -`)
- Returns RTF-formatted text output
- Can be called via: `shortcuts run "Ask ChatGPT" --input-path -`

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

This ensures the script only runs when PDF files are added, preventing unnecessary processing for other file types.

### Creating the "Ask ChatGPT" Shortcut

The `file-sort.py` script requires an Apple Shortcut named "Ask ChatGPT" to interact with ChatGPT. Follow these exact steps to create it:

1. **Create a new Shortcut** in the Shortcuts app
   - Name it: `Ask ChatGPT`

2. **Add "Receive"** action:
   - Configure to receive input from "Nowhere" (allows the shortcut to be called from command line)
   - Set "If there's no input:" to `Continue`
   - This allows the shortcut to accept various input types including text from stdin

3. **Add "Get Text"** action:
   - Get text from: `Shortcut Input`
   - This extracts the text content from whatever input was received

4. **Add "Use Model"** action:
   - Model: Select `ChatGPT`
   - Input: Pass the text from the previous "Get Text" action
   - This sends the text to ChatGPT and gets a response

5. **Add "Stop and output"** action:
   - Output: `Response` (from the "Use Model" action)
   - Set "If there's nowhere to output:" to `Do Nothing`
   - This returns the ChatGPT response as the shortcut's output

### Important Notes

- **PDF Filter Required**: The shortcut must check for PDF files before running the script. Without this filter, the shortcut will trigger for every file type added to the folder, which can cause unnecessary processing and errors.
- **iCloud Drive Considerations**: If using iCloud Drive, allow time for files to fully download before processing. The script includes iCloud download handling, but the automation may need a slight delay.
- **Testing**: Test the automation with a single PDF file first to ensure it works correctly before relying on it for automatic processing.
- **Update Path**: Make sure to update the Python script path in the "Run Shell Script" action to match your actual file location.
- **ChatGPT Shortcut Name**: The shortcut must be named exactly "Ask ChatGPT" for the script to find it when calling `shortcuts run "Ask ChatGPT"`.

## How It Works

1. **Text Extraction**: Tries multiple methods to extract text:
   - Direct text extraction (PyPDF2, pdfplumber)
   - OCR fallback for scanned/image-based PDFs

2. **Classification**: Sends document content to ChatGPT with category definitions and asks for classification

3. **Filename Generation**: Uses ChatGPT to generate a descriptive filename following the format `YYYY-MM-DD - Description`, prioritizing dates found in the document

4. **File Organization**: Moves files to the appropriate folder based on category and subcategory

5. **Logging**: Creates timestamped debug logs and maintains a CSV log of all file movements

## Log Files

- **Debug Logs**: Created in the scan inbox folder as `file_sort_debug_YYYYMMDD_HHMMSS.log`
- **CSV Log**: `file_move_log.csv` in the scan inbox folder, tracking all file movements with timestamps

## Notes

- Files that already follow the `YYYY-MM-DD - Description.pdf` format are treated as manual overrides and skip renaming
- The script handles iCloud Drive files by forcing downloads before processing
- All operations are logged for debugging and audit purposes
