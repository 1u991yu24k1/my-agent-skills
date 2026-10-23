#!/usr/bin/env python3
"""clear-japanese 用の機械検査. 標準ライブラリのみ.

使い方: python3 lint_ja.py [--no-info] [--max-width N] [--allow-log] [--all]
                         [--profile general|tech] FILE...
--max-width は端末向けの出力を検査するときだけ指定する(例: 70).
--allow-log は検証記録など, 作業の経緯を書いてよい文書で作業ログ語の検査を外す.
--all は同じ種類の FAIL を省略せずに全件表示する(既定は種類ごとに15件).
--profile tech は実装を読む技術資料向けの検査(作業環境の絶対パスなど)を足す.
既定の general は会話や一般文書向けで, 技術資料向けの検査を行わない.
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
NOUN_TAIL = re.compile(r"(もの|こと|ところ|ため|よう|とき|うち|ほか|など|だけ|のみ|あたり)$")
NEGATIVE_END = re.compile(r"(ない|ません)\.?$")
HEADING = re.compile(r"^(#{1,6})\s+(.*)$")
PROPOSITION_HINT = re.compile(r"(は|が).*(る|い|ない|である)$")
JP_CHAR = re.compile(r"[ぁ-んァ-ヶー一-龥]")
WORKLOG = re.compile(
    r"(指定された|指定ソース|ユーザー指定|今回|作業範囲|確認した|"
    r"実施していない|未実施|行っていない|この会話|先ほど|前回)"
)
EMPTY_HEADING = re.compile(r"(中核|その他|まとめ|メモ(?!リ)|雑記)")
DEFINITION = re.compile(r"(とは|である\.|を指す\.|を表す\.|をいう\.)")
KEEP_ENGLISH = {
    "Linux", "Rust", "Kconfig", "Makefile", "Git", "GitHub", "Obsidian",
    "Python", "Codex", "Claude", "Markdown", "LaTeX", "mermaid", "Mermaid",
}
# 地の文で英語と日本語を併用してはいけない対応. (英語, 日本語)
VARIANT_PAIRS = [
    ("bucket", "バケット"), ("cache", "キャッシュ"), ("lookup", "検索"),
    ("slot", "スロット"), ("node", "ノード"), ("key", "キー"),
    ("lock", "ロック"), ("thread", "スレッド"), ("pointer", "ポインタ"),
]
ABS_PATH = re.compile(r"(?<![\w.~])/(?:root|home|mnt|Users)/[\w.\-/]+")
ACRONYM = re.compile(r"\b[A-Z][A-Z0-9]{2,}\b")
ACRONYM_DEFINED = re.compile(r"(\(|（|とは|の略|を表す|を指す|である)")
TECH_MAX_LINES = 600
MAX_SENTENCE = 100
MAX_NEGATIVE_RATE = 0.10
MAX_ENGLISH_DENSITY = 3.0
SHOW_LIMIT = 15


def split_blocks(lines):
    """(行番号, 行, コード内か) を返す."""
    in_fence = False
    in_math = False
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
        if not in_fence and line.strip() == "$$":
            in_math = not in_math
            yield n, line, True
            continue
        yield n, line, in_fence or in_math


def clean(line):
    """Markdown の装飾を外した本文を返す. インラインコードは残す."""
    s = line.strip()
    s = re.sub(r"^(>\s*)+", "", s)
    s = re.sub(r"^\[![A-Za-z]+\]\s*", "", s)
    s = re.sub(r"^([-*+]|\d+\.)\s+", "", s)
    s = re.sub(r"\[\[([^\]|]*\|)?([^\]]*)\]\]", r"\2", s)
    s = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", s)
    s = re.sub(r"\$[^$]*\$", "式", s)
    s = s.replace("**", "")
    return s.strip()


def only_links(line):
    rest = re.sub(r"\[\[.*?\]\]|\[[^\]]*\]\([^)]*\)|[\s/,\-*+>.]", "", line)
    return rest == ""


def is_noun_end(s):
    """文末が名詞, 記号, 英数字で終わる(体言止め)なら True."""
    s = re.sub(r"\s*[(（][^()（）]*[)）]$", "", s.rstrip("."))
    s = s.rstrip()
    if not s:
        return False
    if re.search(r"[ぁ-ん]$", s):
        return bool(NOUN_TAIL.search(s))
    return True


def exempt_word(w):
    if w in KEEP_ENGLISH or w.upper() == w:
        return True
    return bool(re.fullmatch(r"[A-Za-z]{1,2}\d.*", w))


def english_words(plain):
    """(語, 日本語に空白なしで接しているか) を返す. 略語と固有名詞は除く."""
    for m in ASCII_WORD.finditer(plain):
        w = m.group(0)
        if len(w) < 3 or exempt_word(w):
            continue
        before = plain[m.start() - 1] if m.start() > 0 else " "
        after = plain[m.end()] if m.end() < len(plain) else " "
        glued = bool(JP_CHAR.match(before) or JP_CHAR.match(after))
        yield w, glued


def sentences_of(buffer):
    parts = re.split(r"(?<=\.)\s+", buffer.strip())
    return [p for p in parts if p]


def check_file(path, show_info, max_width, allow_log, show_all, profile="general"):
    with open(path, encoding="utf-8") as f:
        lines = f.read().split("\n")
    fails, infos = [], []
    first_ascii = {}
    negative_run = 0
    title = None
    prose_after_title = []
    sentences = []
    buffer, buffer_line = "", 0
    jp_chars = 0
    eng_words = 0
    variants_en = {}
    tech = profile == "tech"
    section_forward = 0
    seen_acronyms = {}

    def flush():
        nonlocal buffer
        if buffer:
            for s in sentences_of(buffer):
                sentences.append((buffer_line, s))
        buffer = ""

    for n, line, in_code in split_blocks(lines):
        if in_code:
            flush()
            continue
        stripped = line.strip()
        plain = INLINE_CODE.sub("", line)

        for ch, msg in BANNED.items():
            if ch in plain:
                fails.append((n, f"'{ch}' {msg}", "禁止文字"))
        if EMOJI.search(plain):
            fails.append((n, "絵文字を使わない", "絵文字"))

        skip_width = stripped.startswith(("|", ">")) or "http" in line
        if max_width and not skip_width and len(line) > max_width:
            fails.append((n, f"{len(line)} 文字が {max_width} 文字を超える", "行長"))

        for m in EMPHASIS.finditer(plain):
            before = plain[m.start() - 1] if m.start() > 0 else " "
            after = plain[m.end()] if m.end() < len(plain) else " "
            if ord(before) > 0x2FFF or ord(after) > 0x2FFF:
                fails.append((n, "強調の前後に空白を1文字入れる", "強調"))

        h = HEADING.match(stripped)
        is_table = stripped.startswith("|")
        if is_table and re.fullmatch(r"[|\-:\s]+", stripped):
            continue
        if not stripped or set(stripped) <= set("-*_ "):
            flush()
            negative_run = 0
            continue

        if h:
            flush()
            level, text = len(h.group(1)), h.group(2)
            if level == 1 and title is None:
                title = text
            elif text.endswith("."):
                fails.append((n, "見出しを文(結論)にしない", "見出し"))
            elif PROPOSITION_HINT.search(text):
                infos.append((n, "見出しが命題になっていないか確認"))
            if EMPTY_HEADING.search(text):
                fails.append((n, f"内容を予告しない語を見出しに使う: {text}", "空語見出し"))
            body = clean(text)
        elif is_table:
            flush()
            cells = re.split(r"(?<!\\)\|", stripped.strip("|"))
            body = " ".join(clean(c.replace("\\|", "|")) for c in cells)
        else:
            body = clean(line)
            if only_links(stripped):
                flush()
                continue
            if title is not None:
                prose_after_title.append(body)
            if buffer.rstrip().endswith(","):
                buffer += " " + body
            else:
                flush()
                buffer, buffer_line = body, n

        text_plain = INLINE_CODE.sub(" ", body)
        text_plain = re.sub(r"https?://\S+", " ", text_plain)

        if tech:
            m = ABS_PATH.search(line)
            if m:
                fails.append((n, f"作業環境の絶対パス '{m.group(0)}' を本文に書かない. "
                              "版と取得元を書き, ローカルの場所は frontmatter に置く", "絶対パス"))
            if h and len(h.group(1)) <= 2:
                section_forward = 0
            section_forward += text_plain.count("後述")
            if section_forward == 2 and "後述" in text_plain:
                infos.append((n, "同じ節で '後述' が2回目. 定義を先に書けないか確認"))
            for am in ACRONYM.finditer(text_plain):
                w = am.group(0)
                if w not in seen_acronyms:
                    seen_acronyms[w] = (n, bool(ACRONYM_DEFINED.search(text_plain)))

        if re.search(r"\s/\s", text_plain):
            fails.append((n, "' / ' で語を並べず, 文か箇条書きで書く", "スラッシュ列挙"))
        if not allow_log:
            m = WORKLOG.search(text_plain)
            if m:
                fails.append((n, f"作業の経緯を示す語 '{m.group(0)}' を本文に書かない", "作業ログ"))

        jp_chars += len(JP_CHAR.findall(text_plain))
        for w, glued in english_words(text_plain):
            eng_words += 1
            variants_en[w.lower()] = n
            if glued:
                fails.append((n, f"英単語 '{w}' が日本語に空白なしで接している", "英日接着"))

        if not h and not is_table:
            if NEGATIVE_END.search(stripped):
                negative_run += 1
                if negative_run == 3:
                    infos.append((n, "否定文末が3行連続. 注意書きにできないか確認"))
            else:
                negative_run = 0

        for m in ASCII_WORD.finditer(text_plain):
            w = m.group(0)
            if len(w) >= 3 and w.lower() not in first_ascii:
                first_ascii[w.lower()] = (n, w)
    flush()

    negatives = 0
    long_count = 0
    noun_count = 0
    for n, s in sentences:
        terminated = s.endswith(".")
        body = s.rstrip(".").rstrip()
        if not terminated and (
            len(body) < 12 or not JP_CHAR.search(body) or body[-1] in ",:"
        ):
            continue
        if len(body) > MAX_SENTENCE:
            long_count += 1
            fails.append((n, f"{len(body)} 文字の文. {MAX_SENTENCE} 文字以内に分ける", "長文"))
        if is_noun_end(body):
            noun_count += 1
            tail = body[-12:]
            fails.append((n, f"体言止めで文を終えない: ...{tail}", "体言止め"))
        if NEGATIVE_END.search(body):
            negatives += 1

    total = len(sentences)
    neg_rate = negatives / total if total else 0.0
    if total >= 10 and neg_rate > MAX_NEGATIVE_RATE:
        fails.append((0, f"否定文が {negatives}/{total} 文({neg_rate:.0%}). "
                      f"{MAX_NEGATIVE_RATE:.0%} 以下にする", "否定文率"))

    density = eng_words * 100 / jp_chars if jp_chars else 0.0
    if density > MAX_ENGLISH_DENSITY:
        fails.append((0, f"地の文の英単語が日本語100文字あたり {density:.1f} 語. "
                      f"{MAX_ENGLISH_DENSITY:g} 語以下にする", "英単語密度"))

    jp_text = "\n".join(prose_after_title)
    for en, ja in VARIANT_PAIRS:
        if en in variants_en and ja in jp_text:
            fails.append((variants_en[en], f"'{en}' と '{ja}' が混在している", "表記ゆれ"))

    if title:
        head = "".join(prose_after_title)[:300]
        if len(head) >= 100 and not DEFINITION.search(head):
            fails.append((0, "冒頭300字に主題の定義文(とは, である, を指す)がない", "冒頭の定義"))
        head200 = head[:200]
        tokens = [t for t in re.split(r"[\s/,:()]+", title) if len(t) >= 2]
        missing = [t for t in tokens if t not in head200]
        if missing:
            infos.append((1, "冒頭200字に主題語がない: " + ", ".join(missing)))

    if tech:
        if len(lines) > TECH_MAX_LINES:
            infos.append((0, f"{len(lines)} 行. {TECH_MAX_LINES} 行を超える. 節ごとにページを分けられないか確認"))
        undefined = [f"{w}({n})" for w, (n, ok) in seen_acronyms.items() if not ok]
        if undefined:
            infos.append((0, "初出で定義が近くにない略語: " + ", ".join(undefined[:20])))

    if first_ascii:
        words = ", ".join(f"{w}({n})" for n, w in first_ascii.values())
        infos.append((0, "初出の英単語. 定義か実在の識別子か確認: " + words))

    shown = {}
    counts = {}
    for n, msg, cat in fails:
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
        print(f"{path}: [INFO] 文={total} 体言止め={noun_count} 否定率={neg_rate:.0%} "
              f"英単語密度={density:.1f} 長文={long_count}")
    return len(fails)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-info", action="store_true")
    ap.add_argument("--max-width", type=int, default=0)
    ap.add_argument("--allow-log", action="store_true")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--profile", choices=("general", "tech"), default="general")
    ap.add_argument("files", nargs="+")
    args = ap.parse_args()
    total = sum(
        check_file(p, not args.no_info, args.max_width, args.allow_log, args.all, args.profile)
        for p in args.files
    )
    print(f"FAIL: {total}")
    return 1 if total else 0


if __name__ == "__main__":
    sys.exit(main())
