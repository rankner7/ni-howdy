"""Project real-text counts from NAER's official COCT frequency workbook.

Usage: python3 scripts/prepare_frequency.py /path/to/workbook.xlsx
No spreadsheet dependency is needed. Preserve the source workbook separately.
"""
import gzip
import hashlib
import json
from pathlib import Path
import re
import sys
import unicodedata
import xml.etree.ElementTree as ET
import zipfile

ROOT=Path(__file__).resolve().parent.parent
NS={'s':'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
SOURCE='https://coct.naer.edu.tw/file/files/%E9%80%9A%E7%94%A8%E8%A9%9E%E9%A0%BB%E8%A1%A8%20-%20%E5%AE%9A%E7%A8%BF1141208.xlsx'


def project(path):
    counts={}
    with zipfile.ZipFile(path) as workbook:
        strings=[]
        for _,node in ET.iterparse(workbook.open('xl/sharedStrings.xml'),events=['end']):
            if node.tag.endswith('}si'):
                strings.append(''.join(node.itertext()))
                node.clear()
        for _,row in ET.iterparse(workbook.open('xl/worksheets/sheet1.xml'),events=['end']):
            if not row.tag.endswith('}row'):
                continue
            cells={}
            for cell in row:
                value=cell.find('s:v',NS)
                if value is not None:
                    cells[re.sub(r'\d','',cell.attrib['r'])]=strings[int(value.text)] if cell.attrib.get('t')=='s' else value.text
            if row.attrib['r']=='1':
                expected={'B':'詞','C':'書面語\n詞頻','I':'新聞\n詞頻'}
                if any(cells.get(k)!=v for k,v in expected.items()):
                    raise ValueError('Unexpected workbook headers; no frequency data was written.')
            else:
                word=unicodedata.normalize('NFC',cells.get('B','').strip())
                if word and all('\u3400' <= c <= '\u9fff' for c in word):
                    count=int(float(cells.get('C') or 0))+int(float(cells.get('I') or 0))
                    if count>0:
                        counts[word]=counts.get(word,0)+count
            row.clear()
    return {'source':SOURCE,'publisher':'National Academy for Educational Research, Taiwan',
            'workbook_sha256':hashlib.sha256(Path(path).read_bytes()).hexdigest(),
            'measure':'written_count + news_count (columns C + I); spoken corpus excluded',
            'counts':counts}


if __name__=='__main__':
    result=project(sys.argv[1])
    with gzip.GzipFile(ROOT/'data/word-frequency.json.gz','wb',mtime=0) as output:
        output.write(json.dumps(result,ensure_ascii=False,separators=(',',':')).encode())
    print(f"Prepared measured text counts for {len(result['counts']):,} words.")
