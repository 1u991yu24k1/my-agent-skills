#!/usr/bin/env python3
"""抜粋コードが対象ソースの指定行範囲にあるかを検査する. 標準ライブラリのみ.

使い方: python3 check_excerpt.py [--tree DIR] [--max-lines N] [--no-info] FILE...
```c などのコードブロックの直前8行以内にある `パス:開始行-終了行` を出典とみなす.
終了行がなければ, 開始行から150行を範囲にする.
--tree を指定すると, 抜粋の各行が出典の範囲に存在するかを検査する(FAIL).
空白の違いと行末のコメントは無視する. コメントだけの行と, 省略を示す行は検査しない.
--tree の有無にかかわらず, 次を INFO で示す.
長すぎる抜粋, 日本語の注釈が無い長い抜粋, 出典も書き手のコードである旨も無いブロック.
FAIL があれば終了コード 1.
"""
import argparse
import os
import re
import sys

FENCE = re.compile(r"^(\s*)```(\w*)\s*$")
SOURCE_REF = re.compile(
    r"`?([\w./+\-]+\.(?:cpp|cxx|cc|c|hpp|hh|h|rs|S|s|asm|py|go|mjs|js|ts|java|kt|php|rb|zig|swift|cs))"
    r":(\d+)(?:-(\d+))?`?"
)
CODE_LANGS = {
    "c", "h", "cpp", "cc", "cxx", "hpp", "rust", "rs", "python", "py", "go",
    "javascript", "js", "typescript", "ts", "java", "kotlin", "kt", "php", "ruby", "rb",
    "asm", "nasm", "s", "zig", "swift", "csharp", "cs",
}
HASH_COMMENT_LANGS = {"python", "py", "ruby", "rb"}
SEMICOLON_COMMENT_LANGS = {"asm", "nasm", "s"}
TRAILING_COMMENT = re.compile(r"\s*(/\*.*?\*/|//.*)\s*$")
AUTHORED = re.compile(r"(説明用|疑似コード|自作|書いたコード|攻撃コード|エクスプロイト|PoC|再現コード|最小の例|実行例)")
JP_CHAR = re.compile(r"[ぁ-んァ-ヶー一-龥]")
OPEN_WINDOW = 8
DEFAULT_SPAN = 150
MAX_LINES = 30
ANNOTATE_FROM = 10


def normalize(line, lang=""):
    s = TRAILING_COMMENT.sub("", line)
    if lang in HASH_COMMENT_LANGS:
        s = re.sub(r"\s+#.*$", "", s)
    elif lang in SEMICOLON_COMMENT_LANGS:
        s = re.sub(r"\s*;.*$", "", s)
    return re.sub(r"\s+", " ", s).strip()


def is_skippable(line, lang=""):
    s = line.strip()
    if not s or s in ("...", "…"):
        return True
    if s.startswith(("/*", "*", "//", "*/")):
        return True
    if lang in HASH_COMMENT_LANGS and s.startswith("#"):
        return True
    if lang in SEMICOLON_COMMENT_LANGS and s.startswith(";"):
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


def check_shape(first, body, infos, max_lines):
    """抜粋の長さと, 日本語の注釈の有無を INFO で示す."""
    size = len([line for line in body if line.strip()])
    if size > max_lines:
        infos.append((first, f"[Q1] {size} 行の抜粋. {max_lines} 行を目安に, 問いに答える範囲に絞るか分ける"))
    if size >= ANNOTATE_FROM and not any(JP_CHAR.search(line) for line in body):
        infos.append((first, f"[Q2] {size} 行の抜粋に日本語の注釈が無い. 読む点に注釈を付ける"))


def check_file(path, tree, show_info, max_lines=MAX_LINES):
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
            if not any(AUTHORED.search(line) for _, line in prose):
                infos.append((first, "出典(パス:行番号)が直前にない. 抜粋なら出典を, 書き手のコードならその旨を前の文に書く"))
            continue
        check_shape(first, body, infos, max_lines)
        if tree is None:
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
        window = {normalize(line, lang) for line in src[start - 1:last]}
        checked += 1
        for i, line in enumerate(body):
            if is_skippable(line, lang):
                continue
            if normalize(line, lang) not in window:
                fails.append((first + i, f"{rel}:{start}-{last} にない行: {line.strip()[:60]}"))
    for n, msg in fails:
        print(f"{path}:{n}: [FAIL] {msg}")
    if show_info:
        for n, msg in infos:
            print(f"{path}:{n}: [INFO] {msg}")
        if tree is None:
            print(f"{path}: [INFO] --tree が無いので, 抜粋と出典の行の照合は行わない")
        else:
            print(f"{path}: [INFO] 検査した抜粋={checked}")
    return len(fails)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tree", default=None)
    ap.add_argument("--max-lines", type=int, default=MAX_LINES)
    ap.add_argument("--no-info", action="store_true")
    ap.add_argument("files", nargs="+")
    args = ap.parse_args()
    total = sum(check_file(p, args.tree, not args.no_info, args.max_lines) for p in args.files)
    print(f"FAIL: {total}")
    return 1 if total else 0


if __name__ == "__main__":
    sys.exit(main())
