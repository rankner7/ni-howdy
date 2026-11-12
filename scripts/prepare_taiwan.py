"""Prepare offline Taiwan MOE guided templates from g0v's source archive.

Run without arguments to download, or pass a local zh-stroke-data .tar.gz.
Only original XML-backed characters are imported; synthetic missing/ entries
are excluded. No access to the application's existing data/ is needed.
"""
import argparse
import gzip
import io
import json
import re
import sys
import tarfile
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from nihowdy.taiwan import SOURCE, TEMPLATES, convert_character


def prepare(archive, output=TEMPLATES):
    characters = {}
    skipped = []
    with tarfile.open(fileobj=archive, mode='r:gz') as source:
        members = source.getmembers()
        original = {Path(m.name).stem.lower() for m in members if '/utf8/' in m.name and m.name.endswith('.xml')}
        for member in members:
            match = re.fullmatch(r'[^/]+/json/([0-9a-fA-F]{4,6})\.json', member.name)
            if not match or not member.isfile() or match[1].lower() not in original:
                continue
            ch = chr(int(match[1], 16))
            if not ('\u3400' <= ch <= '\u9fff' or ord(ch) >= 0x20000):
                continue
            try:
                characters[ch] = convert_character(json.load(source.extractfile(member)))
            except (ValueError, KeyError, TypeError) as exc:
                skipped.append((ch, str(exc)))
    if not characters:
        raise ValueError('No original Taiwan character templates found in this archive.')
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    document = {'version': 1, 'standard': 'Taiwan MOE', 'source': SOURCE, 'characters': characters}
    temporary = output.with_suffix('.tmp')
    with gzip.GzipFile(temporary, 'wb', mtime=0) as target:
        target.write(json.dumps(document, ensure_ascii=False, separators=(',', ':')).encode())
    temporary.replace(output)
    print(f'Prepared {len(characters):,} Taiwan MOE characters in {output}')
    if skipped:
        print(f'Excluded {len(skipped)} characters with unsupported or incomplete geometry:')
        for ch, reason in skipped:
            print(f'  {ch}: {reason}')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('archive', nargs='?', type=Path)
    parser.add_argument('--output', type=Path, default=TEMPLATES)
    args = parser.parse_args()
    if args.archive:
        with args.archive.open('rb') as archive:
            prepare(archive, args.output)
    else:
        url = 'https://codeload.github.com/g0v/zh-stroke-data/tar.gz/refs/heads/master'
        print('Downloading Taiwan MOE source archive…', flush=True)
        with urllib.request.urlopen(url, timeout=120) as response:
            prepare(io.BytesIO(response.read()), args.output)


if __name__ == '__main__':
    main()
