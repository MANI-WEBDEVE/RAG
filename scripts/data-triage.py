# scripts/data_triage.py
"""
Har file ko: (1) lane assign karo, (2) hash se track karo.
Future runs mein sirf NEW/CHANGED files process hongi.
"""

import hashlib, json
from pathlib import Path
from datetime import datetime

MANIFEST_PATH = Path("/mnt/inam/RAG_SYSTEM/RAG_SYSTEM/data/processing_manifest.json")

LANE_RULES = {
    "pdf":         [".pdf"],
    "word_legacy": [".doc"],          # LibreOffice conversion chahiye
    "word_modern": [".docx"],
    "excel":       [".xls", ".xlsx", ".csv"],
    "slides":      [".ppt", ".pptx", ".pps"],
    "rtf":         [".rtf"],
    "text":        [".txt", ".md"],
    "image":       [".jpg", ".jpeg", ".png", ".tiff"],
    "audio":       [".mp3", ".wav"],
    "archive":     [".rar", ".zip", ".7z"],
    "database":    [".db", ".sqlite"],
}

def detect_magic(path: Path) -> str:
    """Extension missing/unknown ho toh asli type magic bytes se."""
    with open(path, "rb") as f:
        h = f.read(16)
    if h[:4]  == b"%PDF":                    return ".pdf"
    if h[:8]  == b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1": return ".doc"  # OLE: doc/xls/ppt
    if h[:2]  == b"PK":                      return ".docx"  # zip family
    if h[:7]  == b"Rar!":                    return ".rar"
    if h[:15] == b"SQLite format 3":         return ".db"
    if h[:8]  == b"\x89PNG\r\n\x1a\n":       return ".png"
    if h[:2]  == b"\xff\xd8":                return ".jpg"
    if h[:3]  == b"ID3":                     return ".mp3"
    return "unknown"

def sha256(path: Path) -> str:
    hasher = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(8192), b""):
            hasher.update(block)
    return hasher.hexdigest()

def assign_lane(path: Path) -> str:
    ext = path.suffix.lower()
    for lane, exts in LANE_RULES.items():
        if ext in exts:
            return lane
    real_ext = detect_magic(path)          # (no ext) files ke liye
    for lane, exts in LANE_RULES.items():
        if real_ext in exts:
            return lane
    return "unknown"

def run_triage(data_dir: str):
    manifest = {}
    if MANIFEST_PATH.exists():
        manifest = json.loads(MANIFEST_PATH.read_text())

    report = {}
    for f in sorted(Path(data_dir).rglob("*")):
        if not f.is_file():
            continue

        file_hash = sha256(f)
        lane = assign_lane(f)

        # INCREMENTAL LOGIC: same hash already processed? → skip
        prev = manifest.get(file_hash)
        status = "processed" if (prev and prev["status"] == "processed") else "pending"

        manifest[file_hash] = {
            "path": str(f),
            "lane": lane,
            "size_mb": round(f.stat().st_size / 1e6, 2),
            "status": status,
            "triaged_at": datetime.now().isoformat(),
        }

        r = report.setdefault(lane, {"count": 0, "pending": 0, "size_mb": 0.0})
        r["count"] += 1
        r["size_mb"] = round(r["size_mb"] + manifest[file_hash]["size_mb"], 2)
        if status == "pending":
            r["pending"] += 1

    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2))

    # Pretty report
    print(f"\n{'Lane':<14}{'Files':>6}{'Pending':>9}{'Size MB':>10}")
    print("-" * 40)
    for lane, r in sorted(report.items(), key=lambda x: -x[1]["size_mb"]):
        print(f"{lane:<14}{r['count']:>6}{r['pending']:>9}{r['size_mb']:>10}")

if __name__ == "__main__":
    run_triage("/mnt/inam/RAG_SYSTEM/RAG_SYSTEM/data/raw")