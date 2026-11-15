#!/usr/bin/env python3
"""clear-japanese 用の骨格の表示と構成の検査. 標準ライブラリのみ.

使い方: python3 outline_ja.py [--no-info] [--genre general|blog|writeup|internals|paper] FILE...
見出しの木と, 各節の冒頭文, 段落数, 図, コード, 表の数を表示する.
骨格だけで, 課題, 方針, 結論が読めるかを確かめるための出力である.
検査項目: 節の冒頭の予告文(FAIL), 1段落だけの節(INFO), 種別ごとの必須要素(INFO).
FAIL があれば終了コード 1.
"""
import argparse
import re
import sys

HEADING = re.compile(r"^(#{1,6})\s+(.*)$")
FENCE = re.compile(r"^\s*```(\w*)")
LIST_ITEM = re.compile(r"^\s*(?:[-*+]|\d+\.)\s+")
PREVIEW = re.compile(
    r"^(本節|この節|本章|この章|本項|ここ|次に)(では|で|は)?[, ]*.{0,60}?"
    r"(説明する|説明します|見ていく|見ていきます|見ていきましょう|紹介する|紹介します|"
    r"述べる|述べます|解説する|解説します|整理する|整理します)\.?$"
)
GENRES = ("general", "blog", "writeup", "internals", "paper")
LEAD_LINES = 5


class Section:
    def __init__(self, level, title, line):
        self.level, self.title, self.line = level, title, line
        self.first = None
        self.first_line = 0
        self.blocks = 0
        self.figs = 0
        self.codes = 0
        self.tables = 0
        self.lead = []
        self.children = 0


def first_sentence(text):
    m = re.match(r"(.+?\.)(?:\s|$)", text)
    return m.group(1) if m else text


def parse(lines):
    """節の一覧と, frontmatter の本文を返す."""
    sections = []
    front = []
    i = 0
    if lines and lines[0] == "---":
        for j in range(1, len(lines)):
            if lines[j] == "---":
                front = lines[1:j]
                i = j + 1
                break
    cur = Section(0, "(見出しの前)", 1)
    sections.append(cur)
    in_fence = False
    prev = "blank"
    for n in range(i, len(lines)):
        line = lines[n]
        stripped = line.strip()
        m = FENCE.match(line)
        if m:
            if not in_fence:
                in_fence = True
                if m.group(1) in ("mermaid", "text"):
                    cur.figs += 1
                else:
                    cur.codes += 1
                if cur.first is None:
                    cur.first, cur.first_line = "(ブロックから始まる)", n + 1
                cur.blocks += 1
            else:
                in_fence = False
            prev = "block"
            continue
        if in_fence:
            continue
        if not stripped:
            prev = "blank"
            continue
        h = HEADING.match(stripped)
        if h:
            for s in reversed(sections):
                if s.level and s.level < len(h.group(1)):
                    s.children += 1
                    break
            cur = Section(len(h.group(1)), h.group(2).strip(), n + 1)
            sections.append(cur)
            prev = "heading"
            continue
        if stripped.startswith("|"):
            if prev != "table":
                cur.tables += 1
                cur.blocks += 1
                if cur.first is None:
                    cur.first, cur.first_line = "(表から始まる)", n + 1
            prev = "table"
            continue
        is_list = bool(LIST_ITEM.match(line))
        text = LIST_ITEM.sub("", stripped).lstrip("> ").strip()
        if cur.level == 1 and len(cur.lead) < LEAD_LINES:
            cur.lead.append(text)
        if cur.first is None:
            label = "(箇条書き) " if is_list else ""
            cur.first, cur.first_line = label + first_sentence(text), n + 1
        if is_list or (prev == "list" and line[:1] in (" ", "\t")):
            kind = "list"
        else:
            kind = "prose"
        if prev != kind:
            cur.blocks += 1
        prev = kind
    return sections, front


def genre_infos(genre, lines, sections, front, infos):
    title_idx = next((s for s in sections if s.level == 1), None)
    lead = " ".join(title_idx.lead) if title_idx else ""
    body = "\n".join(lines)
    head = "\n".join(lines[:40])
    if genre == "blog":
        if not re.search(r"(環境|対象|版|バージョン|\d+\.\d+)", lead):
            infos.append((1, "リードに環境と版の記述が無い. 読者が自分向けかを判定できるようにする"))
    elif genre == "writeup":
        if not re.search(r"(フラグ|flag|FLAG)", body):
            infos.append((1, "フラグの記述が無い. 取得していなければ, その旨を書く"))
    elif genre == "internals":
        has_target = re.search(r"(?m)^対象:", head) or any(
            f.startswith("source_version:") for f in front)
        if not has_target:
            infos.append((1, "冒頭に '対象:' の行が無い. 対象の版と取得元を書く"))
    elif genre == "paper":
        if not (re.search(r"(DOI|doi\.org|arXiv|arxiv|https?://)", head)
                and re.search(r"(19|20)\d{2}", head)):
            infos.append((1, "冒頭に書誌情報(DOI か URL と, 年)が無い"))


def check_file(path, show_info, genre):
    with open(path, encoding="utf-8") as f:
        lines = f.read().split("\n")
    sections, front = parse(lines)
    fails, infos = [], []

    print(f"== 骨格: {path} ==")
    for s in sections:
        if s.level == 0:
            if s.first is not None and s.first != "(見出しの前)":
                print(f"(見出しの前) 冒頭: {s.first}")
            continue
        indent = "  " * (s.level - 1)
        counts = f"段落 {s.blocks}, 図 {s.figs}, コード {s.codes}, 表 {s.tables}"
        print(f"{indent}H{s.level} {s.title}  (L{s.line}) [{counts}]")
        if s.level == 1:
            for text in s.lead:
                print(f"{indent}   冒頭: {first_sentence(text)}")
        elif s.first is not None:
            print(f"{indent}   冒頭: {s.first}")

        if s.level >= 2 and s.first and PREVIEW.search(s.first.rstrip()):
            fails.append((s.first_line, f"節の冒頭が予告になっている: {s.first} "
                                        "冒頭文には, その節の結論を書く"))
        if s.level >= 2 and s.children == 0 and s.blocks == 1:
            infos.append((s.line, f"1段落だけの節: {s.title}. 2段落以上にするか, 前後の節に統合できないか確認"))
    genre_infos(genre, lines, sections, front, infos)

    for n, msg in fails:
        print(f"{path}:{n}: [FAIL] {msg}")
    if show_info:
        for n, msg in infos:
            print(f"{path}:{n}: [INFO] {msg}")
        print(f"{path}: [INFO] 骨格読み: 上の見出しと冒頭文だけで, 課題, 方針, 結論を言えるか確かめる")
    return len(fails)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-info", action="store_true")
    ap.add_argument("--genre", choices=GENRES, default="general")
    ap.add_argument("files", nargs="+")
    args = ap.parse_args()
    total = sum(check_file(p, not args.no_info, args.genre) for p in args.files)
    print(f"FAIL: {total}")
    return 1 if total else 0


if __name__ == "__main__":
    sys.exit(main())
