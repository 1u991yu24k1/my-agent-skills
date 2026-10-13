---
name: ctf-writeup-skill
description : AI Agent が CTF challenge の writeup を記述するためのスキル. 
---

Challenge を解き flag を得たタイミングで起動する.
Challengeの名前, description, flag, 解析結果, Bug Class / Vulnerability,
Exploit組み立て方針, Primitives の構築方法, 最終 Exploit 実行結果を md ファイルに残す.


askUserQuestion / read_input により, writeup の言語を, 英語で記述するか, 日本語で記述するかを決めること. 
日本語で記述する場合, `clear-japanese` スキルを使用して, 明瞭な日本語で記述すること. 
> If `clear-japanese` is unavailable, report the missing dependency rather than silently substituting it.


## 記載方式

writeup を記述する際には, 以下規約を遵守する.

* 文章は日本語で記載する.
* markdown ファイルで記述する.
* ファイル名は, `<カテゴリ>_<チャレンジ名>_writeup.md` とする.
  * チャレンジ名に, ファイル名に使用できない文字がある場合は, チャレンジ名を正規化, サニタイズする.

## 記載内容

以下を必ず含める.

1. 解析結果の実際のコマンド, スクリプト結果.
2. Challenge の Root Cause となる Bug Class とそれを発火させる最小の PoC.
3. Exploit 組み立て方針.
4. Exploit 成功に必要な 各種primitives, Mitigation bypasses.
5. Flag を求解するための, Final Exploit と実行結果
6. 得られた flag 
7. Challenge に対する Key Findings.

### 解析結果の実際のコマンド, スクリプト結果

解析結果は, 要約サマリだけでなく実行したコマンドの証跡を載せる.

* 悪い例

```
配布されたバイナリは, PIE + NX 有効.
```

* 良い例

```
checksec 実行結果 : `gdb -ex checksec ./chall`
(ctf-venv) root@Ubu2604x64:pwn_chall1# gdb -ex 'checksec' ./chall
Loading GEF...
GEF is ready, type 'gef' to start, 'gef config' to configure
Loaded 410 commands (+110 aliases) for GDB 17.1 using Python engine 3.14
[+] Could not find /root/.gef.rc, GEF uses default settings
Reading symbols from ./revenant-worker...
(No debugging symbols found in ./revenant-worker)
--------------------------------------------------------- Basic information ---------------------------------------------------------
Canary                                  : Enabled
NX                                      : Enabled
PIE                                     : Enabled
RELRO                                   : Full RELRO
Fortify                                 : Not found
------------------------------------------------------ Additional information ------------------------------------------------------
Static/Dynamic                          : Static-PIE
Symbol                                  : Stripped
Debuginfo                               : Stripped
CET SHSTK feature flag (via Ehdr)       : Found
CET IBT feature flag (via Ehdr)         : Found
System ASLR                             : Enabled (randomize_va_space: 2)
GDB ASLR setting                        : Disabled (disable-randomization: on)
gef>
配布されたバイナリは, Static PIE + NX
```

コマンド結果の全てを載せる必要はないが, writeup の読み手が,

* どのようなコマンド打つのか
* そのコマンドの結果のどこに着目するべきか

を, 判断できること.

### Challenge の Root Cause となる Bug Class とそれを発火させる最小の PoC

悪い例.

```
関数 XXX の stack BOF がRoot Cause.
```

良い例

```
関数 XXX には, Stack BOF の脆弱性がある. スタックバッファが, 20 bytes 固定なのに対して, 
`read`関数で, 64 bytes を読み込む. 
```

また, race condition や data race を説明する場合, 文字だけでなく, UML シーケンス図 (mermaidが望ましい)を記載すること.

PoC は, 実コードを交えて説明する場合,
boiler plate コード(例: `from pwn import *` とか `#include <stdio.h>` とか)は省略して良い.


また, `objdump`や, `gdb`の crash 時 context 出力も, 出力結果全てを載せる必要はない.
> 例えば, 脆弱性を持つ関数のみを載せる, stack contextと code context だけ載せるなどの, 重要部分だけをトリアージして記載して良い. 
> 繰り返し同じ入力を行う部分は, (以降 n 回繰り返し... ) のような表現も可. 

ただし, コマンド結果を載せる場合は, コピペして後から同じ実行結果が得られるようにオプションなどを含めて記載すること.

## Exploit 組み立て方針
方針の組み立てロジックの構築には必ず根拠となった理由を示すこと. 
また, 複数の方針を試して, 実験や検証により棄却した方針などがあれば, それも記載する. 
また, 複数方針を検討し, どちらの方針でも Exploit が成功する場合も その旨記載する. 

## Exploit 成功に必要な 各種primitives, Mitigation bypasses
何ができれば RCE / LPE / SBX Escape できるのかを具体的に記述する. 
また AAR / AAW / AddrOf / FakeObj などの強力な primives 作成を説明する際には, 
それぞれ前提として想定しているメモリのレイアウトを図示すること. 

## Flag を求解するための, Final Exploit
最終的な Exploit コードを記載すること. 
ただし, 解析, 推論によってすでに別ファイルとして Final Exploit が存在する場合, そのファイルへの参照パスを記載すること.
ここでの成果物は, 必ずソースコードであり人間が可読可能であること. (LPE などで バイナリをそのまま配置するのは NG )

また、**実行結果も記載すること** . 

例えばoutbound socket が作れない場合などでエージェントが直接実行できない場合, ユーザに実行結果の取得を求めること.
Final Exploitが 別ファイルに存在する場合は, 実際の実行結果 (flag 抽出結果) を コードコメントに示すこと. 

LPE などで Exploit Code が C 言語の場合には, 以下も記述すること. 
* ビルド手順(gccやclang, musl-gccのコマンドラインオプション)
* initramfs / ディスクイメージへの埋め込み (cpio や mount / umount ) 
* `implement-style-c` スキルを使用して, 見やすいコードを記述すること. 

尚, ビルドについては, Makefile を作成し, そのファイルへの参照を記載する方針でもよい. 

もし, Exploit 方針に 確率的ロジックを採用しており, Exploit 成功 / flag 取得に複数回実行する可能性がある場合は, 
その旨も記載. 理論値の成功確率も記載する. 
もし, 複数回試行を Exploit Code 内で回している場合でも, 成功確率は記載すること. 

また, Exploit の実行 or ビルドに必要な ツール, 3rd party library がある場合, そのインストール方法も記載する. 
* インストールする環境は Ubuntu 想定でよい. 
* ソースコードからビルドする必要があるものは, ビルド手順も含めて記載する. 
* `pwntools` / `ptrlib` は代表的なので明記不要.

## 得られた flag 
Exploit の実行結果から, 得られた flag を 見やすい形で記載すること. 

## Challenge に対する Key Findings
この問題を求解する上で, 理解しておくべき技術的/概念的エッセンス, 知っておくべき概念, 調査しておくべきドキュメント, 題材として扱ったプロジェクトを記載する. 
 
