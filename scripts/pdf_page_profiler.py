# scripts/pdf_page_profiler.py
"""
Phase B — Step 2: Page-Level Profiling
Saare PDFs (original + converted) ke har page ko 5 classes mein todo.
Output: distribution report + manifest update (page_profile).
"""

import fitz
import json
import logging
from pathlib import Path
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from tqdm import tqdm

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(message)s")
log = logging.getLogger("profiler")

MANIFEST = Path("/mnt/inam/RAG_SYSTEM/data/processing_manifest.json")
WORKERS  = 8   # PyMuPDF C-level hai → threads I/O parallel karte hain

# ── Thresholds (har value ka reason niche table mein) ──
SCANNED_TEXT_CHARS   = 100   # digital page pe 100+ chars pakka hote hain
SLIDE_MAX_TEXT       = 800   # slide = bullets, essay nahi
SLIDE_MAX_HEADINGS   = 2     # slide pe 1-2 headings max
SLIDE_IMG_AREA_RATIO = 0.30  # slide/diagram ka ~1/3 area image
TABLE_AREA_RATIO     = 0.30  # page ka 1/3 table = table-centric


def classify_page(page) -> dict:
    """Ek page ka profile — fast heuristics, no ML."""
    
    text = page.get_text()
    text_chars = len(text.strip())
    page_area = page.rect.width * page.rect.height
    
    # ── Image area ratio ──
    img_area, img_count = 0.0, 0
    for info in page.get_image_info():
        x0, y0, x1, y1 = info["bbox"]
        img_area += (x1 - x0) * (y1 - y0)
        img_count += 1
    img_ratio = img_area / page_area if page_area else 0
    
    # ── Table area ratio ──
    tables = page.find_tables().tables
    table_area = sum((t.bbox[2]-t.bbox[0]) * (t.bbox[3]-t.bbox[1])
                     for t in tables)
    table_ratio = table_area / page_area if page_area else 0
    
    # ── Heading count (font-size heuristic) ──
    heading_count = 0
    if text_chars >= SCANNED_TEXT_CHARS:
        sizes = [s["size"]
                 for b in page.get_text("dict")["blocks"] if b["type"] == 0
                 for line in b["lines"]
                 for s in line["spans"] if s["text"].strip()]
        if sizes:
            median = sorted(sizes)[len(sizes) // 2]
            heading_count = sum(1 for s in sizes if s > median * 1.25)
    
    # ── Classification (ORDER MATTERS — pehle scanned, phir slide) ──
    if text_chars < SCANNED_TEXT_CHARS:
        cls = "scanned"
    elif (img_ratio >= SLIDE_IMG_AREA_RATIO
          and text_chars < SLIDE_MAX_TEXT
          and heading_count <= SLIDE_MAX_HEADINGS):
        cls = "slide_style"
    elif table_ratio >= TABLE_AREA_RATIO:
        cls = "table_heavy"
    elif len(tables) > 0:
        cls = "text_with_tables"
    else:
        cls = "text_structured"
    
    return {"class": cls, "text_chars": text_chars,
            "images": img_count, "tables": len(tables),
            "headings": heading_count}


def profile_pdf(item):
    path, origin, file_hash = item
    result = {"hash": file_hash, "path": str(path),
              "origin": origin, "pages": None, "error": None}
    try:
        doc = fitz.open(path)
        result["pages"] = [classify_page(p) for p in doc]
        doc.close()
    except Exception as e:   # encrypted/corrupt → skip with log
        result["error"] = str(e)
    return result


def collect_pdfs(manifest):
    """Manifest se saare ready PDFs uthao (original + converted)."""
    pdfs = []
    for h, e in manifest.items():
        if e.get("lane") == "pdf":
            p = Path(e["path"])
            if p.exists():
                pdfs.append((p, "original", h))
        elif e.get("convert_status") == "done" and e.get("converted_pdf"):
            p = Path(e["converted_pdf"])
            if p.exists():
                pdfs.append((p, "converted", h))
    return pdfs


def main():
    manifest = json.loads(MANIFEST.read_text())
    pdfs = collect_pdfs(manifest)
    log.info(f"PDFs to profile: {len(pdfs)}")
    
    class_counter  = Counter()
    origin_counter = Counter()
    total_pages = 0
    
    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        futures = [pool.submit(profile_pdf, item) for item in pdfs]
        
        for fut in tqdm(as_completed(futures), total=len(futures),
                        desc="Profiling"):
            res = fut.result()
            
            if res["error"]:
                log.warning(f"SKIP {res['path']} | {res['error']}")
                continue   # encrypted PDF yahan girega — password pending
            
            summary = Counter(p["class"] for p in res["pages"])
            class_counter.update(summary)
            for cls, cnt in summary.items():
                origin_counter[(res["origin"], cls)] += cnt
            total_pages += len(res["pages"])
            
            # Manifest update — O(1) via hash key
            manifest[res["hash"]]["page_profile"] = dict(summary)
            manifest[res["hash"]]["page_count"] = len(res["pages"])
    
    MANIFEST.write_text(json.dumps(manifest, indent=2))
    
    # ── Final Report ──
    print(f"\n{'='*52}")
    print(f" PAGE PROFILE — {len(pdfs)} PDFs | {total_pages} pages")
    print(f"{'='*52}")
    print(f"{'Class':<18}{'Pages':>7}{'%':>8}")
    print("-" * 33)
    for cls, cnt in class_counter.most_common():
        print(f"{cls:<18}{cnt:>7}{cnt/total_pages*100:>7.1f}%")
    
    print("\nBy origin:")
    for (origin, cls), cnt in sorted(origin_counter.items()):
        print(f"  {origin:<10} {cls:<18} {cnt}")


if __name__ == "__main__":
    main()