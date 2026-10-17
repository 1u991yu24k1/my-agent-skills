---
name: ctf-writeup-skill
description : AI Agent が CTF challenge の writeup を記述するためのスキル. 
---

以下のタイミングで起動する. 
* AI エージェントが CTF Challenge を解き flag を得たタイミングで起動する.
* ローカルでupsolveしている場合は, リモートシェルが取れた場合(RCE) or ローカルのrootシェルが取れた場合(LPE).
* ユーザが, 「writeup を記載して」,「解説記事書いて」とエージェントに依頼した場合.

## 記事の体裁
明示的に指定されない場合は, 以下のフォーマットで記述する. 
* Markdown 1ファイルで記述する.
  * ファイル名は, `<カテゴリ>_<チャレンジ名>_writeup.md` とする.
  * 例:
    * `pwnable_pwnme_writeup.md`
    * `crypto_solve-cheap-rsa_writeup.md`
    * `reversing_crackme_writeup.md`
    * `web_exploit_ssrf_writeup.md`
  * チャレンジ名に, ファイル名として使用できない文字がある場合は, 名前を正規化/サニタイズすること. 
* 内容は, 特に指定しない限り日本語で記述する. 

## 記載内容

記事内には, 以下を必ず含める.

* Challengeの情報
  * チャレンジ名
  * description
* チャンレンジの解析結果
  * スクリプトやコマンドの実行結果
  * Root Cause となる Bug Class / Vulnerabilityとそれを発火させるPoC
* Exploit方針組み立て過程
  * Primitives の構築方法
  * mitigation bypass方法
  * RCE / LPE / VMEscapeを達成するペイロードの方針
* 最終 Exploit Codeと その実行結果. 
* flag (取得できた場合のみ. もしupsolveや練習でflagがない場合は, その旨を記載)
* Challenge に対する Key Findings.

### Challengeの情報
チャレンジの名前, Descriptionを記載する. 
もし, connect info や, 別サイトへのリンク参照がある場合は, それも記載する. 
また, チャレンジの配布物も `tree`コマンド方式で記載する. 

### チャンレンジの解析結果
チャレンジの初動解析, Root Cause, その発火方法を端的に書く. 

初動解析で書くべきは, 例えば以下のようなもの. 
* fileコマンド結果
* Dockerfileの中身や, libcのバージョン情報.
* ソースコードが添付されている場合は, `main`ロジック部分.
* checksecコマンド結果 (bata24/gefの checksecコマンドが望ましい. 例は後述)
* チャレンジを起動するためのコマンド.
  * 例えば, `docker`の起動方法や, kernel exploit challenge なら `run.sh`の中身や, `qemu-system`の起動コマンド.
  * リモートに `nc`でつなぎに行ったときの挙動など.
  * また, ソースが添付されていないバイナリなら, `main`ロジックを, Decompileした疑似コードなども有用.
    
> [!Warning]
> `main`ロジックとは必ずしも `main`関数を意味しない.
> チャレンジアプリケーションのコアロジックを実装しているコードブロック全般を指す. `main`関数でなくてもよい.

#### スクリプトやコマンドの実行結果
解析結果は, 要約サマリだけでなく実行したコマンドの証跡を載せる.
* 悪い例
```
配布されたバイナリは, PIE + NX 有効.
```
* 良い例
```
checksec 実行結果(`gdb -ex checksec ./chall`)
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

コマンド結果の全てを載せる必要はないが, writeup の読み手が以下を判断できることが重要. 
* どのようなコマンド打つのか
* そのコマンドの結果のどこに着目するべきか

### Challenge の Root Cause となる Bug Class とそれを発火させる最小の PoC

Root Cause Analysisでは, 必ずBug Classと発火させる最小PoCを含める. 

また, 以下を遵守すること. 
* 自然言語だけの説明ではなく, 図解や転記コードにコメントを入れて実コードとの突合を踏まえて記載するのが望ましい.
  * race condition や data race を説明する場合, 文字だけでなく, UML シーケンス図 (mermaidが望ましい)を記載すること. 
* PoCのコード全体は別コードにしてもよい. ただしPoCの理解に必要な部分はドキュメント内に Inline Code Blockで記載すること. 
* PoCのコードだけでなく, PoC自体を実行した結果も載せること.
* AOT コンパイルなどで実行前にビルド処理や, 前処理が必要な場合はそれも記載すること.
* 別途ライブラリのインストールが必要な場合は, インストール方法を記載すること.
  * ユーザの実行環境は Ubuntu の最新LTSバージョン (2026/10時点で, 26.04 LTS). x86_64を使用していると想定して良い.
  * aptでインストールする or ソースコードからビルドする.  
  * pythonは, uv をインストールしていると仮定して, インストールコマンドを記載すること. (`uv pip install ...`)
  * 尚, `pwntools` は例外としてよい.

**悪い例**
```
関数 XXX の stack BOF がRoot Cause.
```

**良い例**
```
関数 XXX には, Stack BOF の脆弱性がある. スタックバッファが, 20 bytes 固定なのに対して, 
`read`関数で, 64 bytes を読み込む. 
```

また, 

PoC は, 実コードを交えて説明する場合,
boiler plate コード(例: `from pwn import *` とか `#include <stdio.h>` とか)は省略して良い.

また, `objdump`や, `gdb`の crash 時 context 出力も, 出力結果全てを載せる必要はない.
> 例えば, 脆弱性を持つ関数のみを載せる, stack contextと code context だけ載せるなどの, 重要部分だけをトリアージして記載して良い. 
> 繰り返し同じ入力を行う部分は, (以降 n 回繰り返し... ) のような表現も可. 

ただし, コマンド結果を載せる場合は, コピペして後から同じ実行結果が得られるようにオプションなどを含めて記載すること.

### Exploit方針組み立て過程
何ができれば RCE / LPE / SBX Escape できるのかを具体的に記述する. 
方針の組み立てロジック構築には, 必ず根拠となった理由を示すこと. 
また以下の内容も記載すること. 
* 複数の方針を試して, 実験や検証により棄却した方針がある場合, 棄却した理由を記載する.
* 複数方針を検討し, 複数の方針で Exploit が成功する場合, 別解として記載する.  


#### Primitives の構築方法
まず組み立てに伴い, どのようなprimitiveが構築できればよいかを記載すること.
複数種 or 複数回の限定的な Primitives をより強力な primitives に拡張できるか? 
それとも, 限定的な Primitives のみで Exploit完了まで持っていけるか？など, 
Exploitの Step毎に必要な Primitive内容を説明すること. 

また AAR / AAW / AddrOf / FakeObj などの強力な primives 作成を説明する際には, 
それぞれ前提として想定しているメモリのレイアウトを図示すること. 

#### mitigation bypass方法
* ASLR / KASLR(Virtual/Physical) のバイパスは必要か？
* Cage Sandboxを抜けられるか?
* SMEP/SMAP/CET などの CPU 固有の mitigationを回避できるか？
* CONFIG_STATIC_USERMODE_HELPER や CONFIG_SLAB_VIRTUAL, COFNIG_KMALLOC_RANDOM_CACHESなどのkernelのmitigationを回避できるか?

#### RCE / LPE / VMEscapeを達成するペイロードの方針
最終的な リモートshell実行, ローカルのroot実行, ホストシェル実行に繋げるには, どのようなペイロードが実行できればよいか？という観点で
記載する. 
例えば観点は以下の通り. 
* シェルコードを直接実行できるか?
* ROP/COP/JOPから `system("/bin/sh")`, `execve("/bin/sh", NULL, NULL)`できるか? / `commit_creds(prepare_kernel_creds(&init_creds))` or cred=0できるか?
* one_gadgetは有効か？
* BPF JITに jmp / ret できるか？
* Physicalメモリを書き換えられるか?
* Page Tableを書き換え可能か？
* Dirty Pipeテクニック, PipeBufferテクニックは使用可能か？
* ユーザランドに戻った場合に, 別のアクションが必要か?
* 別namespaceへのslideが必要か？
* ページキャッシュは書き換え可能か？

ここは前説の, [Primitives の構築方法], [mitigation bypass方法] と深く関わる内容であるため, 必ずしも章立てはこの通りにしなくても良い. 

## 最終 Exploit Codeと その実行結果
最終的な Exploit コードを記載すること. 
ただし, 解析, 推論によってすでに別ファイルとして Final Exploit が存在する場合, そのファイルへの参照パスを記載すること.
その場合は, `main`ロジックのみだけでも, Inline Code Blockに含めること. 
> ここでの成果物は, 必ずソースコードであり人間が可読可能であること. (LPE などで バイナリをそのまま配置するのは NG )

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
尚, upsolveやローカルでの実行で, flagがない場合は, その旨を記載すること. 

## Challenge に対する Key Findings
この問題を求解する上で, 理解しておくべき技術的/概念的エッセンス, 知っておくべき概念, 調査しておくべきドキュメント, 題材として扱ったプロジェクト, CVEを記載する. 
 
