---
name: qemu-storage-management
description: >-
  QEMUのraw/qcow2ディスクを調査し, qemu-nbdによるオフライン保守,
  discard, sparsify, 変換, 整合性確認を安全に行う.
  仮想ディスク内の削除後にホスト上のイメージが増えた場合や,
  配布用イメージを縮小する場合に使う.
---

# QEMU Storage Management

QEMUディスクのゲスト使用量, ホスト割当量, 仮想容量を区別し,
要求された対象だけを変更する.

具体的なコマンドが必要な場合は,
[README.md](README.md)の該当手順を読む.

## 安全条件

- 実行中のVM, mount中のfilesystem, 接続中のNBDを変更しない.
- `qemu-img convert`の入力と出力を同じパスにしない.
- 元イメージは, 検証とboot testが完了するまで置換しない.
- backing chainがある場合は, flattenしてよいか確認する.
- filesystemやpartitionの削除は, ユーザーが明示的に許可した
  範囲だけで行う.
- root権限やホストデバイス操作が必要な直前に承認を得る.
- 失敗時も`umount`してからNBDを切断する.

## 調査

最初に次を確認する.

1. `qemu-img info --backing-chain`で形式, 仮想容量,
   ホスト割当量, backing chainを確認する.
2. `ls -lh`と`du -h`を比較する.
3. `findmnt`, `lsblk`, `/sys/block/nbd*/pid`を確認し,
   使用中のイメージやNBDを特定する.
4. NBD接続後は`lsblk -f`と`blkid`で,
   filesystemがディスク直下かpartition内かを判定する.

次の値を混同しない.

- filesystem使用量: ゲストfilesystemが使用しているblock量.
- ホスト割当量: ホストfilesystemがイメージへ割り当てたblock量.
- 仮想容量: ゲストから見えるディスク容量.

ファイル削除はfilesystem使用量を減らすが,
discardなしではホスト割当量を減らさない.
qcow2のcopy-on-writeとfilesystem journalにより,
削除直後にホスト割当量が増えることもある.

## 目的別の処理

### ゲスト使用量を減らす

filesystemをオフラインでmountし,
ユーザーが指定したファイルだけを削除する.
削除前後の`du`を記録する.

### ホスト割当量を減らす

`qemu-nbd`を`--discard=unmap`と
`--detect-zeroes=unmap`付きで接続する.
filesystemをmountして`fstrim`を実行し,
未使用blockをqcow2へ通知する.

`fstrim`後は`ls`の表示が変わらず,
`du`または`qemu-img info`の`actual-size`だけが
減る場合がある.

### 配布ファイルを詰め直す

NBDを切断した後, 別パスへ`qemu-img convert`する.
配布サイズを優先する場合はqcow2圧縮を検討する.
書き込み性能を優先する場合は非圧縮のsparse出力を使う.

変換後に次を確認する.

1. `qemu-img check`が成功する.
2. `qemu-img compare`で元イメージと一致する.
3. `qemu-img info`, `ls -lh`, `du -h`を記録する.
4. 実際のQEMU launcherでboot testする.

### 仮想容量を減らす

単なる配布サイズ削減では仮想容量を変更しない.
仮想容量の縮小が必要な場合は,
filesystem, partition, diskの順に外側を縮小する.
filesystemより先に`qemu-img resize --shrink`を実行しない.

## filesystem別の扱い

- ext4は, unmount状態で`e2fsck`を行ってから保守する.
- XFSは縮小できないが, mount状態でtrimできる.
- 未知のfilesystemへext4用コマンドを適用しない.
- LVM, LUKS, partition tableがある場合は,
  各層を識別してから対象deviceを選ぶ.

## 完了報告

次を簡潔に報告する.

- 変更したイメージとfilesystem.
- 削除, trim, convertのどこまで実行したか.
- 変更前後のfilesystem使用量とホスト割当量.
- `qemu-img check`, compare, boot testの結果.
- 元イメージを保持しているか.
- 未実行の検証と残る制約.
