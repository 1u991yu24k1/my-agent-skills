#!/usr/bin/env python3
"""抜粋コードが対象ソースの指定行範囲にあるかを検査する. 標準ライブラリのみ.

使い方: python3 check_excerpt.py --tree DIR [--no-info] FILE...
```c などのコードブロックの直前8行以内にある `パス:開始行-終了行` を出典とみなす.
終了行がなければ, 開始行から150行を範囲にする.
抜粋の各行が, 出典の範囲に存在するかを検査する. 空白の違いと行末のコメントは無視する.
コメントだけの行と, 省略を示す行は検査しない.
ツリーを指定したときだけ使う任意の検査である. FAIL があれば終了コード 1.
"""
import argparse
import os
import re
import sys

FENCE = re.compile(r"^(\s*)```(\w*)\s*$")
SOURCE_REF = re.compile(r"`?([\w./+\-]+\.(?:c|h|rs|S)):(\d+)(?:-(\d+))?`?")
CODE_LANGS = {"c", "h", "cpp", "rust", "rs"}
TRAILING_COMMENT = re.compile(r"\s*(/\*.*?\*/|//.*)\s*$")
OPEN_WINDOW = 8
DEFAULT_SPAN = 150


def normalize(line):
    s = TRAILING_COMMENT.sub("", line)
    return re.sub(r"\s+", " ", s).strip()


def is_skippable(line):
    s = line.strip()
    if not s:
        return True
    if s.startswith(("/*", "*", "//", "*/")):
        return True
    return "省略" in s


def blocks(lines):
    """(コードの開始行番号, 言語, 本文の行リスト, 直前の本文の行リスト) を返す."""
    start, lang, body, prose = None, "", [], []
    recent = []
    for n, line in enumerate(lines, 1):
        m = FENCE.match(line)
        if m and start is None:
            start, lang, body = n, m.group(2), []
            prose = recent[-OPEN_WINDOW:]
        elif m and start is not None:
            yield start + 1, lang, body, prose
            start = None
            recent = []
        elif start is not None:
            body.append(line)
        else:
            recent.append((n, line))


def find_reference(prose):
    ref = None
    for n, line in prose:
        for m in SOURCE_REF.finditer(line):
            end = int(m.group(3)) if m.group(3) else None
            ref = (m.group(1), int(m.group(2)), end)
    return ref


def check_file(path, tree, show_info):
    with open(path, encoding="utf-8") as f:
        lines = f.read().split("\n")
    fails, infos = [], []
    source_cache = {}
    checked = 0
    for first, lang, body, prose in blocks(lines):
        if lang not in CODE_LANGS:
            continue
        ref = find_reference(prose)
        if ref is None:
            infos.append((first, "出典(パス:行番号)が直前にない. 抜粋かどうかを確認"))
            continue
        rel, start, end = ref
        full = os.path.join(tree, rel)
        if full not in source_cache:
            try:
                with open(full, encoding="utf-8", errors="replace") as f:
                    source_cache[full] = f.read().split("\n")
            except OSError:
                source_cache[full] = None
        src = source_cache[full]
        if src is None:
            fails.append((first, f"出典のファイル {rel} がツリーにない"))
            continue
        last = end if end else start + DEFAULT_SPAN
        window = {normalize(line) for line in src[start - 1:last]}
        checked += 1
        for i, line in enumerate(body):
            if is_skippable(line):
                continue
            if normalize(line) not in window:
                fails.append((first + i, f"{rel}:{start}-{last} にない行: {line.strip()[:60]}"))
    for n, msg in fails:
        print(f"{path}:{n}: [FAIL] {msg}")
    if show_info:
        for n, msg in infos:
            print(f"{path}:{n}: [INFO] {msg}")
        print(f"{path}: [INFO] 検査した抜粋={checked}")
    return len(fails)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tree", required=True)
    ap.add_argument("--no-info", action="store_true")
    ap.add_argument("files", nargs="+")
    args = ap.parse_args()
    total = sum(check_file(p, args.tree, not args.no_info) for p in args.files)
    print(f"FAIL: {total}")
    return 1 if total else 0


if __name__ == "__main__":
    sys.exit(main())
