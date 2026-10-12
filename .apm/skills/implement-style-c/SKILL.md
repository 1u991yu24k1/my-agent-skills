---
name: implement-style-c
description: Apply the project's C coding conventions when writing, modifying, reviewing, or formatting C source and header files. Enforce the specified clang-format rules, function/struct/enum layout, include guards with trailing #endif comments, and C-style comments. Use for .c and .h changes or when asked to check C code style.
---

# Implement Style C

## When to apply

Use this skill when creating, editing, refactoring, or reviewing C (`.c`, `.h`) code. Apply it to touched code rather than reformatting unrelated files. Do not apply it automatically to C++ projects, generated code, or third-party/vendor sources unless explicitly requested.

## Required workflow

1. Inspect the target project's `.clang-format` and nearby source conventions. Preserve explicit project requirements when they conflict with this skill, and report the conflict.
2. For new projects without a formatter configuration, create `.clang-format` using the canonical configuration below. For existing configurations, propose or apply only the changes authorized by the task; do not silently overwrite unrelated options.
3. Implement or edit the requested C code. For new headers, create a collision-resistant include guard and an exactly matching `#endif /* GUARD_NAME */` comment.
4. Format only the files or changed ranges in scope with `clang-format --style=file`. If the formatter is unavailable, follow the rules manually and report that formatting was not run.
5. Review formatting, blank lines, comments, and include guards. In particular, do not expect clang-format to synthesize missing `#endif` comments.
6. Report any style deviations or validation limitations in the final response.

## Canonical clang-format configuration

```yaml
BasedOnStyle: LLVM
Language: Cpp

IndentWidth: 4
UseTab: Never
ColumnLimit: 128
PointerAlignment: Right
IndentCaseLabels: true

BreakBeforeBraces: Custom
BraceWrapping:
  AfterFunction: true
  AfterControlStatement: Never
  AfterCaseLabel: false
  AfterStruct: false
  BeforeElse: false

SeparateDefinitionBlocks: Always

Macros: [ "VA_ARGS" ]

AllowShortBlocksOnASingleLine: Never
AllowShortIfStatementsOnASingleLine: Never
AllowShortLoopsOnASingleLine: false
AllowShortEnumsOnASingleLine: false
```

## Brace style

関数定義の opening brace は次行に置きます.

```c
int net_init(void)
{
    return 0;
}
```

`if`, `for`, `while`, `switch` などの制御構文では opening brace を同じ行に置きます.

```c
if (platform_init() == -1) {
    return -1;
}
```

`else` は closing brace と同じ行に置きます.

```c
if (cond) {
    foo();
} else {
    bar();
}
```

## Definition blocks

関数, 構造体, 列挙体などの定義ブロック同士の間には空行を 1 行入れます.

```c
struct foo {
    int value;
};

struct bar {
    int value;
};

int foo_init(void)
{
    return 0;
}
```

`SeparateDefinitionBlocks: Always` を使用して定義ブロック間を分離します.

## Enum style

列挙体は 1 行に圧縮しません.

```c
enum kedr_type {
    KEDR_EXEC = 1,
    KEDR_ELF,
    KEDR_MEMORY,
    KEDR_SYSCALL,
    KEDR_SPRAY,
    KEDR_GROOM
};
```

`AllowShortEnumsOnASingleLine: false` を使用します.

## Indentation

- インデント幅は 4 spaces とします.
- tab は使用しません.
- `case` ラベルは `switch` 本体より 1 段深くインデントします.

```c
switch (type) {
    case KEDR_EXEC:
        handle_exec();
        break;

    default:
        break;
}
```

## Pointer style

`*` は変数名側に寄せます.

```c
char *buf;
struct foo *ctx;
```

以下の形にはしません.

```c
char* buf;
```

## Include guard

ヘッダファイルには include guard を使用します.

```c
#ifndef KEDR_GUARD_H
#define KEDR_GUARD_H

/* declarations */

#endif /* KEDR_GUARD_H */
```

### Guard name

原則として, ファイル名またはプロジェクト内で一意になる名前を uppercase snake case に変換して使用します.

例:

```text
kedr_guard.h        -> KEDR_GUARD_H
kedr_guard_event.h  -> KEDR_GUARD_EVENT_H
net/platform.h      -> NET_PLATFORM_H
```

プロジェクト名を prefix に含めても構いません.

```c
#ifndef MICROPS_NET_PLATFORM_H
#define MICROPS_NET_PLATFORM_H
```

### `#endif` comment

include guard の末尾には必ず guard macro 名をコメントで記載します.

```c
#endif /* KEDR_GUARD_H */
```

clang-format はこのコメントを自動生成しません.
したがって, 新規ヘッダ作成時に明示的に記述してください.

## Comments
コメントを 日本語で記載するか, 英語で記載するかまずユーザに確認すること. 
* ClaudeCode: askUserQuestion
* OpenAI Codex: request_user_input

日本語でコメントを書く場合は, clear-japanese スキルを使用すること.

### General rule

通常の説明コメントは C-style block comment を優先します.

```c
/* Initialize the platform backend before network setup. */
```

短い補足や構造体メンバの説明にも同じ形式を使用します.

```c
struct kedr_event {
    uint32_t type;   /* Event type. */
    uint32_t size;   /* Payload size in bytes. */
};
```

### Multi-line comments

複数行コメントは次の形式にします.

```c
/*
 * Initialize the backend first.
 * The network layer depends on platform-specific state.
 */
```

先頭行に本文を書かず, 2 行目以降を ` * ` で揃えます.

### Function comments

関数の意図や制約を説明する必要がある場合は, 関数定義の直前に記載します.

```c
/*
 * Initialize network-related state.
 * Returns 0 on success and -1 on failure.
 */
int net_init(void)
{
    ...
}
```

自明な関数に冗長なコメントは付けません.
コメントはコードそのものの説明ではなく, 意図, 前提, 制約, 副作用, 非自明な理由を書くために使用します.

### TODO comments

未実装や後続作業は `TODO:` を使用します.

```c
/* TODO: Replace this with lock-free queue handling. */
```

必要であれば owner や issue ID を追記して構いません.

```c
/* TODO(ryo): Remove after event ABI v2 migration. */
```

### Disabled code

コードをコメントアウトして残すことは原則避けます.
不要なコードは削除し, 履歴は VCS に任せます.

## Struct initialization

構造体初期化では, project style に合わせて braced initializer 内の spacing を統一します.

```c
struct sigaction sa = { 0 };
```

この形式が必要な場合は, 使用中の clang-format の挙動を確認したうえで次を追加します (これは上記 canonical configuration には含まれません).

```yaml
Cpp11BracedListStyle: false
```

ただし, この設定は braced-init-list 全般に影響するため, プロジェクト全体で採用する場合のみ有効化してください.

## Short statements

短い block や `if` であっても 1 行にはまとめません.

```c
if (failed) {
    return -1;
}
```

以下の形にはしません.

```c
if (failed) return -1;
```

## Line length

1 行は原則 128 columns 以内に収めます.

長い呼び出しや条件式は, clang-format の結果に従って適切に改行します.

## clang-format usage

現在の設定を確認する場合は次を使用します.

```sh
clang-format --style=file --dump-config
```

利用中バージョンは次で確認します.

```sh
clang-format --version
```

ファイルを整形する場合は次を使用します.

```sh
clang-format -i path/to/file.c
clang-format -i path/to/file.h
```

VS Code では C / C++ の `editor.formatOnSave` を有効にし, 保存時に自動整形する運用を推奨します.

## Implementation checklist

実装時には以下を確認します.

- `.clang-format` に従って整形されている.
- 関数定義の `{` は次行にある.
- 制御構文の `{` は同じ行にある.
- 関数, struct, enum 定義間に空行がある.
- enum が 1 行に圧縮されていない.
- indentation は 4 spaces で tab を使用していない.
- pointer `*` は変数名側に寄っている.
- header に include guard がある.
- `#endif /* GUARD_NAME */` が付いている.
- コメントは C-style を基本とする.
- コメントは処理内容の逐語説明ではなく, 意図や制約を書く.
- 不要なコメントアウトコードを残していない.
- 1 行が原則 128 columns を超えていない.
