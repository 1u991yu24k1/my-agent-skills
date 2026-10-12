# Ubuntu 26.04 x86_64 で Android Emulator を構築する手順

この README は, Ubuntu 26.04 x86_64 + Wayland 環境で Android Emulator を構築した実績を, 再利用できる形でまとめたものです.

今回の検証では, 次の 2 パターンを扱いました.

- Ubuntu ホスト上で Android Emulator を直接起動する.
- Docker コンテナ内で Android Emulator を起動し, noVNC で GUI を操作する.

特に後者では, VMware 上の Ubuntu guest から Nested Virtualization で KVM を利用し, Android Automotive の GUI を noVNC でブラウザ表示するところまで確認しています.

---

## 1. 検証環境

実際に動作確認した主な環境は以下です.

| 項目 | 値 |
|---|---|
| OS | Ubuntu 26.04 x86_64 |
| Desktop session | Wayland |
| 仮想化 | VMware Workstation 上の Ubuntu guest |
| CPU virtualization | AMD-V / SVM を nested virtualization で guest に公開 |
| KVM | `/dev/kvm`, KVM version 12 |
| Android CLI | 1.0.16261425 |
| Android Emulator | 37.1.11.0 |
| Host-native AVD | Android 11 / API 30 / `google_apis` / x86_64 |
| Docker AVD | Android Automotive / API 33 / x86_64 |
| GUI | Xvfb + x11vnc + noVNC |
| ADB | Host-native は `emulator-5554`, Docker は host `42069` -> container `5555` |

---

## 2. 最初に決めること

Android Emulator をどこで動かすかを先に決めます.

### パターン A. Ubuntu ホスト上で直接起動する

ホスト側に以下をインストールします.

- Android CLI
- Android SDK
- Android Emulator
- AVD system image
- ADB

構成は以下です.

```text
Ubuntu 26.04
  |
  +-- Android CLI
  +-- Android SDK
  +-- Android Emulator
  +-- AVD
  +-- /dev/kvm
```

### パターン B. Docker 内だけで Android Emulator を起動する

Android SDK と Emulator が Docker image に入っているなら, ホスト側に Android Emulator をインストールする必要はありません.

ホスト側に必要なのは主に以下です.

- Docker Engine
- Docker Compose
- `/dev/kvm`

構成は以下です.

```text
Ubuntu 26.04
  |
  +-- /dev/kvm
  |
  +-- Docker
       |
       +-- Android Emulator
       +-- Android SDK
       +-- ADB
       +-- Xvfb
       +-- x11vnc
       +-- noVNC
```

今回, ホスト側 Android Emulator も一度構築しましたが, これは KVM と Emulator 単体の動作確認用でした.

Docker-only 構成では, ホスト側 Emulator を起動すると host port `5554` が競合するため, 同時起動しない方が安全です.

---

# 3. Ubuntu 側の基本パッケージ

まず最低限のツールを入れます.

```bash
sudo apt update

sudo apt install -y \
    curl \
    ca-certificates \
    unzip \
    default-jre-headless
```

KVM の確認用に以下も入れておくと便利です.

```bash
sudo apt install -y \
    qemu-kvm \
    cpu-checker
```

Android Emulator のためだけなら, libvirt の管理 stack 自体は必須ではありません.

---

# 4. KVM を有効にする

x86_64 system image を実用速度で動かす場合, Linux では KVM を使います.

## 4.1 CPU virtualization extension の確認

```bash
egrep -c '(vmx|svm)' /proc/cpuinfo
```

1 以上なら, guest OS から VT-x または AMD-V が見えています.

さらに,

```bash
ls -l /dev/kvm
```

を確認します.

正常例.

```text
crw-rw----+ 1 root kvm 10, 232 ... /dev/kvm
```

module も確認できます.

Intel の例.

```bash
lsmod | grep kvm
```

```text
kvm_intel
kvm
```

AMD の例.

```text
kvm_amd
kvm
```

## 4.2 VMware guest の場合

Ubuntu 自体を VMware Workstation の guest として動かしている場合, VMware 側で Nested Virtualization を有効にする必要があります.

VM を完全に shutdown し, VMware の VM 設定から,

```text
プロセッサ
  -> Intel VT-x/EPT または AMD-V/RVI を仮想化
```

を ON にします.

再起動後に,

```bash
egrep -o 'vmx|svm' /proc/cpuinfo | head
ls -l /dev/kvm
```

を再確認します.

今回の環境では, Nested Virtualization を有効にする前は,

```text
/dev/kvm: No such file or directory
vmx/svm count: 0
```

でした.

有効化後は,

```text
svm
/dev/kvm
kvm_amd
```

が確認できました.

## 4.3 Android Emulator 側から確認

Android Emulator をインストールした後は,

```bash
emulator -accel-check
```

を実行します.

正常例.

```text
accel:
0
KVM (version 12) is installed and usable.
accel
```

この状態なら `-accel on` を使用できます.

---

# 5. Android CLI のインストール

2026 年時点では, Google 公式の `android` CLI が利用できます.

この README では apt repository を使う方法を採用します.

```bash
curl -fsSL https://dl.google.com/linux/linux_signing_key.pub \
    | sudo tee /etc/apt/keyrings/google.asc >/dev/null

sudo sh -c \
'echo "deb [arch=amd64 signed-by=/etc/apt/keyrings/google.asc] http://dl.google.com/android/cli/latest/debian/ stable main" \
> /etc/apt/sources.list.d/android-cli.list'

sudo apt update
sudo apt install -y android-cli
```

確認します.

```bash
android --version
android info
```

実環境では以下でした.

```text
1.0.16261425
```

SDK root は,

```bash
android info
```

で確認します.

実環境では,

```text
sdk: /root/Android/Sdk
```

でした.

一般ユーザなら通常は `$HOME` 配下になります.

---

# 6. Android SDK component のインストール

Android 11 / API 30 / Google APIs / x86_64 の例です.

```bash
android sdk install \
    platform-tools \
    emulator \
    system-images/android-30/google_apis/x86_64 \
    cmdline-tools/latest
```

必要なものは以下です.

```text
platform-tools
  -> adb

emulator
  -> emulator

system-images/android-30/google_apis/x86_64
  -> AVD の guest image

cmdline-tools/latest
  -> avdmanager など
```

現在インストール可能な package は,

```bash
android sdk list --all
```

で確認できます.

---

# 7. PATH の設定

SDK root が `$HOME/Android/Sdk` の場合です.

```bash
export ANDROID_HOME="$HOME/Android/Sdk"

export PATH="$ANDROID_HOME/platform-tools:$PATH"
export PATH="$ANDROID_HOME/emulator:$PATH"
export PATH="$ANDROID_HOME/cmdline-tools/latest/bin:$PATH"
```

恒久化するなら `~/.bashrc` に追加します.

確認.

```bash
which adb
which emulator
which avdmanager

adb version
emulator -version
```

実環境では,

```text
/root/Android/Sdk/platform-tools/adb
/root/Android/Sdk/emulator/emulator
/root/Android/Sdk/cmdline-tools/latest/bin/avdmanager
```

となりました.

---

# 8. AVD の作成

2026 年現在, Google は新しい `android emulator` command を推奨しており, `avdmanager` は deprecated 扱いです.

ただし, 今回実際に動作確認した手順は `avdmanager` なので, 再現用として以下を残します.

```bash
echo no | avdmanager create avd \
    -n chv_api30 \
    -k "system-images;android-30;google_apis;x86_64"
```

確認.

```bash
emulator -list-avds
```

期待値.

```text
chv_api30
```

新規構築では,

```bash
android emulator --help
android emulator create --help
```

も確認し, 利用可能であれば新 CLI を優先してください.

---

# 9. userdata partition のサイズ

AVD の default userdata partition が大きすぎると, 初回起動時に disk space error になる場合があります.

今回発生した例.

```text
FATAL | Not enough space to create userdata partition.
Available: 10716.96 MB
need 12288.00 MB
```

設定確認.

```bash
grep -E 'disk.dataPartition.size|disk.dataPartition' \
    ~/.android/avd/chv_api30.avd/config.ini
```

今回の AVD では,

```text
disk.dataPartition.size=10G
```

でした.

CTF や検証用途なら 4 GiB 程度でも十分な場合があります.

初回 boot 前なら,

```bash
sed -i \
    's/^disk.dataPartition.size=.*/disk.dataPartition.size=4G/' \
    ~/.android/avd/chv_api30.avd/config.ini
```

で変更できます.

既に userdata image を作成済みの場合は, config だけを書き換えず, AVD の再作成や data wipe を検討してください.

---

# 10. Emulator の起動

## 10.1 headless

KVM を使う headless 構成です.

```bash
emulator \
    -avd chv_api30 \
    -no-window \
    -no-audio \
    -gpu swiftshader \
    -accel on \
    -no-snapshot
```

`-accel on` は KVM が利用できない場合に起動失敗するため, 先に,

```bash
emulator -accel-check
```

を実行してください.

### `swiftshader_indirect` について

今回の Emulator 37.1.11.0 では,

```text
-gpu swiftshader_indirect
```

でも動作確認しました.

ただし, 2026 年時点の公式ドキュメントでは `swiftshader_indirect` は deprecated です.

新規構築では,

```text
-gpu swiftshader
```

または,

```text
-gpu software
```

を優先してください.

---

# 11. Boot 完了確認

まず ADB server を起動します.

```bash
adb start-server
```

device 確認.

```bash
adb devices
```

初回起動時は一時的に,

```text
emulator-5554   offline
```

になる場合があります.

boot が進むと,

```text
emulator-5554   device
```

になります.

Android framework の boot 完了確認.

```bash
adb shell getprop sys.boot_completed
```

`1` が返れば完了です.

待機処理にするなら,

```bash
adb wait-for-device

until [ "$(adb shell getprop sys.boot_completed 2>/dev/null | tr -d '\r')" = "1" ]; do
    sleep 1
done

echo "Android boot completed"
```

状態確認.

```bash
adb shell getprop | grep -E \
    'sys.boot_completed|dev.bootcomplete|init.svc.bootanim'
```

正常例.

```text
[dev.bootcomplete]: [1]
[sys.boot_completed]: [1]
[init.svc.bootanim]: [stopped]
```

---

# 12. `-accel off` は避ける

今回, Nested Virtualization が無効な状態で,

```bash
-accel off
```

を使って起動しました.

その場合, QEMU TCG に落ち,

```text
TCG doesn't support requested feature ...
```

などの warning が出ました.

Android framework 自体は進みましたが, boot は非常に遅くなりました.

x86_64 host + x86_64 guest では, 基本的に KVM を有効化して,

```bash
-accel on
```

または default の automatic detection を使ってください.

---

# 13. VMware 内では GPU host rendering が失敗することがある

今回,

```text
-gpu host
```

を指定したところ,

```text
ERROR | Your GPU cannot be used for hardware rendering.
VK_ERROR_INCOMPATIBLE_DRIVER
```

となりました.

VMware guest 内で Android Emulator を動かす場合, CPU virtualization と GPU virtualization は別問題です.

KVM が使えていても, Vulkan / OpenGL の host GPU path が利用できるとは限りません.

今回の安定構成は,

```bash
-gpu swiftshader
```

または実績値として,

```bash
-gpu swiftshader_indirect
```

でした.

---

# 14. Wayland 環境について

Ubuntu 26.04 の desktop session が Wayland でも, headless 起動には特に問題ありません.

```bash
-no-window
```

を使う場合, Wayland / XWayland の GUI integration を気にする必要はありません.

GUI を Docker 内で提供する場合も, host Wayland session に直接描画するより,

```text
Android Emulator
  -> Xvfb
  -> x11vnc
  -> noVNC
  -> Browser
```

とする方が再現性が高くなります.

この README で検証した GUI path はこの方式です.

---

# 15. Docker 内で Android Emulator を起動する

Docker-only で Emulator を動かす場合, host Android SDK は不要です.

## 15.1 KVM を container に渡す

Compose の例.

```yaml
services:
  android-emulator:
    devices:
      - /dev/kvm:/dev/kvm
```

通常, KVM 利用のためだけなら `privileged: true` は必須ではありません.

Challenge や network device 操作の都合で additional capability が必要な場合だけ追加します.

---

# 16. Docker と ADB port forwarding

Android Emulator は container 内で,

```text
127.0.0.1:5554
127.0.0.1:5555
```

だけに listen することがあります.

この状態では Docker bridge の port publishing から直接到達できません.

今回の構成では, container 内で `socat` を使い,

```text
container-ip:5554 -> 127.0.0.1:5554
container-ip:5555 -> 127.0.0.1:5555
```

を中継しました.

例.

```bash
emulatorConsolePort=5554
adbPort=5555

containerIp=$(
    ip -4 route get 1.1.1.1 2>/dev/null |
    awk '{for (i = 1; i <= NF; i++) if ($i == "src") { print $(i + 1); exit }}'
)

socat \
    "TCP-LISTEN:${emulatorConsolePort},bind=${containerIp},reuseaddr,fork" \
    "TCP:127.0.0.1:${emulatorConsolePort}" &

socat \
    "TCP-LISTEN:${adbPort},bind=${containerIp},reuseaddr,fork" \
    "TCP:127.0.0.1:${adbPort}" &
```

Compose 側.

```yaml
ports:
  - "5554:5554"
  - "42069:5555"
```

host からは,

```bash
adb connect localhost:42069
```

で接続します.

確認.

```bash
adb devices
```

```text
localhost:42069    device
```

---

# 17. `network_mode: host` と `ports:` を混ぜない

今回ハマった点です.

runtime の,

```yaml
network_mode: host
```

を設定すると, Docker の,

```yaml
ports:
  - "42069:5555"
```

による bridge/NAT port publishing は使われません.

その結果,

```text
adb connect localhost:42069
Connection refused
```

となりました.

今回の正しい構成は,

```text
Docker bridge network
  +
ports:
  host 42069 -> container 5555
  +
container 内 socat
  container-ip:5555 -> 127.0.0.1:5555
```

です.

なお,

```yaml
build:
  network: host
```

は image build 時の network 設定であり,

```yaml
network_mode: host
```

とは別物です.

---

# 18. host Emulator と Docker Emulator の port 競合

host 側 Android Emulator を起動したまま Docker Emulator を起動すると,

```text
failed to bind host port 0.0.0.0:5554/tcp:
address already in use
```

となる場合があります.

Docker 版を起動する前に host Emulator を止めます.

```bash
adb devices
adb emu kill
```

確認.

```bash
ss -lntp | grep -E ':5554|:5555'
```

host Emulator と Docker Emulator は同時に起動しない方が安全です.

---

# 19. noVNC で Android GUI を表示する

Docker / headless 環境で GUI を使う場合は,

```text
Browser
  -> noVNC / websockify
  -> x11vnc
  -> Xvfb
  -> Android Emulator window
```

とします.

## 19.1 必要 package

container に以下を入れます.

```bash
apt-get update

apt-get install -y --no-install-recommends \
    xvfb \
    x11vnc \
    novnc \
    websockify \
    socat
```

## 19.2 noVNC 用 port

Compose.

```yaml
ports:
  - "6080:6080"
```

## 19.3 Xvfb + x11vnc + websockify

今回安定した設定.

```bash
export DISPLAY=":99"
export GPU_MODE="swiftshader"

Xvfb "$DISPLAY" \
    -screen 0 1920x1080x24 \
    -nolisten tcp \
    -ac &

sleep 1

x11vnc \
    -display "$DISPLAY" \
    -forever \
    -shared \
    -nopw \
    -rfbport 5900 \
    -listen 127.0.0.1 &

websockify \
    --web=/usr/share/novnc \
    0.0.0.0:6080 \
    127.0.0.1:5900 &
```

Emulator 側では,

```text
-no-window
```

を外します.

例.

```bash
exec emulator \
    -avd android \
    -gpu "$GPU_MODE" \
    -memory 8192 \
    -partition-size 4096 \
    -no-boot-anim \
    -cores 4 \
    -no-audio \
    -no-snapshot \
    -no-snapshot-save \
    -no-snapshot-load \
    -no-metrics
```

ブラウザから,

```text
http://localhost:6080/vnc.html
```

へアクセスします.

---

# 20. Xvfb の display 番号

今回 `:0` を使ったところ,

```text
Fatal server error:
Server is already active for display 0
```

となりました.

そのため,

```bash
export DISPLAY=:99
```

を使用しました.

x11vnc 側も必ず同じ display を参照させます.

```bash
x11vnc -display :99 ...
```

正常時はログに,

```text
Using X display :99
Listening for VNC connections on TCP port 5900
```

が出ます.

---

# 21. hardware keyboard

Android Automotive AVD では,

```text
hw.keyboard = no
```

になっている場合があります.

その場合, noVNC 画面の textbox をクリックしても PC のキーボードから文字入力できません.

確認.

```bash
grep '^hw.keyboard' /data/android.avd/config.ini
```

今回の値.

```text
hw.keyboard = no
hw.keyboard.charmap = qwerty2
hw.keyboard.lid = yes
```

有効化.

```bash
sed -i \
    's/^hw.keyboard *= *.*/hw.keyboard = yes/' \
    /data/android.avd/config.ini
```

AVD 再起動後に反映されます.

AVD 作成 script へ入れるなら,

```bash
config="${avdDir}/config.ini"

if grep -q '^hw.keyboard *= *' "$config"; then
    sed -i \
        's/^hw.keyboard *= *.*/hw.keyboard = yes/' \
        "$config"
else
    echo 'hw.keyboard = yes' >> "$config"
fi
```

とします.

---

# 22. APK の install と起動

install.

```bash
adb install -r app.apk
```

package 名確認.

```bash
adb shell pm list packages | grep -i '<keyword>'
```

launcher activity 確認.

```bash
adb shell cmd package resolve-activity \
    --brief com.example.app
```

activity を直接起動.

```bash
adb shell am start \
    -n com.example.app/.MainActivity
```

Automotive launcher の category に表示されない application でも, `am start` なら直接起動できます.

---

# 23. よくある warning と扱い

## `Unable to connect to adb daemon on port: 5037`

Emulator 起動時に ADB server がまだ起動していないと出る場合があります.

```bash
adb start-server
```

を実行します.

Android guest がまだ boot 中なら,

```text
offline
```

から,

```text
device
```

へ変化するまで待ちます.

## snapshot warning

```text
Failed to load snapshot 'default_boot'
```

初回起動や snapshot 無効構成では問題ありません.

`-no-snapshot` を使う場合は cold boot になります.

## PulseAudio

Docker 内に audio server が無いと,

```text
pulseaudio: Connection refused
```

などが出ます.

音声が不要なら,

```text
-no-audio
```

を付けます.

## core 数

Emulator が対応上限を超えた core 数を指定すると,

```text
Emulator does not support more than 6 cores.
```

などと補正されます.

必要以上に増やさず, 4 core 程度から始めるのが安全です.

---

# 24. disk space の確認

Android SDK, system image, Docker image, build cache はかなり容量を使用します.

確認.

```bash
df -h /
docker system df
```

今回, root filesystem が,

```text
98G total
97G used
0 available
100%
```

まで到達し, Emulator が起動できなくなりました.

Docker build cache だけで約 20 GB 使用していました.

削除.

```bash
docker builder prune -a -f
```

今回これで約 20 GB 回収でき,

```text
14G available
86% used
```

まで戻りました.

Docker image, volume を削除する前に, まず build cache を疑う価値があります.

---

# 25. トラブルシュートの順番

Emulator が起動しない場合, 次の順で確認します.

## 25.1 disk

```bash
df -h /
docker system df
```

## 25.2 KVM

```bash
egrep -c '(vmx|svm)' /proc/cpuinfo
ls -l /dev/kvm
emulator -accel-check
```

## 25.3 Emulator process

```bash
ps -ef | grep -E '[e]mulator|[q]emu'
```

Docker.

```bash
docker exec <container> \
    sh -c 'ps -ef | grep -E "[e]mulator|[q]emu"'
```

## 25.4 ADB

```bash
adb start-server
adb devices
```

Docker の TCP ADB.

```bash
adb connect localhost:42069
adb devices
```

## 25.5 boot progress

```bash
adb shell getprop sys.boot_completed

adb shell ps -A | grep -E \
    'zygote|system_server|surfaceflinger|bootanim'
```

## 25.6 logcat

```bash
adb logcat -b all -d | grep -Ei \
    'FATAL EXCEPTION|SystemServer|ActivityManager|PackageManager|Watchdog|boot|avc: denied'
```

## 25.7 noVNC

```bash
ss -lntp | grep 6080

docker exec <container> \
    sh -c 'ps -ef | grep -E "[X]vfb|[x]11vnc|[w]ebsockify"'
```

---

# 26. アンインストール

## 26.1 Emulator を停止

host-native.

```bash
adb devices
adb emu kill
```

TCP 接続している device は,

```bash
adb disconnect
```

でも切断できます.

---

## 26.2 AVD を削除

今回の AVD.

```bash
avdmanager delete avd -n chv_api30
```

新しい Android CLI を使う場合は,

```bash
android emulator remove --help
```

で現在の syntax を確認してください.

残骸確認.

```bash
ls -la ~/.android/avd
```

不要なら個別に削除します.

---

## 26.3 SDK package を削除

```bash
android sdk remove \
    platform-tools \
    emulator \
    system-images/android-30/google_apis/x86_64 \
    cmdline-tools/latest
```

削除可能 package は,

```bash
android sdk list --all
```

で確認します.

---

## 26.4 Android SDK 全体を削除

SDK root を先に確認します.

```bash
android info
```

例.

```text
sdk: /root/Android/Sdk
```

本当に不要なら,

```bash
rm -rf "$HOME/Android/Sdk"
```

root で構築した場合は,

```bash
rm -rf /root/Android/Sdk
```

です.

誤削除防止のため, `android info` で SDK path を確認してから実行してください.

---

## 26.5 AVD / Android user state を削除

AVD や ADB key も含めて完全に消したい場合のみ,

```bash
rm -rf "$HOME/.android"
```

を実行します.

`~/.android` には AVD だけでなく ADB key や各種 user state が含まれるため, 他の Android 開発環境を使っている場合は全削除しないでください.

---

## 26.6 Android CLI を apt から削除

```bash
sudo apt remove --purge -y android-cli
sudo apt autoremove -y
```

repository も不要なら,

```bash
sudo rm -f /etc/apt/sources.list.d/android-cli.list
sudo rm -f /etc/apt/keyrings/google.asc
sudo apt update
```

---

## 26.7 PATH 設定を削除

`~/.bashrc` などから以下を削除します.

```bash
export ANDROID_HOME="$HOME/Android/Sdk"
export PATH="$ANDROID_HOME/platform-tools:$PATH"
export PATH="$ANDROID_HOME/emulator:$PATH"
export PATH="$ANDROID_HOME/cmdline-tools/latest/bin:$PATH"
```

反映.

```bash
source ~/.bashrc
```

---

## 26.8 KVM package の削除

Android Emulator のためだけに入れ, 他用途で KVM を使わない場合のみ削除します.

```bash
sudo apt remove --purge -y \
    qemu-kvm \
    cpu-checker

sudo apt autoremove -y
```

VMware guest の Nested Virtualization 設定は, 他で KVM を使わないなら OFF に戻しても構いません.

---

# 27. Docker 版の削除

対象 project directory で,

```bash
docker compose down
```

volume も削除する場合.

```bash
docker compose down -v
```

image も不要なら確認後に削除します.

```bash
docker image ls
docker image rm <image-name-or-id>
```

build cache.

```bash
docker builder prune -a -f
```

Docker 全体の未使用 resource を一括削除する,

```bash
docker system prune -a
```

は影響範囲が広いため, 他 project がある環境では安易に使わないでください.

---

# 28. 最終確認用チェックリスト

## Native Emulator

```bash
command -v android
command -v adb
command -v emulator

android info
emulator -accel-check
emulator -list-avds

ls -l /dev/kvm
```

起動後.

```bash
adb devices
adb shell getprop sys.boot_completed
```

## Docker Emulator

```bash
ls -l /dev/kvm

docker compose ps

docker exec <container> ls -l /dev/kvm

adb connect localhost:42069
adb devices

ss -lntp | grep 6080
```

ブラウザ.

```text
http://localhost:6080/vnc.html
```

---

# 29. 今回の重要な学び

1. x86_64 Android Emulator は KVM を使う前提で考える.
2. VMware guest では Nested Virtualization を明示的に有効化する.
3. `/dev/kvm` が無い状態で `-accel off` に逃げると非常に遅い.
4. VMware guest では `-gpu host` が使えるとは限らない.
5. software rendering は `swiftshader` を基本にする.
6. AVD の userdata partition は disk 容量を圧迫するため, 検証用途では適切に縮小する.
7. Docker-only 構成なら host に Android Emulator を入れる必要はない.
8. host Emulator と Docker Emulator を同時に起動すると `5554` が競合しやすい.
9. Docker bridge 越しの ADB は, Emulator の loopback bind を考慮する.
10. runtime `network_mode: host` と Compose `ports:` を同時に期待しない.
11. Wayland host で Docker GUI を安定させるなら Xvfb + x11vnc + noVNC が扱いやすい.
12. `DISPLAY=:0` は既存 X server と競合しやすいため, headless X server は `:99` などに分離する.
13. Android Automotive では `hw.keyboard = no` の場合があり, 物理キーボード入力には `yes` が必要.
14. Android SDK + Docker build cache は簡単に数十 GB 消費する.
15. 起動確認は `adb devices` だけでなく `sys.boot_completed=1` まで見る.

---

# 30. 参考資料

Google Android Developers の以下のドキュメントを基準にしています.

- Android CLI download
  - https://developer.android.com/tools/agents/android-cli/download
- Android CLI
  - https://developer.android.com/agents/skills/devtools/android-cli/skill
- Android Emulator command-line options
  - https://developer.android.com/studio/run/emulator-commandline
- Android Emulator hardware acceleration
  - https://developer.android.com/studio/run/emulator-acceleration
- avdmanager
  - https://developer.android.com/tools/avdmanager

この README は 2026-10-12 時点の Android CLI / Emulator と, Ubuntu 26.04 x86_64 での実動作結果を反映しています.

