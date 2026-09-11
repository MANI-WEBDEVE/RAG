# scripts/fix_manifest_profiles.py
"""
Baaki bache hue PDFs ko profile karo aur manifest update karo.
Bug Fix: page_count document close karne se pehle calculate kiya.
"""
import fitz, json
from pathlib import Path

MANIFEST = Path("/mnt/inam/RAG_SYSTEM/data/processing_manifest.json")

def main():
    manifest = json.loads(MANIFEST.read_text())
    print(f"Total entries in manifest: {len(manifest)}")
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
            
            # ✅ FIX: Length pehle nikalo jab document OPEN hai
            page_count = len(doc) 
            print(page_count)
            scanned_pages = 0
            for page in doc:
                text = page.get_text()
                print(len(text))
                if len(text.strip()) < 10:  # Simple scanned detection
                    scanned_pages += 1
                    
            doc.close()  # Ab safe hai close karna

            if scanned_pages > 0:
                entry["page_profile"] = {"scanned": scanned_pages}
                entry["page_count"] = page_count  # ✅ FIX: Saved variable use kiya
                updated_count += 1
                print(f"✅ Profiled: {Path(pdf_path).name} (Scanned: {scanned_pages}/{page_count})")
                
        except Exception as e:
            print(f" Error processing {Path(pdf_path).name}: {e}")

    MANIFEST.write_text(json.dumps(manifest, indent=2))
    print(f"\n Manifest updated: {updated_count} new files profiled.")

if __name__ == "__main__":
    main()