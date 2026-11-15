#!/usr/bin/env python3
"""clear-japanese の検査をまとめて実行する入口. 標準ライブラリのみ.

使い方: python3 check_doc.py [--genre general|blog|writeup|internals|paper]
                            [--tree DIR] [--allow-log] [--max-width N] [--no-info] FILE...
lint_ja.py, outline_ja.py, check_diagrams.py, check_excerpt.py を順に実行する.
genre が general 以外なら, lint_ja.py に --profile tech を付ける.
--tree が無く, frontmatter の source_tree: が存在するディレクトリなら, それを使う.
1つでも FAIL があれば終了コード 1.
"""
import argparse
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
GENRES = ("general", "blog", "writeup", "internals", "paper")


def source_tree_of(path):
    """frontmatter の source_tree: を返す. 無ければ None."""
    try:
        with open(path, encoding="utf-8") as f:
            lines = f.read().split("\n")
    except OSError:
        return None
    if not lines or lines[0] != "---":
        return None
    for line in lines[1:]:
        if line == "---":
            break
        m = re.match(r"source_tree:\s*(.+)$", line)
        if m:
            tree = m.group(1).strip().strip("'\"")
            if not os.path.isabs(tree):
                tree = os.path.join(os.path.dirname(os.path.abspath(path)), tree)
            return tree if os.path.isdir(tree) else None
    return None


def run(name, args):
    print(f"== {name} ==", flush=True)
    p = subprocess.run([sys.executable, "-I", os.path.join(HERE, name)] + args,
                       capture_output=True, text=True)
    out = (p.stdout + p.stderr).rstrip("\n")
    if out:
        print(out, flush=True)
    return p.returncode


def check(path, args):
    common = ["--no-info"] if args.no_info else []
    lint_args = list(common)
    if args.genre != "general":
        lint_args += ["--profile", "tech"]
    if args.allow_log:
        lint_args.append("--allow-log")
    if args.max_width:
        lint_args += ["--max-width", str(args.max_width)]
    tree = args.tree or source_tree_of(path)
    excerpt_args = list(common) + (["--tree", tree] if tree else [])

    results = [
        ("lint_ja.py", run("lint_ja.py", lint_args + [path])),
        ("outline_ja.py", run("outline_ja.py", common + ["--genre", args.genre, path])),
        ("check_diagrams.py", run("check_diagrams.py", common + [path])),
        ("check_excerpt.py", run("check_excerpt.py", excerpt_args + [path])),
    ]
    summary = ", ".join(f"{name}={'FAIL' if rc else 'OK'}" for name, rc in results)
    print(f"== 結果: {path} ==")
    print(summary)
    return sum(1 for _, rc in results if rc)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--genre", choices=GENRES, default="general")
    ap.add_argument("--tree", default=None)
    ap.add_argument("--allow-log", action="store_true")
    ap.add_argument("--max-width", type=int, default=0)
    ap.add_argument("--no-info", action="store_true")
    ap.add_argument("files", nargs="+")
    args = ap.parse_args()
    failed = sum(check(p, args) for p in args.files)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
