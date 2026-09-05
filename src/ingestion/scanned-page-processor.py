# scripts/ocr_scanned_pages.py
"""
Phase C — OCR Pipeline for Scanned Pages
112 pages → text extraction → structured output
"""

import fitz
import pytesseract
from PIL import Image, ImageFilter
import io
from pathlib import Path
import json
from tqdm import tqdm

MANIFEST = Path("/mnt/inam/RAG_SYSTEM/data/processing_manifest.json")
OCR_OUTPUT_DIR = Path("/mnt/inam/RAG_SYSTEM/data/ocr_output")


def enhanced_ocr_page(page, page_num: int) -> dict:
    """
    Layout-aware OCR:
    1. Detect regions (heading, paragraph, table)
    2. OCR each region separately
    3. Preserve structure
    """
    
    pix = page.get_pixmap(dpi=300)
    img = Image.open(io.BytesIO(pix.tobytes("png")))
    
    # Preprocessing for better OCR
    img = img.convert('L')  # Grayscale
    img = img.filter(ImageFilter.SHARPEN)
    
    # Layout detection (simple heuristic)
    width, height = img.size
    
    regions = [
        {"type": "heading", "bbox": (0, 0, width, height // 8)},
        {"type": "body", "bbox": (0, height // 8, width, height * 7 // 8)},
        {"type": "footer", "bbox": (0, height * 7 // 8, width, height)},
    ]
    
    ocr_results = []
    
    for region in regions:
        crop = img.crop(region["bbox"])
        
        # Region-specific PSM (Page Segmentation Mode)
        psm = {
            "heading": 5,   # Single block of text
            "body": 6,      # Uniform block
            "footer": 12    # Sparse text
        }[region["type"]]
        
        text = pytesseract.image_to_string(
            crop,
            lang='eng+hin',
            config=f'--psm {psm}'
        )
        
        if text.strip():
            ocr_results.append({
                "region": region["type"],
                "text": text.strip()
            })
    
    return {
        "regions": ocr_results,
        "page_num": page_num,
        "combined_text": "\n\n".join(r["text"] for r in ocr_results)
    }

def ocr_page(page, page_num: int, dpi: int = 300) -> dict:
    """
    Scanned page ko OCR karo.
    
    Returns:
    {
        "text": extracted_text,
        "confidence": avg_confidence,
        "language": detected_lang,
        "page_num": int
    }
    """
    
    # High-res render (300 DPI = good OCR quality)
    pix = page.get_pixmap(dpi=dpi)
    img = Image.open(io.BytesIO(pix.tobytes("png")))
    
    # OCR with Hindi + English (aapke context ke hisaab se)
    data = pytesseract.image_to_data(
        img,
        lang='eng+hin',
        output_type=pytesseract.Output.DICT
    )
    
    # Text extract + confidence calculate
    text_lines = []
    confidences = []
    
    for i in range(len(data['text'])):
        text = data['text'][i].strip()
        if text:
            text_lines.append(text)
            conf = int(data['conf'][i])
            if conf >= 0:  # -1 = no text
                confidences.append(conf)
    
    avg_conf = sum(confidences) / len(confidences) if confidences else 0
    
    return {
        "text": "\n".join(text_lines),
        "confidence": avg_conf,
        "language": "eng+hin",
        "page_num": page_num,
        "word_count": len(text_lines)
    }


def process_scanned_pdfs():
    """Saare scanned pages ko OCR karo."""
    
    manifest = json.loads(MANIFEST.read_text())
    OCR_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    
    # Filter: sirf scanned pages wale PDFs
    scanned_pdfs = []
    for h, entry in manifest.items():
        if entry.get("page_profile", {}).get("scanned", 0) > 0:
            pdf_path = entry.get("converted_pdf") or entry.get("path")
            if pdf_path and Path(pdf_path).exists():
                scanned_pdfs.append((h, pdf_path, entry))
    
    print(f"PDFs with scanned pages: {len(scanned_pdfs)}")
    
    results = []
    
    for file_hash, pdf_path, entry in tqdm(scanned_pdfs, desc="OCR"):
        doc = fitz.open(pdf_path)
        
        ocr_results = []
        ocr_results_img = []
        for page_num, page in enumerate(doc, 1):
            ocr_result = ocr_page(page, page_num)
            ocr_result_img = enhanced_ocr_page(page, page_num)
            ocr_results_img.append(ocr_result_img) 
            ocr_results.append(ocr_result)
        
        doc.close()
        
        # Save OCR output
        output_file = OCR_OUTPUT_DIR / f"{file_hash}_ocr.json"
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump({
                "file_hash": file_hash,
                "source_pdf": pdf_path,
                "ocr_results": ocr_results,
                "total_pages": len(ocr_results)
            }, f, ensure_ascii=False, indent=2)
        
        # Manifest update
        manifest[file_hash]["ocr_status"] = "done"
        manifest[file_hash]["ocr_output"] = str(output_file)
        
        results.append({
            "file": pdf_path,
            "pages": len(ocr_results),
            "avg_confidence": sum(r["confidence"] for r in ocr_results) / len(ocr_results)
        })
    
    # Save updated manifest
    MANIFEST.write_text(json.dumps(manifest, indent=2))
    
    # Report
    print(f"\n{'='*60}")
    print(f" OCR COMPLETE — {len(results)} PDFs processed")
    print(f"{'='*60}")
    
    total_pages = sum(r["pages"] for r in results)
    avg_conf = sum(r["avg_confidence"] for r in results) / len(results) if results else 0
    
    print(f"Total pages OCR'd: {total_pages}")
    print(f"Average confidence: {avg_conf:.1f}%")
    print(f"Output directory: {OCR_OUTPUT_DIR}")


if __name__ == "__main__":
    process_scanned_pdfs()