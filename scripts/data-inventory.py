# scripts/data_inventory.py
"""
Step 1: Apne 1GB data ka complete inventory banao.
Kya hai, kahan hai, kitna hai, kaunsa format hai.
"""

import os
import hashlib
from pathlib import Path
from collections import Counter
from dataclasses import dataclass, field
from rich.console import Console
from rich.table import Table
import chardet

console = Console()

@dataclass
class FileInfo:
    path: str
    name: str
    extension: str
    size_mb: float
    is_encrypted: bool = False
    encoding: str = "unknown"
    page_count: int = 0
    error: str = ""

def scan_directory(data_dir: str) -> list[FileInfo]:
    """Recursively scan and catalog all files."""
    
    files = []
    data_path = Path(data_dir)
    
    for file_path in data_path.rglob("*"):
        if file_path.is_file():
            info = FileInfo(
                path=str(file_path),
                name=file_path.name,
                extension=file_path.suffix.lower(),
                size_mb=file_path.stat().st_size / (1024 * 1024),
            )
            
            # Check if file is readable / encrypted
            try:
                with open(file_path, 'rb') as f:
                    header = f.read(1024)
                    
                # PDF encryption check
                if info.extension == '.pdf':
                    if b'/Encrypt' in header:
                        info.is_encrypted = True
                        
                # Encoding detection for text files
                if info.extension in ['.txt', '.csv', '.md']:
                    with open(file_path, 'rb') as f:
                        raw = f.read(10000)
                    detected = chardet.detect(raw)
                    info.encoding = detected['encoding']
                    
            except PermissionError:
                info.error = "Permission denied"
            except Exception as e:
                info.error = str(e)
            
            files.append(info)
            print(f"Scanned: {info.name} | Size: {info.size_mb:.2f} MB | Encrypted: {info.is_encrypted} | Encoding: {info.encoding} | Error: {info.error}")

    return files

def print_inventory(files: list[FileInfo]):
    """Pretty print the inventory."""
    
    table = Table(title="📚 ABC Library — Data Inventory")
    table.add_column("Format", style="cyan")
    table.add_column("Count", justify="right")
    table.add_column("Total Size (MB)", justify="right")
    table.add_column("Encrypted", justify="center")
    table.add_column("Avg Size (MB)", justify="right")
    
    # Group by extension
    by_ext = {}
    for f in files:
        ext = f.extension or "(no ext)"
        if ext not in by_ext:
            by_ext[ext] = []
        by_ext[ext].append(f)
    
    total_size = 0
    total_encrypted = 0
    
    for ext, ext_files in sorted(by_ext.items()):
        count = len(ext_files)
        size = sum(f.size_mb for f in ext_files)
        encrypted = sum(1 for f in ext_files if f.is_encrypted)
        avg = size / count if count > 0 else 0
        total_size += size
        total_encrypted += encrypted
        
        table.add_row(
            ext,
            str(count),
            f"{size:.2f}",
            f"🔒 {encrypted}" if encrypted else "—",
            f"{avg:.2f}"
        )
    
    table.add_section()
    table.add_row(
        "[bold]TOTAL[/bold]",
        f"[bold]{len(files)}[/bold]",
        f"[bold]{total_size:.2f}[/bold]",
        f"[bold]🔒 {total_encrypted}[/bold]",
        ""
    )
    
    console.print(table)
    
    # Errors report
    errors = [f for f in files if f.error]
    if errors:
        console.print(f"\n[red]⚠️  {len(errors)} files with errors:[/red]")
        for f in errors[:10]:
            console.print(f"  [red]✗[/red] {f.name}: {f.error}")

if __name__ == "__main__":
    import sys
    data_dir = sys.argv[1] if len(sys.argv) > 1 else "/mnt/inam/RAG_SYSTEM/RAG_SYSTEM/data/raw"
    
    console.print(f"\n[bold green]Scanning:[/bold green] {data_dir}\n")
    files = scan_directory(data_dir)
    print_inventory(files)