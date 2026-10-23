#!/usr/bin/env python3
"""clear-japanese 用の機械検査. 標準ライブラリのみ.

使い方: python3 lint_ja.py [--no-info] [--max-width N] FILE...
--max-width は端末向けの出力を検査するときだけ指定する(例: 70).
FAIL があれば終了コード 1. INFO は人手で確認する参考出力.
"""
import argparse
import re
import sys

BANNED = {
    "、": "読点は ',' を使う",
    "。": "句点は '.' を使う",
    "「": "かぎ括弧を使わない",
    "」": "かぎ括弧を使わない",
    "・": "中黒を使わない",
    "—": "長いダッシュを使わない",
    "―": "長いダッシュを使わない",
    "　": "全角スペースを使わない",
}
EMOJI = re.compile("[\U0001F300-\U0001FAFF☀-➿️]")
INLINE_CODE = re.compile(r"`[^`]*`")
EMPHASIS = re.compile(r"\*\*[^*\n]+\*\*")
ASCII_WORD = re.compile(r"[A-Za-z][A-Za-z0-9_]*(?:[-/.][A-Za-z0-9_]+)*")
NOUN_END = re.compile(r"(仕組み|機構|もの)\.$")
NEGATIVE_END = re.compile(r"(ない|ません)\.$")
HEADING = re.compile(r"^(#{1,6})\s+(.*)$")
PROPOSITION_HINT = re.compile(r"(は|が).*(る|い|ない|である)$")


def split_blocks(lines):
    """(行番号, 行, コード内か) を返す."""
    in_fence = False
    in_front = bool(lines) and lines[0] == "---"
    for n, line in enumerate(lines, 1):
        if in_front:
            if n > 1 and line == "---":
                in_front = False
            yield n, line, True
            continue
        if line.lstrip().startswith("```"):
            in_fence = not in_fence
            yield n, line, True
            continue
        yield n, line, in_fence


def check_file(path, show_info, max_width):
    with open(path, encoding="utf-8") as f:
        lines = f.read().split("\n")
    fails, infos = [], []
    first_ascii = {}
    negative_run = 0
    title, body_after_title = None, []

    for n, line, in_code in split_blocks(lines):
        if in_code:
            continue
        stripped = line.strip()
        plain = INLINE_CODE.sub("", line)

        for ch, msg in BANNED.items():
            if ch in plain:
                fails.append((n, f"'{ch}' {msg}"))
        if EMOJI.search(plain):
            fails.append((n, "絵文字を使わない"))

        skip_width = stripped.startswith(("|", ">")) or "http" in line
        if max_width and not skip_width and len(line) > max_width:
            fails.append((n, f"{len(line)} 文字が {max_width} 文字を超える"))

        if NOUN_END.search(stripped):
            fails.append((n, "体言止めで文を終えない"))

        for m in EMPHASIS.finditer(plain):
            before = plain[m.start() - 1] if m.start() > 0 else " "
            after = plain[m.end()] if m.end() < len(plain) else " "
            if ord(before) > 0x2FFF or ord(after) > 0x2FFF:
                fails.append((n, "強調の前後に空白を1文字入れる"))

        h = HEADING.match(stripped)
        if h:
            level, text = len(h.group(1)), h.group(2)
            if level == 1 and title is None:
                title = text
            elif text.endswith("."):
                fails.append((n, "見出しを文(結論)にしない"))
            elif PROPOSITION_HINT.search(text):
                infos.append((n, "見出しが命題になっていないか確認"))
        elif title is not None:
            body_after_title.append(stripped)

        if NEGATIVE_END.search(stripped):
            negative_run += 1
            if negative_run == 3:
                infos.append((n, "否定文末が3行連続. 注意書きにできないか確認"))
        elif stripped:
            negative_run = 0
        else:
            negative_run = 0

        for m in ASCII_WORD.finditer(plain):
            w = m.group(0)
            if len(w) >= 3 and w.lower() not in first_ascii:
                first_ascii[w.lower()] = (n, w)

    if title:
        head = "".join(body_after_title)[:200]
        tokens = [t for t in re.split(r"[\s/,:()]+", title) if len(t) >= 2]
        missing = [t for t in tokens if t not in head]
        if missing:
            infos.append((1, "冒頭200字に主題語がない: " + ", ".join(missing)))

    if first_ascii:
        words = ", ".join(f"{w}({n})" for n, w in first_ascii.values())
        infos.append((0, "初出の英単語. 定義か実在の識別子か確認: " + words))

    for n, msg in fails:
        print(f"{path}:{n}: [FAIL] {msg}")
    if show_info:
        for n, msg in infos:
            print(f"{path}:{n}: [INFO] {msg}")
    return len(fails)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-info", action="store_true")
    ap.add_argument("--max-width", type=int, default=0)
    ap.add_argument("files", nargs="+")
    args = ap.parse_args()
    total = sum(check_file(p, not args.no_info, args.max_width) for p in args.files)
    print(f"FAIL: {total}")
    return 1 if total else 0


if __name__ == "__main__":
    sys.exit(main())
