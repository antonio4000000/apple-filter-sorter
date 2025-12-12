import subprocess
import re
import os
import csv
import sys
import traceback
from pathlib import Path
from datetime import datetime

# Global log file handle
LOG_FILE = None
LOG_FILE_PATH = None

# Set up PATH for Homebrew when running from Shortcuts
def setup_environment():
    """Set up environment variables for Homebrew tools when running from Shortcuts"""
    homebrew_paths = [
        "/opt/homebrew/bin",  # Apple Silicon
        "/usr/local/bin",      # Intel Mac
    ]
    
    current_path = os.environ.get("PATH", "")
    for path in homebrew_paths:
        if Path(path).exists() and path not in current_path:
            os.environ["PATH"] = f"{path}:{current_path}"
    
    # Also set poppler path for pdf2image
    poppler_paths = [
        "/opt/homebrew/opt/poppler/bin",  # Apple Silicon
        "/usr/local/opt/poppler/bin",      # Intel Mac
    ]
    
    for poppler_path in poppler_paths:
        if Path(poppler_path).exists():
            os.environ["PATH"] = f"{poppler_path}:{os.environ.get('PATH', '')}"
            break

# Set up environment at import time
setup_environment()


def setup_logging(scan_folder):
    """Set up file logging for debugging when running from Shortcuts. Creates a new log file per run."""
    global LOG_FILE, LOG_FILE_PATH
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_path = scan_folder / f"file_sort_debug_{timestamp}.log"
    LOG_FILE_PATH = log_path
    try:
        LOG_FILE = open(log_path, 'w', encoding='utf-8')
        log_print(f"=== File Sort Script Started at {datetime.now()} ===")
        log_print(f"Log file: {log_path}")
        log_print(f"Python version: {sys.version}")
        log_print(f"Working directory: {os.getcwd()}")
        log_print("=" * 80)
        return log_path
    except Exception as e:
        print(f"ERROR: Could not create log file: {e}")
        return None


def log_print(*args, **kwargs):
    """Print to both console and log file"""
    # Print to console
    print(*args, **kwargs)
    # Also write to log file
    if LOG_FILE:
        try:
            print(*args, **kwargs, file=LOG_FILE)
            LOG_FILE.flush()  # Ensure it's written immediately
        except Exception as e:
            print(f"ERROR writing to log: {e}", file=sys.stderr)


def close_logging():
    """Close the log file"""
    global LOG_FILE
    if LOG_FILE:
        try:
            print("=" * 80, file=LOG_FILE)
            print(f"=== File Sort Script Completed at {datetime.now()} ===", file=LOG_FILE)
            LOG_FILE.flush()
            LOG_FILE.close()
            LOG_FILE = None
        except Exception as e:
            print(f"ERROR closing log file: {e}", file=sys.stderr)


def extract_text_from_rtf(rtf_text):
    """
    Extract plain text from RTF format.
    This handles the RTF output from Apple Shortcuts.
    """
    # Try using striprtf library if available (install with: pip install striprtf)
    try:
        from striprtf.striprtf import rtf_to_text
        return rtf_to_text(rtf_text).strip()
    except ImportError:
        # Fallback: Improved regex-based extraction
        text = rtf_text
        
        # Remove RTF header (everything up to the first content)
        # Remove common RTF control words and groups
        # Pattern: \word123 or \word followed by optional number and space
        text = re.sub(r'\\[a-z]+\d*\s*', '', text)
        
        # Remove RTF special characters (like \par, \tab, etc.)
        text = re.sub(r'\\[^a-z{}]', '', text)
        
        # Remove empty RTF groups like {\listtext ...} or {*}
        # This pattern matches groups that contain only RTF commands
        def remove_formatting_groups(match):
            content = match.group(1)
            # If the group contains only RTF commands (backslashes) or is empty, remove it
            if re.match(r'^[\s\\]*$', content) or '\\' in content:
                return ''
            return content
        
        # Remove formatting groups (recursively handle nested braces)
        while '{' in text:
            text = re.sub(r'\{([^{}]*)\}', remove_formatting_groups, text)
        
        # Remove any remaining braces
        text = text.replace('{', '').replace('}', '')
        
        # Clean up escaped characters
        text = text.replace('\\', '')
        
        # Normalize whitespace - replace multiple spaces/newlines with single space
        text = re.sub(r'\s+', ' ', text)
        
        # Remove leading/trailing whitespace
        return text.strip()


def check_file_downloaded(file_path):
    """
    Check if an iCloud file is actually downloaded by checking extended attributes.
    Returns True if downloaded, False if still in cloud.
    """
    try:
        result = subprocess.run(
            ["xattr", "-l", str(file_path)],
            capture_output=True,
            text=True,
            timeout=5
        )
        output = result.stdout.lower()
        # If file has com.apple.icloud.download or is marked as needing download
        if "com.apple.icloud" in output and "download" in output:
            return False
        return True
    except:
        return True  # Assume downloaded if we can't check


def ensure_file_downloaded(file_path):
    """
    Force iCloud Drive files to be downloaded/available offline before processing.
    Returns True if file is available, False otherwise.
    """
    log_print(f"  [ICLOUD] Ensuring file is downloaded from iCloud...")
    
    # Check if file is already downloaded
    if check_file_downloaded(file_path):
        log_print(f"  [ICLOUD] File appears to be already downloaded")
    else:
        log_print(f"  [ICLOUD] File needs to be downloaded from iCloud")
    
    # Method 1: Try using brctl (macOS built-in command) to force download
    try:
        log_print(f"  [ICLOUD] Attempting to force download using brctl...")
        # Try downloading the specific file
        result = subprocess.run(
            ["brctl", "download", str(file_path)],
            capture_output=True,
            text=True,
            timeout=15
        )
        if result.returncode == 0:
            log_print(f"  [ICLOUD] brctl download command executed successfully")
        else:
            log_print(f"  [ICLOUD] brctl returned code {result.returncode}: {result.stderr}")
    except FileNotFoundError:
        log_print(f"  [ICLOUD] brctl not available, trying alternative method...")
    except Exception as e:
        log_print(f"  [ICLOUD] brctl error: {e}")
    
    # Wait a bit for download to start
    import time
    time.sleep(2)
    
    # Method 2: Copy file to temp location (forces download)
    temp_file = None
    try:
        import tempfile
        log_print(f"  [ICLOUD] Attempting to copy file to temp location to force download...")
        temp_dir = tempfile.gettempdir()
        temp_file = Path(temp_dir) / f"icloud_download_{file_path.name}"
        
        # Try to copy the file - this will force iCloud to download it
        import shutil
        max_copy_retries = 5
        for attempt in range(max_copy_retries):
            try:
                shutil.copy2(file_path, temp_file)
                log_print(f"  [ICLOUD] File copied to temp location successfully ({temp_file.stat().st_size} bytes)")
                break
            except (IOError, OSError) as e:
                if attempt < max_copy_retries - 1:
                    log_print(f"  [ICLOUD] Copy attempt {attempt + 1} failed: {e}, waiting and retrying...")
                    time.sleep(2)  # Wait longer between retries
                else:
                    log_print(f"  [ICLOUD] All copy attempts failed")
                    raise
        
        # Verify the temp file is good
        if temp_file.exists() and temp_file.stat().st_size > 0:
            log_print(f"  [ICLOUD] Temp file verified: {temp_file.stat().st_size} bytes")
            # Now try to read the original file
            time.sleep(1)
            
            # Try reading the original file now
            try:
                with open(file_path, 'rb') as f:
                    test_read = f.read(1024)  # Read first 1KB
                log_print(f"  [ICLOUD] Original file is now readable")
                # Clean up temp file
                if temp_file.exists():
                    temp_file.unlink()
                return True
            except Exception as e:
                log_print(f"  [ICLOUD] Original file still not readable: {e}")
                # Use temp file instead - return the temp file path
                log_print(f"  [ICLOUD] Will use temp file for processing")
                return temp_file
        else:
            log_print(f"  [ICLOUD] Temp file verification failed")
            if temp_file.exists():
                temp_file.unlink()
            return False
            
    except Exception as e:
        log_print(f"  [ICLOUD] Copy method error: {e}")
        if temp_file and temp_file.exists():
            try:
                temp_file.unlink()
            except:
                pass
    
    # Method 3: Try reading the file directly with longer waits
    try:
        log_print(f"  [ICLOUD] Attempting direct file read...")
        max_retries = 5
        for attempt in range(max_retries):
            try:
                with open(file_path, 'rb') as f:
                    # Read in chunks to avoid memory issues
                    content = b""
                    chunk_size = 1024 * 1024  # 1MB chunks
                    while True:
                        chunk = f.read(chunk_size)
                        if not chunk:
                            break
                        content += chunk
                log_print(f"  [ICLOUD] File read successfully ({len(content)} bytes)")
                return True
            except (IOError, OSError) as e:
                if attempt < max_retries - 1:
                    wait_time = (attempt + 1) * 2  # Exponential backoff
                    log_print(f"  [ICLOUD] Attempt {attempt + 1} failed: {e}, waiting {wait_time}s...")
                    time.sleep(wait_time)
                else:
                    log_print(f"  [ICLOUD] All read attempts failed")
                    raise
        
        # Verify file is accessible and has content
        if file_path.exists():
            file_size = file_path.stat().st_size
            if file_size > 0:
                log_print(f"  [ICLOUD] File verified: {file_size} bytes")
                return True
            else:
                log_print(f"  [ICLOUD] WARNING: File exists but is 0 bytes")
                return False
        else:
            log_print(f"  [ICLOUD] ERROR: File does not exist")
            return False
    except Exception as e:
        log_print(f"  [ICLOUD] ERROR reading file: {e}")
        log_print(f"  [ICLOUD] Error type: {type(e).__name__}")
        return False


def extract_text_from_pdf(pdf_path):
    """
    Extract text content from a PDF file.
    Tries direct text extraction first, then falls back to OCR for image-based PDFs.
    """
    log_print(f"  [EXTRACT] Starting text extraction for: {pdf_path.name}")
    
    # Ensure file is downloaded from iCloud first
    download_result = ensure_file_downloaded(pdf_path)
    if download_result is False:
        log_print(f"  [EXTRACT] ERROR: Could not download file from iCloud, aborting...")
        return ""
    elif isinstance(download_result, Path):
        # File was copied to temp location, use that instead
        log_print(f"  [EXTRACT] Using temp file for processing: {download_result}")
        actual_pdf_path = download_result
        use_temp = True
    else:
        actual_pdf_path = pdf_path
        use_temp = False
    
    text = ""
    
    # Try PyPDF2 first
    try:
        import PyPDF2
        log_print("  [EXTRACT] Trying PyPDF2...")
        # Try with strict=False to handle corrupted PDFs
        try:
            with open(actual_pdf_path, 'rb') as file:
                pdf_reader = PyPDF2.PdfReader(file, strict=False)
                log_print(f"  [EXTRACT] PyPDF2 found {len(pdf_reader.pages)} page(s)")
                for i, page in enumerate(pdf_reader.pages):
                    try:
                        page_text = page.extract_text()
                        if page_text:
                            text += page_text + "\n"
                            log_print(f"  [EXTRACT] Page {i+1}: extracted {len(page_text)} characters")
                    except Exception as page_error:
                        log_print(f"  [EXTRACT] Page {i+1} extraction failed: {page_error}")
        except Exception as e:
            # If strict=False doesn't work, try with a fresh file handle
            log_print(f"  [EXTRACT] PyPDF2 first attempt failed: {e}, retrying...")
            import time
            time.sleep(0.1)  # Brief pause to avoid resource deadlock
            with open(actual_pdf_path, 'rb') as file:
                pdf_reader = PyPDF2.PdfReader(file, strict=False)
                for page in pdf_reader.pages:
                    page_text = page.extract_text()
                    if page_text:
                        text += page_text + "\n"
        log_print(f"  [EXTRACT] PyPDF2 total extracted: {len(text)} characters")
    except ImportError:
        log_print("  [EXTRACT] PyPDF2 not available")
    except Exception as e:
        log_print(f"  [EXTRACT] PyPDF2 extraction failed: {e}")
        log_print(f"  [EXTRACT] PyPDF2 error type: {type(e).__name__}")
    
    # Try pdfplumber if PyPDF2 didn't work or returned little text
    if len(text.strip()) < 50:
        try:
            import pdfplumber
            log_print("  [EXTRACT] Trying pdfplumber...")
            with pdfplumber.open(actual_pdf_path) as pdf:
                text = ""
                for page in pdf.pages:
                    page_text = page.extract_text()
                    if page_text:
                        text += page_text + "\n"
            log_print(f"  [EXTRACT] pdfplumber extracted {len(text)} characters")
        except ImportError:
            log_print("  [EXTRACT] pdfplumber not available")
        except Exception as e:
            log_print(f"  [EXTRACT] pdfplumber extraction failed: {e}")
    
    # If we still have very little text, try OCR (for scanned/image-based PDFs)
    if len(text.strip()) < 50:
        log_print("  [EXTRACT] Text extraction returned little/no text, trying OCR...")
        try:
            import pytesseract
            from pdf2image import convert_from_path
            
            # Find poppler path
            poppler_path = None
            poppler_paths = [
                "/opt/homebrew/opt/poppler/bin",  # Apple Silicon
                "/usr/local/opt/poppler/bin",     # Intel Mac
            ]
            
            for path in poppler_paths:
                if Path(path).exists():
                    poppler_path = path
                    log_print(f"  [EXTRACT] Found poppler at: {poppler_path}")
                    break
            
            if not poppler_path:
                # Try to find it in PATH
                try:
                    result = subprocess.run(["which", "pdftoppm"], capture_output=True, text=True)
                    if result.returncode == 0:
                        poppler_path = Path(result.stdout.strip()).parent
                        log_print(f"  [EXTRACT] Found poppler in PATH: {poppler_path}")
                except:
                    pass
            
            # Convert PDF pages to images
            log_print("  [EXTRACT] Converting PDF to images...")
            if poppler_path:
                images = convert_from_path(actual_pdf_path, dpi=300, poppler_path=str(poppler_path))
            else:
                log_print("  [EXTRACT] WARNING: Poppler path not found, trying default...")
                images = convert_from_path(actual_pdf_path, dpi=300)
            log_print(f"  [EXTRACT] Converted to {len(images)} image(s)")
            text = ""
            for i, image in enumerate(images):
                log_print(f"  [EXTRACT] OCR processing page {i+1}/{len(images)}...")
                page_text = pytesseract.image_to_string(image)
                if page_text:
                    text += page_text + "\n"
            log_print(f"  [EXTRACT] OCR extracted {len(text)} characters")
        except ImportError:
            log_print("  [EXTRACT] ERROR: OCR libraries not available. Install with: pip install pytesseract pdf2image")
            log_print("  [EXTRACT] Also install Tesseract: brew install tesseract (on macOS)")
            return ""
        except Exception as e:
            log_print(f"  [EXTRACT] ERROR: OCR extraction failed: {e}")
            log_print(f"  [EXTRACT] Error type: {type(e).__name__}")
            log_print(f"  [EXTRACT] PATH: {os.environ.get('PATH', 'NOT SET')}")
            return ""
    
    log_print(f"  [EXTRACT] Final extracted text length: {len(text.strip())} characters")
    
    # Clean up temp file if we used one
    if use_temp and actual_pdf_path.exists():
        try:
            actual_pdf_path.unlink()
            log_print(f"  [EXTRACT] Cleaned up temp file")
        except Exception as e:
            log_print(f"  [EXTRACT] WARNING: Could not delete temp file: {e}")
    
    return text.strip()


def get_file_created_date(file_path):
    """
    Get the file creation date in YYYY-MM-DD format.
    """
    try:
        stat = os.stat(file_path)
        # On macOS, st_birthtime is the creation time
        created_time = datetime.fromtimestamp(stat.st_birthtime)
        return created_time.strftime("%Y-%m-%d")
    except Exception as e:
        print(f"Warning: Could not get creation date for {file_path}: {e}")
        return datetime.now().strftime("%Y-%m-%d")


def call_chatgpt_shortcut(prompt):
    """
    Call the ChatGPT shortcut and return the extracted plain text response.
    """
    log_print("  [CHATGPT] Calling ChatGPT shortcut...")
    log_print(f"  [CHATGPT] Prompt length: {len(prompt)} characters")
    
    try:
        result = subprocess.run(
            ["shortcuts", "run", "Ask ChatGPT", "--input-path", "-"],
            input=prompt,
            capture_output=True,
            text=True,
            timeout=120  # 2 minute timeout
        )
        
        log_print(f"  [CHATGPT] Return code: {result.returncode}")
        
        if result.returncode == 0:
            log_print(f"  [CHATGPT] Response length: {len(result.stdout)} characters")
            plain_text = extract_text_from_rtf(result.stdout)
            log_print(f"  [CHATGPT] Extracted text length: {len(plain_text)} characters")
            log_print(f"  [CHATGPT] Response: {plain_text[:200]}..." if len(plain_text) > 200 else f"  [CHATGPT] Response: {plain_text}")
            return plain_text.strip()
        else:
            log_print(f"  [CHATGPT] ERROR: {result.stderr}")
            log_print(f"  [CHATGPT] Return code: {result.returncode}")
            return None
    except subprocess.TimeoutExpired:
        log_print("  [CHATGPT] ERROR: Timeout waiting for ChatGPT response")
        return None
    except Exception as e:
        log_print(f"  [CHATGPT] ERROR: Exception calling shortcut: {e}")
        log_print(f"  [CHATGPT] Traceback: {traceback.format_exc()}")
        return None


# Base path for all documents
DOCUMENTS_BASE_PATH = Path("/Users/anthonywheeler/Library/Mobile Documents/com~apple~CloudDocs/Documents")

# Category definitions with their valid subcategories
# Format: "Category": ["valid", "subcategories", ...] or None if no subcategories
CATEGORY_STRUCTURE = {
    # Medical records - subcategory is patient name
    "Medical": ["Anthony", "Hannah", "Oliver", "Roman"],
    
    # Financial categories with various subcategories
    "Financial/Bills": ["HOA", "Electric", "Gas", "Water", "Internet", "Lawn", "Storage", "Health", "Medical"],
    "Financial/Cards": ["Chase", "Target", "Sams Club"],
    "Financial/Checks": None,
    "Financial/Class Action": None,
    "Financial/Home Maintenance": ["HVAC", "Pool"],
    "Financial/Insurance": ["Auto Home", "Health Dental Vision"],
    "Financial/Investments": ["401k", "Roth IRA", "Stocks"],
    "Financial/Legal": None,
    "Financial/Mortgage": None,
    "Financial/Paystubs": None,
    "Financial/Receipts": None,  # Will use year as dynamic subcategory
    "Financial/Taxes": None,  # Will use year as dynamic subcategory
    "Financial/Tolls": None,
    "Financial/Misc": None,
    
    # Career - subcategory can be employer or type
    "Career": ["Certifications", "Resumes", "Business Cards"],
    
    # Cars - subcategory is vehicle
    "Cars": ["2021 Sequoia", "2022 Accord"],
    
    # Kids
    "Kids/School": None,
    
    # Personal
    "Personal/Government Documents": None,
    "Personal/Letters": None,
    "Personal/Spiritual": None,
    
    # Purchases
    "Purchases/Tickets": None,  # Will use year as dynamic subcategory
    "Purchases/Product Manuals": ["Appliances", "Home", "Tools", "Toys", "Music", "Baby Products", "Amazon Basics"],
    "Purchases/Other": None,
    
    # Other top-level categories
    "Sheet Music": None,
    "Recipes": None,
    "User Manuals": None,
    "Misc": None,
}


def get_folder_path_for_category(category, subcategory=None):
    """
    Given a category and optional subcategory, return the destination folder path.
    Handles special cases like year-based subcategories for Receipts/Taxes/Tickets.
    """
    base = DOCUMENTS_BASE_PATH
    
    # Parse the category (may contain "/" for nested categories like "Financial/Bills")
    category_parts = category.split("/")
    
    # Build the base path from category
    if category == "Medical":
        path = base / "Medical"
        if subcategory:
            path = path / subcategory
    
    elif category.startswith("Financial/"):
        subcat_name = category_parts[1]
        # Map category names to actual folder names
        folder_name_map = {
            "Bills": "Bills",
            "Cards": "Cards",
            "Checks": "Checks",
            "Class Action": "Class Action",
            "Home Maintenance": "Home Maintenance",
            "Insurance": "Insurance",
            "Investments": "Investments",
            "Legal": "Legal",
            "Mortgage": "Mortgage",
            "Paystubs": "Paystubs",
            "Receipts": "Receipts",
            "Taxes": "Taxes",
            "Tolls": "Tolls",
            "Misc": "Misc.",
        }
        folder_name = folder_name_map.get(subcat_name, subcat_name)
        path = base / "Financial" / folder_name
        
        if subcategory:
            # Handle special folder name mappings for subcategories
            subcat_folder_map = {
                "Sams Club": "Sam's Club",
                "Auto Home": "Encompass:Safeco",
                "Health Dental Vision": "Health:Dental:Vision",
            }
            subcat_folder = subcat_folder_map.get(subcategory, subcategory)
            path = path / subcat_folder
    
    elif category == "Career":
        path = base / "Career"
        if subcategory:
            path = path / subcategory
    
    elif category == "Cars":
        path = base / "Cars"
        if subcategory:
            path = path / subcategory
    
    elif category.startswith("Kids/"):
        path = base / "Kids" / category_parts[1]
    
    elif category.startswith("Personal/"):
        path = base / "Personal" / category_parts[1]
    
    elif category.startswith("Purchases/"):
        subcat_name = category_parts[1]
        path = base / "Purchases" / subcat_name
        if subcategory:
            path = path / subcategory
    
    elif category == "Sheet Music":
        path = base / "Sheet Music"
    
    elif category == "Recipes":
        path = base / "Recipes"
    
    elif category == "User Manuals":
        path = base / "User Manuals"
    
    elif category == "Misc":
        path = base / "Misc. "  # Note: has trailing space in actual folder name
    
    else:
        # Default to Misc
        path = base / "Misc. "
    
    return path


def get_all_categories_for_prompt():
    """
    Generate the category list and descriptions for the classification prompt.
    """
    return """
=== MAIN CATEGORIES ===

MEDICAL (Subcategory = Patient Name)
- Medical records, lab results, doctor visits, prescriptions, dental records, vision exams
- Subcategories: Anthony, Hannah, Oliver, Roman
- Example: "Medical/Oliver" for Oliver's medical records

FINANCIAL/BILLS (Subcategory = Bill Type)
- Recurring bills and utility statements
- Subcategories: HOA, Electric, Gas, Water, Internet, Lawn, Storage, Health, Medical
- Example: "Financial/Bills/Electric" for electric bills

FINANCIAL/CARDS (Subcategory = Card Provider)
- Credit card statements and card-related documents
- Subcategories: Chase, Target, Sams Club
- Example: "Financial/Cards/Chase" for Chase card statements

FINANCIAL/CHECKS
- Check images, check copies, deposited checks
- No subcategory needed

FINANCIAL/CLASS ACTION
- Class action lawsuit documents, settlements
- No subcategory needed

FINANCIAL/HOME MAINTENANCE (Subcategory = Type)
- Home repair invoices, maintenance records, contractor receipts
- Subcategories: HVAC, Pool
- Example: "Financial/Home Maintenance/Pool" for pool service

FINANCIAL/INSURANCE (Subcategory = Insurance Type)
- Insurance policies, declarations, claims
- Subcategories: Auto Home, Health Dental Vision
- Example: "Financial/Insurance/Auto Home" for auto or homeowners insurance

FINANCIAL/INVESTMENTS (Subcategory = Account Type)
- Investment statements, account documents
- Subcategories: 401k, Roth IRA, Stocks
- Example: "Financial/Investments/401k" for 401k statements

FINANCIAL/LEGAL
- Legal documents, contracts, agreements (non-insurance, non-mortgage)
- No subcategory needed

FINANCIAL/MORTGAGE
- Mortgage documents, loan statements, property paperwork
- No subcategory needed

FINANCIAL/PAYSTUBS
- Pay stubs, salary statements, W-2s, employment income
- No subcategory needed

FINANCIAL/RECEIPTS (Subcategory = Year)
- Purchase receipts, transaction receipts
- Subcategory should be the year (e.g., 2024, 2025)
- Example: "Financial/Receipts/2025" for 2025 receipts

FINANCIAL/TAXES (Subcategory = Tax Year)
- Tax returns, tax forms, tax-related documents
- Subcategory should be the tax year (e.g., 2023, 2024)
- Example: "Financial/Taxes/2024" for 2024 tax documents

FINANCIAL/TOLLS
- Toll road receipts, toll statements
- No subcategory needed

FINANCIAL/MISC
- Other financial documents that don't fit elsewhere
- No subcategory needed

CAREER (Subcategory = Type)
- Employment documents, professional certifications, resumes
- Subcategories: Certifications, Resumes, Business Cards
- Example: "Career/Certifications" for professional certifications
- Note: For employer-specific docs, use just "Career" with no subcategory

CARS (Subcategory = Vehicle)
- Vehicle titles, registration, non-financial car documents
- Subcategories: 2021 Sequoia, 2022 Accord
- Example: "Cars/2022 Accord" for 2022 Honda Accord documents

KIDS/SCHOOL
- School records, report cards, transcripts, education documents
- No subcategory needed

PERSONAL/GOVERNMENT DOCUMENTS
- Passports, birth certificates, social security, government IDs
- No subcategory needed

PERSONAL/LETTERS
- Personal correspondence, letters, cards
- No subcategory needed

PERSONAL/SPIRITUAL
- Religious documents, church records, spiritual materials
- No subcategory needed

PURCHASES/TICKETS (Subcategory = Year)
- Event tickets, concert tickets, admission tickets
- Subcategory should be the year (e.g., 2024, 2025)
- Example: "Purchases/Tickets/2025" for 2025 event tickets

PURCHASES/PRODUCT MANUALS (Subcategory = Product Category)
- User manuals, instruction booklets, product documentation
- Subcategories: Appliances, Home, Tools, Toys, Music, Baby Products, Amazon Basics
- Example: "Purchases/Product Manuals/Appliances" for appliance manuals

PURCHASES/OTHER
- General purchase confirmations, shipping notifications, order receipts
- No subcategory needed

SHEET MUSIC
- Musical scores, chord sheets, sheet music
- No subcategory needed

RECIPES
- Recipe documents, cooking instructions
- No subcategory needed

USER MANUALS
- General user manuals (non-product specific)
- No subcategory needed

MISC
- Anything that doesn't fit the above categories
- No subcategory needed
"""


def classify_file_category(file_contents):
    """
    Ask ChatGPT to classify the file into a category and subcategory based on its contents.
    Returns a tuple of (category, subcategory) where subcategory may be None.
    """
    category_descriptions = get_all_categories_for_prompt()
    
    prompt = f"""Your task is to classify a document into the appropriate category and subcategory.

IMPORTANT: Read the document contents carefully and determine:
1. The main CATEGORY this document belongs to
2. The SUBCATEGORY if applicable (based on the rules below)

{category_descriptions}

=== RESPONSE FORMAT ===
Respond with ONLY the category and subcategory in this exact format:
Category/Subcategory

If no subcategory applies, respond with just:
Category

Examples of valid responses:
- Medical/Anthony
- Medical/Oliver
- Financial/Receipts/2025
- Financial/Bills/Electric
- Financial/Insurance/Auto Home
- Financial/Taxes/2024
- Career/Certifications
- Cars/2022 Accord
- Purchases/Tickets/2025
- Purchases/Product Manuals/Appliances
- Financial/Checks
- Personal/Government Documents
- Misc

=== DOCUMENT CONTENTS ===
{file_contents[:5000]}

=== YOUR RESPONSE (category/subcategory only, nothing else) ==="""
    
    result = call_chatgpt_shortcut(prompt)
    
    if not result:
        return None, None
    
    # Parse the result into category and subcategory
    result = result.strip().strip('"').strip("'")
    parts = result.split("/")
    
    if len(parts) == 1:
        return parts[0], None
    elif len(parts) == 2:
        # Could be "Medical/Anthony" or "Financial/Bills"
        # Check if this is a nested category like "Financial/Bills"
        potential_category = f"{parts[0]}/{parts[1]}"
        if potential_category in CATEGORY_STRUCTURE:
            return potential_category, None
        else:
            return parts[0], parts[1]
    elif len(parts) >= 3:
        # Could be "Financial/Bills/Electric" or "Financial/Receipts/2025"
        potential_category = f"{parts[0]}/{parts[1]}"
        if potential_category in CATEGORY_STRUCTURE:
            return potential_category, "/".join(parts[2:])
        else:
            return parts[0], "/".join(parts[1:])
    
    return result, None


def log_file_move(log_file_path, old_filename, new_filename, destination):
    """
    Log a file move event to the CSV file. Most recent events are added at the top.
    """
    log_file_path = Path(log_file_path)
    
    # Check if CSV exists and read existing entries
    existing_entries = []
    if log_file_path.exists():
        with open(log_file_path, 'r', newline='', encoding='utf-8') as f:
            reader = csv.reader(f)
            # Skip header if it exists
            try:
                header = next(reader)
                if header != ['DateTime', 'Old Filename', 'New Filename', 'Destination']:
                    # If header doesn't match, treat first row as data
                    existing_entries.append(header)
            except StopIteration:
                pass
            existing_entries.extend(list(reader))
    
    # Create new entry
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    new_entry = [timestamp, old_filename, new_filename, str(destination)]
    
    # Write header and new entry first, then existing entries
    with open(log_file_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['DateTime', 'Old Filename', 'New Filename', 'Destination'])
        writer.writerow(new_entry)
        writer.writerows(existing_entries)


def move_file_to_destination(source_file, dest_folder, log_file_path, original_filename=None):
    """
    Move a file to the destination folder and log the move.
    Returns True if successful, False otherwise.
    
    Args:
        source_file: Path to the file to move
        dest_folder: Destination folder path
        log_file_path: Path to the CSV log file
        original_filename: Original filename before any renaming (for logging)
    """
    log_print(f"  [MOVE] Source: {source_file}")
    log_print(f"  [MOVE] Destination folder: {dest_folder}")
    
    if not dest_folder:
        log_print("  ✗ ERROR: No destination folder specified, skipping move")
        return False
    
    try:
        # Create destination folder if it doesn't exist
        log_print(f"  [MOVE] Creating destination folder if needed...")
        dest_folder.mkdir(parents=True, exist_ok=True)
        log_print(f"  [MOVE] Destination folder exists: ✓")
        
        # Check if file already exists in destination
        dest_file = dest_folder / source_file.name
        log_print(f"  [MOVE] Target file path: {dest_file}")
        if dest_file.exists() and dest_file != source_file:
            log_print(f"  ✗ ERROR: File '{source_file.name}' already exists in destination, skipping move")
            return False
        
        # Move the file
        old_filename = original_filename if original_filename else source_file.name
        new_filename = source_file.name
        log_print(f"  [MOVE] Moving file...")
        log_print(f"  [MOVE] Old filename: {old_filename}")
        log_print(f"  [MOVE] New filename: {new_filename}")
        source_file.rename(dest_file)
        log_print(f"  ✓ Successfully moved to: {dest_folder}")
        
        # Log the move
        log_print(f"  [MOVE] Logging to CSV...")
        log_file_move(log_file_path, old_filename, new_filename, dest_folder)
        log_print(f"  [MOVE] CSV log updated")
        
        return True
    except Exception as e:
        log_print(f"  ✗ ERROR moving file: {e}")
        log_print(f"  [MOVE] Traceback: {traceback.format_exc()}")
        return False


def generate_filename(file_contents, created_date):
    """
    Ask ChatGPT to generate a filename following the format: yyyy-mm-dd - File Summary
    Date priority: appointment/due date > header/letterhead date > file created date
    Summary should be specific and include relevant details extracted from the document.
    Returns just the filename.
    """
    prompt = f"""Your task is to analyze a document and generate a descriptive filename.

IMPORTANT: You must extract ALL information from the DOCUMENT CONTENTS provided below. Do NOT use any names, dates, or details from my instructions or examples. The examples below are ONLY to show you the FORMAT - the actual content must come from the document.

=== OUTPUT FORMAT ===
Generate a filename in this exact format:
"YYYY-MM-DD - Brief Description"

=== DATE SELECTION RULES ===
Choose the date using this priority order (use the FIRST one you find in the document):
1. Appointment date, service date, or due date mentioned in the document
2. Date printed on the document header, letterhead, or statement date
3. Invoice date or transaction date
4. If no date is found in the document, use the file created date: {created_date}

The date MUST be in YYYY-MM-DD format (e.g., 2025-01-15).

=== DESCRIPTION RULES ===
The description should be 2-8 words that specifically describe WHAT this document is about. Extract this information from the document contents.

WHEN TO INCLUDE A PERSON'S NAME:
- YES: Medical records, lab results, doctor visits, prescriptions (the patient's name matters)
- YES: School records, report cards, transcripts (the student's name matters)
- YES: Personal legal documents like wills, immigration papers (the person's name matters)
- YES: Employment records specific to one person
- NO: Product purchases, shipments, returns, warranties (the product matters, not who bought it)
- NO: Utility bills, subscriptions, memberships (the service matters, not the account holder)
- NO: General receipts, invoices for products/services
- NO: Home repairs, maintenance records
- NO: Insurance policies, unless it's a claim for a specific person's medical care

WHAT TO INCLUDE IN THE DESCRIPTION:
- Be specific about WHAT the document is (not just "receipt" but what it's for)
- Include the product name, service type, or procedure when relevant
- Include the company or provider name if it adds clarity
- If there's a person's name AND it's relevant per the rules above, include their first name

=== EXAMPLE FILENAMES (FORMAT REFERENCE ONLY - DO NOT USE THESE NAMES/DETAILS) ===

Medical/Healthcare (include patient name):
- "2025-03-15 - John Annual Physical Results"
- "2025-06-22 - Sarah Allergy Test Results"
- "2025-08-10 - Mike Emergency Room Visit"
- "2025-01-05 - Emma Dental Cleaning Receipt"
- "2025-11-30 - Lisa Bloodwork Lab Results"
- "2025-04-18 - Tom Physical Therapy Invoice"

Products/Shipments/Warranties (NO person name needed):
- "2025-02-14 - Dyson Vacuum Warranty Registration"
- "2025-07-03 - iPhone Screen Repair Receipt"
- "2025-09-28 - Maytronics Pool Robot Return Label"
- "2025-05-11 - Samsung TV Purchase Invoice"
- "2025-12-01 - Amazon Return Confirmation"
- "2025-03-22 - Laptop Battery Replacement"

Bills/Utilities/Subscriptions (NO person name needed):
- "2025-01-15 - Electric Bill January"
- "2025-02-01 - Netflix Subscription Receipt"
- "2025-06-30 - Internet Service Invoice"
- "2025-08-15 - Water Utility Statement"
- "2025-10-01 - Gym Membership Renewal"
- "2025-04-05 - Cell Phone Bill"

Financial/Banking (NO person name needed):
- "2025-03-31 - Bank Statement Q1"
- "2025-04-15 - Tax Return Confirmation"
- "2025-07-20 - Credit Card Statement July"
- "2025-12-15 - Investment Account Summary"
- "2025-09-01 - Mortgage Payment Receipt"

Insurance (include name only for personal claims):
- "2025-05-10 - Auto Insurance Policy Renewal"
- "2025-08-22 - Homeowners Insurance Declaration"
- "2025-02-28 - David Medical Claim EOB"
- "2025-11-15 - Health Insurance Card"

Legal/Government (include name when document is person-specific):
- "2025-01-20 - Vehicle Registration Renewal"
- "2025-06-15 - Property Tax Statement"
- "2025-09-05 - Amy Passport Renewal Application"
- "2025-03-10 - Business License Certificate"

Education (include student name):
- "2025-05-30 - Kevin Report Card Spring"
- "2025-08-20 - Maria College Transcript"
- "2025-12-10 - Jake Tuition Invoice Fall"

Home/Repairs (NO person name needed):
- "2025-04-25 - HVAC Maintenance Invoice"
- "2025-07-18 - Plumber Service Receipt"
- "2025-10-30 - Roof Inspection Report"
- "2025-02-05 - Appliance Repair Quote"

=== YOUR TASK ===
1. Read the document contents below carefully
2. Extract the relevant date from the document (or use the file created date if none found)
3. Determine what type of document this is
4. Create a specific, descriptive filename following the rules above
5. Respond with ONLY the filename, nothing else

=== DOCUMENT CONTENTS ===
{file_contents[:5000]}

=== FILE CREATED DATE (use only if no date found in document) ===
{created_date}

=== YOUR RESPONSE (filename only, no quotes, no explanation) ==="""
    
    return call_chatgpt_shortcut(prompt)


def main():
    # Fixed path - folder is "00 - Scan Inbox"
    scan_folder = Path("/Users/anthonywheeler/Library/Mobile Documents/com~apple~CloudDocs/Documents/00 - Scan Inbox")
    
    # Set up logging first
    log_path = setup_logging(scan_folder)
    if not log_path:
        print("ERROR: Could not set up logging")
        return
    
    try:
        log_print(f"Scan folder: {scan_folder}")
        
        if not scan_folder.exists():
            log_print(f"ERROR: Folder does not exist: {scan_folder}")
            return
        
        log_print(f"Scan folder exists: ✓")
        
        # Get all PDF files in the folder
        log_print("Searching for PDF files...")
        pdf_files = list(scan_folder.glob("*.pdf"))
        
        if not pdf_files:
            log_print(f"No PDF files found in {scan_folder}")
            return
        
        log_print(f"Found {len(pdf_files)} PDF file(s) to process")
        for pdf_file in pdf_files:
            log_print(f"  - {pdf_file.name}")
        log_print()
        
        # Set up CSV log file path
        log_file_path = scan_folder / "file_move_log.csv"
        log_print(f"CSV log file: {log_file_path}")
    
        # Process each PDF
        for pdf_file in pdf_files:
            log_print("=" * 80)
            log_print(f"Processing: {pdf_file.name}")
            log_print(f"Full path: {pdf_file}")
            log_print("=" * 80)
            
            # Extract text from PDF
            log_print("\n[1] Extracting text from PDF...")
            file_contents = extract_text_from_pdf(pdf_file)
            if not file_contents:
                log_print(f"WARNING: Could not extract text from {pdf_file.name}, skipping...")
                continue
            
            log_print(f"Extracted {len(file_contents)} characters of text")
        
            # Check if file already follows the desired format (manual override)
            # Pattern: yyyy-mm-dd - description.pdf
            log_print("\n[CHECK] Checking if file already follows desired format...")
            filename_pattern = re.match(r'^\d{4}-\d{2}-\d{2}\s+-\s+.+\.pdf$', pdf_file.name)
            if filename_pattern:
                log_print(f"[SKIP] File already follows desired format (yyyy-mm-dd - summary), treating as manual override")
                log_print(f"  Current filename: {pdf_file.name}")
                log_print(f"  Skipping rename - file name will remain unchanged")
                
                # Still classify and move the file
                log_print("\n[2] Classifying file category...")
                category, subcategory = classify_file_category(file_contents)
                if category:
                    if subcategory:
                        log_print(f"Category: {category}/{subcategory}")
                    else:
                        log_print(f"Category: {category}")
                    dest_folder = get_folder_path_for_category(category, subcategory)
                    log_print(f"Destination folder: {dest_folder}")
                    
                    # Move the file
                    log_print("\n[3] Moving file to destination...")
                    move_file_to_destination(pdf_file, dest_folder, log_file_path, pdf_file.name)
                else:
                    log_print("ERROR: Failed to get category classification, file will remain in inbox")
                
                log_print()
                continue
        
            # Get file creation date
            log_print("\n[2] Getting file creation date...")
            created_date = get_file_created_date(pdf_file)
            log_print(f"File created date: {created_date}")
            
            # Classify file category
            log_print("\n[3] Classifying file category...")
            category, subcategory = classify_file_category(file_contents)
            if category:
                if subcategory:
                    log_print(f"Category: {category}/{subcategory}")
                else:
                    log_print(f"Category: {category}")
                dest_folder = get_folder_path_for_category(category, subcategory)
                log_print(f"Destination folder: {dest_folder}")
            else:
                log_print("ERROR: Failed to get category classification")
                dest_folder = None
            
            # Generate filename
            log_print("\n[4] Generating filename...")
            suggested_filename = generate_filename(file_contents, created_date)
            if not suggested_filename:
                log_print("ERROR: Failed to generate filename, skipping rename...")
                continue
            
            # Clean up the filename (remove any quotes, ensure .pdf extension)
            suggested_filename = suggested_filename.strip().strip('"').strip("'")
            if not suggested_filename.endswith('.pdf'):
                suggested_filename += '.pdf'
            
            log_print(f"Suggested filename: {suggested_filename}")
            
            # Track original filename and current file path
            original_filename = pdf_file.name
            current_file_path = pdf_file
            
            # Rename the file if needed
            log_print("\n[RENAME] Attempting to rename file...")
            if pdf_file.name == suggested_filename:
                log_print(f"  File already has correct name, skipping rename")
            else:
                # Rename the file
                new_file_path = pdf_file.parent / suggested_filename
                log_print(f"  Old name: {pdf_file.name}")
                log_print(f"  New name: {suggested_filename}")
                log_print(f"  New path: {new_file_path}")
                
                # Check if target file already exists
                if new_file_path.exists() and new_file_path != pdf_file:
                    log_print(f"  WARNING: Target file '{suggested_filename}' already exists, skipping rename")
                else:
                    try:
                        pdf_file.rename(new_file_path)
                        current_file_path = new_file_path  # Update to new path after rename
                        log_print(f"  ✓ Successfully renamed to: {suggested_filename}")
                    except Exception as e:
                        log_print(f"  ✗ ERROR renaming file: {e}")
                        log_print(f"  Traceback: {traceback.format_exc()}")
                        current_file_path = pdf_file  # Keep original path if rename failed
            
            # Move file to destination folder
            if dest_folder:
                log_print("\n[5] Moving file to destination...")
                move_file_to_destination(current_file_path, dest_folder, log_file_path, original_filename)
            else:
                log_print("\n[5] No destination folder determined, file will remain in inbox")
            
            log_print()
        
    except Exception as e:
        log_print("=" * 80)
        log_print(f"FATAL ERROR: {e}")
        log_print(f"Traceback:")
        log_print(traceback.format_exc())
        log_print("=" * 80)
    finally:
        if LOG_FILE_PATH:
            log_print(f"\nDebug log saved to: {LOG_FILE_PATH}")
        close_logging()
        if LOG_FILE_PATH:
            print(f"\nDebug log saved to: {LOG_FILE_PATH}")


if __name__ == "__main__":
    main()