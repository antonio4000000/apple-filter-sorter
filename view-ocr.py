#!/usr/bin/env python3
"""
Simple script to view OCR/text extraction results from PDFs.
Useful for debugging what text is being extracted from documents.
"""

import sys
from pathlib import Path


def extract_text_from_pdf(pdf_path):
    """
    Extract text content from a PDF file.
    Tries direct text extraction first, then falls back to OCR for image-based PDFs.
    """
    text = ""
    method_used = []
    
    # Try PyPDF2 first
    try:
        import PyPDF2
        with open(pdf_path, 'rb') as file:
            pdf_reader = PyPDF2.PdfReader(file)
            for page in pdf_reader.pages:
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n"
        if text.strip():
            method_used.append("PyPDF2")
    except ImportError:
        pass
    except Exception as e:
        print(f"  PyPDF2 extraction failed: {e}")
    
    # Try pdfplumber if PyPDF2 didn't work or returned little text
    if len(text.strip()) < 50:
        try:
            import pdfplumber
            with pdfplumber.open(pdf_path) as pdf:
                text = ""
                for page in pdf.pages:
                    page_text = page.extract_text()
                    if page_text:
                        text += page_text + "\n"
            if text.strip():
                method_used.append("pdfplumber")
        except ImportError:
            pass
        except Exception as e:
            print(f"  pdfplumber extraction failed: {e}")
    
    # If we still have very little text, try OCR (for scanned/image-based PDFs)
    if len(text.strip()) < 50:
        print("  Text extraction returned little/no text, trying OCR...")
        try:
            import pytesseract
            from pdf2image import convert_from_path
            
            # Convert PDF pages to images
            images = convert_from_path(pdf_path, dpi=300)
            text = ""
            for i, image in enumerate(images):
                print(f"  OCR processing page {i+1}/{len(images)}...")
                page_text = pytesseract.image_to_string(image)
                if page_text:
                    text += page_text + "\n"
            if text.strip():
                method_used.append("OCR (Tesseract)")
        except ImportError:
            print("  OCR libraries not available. Install with: pip install pytesseract pdf2image")
            print("  Also install Tesseract: brew install tesseract (on macOS)")
            return "", []
        except Exception as e:
            print(f"  OCR extraction failed: {e}")
            return "", []
    
    return text.strip(), method_used


def main():
    # Default folder path
    scan_folder = Path("/Users/anthonywheeler/Library/Mobile Documents/com~apple~CloudDocs/Documents/00 - Scan Inbox")
    
    # Allow specifying a file or folder as argument
    if len(sys.argv) > 1:
        input_path = Path(sys.argv[1])
        if input_path.is_file() and input_path.suffix.lower() == '.pdf':
            pdf_files = [input_path]
        elif input_path.is_dir():
            scan_folder = input_path
            pdf_files = list(scan_folder.glob("*.pdf"))
        else:
            print(f"Error: {input_path} is not a PDF file or directory")
            return
    else:
        # Get all PDF files in the default folder
        pdf_files = list(scan_folder.glob("*.pdf"))
    
    if not pdf_files:
        print(f"No PDF files found in {scan_folder}")
        return
    
    print(f"Found {len(pdf_files)} PDF file(s) to process\n")
    
    # Process each PDF
    for pdf_file in pdf_files:
        print("=" * 80)
        print(f"File: {pdf_file.name}")
        print("=" * 80)
        
        # Extract text
        print("\nExtracting text...")
        text, methods = extract_text_from_pdf(pdf_file)
        
        if methods:
            print(f"Extraction method(s): {', '.join(methods)}")
        
        if not text:
            print("\n[NO TEXT EXTRACTED]")
            print()
            continue
        
        print(f"\nExtracted {len(text)} characters of text\n")
        print("-" * 80)
        print("EXTRACTED TEXT:")
        print("-" * 80)
        print(text)
        print("-" * 80)
        print()
        
        # Optionally save to a text file
        if len(sys.argv) > 2 and sys.argv[2] == '--save':
            output_file = pdf_file.with_suffix('.txt')
            output_file.write_text(text, encoding='utf-8')
            print(f"Saved to: {output_file}\n")


if __name__ == "__main__":
    main()

