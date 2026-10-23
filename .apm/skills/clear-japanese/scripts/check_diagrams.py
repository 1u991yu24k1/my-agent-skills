#!/usr/bin/env python3
"""clear-japanese 用の図の機械検査. 標準ライブラリのみ.

使い方: python3 check_diagrams.py [--no-info] [--max-width N] [--all] FILE...
Markdown の ```text フェンスだけを検査する. mermaid とコード用のフェンスは対象外.
検査項目: ASCII 以外, タブ, 行末の空白, 幅, 枠の右端の位置,
経路図のコメント位置(`#` の列), 識別子(`[S0]` など)の定義と参照.
FAIL があれば終了コード 1. INFO は人手で確認する参考出力.
"""
import argparse
import re
import sys

FENCE = re.compile(r"^(\s*)```(\w*)\s*$")
CALL_COMMENT = re.compile(r"\s#\s+(?:(def|call|gen)\s+)?[\w./+\-]+:\d+\s*$")
BAR_NEIGHBOR = set("|+v^V")
ID_REF = re.compile(r"\[([A-Z][A-Za-z]*\d+)\]")
LABEL_WORD = re.compile(r"(?<![\w\[./-])[a-z]{3,}(?![\w\]./(-])")
SHOW_LIMIT = 15


def fences(lines):
    """(開始行, 言語, 本文の行リスト) を返す."""
    start, lang, body = None, "", []
    for n, line in enumerate(lines, 1):
        m = FENCE.match(line)
        if m and start is None:
            start, lang, body = n, m.group(2), []
        elif m and start is not None:
            yield start, lang, body
            start = None
        elif start is not None:
            body.append(line)


def check_block(first, body, max_width, fails, infos):
    """first は本文 1 行目の行番号."""
    for i, line in enumerate(body):
        n = first + i
        if not line.isascii():
            fails.append((n, "図の中は ASCII 文字だけにする", "ASCII"))
        if "\t" in line:
            fails.append((n, "タブを使わず, 空白で位置をそろえる", "タブ"))
        if line != line.rstrip():
            fails.append((n, "行末に空白を残さない", "行末空白"))
        if len(line) > max_width:
            fails.append((n, f"{len(line)} 桁が {max_width} 桁を超える", "幅"))

    for i, line in enumerate(body):
        for m in re.finditer(r"\|", line):
            c = m.start()
            above = body[i - 1][c] if i > 0 and len(body[i - 1]) > c else " "
            below = body[i + 1][c] if i + 1 < len(body) and len(body[i + 1]) > c else " "
            if above not in BAR_NEIGHBOR and below not in BAR_NEIGHBOR:
                fails.append((first + i, f"{c + 1} 桁目の '|' の上下に枠線がない. 右端のずれを確認",
                              "枠の位置"))

    calls = [(i, line) for i, line in enumerate(body) if CALL_COMMENT.search(line)]
    if calls:
        cols, ends, missing = {}, [], 0
        for i, line in calls:
            m = CALL_COMMENT.search(line)
            code = line[:m.start()].rstrip()
            cols[i] = line.index("#", m.start())
            ends.append(len(code))
            if not m.group(1):
                missing += 1
        longest = max(ends)
        want = longest + 1
        if len(set(cols.values())) > 1:
            fails.append((first + calls[0][0], "経路図の '#' の列が行ごとに異なる", "コメント位置"))
        elif cols[calls[0][0]] != want:
            fails.append((first + calls[0][0],
                          f"'#' は最長のコードの末尾から1文字空けた {want + 1} 桁目に置く",
                          "コメント位置"))
        if missing:
            fails.append((first + calls[0][0],
                          f"経路図の {missing} 行に def, call, gen のマーカーがない", "マーカー"))

    defined, referenced = set(), {}
    for i, line in enumerate(body):
        for m in ID_REF.finditer(line):
            if re.search(r">\s*$", line[:m.start()]):
                referenced.setdefault(m.group(1), first + i)
            else:
                defined.add(m.group(1))
    for name, n in referenced.items():
        if name not in defined:
            fails.append((n, f"識別子 [{name}] を矢印で指しているが, 図の中に定義 [{name}] がない", "識別子"))


def check_file(path, show_info, max_width, show_all):
    with open(path, encoding="utf-8") as f:
        lines = f.read().split("\n")
    fails, infos = [], []
    count = 0
    for start, lang, body in fences(lines):
        if lang != "text":
            continue
        count += 1
        check_block(start + 1, body, max_width, fails, infos)

    shown, counts = {}, {}
    for _, _, cat in fails:
        counts[cat] = counts.get(cat, 0) + 1
    for n, msg, cat in sorted(fails, key=lambda f: (f[2], f[0])):
        shown[cat] = shown.get(cat, 0) + 1
        if show_all or shown[cat] <= SHOW_LIMIT:
            print(f"{path}:{n}: [FAIL] {msg}")
        elif shown[cat] == SHOW_LIMIT + 1:
            print(f"{path}: [FAIL] {cat}: 他 {counts[cat] - SHOW_LIMIT} 件 (--all で全件表示)")
    if show_info:
        for n, msg in infos:
            print(f"{path}:{n}: [INFO] {msg}")
        print(f"{path}: [INFO] text フェンス={count}")
    return len(fails)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-info", action="store_true")
    ap.add_argument("--max-width", type=int, default=80)
    ap.add_argument("--all", action="store_true")
    ap.add_argument("files", nargs="+")
    args = ap.parse_args()
    total = sum(check_file(p, not args.no_info, args.max_width, args.all) for p in args.files)
    print(f"FAIL: {total}")
    return 1 if total else 0


if __name__ == "__main__":
    sys.exit(main())
