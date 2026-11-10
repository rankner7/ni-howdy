"""Rebuild bundled glyph data from downloaded Make Me a Hanzi JSONL files.

Usage: python3 scripts/prepare_data.py dictionary.txt graphics.txt
"""
import gzip
import json
import sys
from pathlib import Path

root = Path(__file__).resolve().parent.parent / "data"
root.mkdir(exist_ok=True)
dictionary = {row["character"]: row for row in
              map(json.loads, Path(sys.argv[1]).read_text().splitlines())}
for line in Path(sys.argv[2]).read_text().splitlines():
    row = json.loads(line)
    if row["character"] in dictionary:
        dictionary[row["character"]].update(row)
with gzip.GzipFile(root / "hanzi.json.gz", "wb", mtime=0) as f:
    f.write(json.dumps(dictionary, ensure_ascii=False, separators=(",", ":")).encode())
print(f"Prepared {len(dictionary)} character records.")
