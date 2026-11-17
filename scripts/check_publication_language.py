#!/usr/bin/env python3
"""Block non-English filenames or Han text in the exact outgoing Git files.

Check staged files with --tree index before committing, and committed files
with --tree HEAD before pushing. Read the Git blobs, not potentially different
working-tree copies. Numerical STL/NPZ payloads are parsed as their formats;
unknown binary formats fail closed. SVG/PNG visual text requires an explicitly
recorded rendered review as well as a machine-readable text/metadata check.
"""
import argparse
import ast
import gzip
import html
import io
import json
from pathlib import Path
import re
import struct
import subprocess
import sys
from urllib.parse import unquote
import zipfile

ROOT=Path(__file__).resolve().parents[1]
RANGES=((0x3400,0x4DBF),(0x4E00,0x9FFF),(0xF900,0xFAFF),
        (0x20000,0x33FFF),(0x2E80,0x2FDF),(0x31C0,0x31EF),
        (0x3021,0x3029),(0x3038,0x303B))


def han_codepoints(text):
    return sorted({ord(c) for c in text if ord(c) in (0x3005,0x3007) or
                   any(lo<=ord(c)<=hi for lo,hi in RANGES)})


def inspect_text(text):
    variants=[text,html.unescape(text),unquote(text)]
    for value in list(variants):
        variants.append(re.sub(r'\\u([0-9a-fA-F]{4})|\\U([0-9a-fA-F]{8})',
            lambda m:chr(int(m.group(1) or m.group(2),16)),value))
    found=set()
    for value in variants:found.update(han_codepoints(value))
    if found:raise ValueError('Han text found: '+', '.join(f'U+{cp:04X}' for cp in sorted(found)))


def strings(value):
    if isinstance(value,str):yield value
    elif isinstance(value,dict):
        for k,v in value.items():yield from strings(k);yield from strings(v)
    elif isinstance(value,(list,tuple)):
        for v in value:yield from strings(v)


def inspect_blob(name,data,reviewed):
    inspect_text(name)
    if not name.isascii():raise ValueError('Filename must use ASCII')
    suffix=Path(name).suffix.lower()
    if suffix=='.stl' and len(data)>=84:
        triangles=struct.unpack('<I',data[80:84])[0]
        if len(data)==84+50*triangles:
            inspect_text(data[:80].rstrip(b'\0').decode('utf-8'))
            return 'binary STL header; triangle records are numeric'
    if suffix=='.npz':
        import numpy as np
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            inspect_text(archive.comment.decode('utf-8'))
            for info in archive.infolist():
                inspect_text(info.filename);inspect_text(info.comment.decode('utf-8'))
                with archive.open(info) as stream:array=np.lib.format.read_array(stream,allow_pickle=False)
                if array.dtype.kind in 'US':
                    for v in array.ravel():inspect_text(v.decode('utf-8') if isinstance(v,bytes) else str(v))
                elif array.dtype.kind not in 'biufc':raise ValueError('Unsupported NPZ data type: '+str(array.dtype))
        return 'NPZ member names and string arrays; numerical arrays parsed without pickle'
    if suffix=='.gz':
        return 'gzip: '+inspect_blob(name[:-3],gzip.decompress(data),reviewed)
    if suffix=='.png':
        if name not in reviewed:raise ValueError('Rendered PNG review not recorded')
        from PIL import Image
        with Image.open(io.BytesIO(data)) as image:
            for text in strings(image.info):inspect_text(text)
        return 'PNG metadata plus recorded rendered review'
    if b'\0' in data:raise ValueError('Unsupported binary format requires a dedicated text/metadata extractor')
    text=data.decode('utf-8');inspect_text(text)
    if suffix=='.json':
        for value in strings(json.loads(text)):inspect_text(value)
    if suffix=='.py':
        for node in ast.walk(ast.parse(text)):
            if isinstance(node,ast.Constant) and isinstance(node.value,str):inspect_text(node.value)
    if suffix=='.svg':
        if name not in reviewed:raise ValueError('Rendered SVG review not recorded')
        if '<image' in text:raise ValueError('Embedded SVG images require separate inspection')
        return 'SVG text/XML plus recorded rendered review'
    return 'UTF-8 text with escaped/HTML/URL text checks'


def check(base,tree,reviewed):
    cmd=['git','diff','--name-only','-z','--diff-filter=ACMRT']
    cmd+=['--cached',base] if tree=='index' else [base,tree]
    names=subprocess.check_output(cmd,cwd=ROOT).decode('utf-8').split('\0')
    rows=[];errors=[]
    for name in filter(None,names):
        blob=':'+name if tree=='index' else tree+':'+name
        data=subprocess.check_output(['git','show',blob],cwd=ROOT)
        try:method=inspect_blob(name,data,reviewed);rows.append(dict(path=name,method=method))
        except Exception as exc:errors.append(dict(path=name,error=str(exc)))
    return dict(base=base,tree=tree,scope='Entire contents and names of new/changed/renamed outgoing files; not a whole-repository historical audit',
        checked_files=len(rows)+len(errors),passed=not errors,files=rows,errors=errors)


def self_test():
    for cp in (0x4E2D,0x3400,0xF900,0x20000,0x3007):
        try:inspect_text(chr(cp))
        except ValueError:pass
        else:raise AssertionError('Missed Han codepoint')
    for sample in ('\\'+'u'+format(0x4E2D,'04x'),'&#'+str(0x4E2D)+';'):
        try:inspect_text(sample)
        except ValueError:pass
        else:raise AssertionError('Missed escaped Han text')
    inspect_text('English: 500 g; 0.5 mm; angle theta; 07:00 EST / 12:00 UTC.')
    try:inspect_blob('unknown.bin',b'\0\1',set())
    except ValueError:pass
    else:raise AssertionError('Unknown binary silently accepted')


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--base',required=True)
    p.add_argument('--tree',default='index');p.add_argument('--reviewed-visual',action='append',default=[])
    p.add_argument('--out',type=Path);a=p.parse_args();self_test()
    result=check(a.base,a.tree,set(a.reviewed_visual))
    if a.out:a.out.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k!='files'},indent=2))
    sys.exit(not result['passed'])
