# scripts/fix_manifest_profiles.py
"""
Baaki bache hue PDFs ko profile karo aur manifest update karo.
"""
import fitz, json
from pathlib import Path

MANIFEST = Path("/mnt/inam/RAG_SYSTEM/data/processing_manifest.json")

def main():
    manifest = json.loads(MANIFEST.read_text())
    updated_count = 0

    for file_hash, entry in manifest.items():
        # Agar page_profile already hai, toh skip karo
        if "page_profile" in entry:
            continue
            
        pdf_path = entry.get("converted_pdf") or entry.get("path")
        if not pdf_path or not Path(pdf_path).exists():
            continue

        # Sirf PDFs ko profile karo
        if Path(pdf_path).suffix.lower() != ".pdf":
            continue

        try:
            doc = fitz.open(pdf_path)
            scanned_pages = 0
            for page in doc:
                text = page.get_text()
                if len(text.strip()) < 100:  # Simple scanned detection
                    scanned_pages += 1
            doc.close()

            if scanned_pages > 0:
                entry["page_profile"] = {"scanned": scanned_pages}
                entry["page_count"] = len(doc) if 'doc' in locals() else scanned_pages
                updated_count += 1
                
        except Exception as e:
            print(f"Error processing {pdf_path}: {e}")

    MANIFEST.write_text(json.dumps(manifest, indent=2))
    print(f"✅ Manifest updated: {updated_count} new files profiled.")

if __name__ == "__main__":
    main()