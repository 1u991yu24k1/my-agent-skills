#!/usr/bin/env python3
"""lint_ja.py と check_diagrams.py の回帰試験. 標準ライブラリのみ.

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


class SkillIntegrity(unittest.TestCase):
    """作業中の巻き戻しを検出する."""

    def test_skill_md_references_existing_files(self):
        with open(os.path.join(SKILL, "SKILL.md"), encoding="utf-8") as f:
            text = f.read()
        for ref in ("references/explainer.md", "references/memory-layout.md",
                    "scripts/lint_ja.py"):
            self.assertIn(ref, text)
            self.assertTrue(os.path.exists(os.path.join(SKILL, ref)), ref)


if __name__ == "__main__":
    unittest.main(verbosity=1)
