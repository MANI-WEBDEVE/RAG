# scripts/convert_doc_to_pdf.py
"""
Phase B — Legacy .doc → PDF batch conversion.

Production qualities:
✅ Parallel      → 4 LibreOffice instances simultaneously
✅ Fault-tolerant → ek corrupt file baaki batch ko nahi maarti
✅ Idempotent    → dobara chalao, sirf pending files process hongi
✅ Validated     → "converted" ≠ "valid" — har PDF verify hota hai
"""

import subprocess, shutil, hashlib, json, time, queue, logging
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from tqdm import tqdm
import fitz  # PyMuPDF — validation ke liye

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(message)s")
log = logging.getLogger("doc2pdf")

RAW_DIR     = Path("/mnt/inam/RAG_SYSTEM/data/raw")
OUT_DIR     = Path("/mnt/inam/RAG_SYSTEM/data/converted/pdf")
MANIFEST    = Path("/mnt/inam/RAG_SYSTEM/data/processing_manifest.json")
WORKERS     = 4        # parallel LibreOffice instances
TIMEOUT_SEC = 180      # per-file hard limit (hang protection)
MAX_RETRIES = 1        # transient failure ke liye ek retry


# ────────────────────────────────────────────────────────────
# UTILITY FUNCTIONS
# ────────────────────────────────────────────────────────────

def find_soffice() -> str:
    """LibreOffice binary locate karo — cross-platform. Complexity: O(1)."""
    for name in ("soffice", "libreoffice"):
        path = shutil.which(name)
        if path:
            return path
    mac = Path("/Applications/LibreOffice.app/Contents/MacOS/soffice")
    if mac.exists():
        return str(mac)
    raise RuntimeError("LibreOffice not found — install first")


def sha256(path: Path) -> str:
    """File fingerprint. Complexity: O(S), S = file size. Streaming = O(1) memory."""
    hasher = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(8192), b""):
            hasher.update(block)
    return hasher.hexdigest()


def load_manifest() -> dict:
    if MANIFEST.exists():
        return json.loads(MANIFEST.read_text())
    return {}


def save_manifest(m: dict):
    MANIFEST.write_text(json.dumps(m, indent=2))


# ────────────────────────────────────────────────────────────
# CORE: SINGLE FILE CONVERSION
# ────────────────────────────────────────────────────────────

def convert_one(file_path: Path, profile_pool: queue.Queue) -> dict:
    """
    Ek file convert karo — isolated subprocess mein.
    
    KEY TRICK: -env:UserInstallation
    Har worker ko ALAG LibreOffice profile milta hai,
    warna parallel instances lock conflict se crash hoti hain.
    """
    
    slot = profile_pool.get()   # exclusive LO profile acquire karo (blocking)
    
    try:
        cmd = [
            SOFFICE,
            "--headless",       # no GUI
            "--norestore",      # recovery dialog se hang protection
            "--nologo",
            f"-env:UserInstallation=file:///tmp/lo_profile_{slot}",
            "--convert-to", "pdf",
            "--outdir", str(OUT_DIR),
            str(file_path),
        ]
        
        start = time.time()
        proc = subprocess.run(
            cmd,
            capture_output=True,
            timeout=TIMEOUT_SEC    #worst-case bound
        )
        elapsed = time.time() - start
        
        out_file = OUT_DIR / (file_path.stem + ".pdf")
        ok = (proc.returncode == 0) and out_file.exists()
        
        return {
            "file": str(file_path),
            "success": ok,
            "seconds": round(elapsed, 1),
            "output": str(out_file) if ok else None,
            "error": "" if ok else proc.stderr.decode(errors="ignore")[-300:],
        }
    
    except subprocess.TimeoutExpired:
        # Corrupt .doc LibreOffice ko hamesha ke liye atka sakta hai
        return {
            "file": str(file_path),
            "success": False,
            "seconds": TIMEOUT_SEC,
            "output": None,
            "error": f"timeout > {TIMEOUT_SEC}s (likely corrupt file)",
        }
    
    finally:
        profile_pool.put(slot)   # slot release — doosra worker use kare


# ────────────────────────────────────────────────────────────
# VALIDATION: "Converted" ≠ "Valid"
# ────────────────────────────────────────────────────────────

def validate_pdf(pdf_path: Path) -> dict:
    """
    LibreOffice kabhi-kabhi return code 0 deta hai lekin 
    empty/corrupt PDF banata hai. Isliye verify karna zaroori hai.
    Complexity: O(P), P = pages.
    """
    try:
        doc = fitz.open(pdf_path)
        pages = len(doc)
        chars = sum(len(p.get_text()) for p in doc)
        doc.close()
        return {"valid": pages > 0, "pages": pages, "text_chars": chars}
    except Exception:
        return {"valid": False, "pages": 0, "text_chars": 0}


# ────────────────────────────────────────────────────────────
# MAIN PIPELINE
# ────────────────────────────────────────────────────────────

def main():
    global SOFFICE
    SOFFICE = find_soffice()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    
    manifest = load_manifest()
    
    # ── Idempotency: sirf pending files uthao ──
    doc_files = [f for f in sorted(RAW_DIR.rglob("*.doc")) if f.is_file()]
    pending = []
    for f in doc_files:
        h = sha256(f)                                  # O(S) ek baar
        entry = manifest.get(h, {})                    # O(1) lookup
        out = OUT_DIR / (f.stem + ".pdf")
        if entry.get("convert_status") == "done" and out.exists():
            continue                                   # already done → skip
        pending.append((f, h))
    
    log.info(f"Total .doc: {len(doc_files)} | Pending: {len(pending)}")
    
    # ── Profile pool: W slots, W parallel conversions ──
    profile_pool = queue.Queue()
    for i in range(WORKERS):
        profile_pool.put(i)
    
    # ── Parallel execution ──
    results = []
    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        
        futures = {pool.submit(convert_one, f, profile_pool): (f, h)
                   for f, h in pending}
        
        for fut in tqdm(as_completed(futures), total=len(futures),
                        desc="Converting"):
            res = fut.result()
            f, h = futures[fut]
            
            # Retry sirf failed pe (transient faults)
            attempts = 0
            while not res["success"] and attempts < MAX_RETRIES:
                attempts += 1
                res = convert_one(f, profile_pool)
            
            # Validate
            if res["success"]:
                v = validate_pdf(Path(res["output"]))
                res.update(v)
                status = "done" if v["valid"] else "corrupt"
            else:
                status = "failed"
            
            # Manifest update — future runs incremental honge
            manifest[h] = {
                **manifest.get(h, {}),
                "path": str(f),
                "lane": "pdf_from_doc",      # origin tag — important!
                "convert_status": status,
                "converted_pdf": res.get("output"),
            }
            results.append(res)
    
    save_manifest(manifest)
    
    # ── Final Report ──
    ok   = [r for r in results if r.get("valid")]
    fail = [r for r in results if not r.get("valid")]
    serial_t = sum(r["seconds"] for r in results)
    
    log.info(f"Valid: {len(ok)} |Failed: {len(fail)}")
    log.info(f"⏱  Serial ≈ {serial_t/60:.1f} min | "
             f"Parallel (W={WORKERS}) ≈ {serial_t/WORKERS/60:.1f} min")
    
    for r in fail:
        log.warning(f"FAILED: {r['file']} | {r['error']}")


if __name__ == "__main__":
    main()