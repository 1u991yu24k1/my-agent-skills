# qemu-storage-management

QEMUのraw/qcow2ディスクを安全に調査し,
不要ファイルの削除, discard, compactを行う手順です.

ファイルを削除したのにqcow2が増える現象にも対応します.

## なぜ削除後にqcow2が増えるのか

ゲストfilesystemでファイルを削除すると,
filesystemはinode, block bitmap, directory,
journalを更新します.

qcow2はcopy-on-write形式なので,
これらの更新に新しいclusterを割り当てます.
一方, 削除したdata blockはdiscardされない限り,
qcow2側で解放されません.

このため, filesystem使用量が減っても,
qcow2のホスト割当量は増える場合があります.

## 3種類のサイズ

次の値は別々に確認します.

| 値 | 確認方法 |
|---|---|
| 仮想容量 | `qemu-img info`の`virtual size` |
| ホスト割当量 | `du -h`, `actual-size` |
| ファイル終端 | `ls -lh` |

raw sparse imageでは, `ls`が示すサイズより
`du`が小さくなることがあります.
qcow2でもdiscard後に同様の差が生じる場合があります.

## 前提条件

次のコマンドを使用します.

- `qemu-img`
- `qemu-nbd`
- `lsblk`
- `blkid`
- `mount`, `umount`
- `fstrim`
- 対象filesystem用の検査コマンド

NBDの接続, mount, filesystem修復にはroot権限が必要です.

## 安全確認

VMを停止し, イメージが使用されていないことを確認します.

```sh
pgrep -af 'qemu-system|qemu-kvm'
findmnt | grep -E 'nbd|rootfs'
lsblk -o NAME,SIZE,FSTYPE,MOUNTPOINTS
sudo fuser -v ./rootfs.qcow2
```

使用中のイメージに`qemu-img convert`, filesystem修復,
resizeを実行しないでください.

元イメージはboot testが終わるまで残します.

## イメージの調査

例では次の変数を使用します.

```sh
IMAGE=./rootfs.qcow2
OUTPUT=./rootfs.compact.qcow2
NBD=/dev/nbd0
MOUNT=/mnt/rootfs
```

形式, backing chain, 仮想容量, ホスト割当量を確認します.

```sh
qemu-img info --backing-chain "$IMAGE"
ls -lh "$IMAGE"
du -h "$IMAGE"
```

backing fileがある場合, `qemu-img convert`は通常,
参照先を含む現在のdisk内容を新しいイメージへflattenします.
この変更が意図どおりか確認してください.

## NBDへの安全な接続

NBD kernel moduleを用意します.

```sh
sudo modprobe nbd max_part=16
```

discardをqcow2へ伝播させて接続します.

```sh
sudo qemu-nbd \
    --discard=unmap \
    --detect-zeroes=unmap \
    --connect="$NBD" \
    "$IMAGE"
sudo udevadm settle
```

filesystemの配置を確認します.

```sh
lsblk -f "$NBD"
sudo blkid "$NBD" "${NBD}p1" 2>/dev/null || true
```

filesystemがディスク直下なら次を使います.

```sh
FSDEV=$NBD
```

最初のpartition内なら次を使います.

```sh
FSDEV=${NBD}p1
```

出力を見ずに`FSDEV`を決めないでください.

## ext4の検査

まず, 書き込まない検査を行います.

```sh
sudo e2fsck -fn "$FSDEV"
```

修復が必要なら, 元イメージを保存したうえで実行します.

```sh
sudo e2fsck -fy "$FSDEV"
```

`e2fsck`はmount中のfilesystemへ実行しないでください.

## ファイル削除とtrim

filesystemをread-writeでmountします.

```sh
sudo mount -t ext4 -o rw "$FSDEV" "$MOUNT"
```

削除前の使用量を記録します.

```sh
df -h "$MOUNT"
sudo du -x -h -d 1 "$MOUNT" | sort -h
```

必要なファイルを削除した後,
未使用blockをqcow2へ通知します.

```sh
sudo fstrim -v "$MOUNT"
sync
sudo umount "$MOUNT"
sudo qemu-nbd --disconnect "$NBD"
```

途中で失敗した場合も,
mount解除後にNBDを切断してください.

切断後の割当量を確認します.

```sh
ls -lh "$IMAGE"
du -h "$IMAGE"
qemu-img info "$IMAGE"
```

`ls`の値が変わらなくても,
`du`または`actual-size`が減っていればdiscardは有効です.

## qcow2のcompact

discardだけではファイル末尾の未使用clusterが残る場合があります.
新しいqcow2へ変換すると, 配置を詰め直せます.

配布サイズを優先する場合は圧縮します.

```sh
qemu-img convert \
    -p \
    -f qcow2 \
    -O qcow2 \
    -c \
    "$IMAGE" \
    "$OUTPUT"
```

書き込み性能を優先する場合は,
圧縮せずsparse出力にします.

```sh
qemu-img convert \
    -p \
    -f qcow2 \
    -O qcow2 \
    -S 4k \
    "$IMAGE" \
    "$OUTPUT"
```

入力と出力に同じパスを指定しないでください.

## 変換後の検証

qcow2構造を確認します.

```sh
qemu-img check "$OUTPUT"
qemu-img info "$OUTPUT"
ls -lh "$OUTPUT"
du -h "$OUTPUT"
```

仮想ディスクの内容を元イメージと比較します.

```sh
qemu-img compare "$IMAGE" "$OUTPUT"
```

最後に, 実際のQEMU launcherでboot testします.
service, device node, ログイン, challengeの動作を確認してから,
元イメージを置換します.

## 仮想容量も縮小する場合

ホスト上の配布サイズを減らすだけなら,
`virtual size`を縮小する必要はありません.

仮想容量を縮小する場合は,
必ず内側から次の順序で処理します.

1. filesystemを縮小する.
2. partitionを縮小する.
3. qcow2の仮想容量を縮小する.

filesystemより先に次を実行するとdataを失います.

```text
qemu-img resize --shrink
```

XFSは縮小できません.
LVM, LUKS, partition tableがある場合は,
各層に個別の縮小手順が必要です.

## パッキング処理への組み込み

パッキングスクリプトでは,
NBD接続時に次を指定します.

```sh
qemu-nbd \
    --discard=unmap \
    --detect-zeroes=unmap \
    --connect=/dev/nbd0 \
    ./rootfs.qcow2
```

ファイルコピー完了後, `umount`の前にtrimします.

```sh
sync
fstrim -v /mnt/rootfs
umount /mnt/rootfs
qemu-nbd --disconnect /dev/nbd0
```

配布ファイルを最小化する場合は,
切断後に別パスへ`qemu-img convert`します.

## よくある失敗

### 削除後にイメージが増えた

discardなしでmountした可能性があります.
`--discard=unmap`付きで再接続し, `fstrim`します.

### `fstrim`が未対応と表示された

次を確認します.

- NBD接続時に`--discard=unmap`を指定したか.
- filesystemがdiscardをサポートするか.
- loop deviceや中間層がdiscardを遮断していないか.

### `ls`のサイズが減らない

`du -h`と`qemu-img info`の`actual-size`を確認します.
ファイル終端まで詰める場合は,
別ファイルへの`qemu-img convert`を行います.

### NBDを切断できない

mountやprocessの参照が残っています.

```sh
findmnt -S "$NBD"
findmnt -S "${NBD}p1"
sudo fuser -vm "$NBD" "${NBD}p1"
```

参照元を停止し, `umount`してから切断します.
