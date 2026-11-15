#!/usr/bin/env python3
"""clear-japanese 用の図の機械検査. 標準ライブラリのみ.

使い方: python3 check_diagrams.py [--no-info] [--max-width N] [--all] FILE...
Markdown の ```text と ```mermaid のフェンスを検査する. コード用のフェンスは対象外.
text の検査項目: ASCII 以外, タブ, 行末の空白, 幅, 枠の右端の位置,
経路図のコメント位置(`#` の列), 識別子(`[S0]` など)の定義と参照.
mermaid の検査項目: 絵文字とアイコン(FAIL), 色の指定, ノード数, 分岐のない flowchart(INFO).
両方に共通する検査項目: 図のラベルが前後の段落にあるか, 図の後に凡例か読み取り文があるか(INFO).
FAIL があれば終了コード 1. INFO は人手で確認する参考出力.
"""
import argparse
import re
import sys

FENCE = re.compile(r"^(\s*)```(\w*)\s*$")
CALL_COMMENT = re.compile(r"\s#\s+(?:(def|call|gen)\s+)?[\w./+\-]+:\d+\s*$")
BAR_NEIGHBOR = set("|+v^V")
ID_REF = re.compile(r"\[([A-Z][A-Za-z]*\d+)\]")
OBJECT_ID = re.compile(r"\b[A-Z][a-z]+[A-Z0-9]\w*\b")
EMOJI = re.compile("[\U0001F300-\U0001FAFF☀-➿️]")
ICON = re.compile(r"\bfa[bsr]?:fa-[\w-]+")
STYLE = re.compile(r"^\s*(style|classDef|linkStyle)\b|:::\w+")
NODE_ID = r"([A-Za-z_][A-Za-z0-9_-]*)"
NODE = re.compile(
    r"(?<![A-Za-z0-9_-])" + NODE_ID + r"\s*"
    r"(?:\[\[(.+?)\]\]|\(\((.+?)\)\)|\[\((.+?)\)\]|\(\[(.+?)\]\)|\{\{(.+?)\}\}|"
    r"\[/(.+?)/\]|\[\\(.+?)\\\]|\[([^\]]+)\]|\(([^)]+)\)|\{([^}]+)\}|>([^\]]+)\])"
)
EDGE_LABEL = re.compile(r"\|([^|]+)\|")
INLINE_EDGE_TEXT = re.compile(r"(--|==|-\.)\s+[^>|]+?\s+(-->|==>|\.->)")
ARROW = re.compile(r"\s*(?:<?[-=.]{2,}>|<?-{2,}[ox]?|<?={3,}|~~~)\s*")
SEQ_PARTICIPANT = re.compile(r"^\s*(?:participant|actor)\s+(\S+)(?:\s+as\s+(.+))?$")
SEQ_MESSAGE = re.compile(r"^\s*[\w-]+\s*[-.]+>>?[+-]?\s*[\w-]+\s*:\s*(.+)$")
STATE_LABEL = re.compile(r"-->.*?:\s*(.+)$")
KEY_TERM = re.compile(r"[一-龥々]{2,}|[ァ-ヶー]{2,}|[A-Za-z_][A-Za-z0-9_]*[A-Za-z0-9_]")
HEADING_LINE = re.compile(r"^\s*#{1,6}\s")
UNITS = {"KiB", "MiB", "GiB", "TiB"}
MAX_NODES = 10
CONTEXT_LINES = 20
LABEL_REPORT_LIMIT = 5
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


def node_labels(line):
    """flowchart の1行から (ID, ラベル) の組を返す."""
    for m in NODE.finditer(line):
        label = next((g for g in m.groups()[1:] if g is not None), "")
        yield m.group(1), label.strip().strip('"').strip()


def check_mermaid(first, body, fails, infos):
    """first は本文 1 行目の行番号. 図のラベルの一覧を返す."""
    kind = ""
    labels = []
    ids, out_deg, in_deg = set(), {}, {}
    edges = 0
    for i, line in enumerate(body):
        n = first + i
        s = line.strip()
        if not s or s.startswith("%%"):
            continue
        if not kind:
            kind = s.split()[0]
            continue
        if EMOJI.search(line):
            fails.append((n, "mermaid の図に絵文字を使わない", "装飾"))
        if ICON.search(line):
            fails.append((n, "mermaid の図にアイコンを使わない", "装飾"))
        if STYLE.search(line):
            infos.append((n, "[F2] 色や線の指定がある. 意味を持つ色なら凡例に書き, 装飾なら外す"))
            continue
        if kind in ("flowchart", "graph"):
            for node_id, label in node_labels(line):
                ids.add(node_id)
                if label:
                    labels.append((n, label))
            for m in EDGE_LABEL.finditer(line):
                labels.append((n, m.group(1).strip()))
            flat = NODE.sub(lambda m: m.group(1), EDGE_LABEL.sub(" ", line))
            flat = INLINE_EDGE_TEXT.sub(r" \2 ", flat)
            segs = [x for x in ARROW.split(flat)]
            if len(segs) < 2:
                continue
            chain = []
            for seg in segs:
                m = re.match(r"\s*([A-Za-z_][A-Za-z0-9_-]*)", seg)
                if m:
                    chain.append(m.group(1))
            for a, b in zip(chain, chain[1:]):
                ids.update((a, b))
                out_deg[a] = out_deg.get(a, 0) + 1
                in_deg[b] = in_deg.get(b, 0) + 1
                edges += 1
        elif kind == "sequenceDiagram":
            m = SEQ_PARTICIPANT.match(line)
            if m:
                ids.add(m.group(1))
                labels.append((n, (m.group(2) or m.group(1)).strip()))
                continue
            m = SEQ_MESSAGE.match(line)
            if m:
                labels.append((n, m.group(1).strip()))
        elif kind.startswith("stateDiagram"):
            m = STATE_LABEL.search(line)
            if m:
                labels.append((n, m.group(1).strip()))
    if len(ids) > MAX_NODES:
        infos.append((first, f"mermaid のノードが {len(ids)} 個ある. {MAX_NODES} 個までにし, 全体像と部分の図に分けられないか確認"))
    if kind in ("flowchart", "graph") and edges >= 2:
        if all(v <= 1 for v in out_deg.values()) and all(v <= 1 for v in in_deg.values()):
            infos.append((first, "[M1] 分岐のない flowchart である. 経路図か表で書けないか確認"))
    return labels


def text_labels(first, body):
    """text の図から, 本文で参照すべきオブジェクトの識別子(`PgA` など)を返す.
    状態の見出し(`[S0]`)は図の中で定義するので, 本文での参照を求めない."""
    labels = []
    for i, line in enumerate(body):
        if CALL_COMMENT.search(line):
            continue
        for m in OBJECT_ID.finditer(line):
            if m.group(0) not in UNITS:
                labels.append((first + i, m.group(0)))
    return labels


def context_text(lines, open_idx, close_idx):
    """図の前後の段落を返す. 見出しか別のフェンスで止める. idx は 0 始まり."""
    before, after = [], []
    i = open_idx - 1
    while i >= 0 and len(before) < CONTEXT_LINES:
        if FENCE.match(lines[i]) and not any(x.strip() for x in before):
            # 直前に隣接する図(操作前と操作後の組など)は飛ばし, その前の段落を読む.
            i -= 1
            while i >= 0 and not FENCE.match(lines[i]):
                i -= 1
            i -= 1
            continue
        if HEADING_LINE.match(lines[i]) or FENCE.match(lines[i]):
            break
        before.append(lines[i])
        i -= 1
    j = close_idx + 1
    while j < len(lines) and len(after) < CONTEXT_LINES:
        if FENCE.match(lines[j]) and not any(x.strip() for x in after):
            j += 1
            while j < len(lines) and not FENCE.match(lines[j]):
                j += 1
            j += 1
            continue
        if HEADING_LINE.match(lines[j]) or FENCE.match(lines[j]):
            break
        after.append(lines[j])
        j += 1
    return "\n".join(reversed(before)) + "\n" + "\n".join(after)


def check_labels(labels, context, infos):
    plain = context.replace("`", "")
    reported = 0
    seen = set()
    for n, label in labels:
        for term in KEY_TERM.findall(ICON.sub(" ", label).replace("`", "")):
            if term in seen or term in plain:
                continue
            seen.add(term)
            if reported < LABEL_REPORT_LIMIT:
                infos.append((n, f"[F1] 図のラベル '{label}' の語 '{term}' が前後の段落に無い. "
                                 "リード文か凡例で同じ表記を使う"))
            reported += 1


def check_reading(lines, close_idx, first, infos):
    for j in range(close_idx + 1, len(lines)):
        s = lines[j].strip()
        if not s:
            continue
        if HEADING_LINE.match(lines[j]) or FENCE.match(lines[j]):
            break
        return
    infos.append((first, "[P3] 図の後に凡例か読み取り文が無い. 図のどこから何が言えるかを書く"))


def check_file(path, show_info, max_width, show_all):
    with open(path, encoding="utf-8") as f:
        lines = f.read().split("\n")
    fails, infos = [], []
    count = 0
    mermaid = 0
    for start, lang, body in fences(lines):
        if lang not in ("text", "mermaid"):
            continue
        open_idx = start - 1
        close_idx = open_idx + len(body) + 1
        if lang == "text":
            count += 1
            check_block(start + 1, body, max_width, fails, infos)
            labels = text_labels(start + 1, body)
        else:
            mermaid += 1
            labels = check_mermaid(start + 1, body, fails, infos)
        check_labels(labels, context_text(lines, open_idx, close_idx), infos)
        check_reading(lines, close_idx, start, infos)

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
        print(f"{path}: [INFO] text フェンス={count} mermaid フェンス={mermaid}")
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
