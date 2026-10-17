# 悪い例

## 使用している単語が何由来なのかわからない. 

### 例1: 
以下の例は, kernelのDevice Driver開発でCodex が使用した文章である. 
この1文は, 使用している単語の由来がわからない. 

```
module exit は online flag を落とし, 全 probe を unregister して grace period を待つ.
```

5つの単語が出ているが, どの単語も引用元が不明確である. 

* `module exit`
* `online flag`
* `probe`     
* `unregister`
* `grace period`

文章の単語数だけを徒に切り詰めた結果, 日本語としておかしな文章を生成し, ユーザの認知負荷増加につながる. 

中身を読むと, 

* `module exit`は, `rmmod` 実行時に呼び出される, Device Driverの `module_exit()` マクロのこと. 
* `online flag`は, グローバル配列 `probes[]` の要素である`sensor_probe` 構造体の `registered` メンバのこと.  
* `probe`は同じく, グローバル配列 `probes[]`のこと. 全 `probe`とは, 配列の全要素を指す. 
* `unregister`とは, `unregister_probes()`を呼び出すこと. 
* `grace period`とは, カーネルの非同期処理が完了し, 同期的に安全に終了できるまでの期限のこと. 
  `tracepoint_synchronize_unregister()` というカーネル内の関数を呼び出す. 

つまり, 言いたいことは以下である. 
```
`rmmod`などのドライバアンロード時に, `module_exit`内で, `unregister_probes()`を呼び出し, 内部で以下の処理を行う. 
1. グローバル配列 `probes[]` の`registered`な要素に対して, 
  - `tracepoint_probe_unregister()`を呼び出し, 
  - `probes[i].registered`をクリアする.  
2. `tracepoint_synchronize_unregister()`を呼び出し, 同期的にドライバをアンロードできるまで待つ. 
```

これは, 由来不明な英単語が存在しない. 
`...` な部分は, コード中の変数, 関数名や構造体名だと即時に判別でき, 
実際のコードと突き合わせられる文章であるため, ユーザは即時にコードに従いながら処理フローに追従できる. 
 
また, 文章としては長くなっているが, 処理の内容を分離し, 
箇条書きにすることでユーザに取って認知負荷を上げにくい構造になっている. 

### 例2: 突然文中にコードブロックが現れる 
以下は BPF の解説資料作成中に Codex が作成した文章. 

```
... (別のトピックの文章) ... 

\`\`\`c
  uint32_t key = 0;
  uint64_t value = 0;
  union bpf_attr lookup = {
      .map_fd = map_fd,
      .key = (uint64_t)(uintptr_t)&key,
      .value = (uint64_t)(uintptr_t)&value,
  };
 
  if (syscall(SYS_bpf, BPF_MAP_LOOKUP_ELEM, &lookup, sizeof(lookup)) == -1) {
      perror("BPF_MAP_LOOKUP_ELEM");
  }
\`\`\`
 
syscall の lookup は値を userland の buffer にコピーする.
BPF helper の lookup は program が使える map value pointer を返す.
同じ「lookup」でも返すものが異なる.
```

突然 Code Block → 説明という流れで記述されると, 
ユーザは一度そのCode Blockに対する認知を0から組み立てる必要があり, 認知負荷が高い. 

そのため, まずその Code Block で何を説明したいのか? 
Code Blockが何をしているのかを先に説明する. 

``` 
... (別のセクションの話し) ...

mapから値を取得するための実際の Cコードの例を示す. 

以下のコードは, `bpf` システムコールを使用して,
map から値を取得(lookup)するための処理を示している.

\`\`\`c
  ...
\`\`\`

`lookup.value` には,検索結果の値を書き込むべきポインタをセットする.
これにより, `value` に対して, 検索結果の値が kernel から書き込まれる.
