#!/usr/bin/env python3
"""lint_ja.py, outline_ja.py, check_diagrams.py, check_excerpt.py, check_doc.py の回帰試験.
標準ライブラリのみ.

使い方: python3 test_lint.py
fixture を一時ディレクトリに書き, 各検査が発火し, 誤検知しないことを確認する.
"""
import os
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL = os.path.dirname(HERE)
LINT = os.path.join(HERE, "lint_ja.py")
DIAG = os.path.join(HERE, "check_diagrams.py")
EXCERPT = os.path.join(HERE, "check_excerpt.py")
OUTLINE = os.path.join(HERE, "outline_ja.py")
CHECKDOC = os.path.join(HERE, "check_doc.py")

GOOD_DOC = """# 赤黒木

赤黒木は, 色を持つ二分探索木である.
本ページは, 木の仕組みを説明する.
前提知識は, 二分探索木の検索である.

## 色の規則

赤ノードの子は, 必ず黒である.
`rb_node` は, 利用者の構造体に置くメンバである.
TLB は, 変換結果のキャッシュである.
"""

BAD_DOC = """# テスト

赤ノードの子は黒.
bucket番号を使う。
`foo` を「呼ぶ」。
今回の作業範囲外である.
検索 / 挿入 / 削除を行う.
キーを検索しない. 値を返さない. 木を作らない. 例外は無い.

## C 実装の中核

**強調**です.
"""

TECH_DOC = """# 技術資料

技術資料は, 実装を読んで理解するための文書である.
本ページは, 経路を説明する.
前提知識は, C の読み方である.

## 経路

対象のソースは `/root/ws/secret-project/linux-7.2.8` にある.
詳細は後述する. 別の詳細も後述する.
"""

DIAGRAM_GOOD = """```text
[S0] before
+------+--------+
|  0   | empty  | <-- head
+------+--------+
```
"""

DIAGRAM_SHIFTED = """```text
+------+--------+
|  0   | empty   |
+------+--------+
```
"""

CALL_GOOD = """```text
__x64_sys_pipe2 # def fs/pipe.c:1152
  do_pipe2      # def fs/pipe.c:1130
```
"""


TABLE_LINK_DOC = """# 木

木は, 階層を表すデータ構造である.
本ページは, リンクの書き方を説明する.
前提知識は, 表の書き方である.

## リンクの例

| ページ | 内容 |
|--------|------|
| [[tree\\|木]] | 階層を持つ構造 |
| [[list\\|リスト]] | 並びを持つ構造 |
"""

SOURCE_C = """int main(void)
{
\tint x = 1; /* 初期値 */
\treturn x;
}
"""


def run(script, args):
    p = subprocess.run([sys.executable, "-I", script] + args,
                       capture_output=True, text=True)
    return p.returncode, p.stdout + p.stderr


class Fixture(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.tmp.cleanup()

    def write(self, text, name="doc.md"):
        path = os.path.join(self.tmp.name, name)
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)
        return path

    def lint(self, text, *args):
        return run(LINT, list(args) + [self.write(text)])

    def diag(self, text, *args):
        return run(DIAG, list(args) + [self.write(text)])


class LintGeneral(Fixture):
    def test_good_document_passes(self):
        rc, out = self.lint(GOOD_DOC, "--no-info")
        self.assertEqual(rc, 0, out)

    def test_bad_document_fires_each_check(self):
        rc, out = self.lint(BAD_DOC, "--no-info", "--all")
        self.assertEqual(rc, 1)
        for needle in ("体言止め", "英単語", "今回", "否定文が", "中核", "句点", "かぎ括弧", "強調"):
            self.assertIn(needle, out, needle)

    def test_allow_log_skips_worklog_words(self):
        _, out = self.lint(BAD_DOC, "--no-info", "--allow-log", "--all")
        self.assertNotIn("作業の経緯", out)

    def test_general_profile_ignores_tech_checks(self):
        rc, out = self.lint(TECH_DOC, "--all")
        self.assertEqual(rc, 0, out)
        self.assertNotIn("絶対パス", out)
        self.assertNotIn("後述", out)

    def test_help_lists_options(self):
        _, out = run(LINT, ["--help"])
        for opt in ("--allow-log", "--profile", "--max-width"):
            self.assertIn(opt, out)


class LintTech(Fixture):
    def test_absolute_path_fails(self):
        rc, out = self.lint(TECH_DOC, "--profile", "tech")
        self.assertEqual(rc, 1)
        self.assertIn("絶対パス", out)

    def test_forward_reference_info(self):
        _, out = self.lint(TECH_DOC, "--profile", "tech")
        self.assertIn("後述", out)

    def test_good_document_passes_in_tech(self):
        rc, out = self.lint(GOOD_DOC, "--profile", "tech", "--no-info")
        self.assertEqual(rc, 0, out)


class TableEscape(Fixture):
    def test_escaped_pipe_in_wikilink_is_not_a_separator(self):
        rc, out = self.lint(TABLE_LINK_DOC, "--no-info", "--all")
        self.assertEqual(rc, 0, out)


class Excerpt(Fixture):
    def tree(self):
        os.makedirs(os.path.join(self.tmp.name, "src"), exist_ok=True)
        with open(os.path.join(self.tmp.name, "src", "a.c"), "w", encoding="utf-8") as f:
            f.write(SOURCE_C)
        return self.tmp.name

    def doc(self, code, ref="`src/a.c:3-4`"):
        return f"# 抜粋\n\n{ref} から抜粋する.\n\n```c\n{code}```\n"

    def test_matching_excerpt_passes(self):
        tree = self.tree()
        text = self.doc("/* 日本語コメント */\nint x = 1;\nreturn x;\n")
        rc, out = run(EXCERPT, ["--tree", tree, self.write(text)])
        self.assertEqual(rc, 0, out)

    def test_changed_line_fails(self):
        tree = self.tree()
        text = self.doc("int x = 2;\n")
        rc, out = run(EXCERPT, ["--tree", tree, self.write(text)])
        self.assertEqual(rc, 1)
        self.assertIn("にない行", out)

    def test_missing_source_file_fails(self):
        tree = self.tree()
        text = self.doc("int x = 1;\n", ref="`src/none.c:1-2`")
        rc, out = run(EXCERPT, ["--tree", tree, self.write(text)])
        self.assertEqual(rc, 1)
        self.assertIn("ツリーにない", out)

    def test_block_without_reference_is_info(self):
        tree = self.tree()
        text = "# 抜粋\n\n```c\nint x;\n```\n"
        rc, out = run(EXCERPT, ["--tree", tree, self.write(text)])
        self.assertEqual(rc, 0, out)
        self.assertIn("出典", out)


class Diagrams(Fixture):
    def test_good_diagram_passes(self):
        rc, out = self.diag(DIAGRAM_GOOD)
        self.assertEqual(rc, 0, out)

    def test_shifted_right_edge_fails(self):
        rc, out = self.diag(DIAGRAM_SHIFTED)
        self.assertEqual(rc, 1)
        self.assertIn("右端", out)

    def test_width_over_limit_fails(self):
        wide = "```text\n" + "x" * 81 + "\n```\n"
        rc, out = self.diag(wide)
        self.assertEqual(rc, 1)
        self.assertIn("80 桁", out)

    def test_non_ascii_tab_and_trailing_space_fail(self):
        for body, needle in (("あ\n", "ASCII"), ("a\tb\n", "タブ"), ("ab \n", "行末")):
            rc, out = self.diag("```text\n" + body + "```\n")
            self.assertEqual(rc, 1, body)
            self.assertIn(needle, out, body)

    def test_call_path_comment_column(self):
        rc, out = self.diag(CALL_GOOD)
        self.assertEqual(rc, 0, out)
        uneven = CALL_GOOD.replace("do_pipe2      #", "do_pipe2       #")
        rc, out = self.diag(uneven)
        self.assertEqual(rc, 1)
        self.assertIn("'#'", out)
        wide_gap = CALL_GOOD.replace("__x64_sys_pipe2 #", "__x64_sys_pipe2  #") \
                            .replace("do_pipe2      #", "do_pipe2       #")
        rc, out = self.diag(wide_gap)
        self.assertEqual(rc, 1)
        self.assertIn("1文字空けた", out)

    def test_marker_absence_fails(self):
        text = "```text\nfoo_bar # fs/pipe.c:1\n```\n"
        rc, out = self.diag(text)
        self.assertEqual(rc, 1)
        self.assertIn("マーカー", out)

    def test_undefined_identifier_fails(self):
        text = "```text\nA --> [A0]\n```\n"
        rc, out = self.diag(text)
        self.assertEqual(rc, 1)
        self.assertIn("A0", out)
        ok = "```text\n[A0] storage\nA --> [A0]\n```\n"
        rc, out = self.diag(ok)
        self.assertEqual(rc, 0, out)

    def test_other_fences_are_ignored(self):
        text = "```c\n/* 日本語 */\n\tint x;\n```\n\n```mermaid\nA[日本語] --> B\n```\n"
        rc, out = self.diag(text)
        self.assertEqual(rc, 0, out)


LEAD_DOC = """# 試験

試験は, 検査を確かめる文書である.

## 節

次のコードは, 変数を宣言する.

```c
int x;
```
"""

OUTLINE_PREVIEW = """# 書き込み

書き込みは, データを渡す操作である.

## 経路

本節では, 書き込みの経路を説明する.

経路は3段で構成する.
"""

OUTLINE_GOOD = OUTLINE_PREVIEW.replace("本節では, 書き込みの経路を説明する.",
                                       "書き込みは, 3段の関数を通ってページに届く.")

MERMAID_GOOD = """書き込みは, 空きがあれば追記し, 無ければページを確保する.

```mermaid
flowchart TD
    W[書き込み] --> Q{空きがあるか}
    Q -->|ある| A[追記する]
    Q -->|無い| N[ページを確保する]
```

追記の枝では, ページの数は変わらない.
"""


def mermaid_doc(body, lead="開始から処理を経て終了する.", after="図は流れを示す."):
    return f"{lead}\n\n```mermaid\n{body}\n```\n\n{after}\n"


class LintNewChecks(Fixture):
    def test_fence_after_heading_fails(self):
        text = LEAD_DOC.replace("次のコードは, 変数を宣言する.\n\n", "")
        rc, out = self.lint(text, "--no-info")
        self.assertEqual(rc, 1)
        self.assertIn("リード文", out)

    def test_fence_with_lead_passes(self):
        rc, out = self.lint(LEAD_DOC, "--no-info")
        self.assertEqual(rc, 0, out)

    def test_fence_at_document_start_fails(self):
        rc, out = self.lint("```c\nint x;\n```\n", "--no-info")
        self.assertEqual(rc, 1)
        self.assertIn("文書の先頭", out)

    def test_consecutive_fences_info(self):
        rc, out = self.lint(LEAD_DOC + "\n```c\nint y;\n```\n")
        self.assertEqual(rc, 0, out)
        self.assertIn("直前が別のコードブロック", out)

    def test_phrase_lists_info(self):
        text = ("# 試験\n\n試験は, 検査を確かめる文書である.\n"
                "ページテーブルの最上位の表の要素を読む.\n"
                "書き込み失敗時再試行処理実行前に解放する.\n"
                "この関数は, 再試行を可能にする.\n"
                "関数を叩くと戻る.\n"
                "この処理は心臓部である.\n")
        _, out = self.lint(text)
        for needle in ("[J1]", "[J2]", "[J3]", "[J4]", "[J5]"):
            self.assertIn(needle, out, needle)

    def test_demonstrative_is_not_no_chain(self):
        _, out = self.lint("# 試験\n\n試験は, その値の表を読む操作である.\n")
        self.assertNotIn("[J3]", out)

    def test_bold_labels_info(self):
        text = "# 試験\n\n試験は, 検査の文書である.\n\n- **期限**: 明日\n- **担当**: 私\n- **場所**: 東京\n"
        _, out = self.lint(text)
        self.assertIn("太字のラベル", out)

    def test_label_value_line_is_not_a_sentence(self):
        text = GOOD_DOC.replace("# 赤黒木\n\n", "# 赤黒木\n\n対象: Linux 7.2.8, x86-64\n\n")
        rc, out = self.lint(text, "--profile", "tech", "--no-info")
        self.assertEqual(rc, 0, out)

    def test_good_document_has_no_phrase_info(self):
        _, out = self.lint(GOOD_DOC)
        self.assertNotIn("[J", out)


class Outline(Fixture):
    def outline(self, text, *args):
        return run(OUTLINE, list(args) + [self.write(text)])

    def test_prints_skeleton(self):
        rc, out = self.outline(OUTLINE_GOOD)
        self.assertEqual(rc, 0, out)
        self.assertIn("H2 経路", out)
        self.assertIn("冒頭: 書き込みは, 3段の関数を通ってページに届く.", out)

    def test_preview_opening_fails(self):
        rc, out = self.outline(OUTLINE_PREVIEW)
        self.assertEqual(rc, 1)
        self.assertIn("予告", out)

    def test_single_paragraph_section_info(self):
        _, out = self.outline(OUTLINE_GOOD + "\n## 小節\n\n本文である.\n")
        self.assertIn("1段落だけの節: 小節", out)

    def test_genre_required_elements(self):
        cases = (
            ("writeup", "フラグの記述が無い", OUTLINE_GOOD + "\nフラグは `flag{x}` である.\n"),
            ("paper", "書誌情報", OUTLINE_GOOD + "\narXiv:2401.00001 (2024)\n"),
            ("blog", "環境と版の記述が無い",
             OUTLINE_GOOD.replace("操作である.", "操作である.\n環境: Linux 6.8.")),
            ("internals", "'対象:' の行が無い",
             "---\nsource_version: \"linux-7.2.8\"\n---\n" + OUTLINE_GOOD),
        )
        for genre, needle, fixed in cases:
            _, out = self.outline(OUTLINE_GOOD, "--genre", genre)
            self.assertIn(needle, out, genre)
            _, out = self.outline(fixed, "--genre", genre)
            self.assertNotIn(needle, out, genre)


class Mermaid(Fixture):
    def test_good_figure_has_no_info(self):
        rc, out = self.diag(MERMAID_GOOD)
        self.assertEqual(rc, 0, out)
        for needle in ("[F1]", "[F2]", "[M1]", "[P3]"):
            self.assertNotIn(needle, out, needle)

    def test_emoji_and_icon_fail(self):
        rc, out = self.diag(mermaid_doc("flowchart LR\n    A[\U0001F680 開始] --> B[終了]"))
        self.assertEqual(rc, 1)
        self.assertIn("絵文字", out)
        rc, out = self.diag(mermaid_doc("flowchart LR\n    A[fa:fa-car 開始] --> B[終了]"))
        self.assertEqual(rc, 1)
        self.assertIn("アイコン", out)

    def test_style_is_info(self):
        rc, out = self.diag(mermaid_doc("flowchart LR\n    classDef hot fill:#f96\n    A[開始] --> B[終了]\n    A --> C[処理]"))
        self.assertEqual(rc, 0, out)
        self.assertIn("[F2]", out)

    def test_linear_flowchart_is_m1(self):
        _, out = self.diag(mermaid_doc("flowchart LR\n    A[開始] --> B[処理] --> C[終了]"))
        self.assertIn("[M1]", out)
        _, out = self.diag(MERMAID_GOOD)
        self.assertNotIn("[M1]", out)

    def test_label_missing_from_prose(self):
        body = "flowchart LR\n    A[wp] --> B[rp]\n    A --> C[head]"
        _, out = self.diag(mermaid_doc(body, lead="本文は `head` を使う."))
        self.assertIn("[F1]", out)
        self.assertIn("'wp'", out)
        self.assertNotIn("'head'", out)

    def test_too_many_nodes(self):
        body = "flowchart TD\n" + "\n".join(f"    N0 --> N{i}" for i in range(1, 11))
        _, out = self.diag(mermaid_doc(body))
        self.assertIn("ノードが 11 個", out)

    def test_figure_without_reading_sentence(self):
        text = mermaid_doc("flowchart LR\n    A[開始] --> B[終了]\n    A --> C[処理]", after="## 次の節")
        _, out = self.diag(text)
        self.assertIn("[P3]", out)

    def test_adjacent_figures_share_context(self):
        text = ("ページ `PgA` を確保する.\n\n```text\n[S0] before\n+-----+\n| PgA |\n+-----+\n```\n\n"
                "```text\n[S1] after\n+-----+\n| PgA |\n+-----+\n```\n\n図は確保の前後を示す.\n")
        _, out = self.diag(text)
        self.assertNotIn("[F1]", out)


class ExcerptShape(Fixture):
    def doc(self, code, ref="`src/a.c:3-4`", lead="から抜粋する."):
        return f"# 抜粋\n\n{ref} {lead}\n\n```c\n{code}```\n"

    def test_runs_without_tree(self):
        rc, out = run(EXCERPT, [self.write(self.doc("int x = 1;\n"))])
        self.assertEqual(rc, 0, out)
        self.assertIn("照合は行わない", out)

    def test_long_excerpt_info(self):
        _, out = run(EXCERPT, [self.write(self.doc("int x; /* 宣言 */\n" * 31))])
        self.assertIn("[Q1]", out)

    def test_unannotated_excerpt_info(self):
        _, out = run(EXCERPT, [self.write(self.doc("int x;\n" * 10))])
        self.assertIn("[Q2]", out)
        _, out = run(EXCERPT, [self.write(self.doc("int x; /* 読む点 */\n" + "int x;\n" * 9))])
        self.assertNotIn("[Q2]", out)

    def test_authored_code_needs_no_source(self):
        text = "# 抜粋\n\n次の説明用のコードを示す.\n\n```c\nint x;\n```\n"
        _, out = run(EXCERPT, [self.write(text)])
        self.assertNotIn("出典(パス:行番号)", out)

    def test_python_reference_is_checked(self):
        os.makedirs(os.path.join(self.tmp.name, "src"), exist_ok=True)
        with open(os.path.join(self.tmp.name, "src", "a.py"), "w", encoding="utf-8") as f:
            f.write("def f():\n    return 1  # one\n")
        good = "# 抜粋\n\n`src/a.py:1-2` から抜粋する.\n\n```python\ndef f():\n    return 1  # 1 を返す\n```\n"
        rc, out = run(EXCERPT, ["--tree", self.tmp.name, self.write(good)])
        self.assertEqual(rc, 0, out)
        rc, out = run(EXCERPT, ["--tree", self.tmp.name, self.write(good.replace("return 1", "return 2"))])
        self.assertEqual(rc, 1)


class CheckDoc(Fixture):
    def check(self, text, *args):
        return run(CHECKDOC, list(args) + [self.write(text)])

    def test_runs_all_tools(self):
        rc, out = self.check(OUTLINE_PREVIEW)
        self.assertEqual(rc, 1)
        for name in ("lint_ja.py", "outline_ja.py", "check_diagrams.py", "check_excerpt.py"):
            self.assertIn(f"== {name} ==", out)
        self.assertIn("outline_ja.py=FAIL", out)

    def test_good_document_passes(self):
        rc, out = self.check(OUTLINE_GOOD, "--no-info")
        self.assertEqual(rc, 0, out)

    def test_genre_selects_tech_profile(self):
        rc, out = self.check(TECH_DOC, "--genre", "internals")
        self.assertEqual(rc, 1)
        self.assertIn("絶対パス", out)
        _, out = self.check(TECH_DOC, "--genre", "general")
        self.assertNotIn("絶対パス", out)

    def test_source_tree_from_frontmatter(self):
        os.makedirs(os.path.join(self.tmp.name, "src"), exist_ok=True)
        with open(os.path.join(self.tmp.name, "src", "a.c"), "w", encoding="utf-8") as f:
            f.write(SOURCE_C)
        text = (f"---\nsource_tree: {self.tmp.name}\n---\n# 抜粋\n\n抜粋は, 実装の一部である.\n\n"
                "`src/a.c:3-4` から抜粋する.\n\n```c\nint x = 2;\n```\n\n値は 2 になる.\n")
        rc, out = self.check(text, "--genre", "internals")
        self.assertEqual(rc, 1)
        self.assertIn("にない行", out)


class SkillIntegrity(unittest.TestCase):
    """作業中の巻き戻しと, 参照先の欠落を検出する."""

    def docs(self):
        paths = [os.path.join(SKILL, "SKILL.md")]
        for root, _, files in os.walk(os.path.join(SKILL, "references")):
            paths += [os.path.join(root, f) for f in files if f.endswith(".md")]
        return paths

    def test_skill_md_references_existing_files(self):
        with open(os.path.join(SKILL, "SKILL.md"), encoding="utf-8") as f:
            text = f.read()
        refs = [line.split("`")[1] for line in text.split("\n")
                if line.startswith("| ") and "`references/" in line]
        self.assertTrue(refs)
        for ref in refs:
            self.assertTrue(os.path.exists(os.path.join(SKILL, ref)), ref)
        for ref in ("references/document-design.md", "references/memory-layout.md",
                    "scripts/check_doc.py"):
            self.assertIn(ref, text)
            self.assertTrue(os.path.exists(os.path.join(SKILL, ref)), ref)

    def test_cross_references_exist(self):
        import re
        for path in self.docs():
            with open(path, encoding="utf-8") as f:
                text = f.read()
            for ref in re.findall(r"`((?:references|scripts)/[\w./-]+\.(?:md|py))`", text):
                self.assertTrue(os.path.exists(os.path.join(SKILL, ref)), f"{path}: {ref}")

    def test_no_references_to_removed_files(self):
        removed = ("references/" + "structure.md", "references/" + "explainer.md",
                   "implementation-" + "explanations")
        for path in self.docs() + [os.path.join(HERE, f) for f in os.listdir(HERE)
                                   if f.endswith(".py") and f != "test_lint.py"]:
            with open(path, encoding="utf-8") as f:
                text = f.read()
            for name in removed:
                self.assertNotIn(name, text, f"{path}: {name}")

    def test_skill_md_is_short(self):
        with open(os.path.join(SKILL, "SKILL.md"), encoding="utf-8") as f:
            self.assertLessEqual(len(f.read().rstrip("\n").split("\n")), 110)



if __name__ == "__main__":
    unittest.main(verbosity=1)
