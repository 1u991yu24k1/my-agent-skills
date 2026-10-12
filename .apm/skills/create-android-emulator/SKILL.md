---
name: create-android-emulator
description: "Set up, validate, troubleshoot, expose a GUI for, or remove an x86_64 Android Emulator on Ubuntu 26.04 + Wayland. Covers KVM and VMware nested virtualization, native Android CLI/SDK/AVD setup, Dockerized Emulator networking and ADB forwarding, Xvfb+x11vnc+noVNC, Android Automotive keyboard input, disk/cache failures, and safe uninstall. Use for reproducible Android Emulator environment construction on Ubuntu x86_64. Do not use for Apple Silicon/ARM64."
---

# create-android-emulator

Build a reproducible Android Emulator environment on Ubuntu 26.04 x86_64 + Wayland.

This skill is intentionally explicit. Follow the workflow in order, validate each gate, and do not guess around failed virtualization, Docker networking, or disk-space checks.

For human-oriented background and the full setup record, read `references/README-ubuntu-2604.md`.

## Supported scope

- Ubuntu 26.04 x86_64.
- Native Android Emulator on the Ubuntu host.
- Ubuntu running as a VMware guest with nested VT-x/AMD-V and KVM.
- Android Emulator inside Docker.
- Android Automotive x86_64 images.
- Host ADB access to a Dockerized Emulator.
- Browser GUI using Xvfb + x11vnc + noVNC.
- Wayland desktop hosts.

Do not use this skill for Apple Silicon/ARM64, macOS-native setup, Windows-native setup, or Waydroid unless the user explicitly asks for an unsupported adaptation.

## Operating rules

1. Decide native vs Docker mode before installing anything.
2. If an existing repository already contains Android SDK/Emulator in Docker, do not install a second host SDK unless the user explicitly wants native testing.
3. Require KVM for x86_64 unless the user explicitly accepts very slow software emulation. Do not silently fall back to `-accel off`.
4. Do not add runtime `network_mode: host` merely to fix ADB when the design relies on Compose `ports:`.
5. Do not declare success from `adb devices` alone. Require `sys.boot_completed=1` for a native Emulator.
6. In VMware guests, prefer software GPU rendering unless host GPU rendering is proven to work.
7. For noVNC, prefer a separate X display such as `:99`, not `:0`.
8. Never run destructive cleanup automatically. Ask before `docker builder prune -a -f`, `docker compose down -v`, `docker system prune -a`, deleting SDK roots, or deleting `$HOME/.android`.
9. Preserve project-specific challenge logic, CAN setup, SOME/IP setup, flags, and network topology unless the user explicitly asks to change them.

---

# 1. Inspect first

Record the environment.

```bash
uname -m
lsb_release -a 2>/dev/null || cat /etc/os-release
echo "${XDG_SESSION_TYPE:-unknown}"
systemd-detect-virt || true
```

Required architecture:

```text
x86_64
```

If working inside a repository, inspect before editing.

```bash
find . -maxdepth 3 \
  \( -name 'docker-compose.yml' -o -name 'compose.yml' -o -name 'Dockerfile' -o -name '*emulator*.sh' -o -name 'run.sh' \) \
  -print
```

Determine all of the following before changing files:

- native or Dockerized Emulator,
- expected API level,
- expected image type,
- expected AVD name,
- expected host/container ADB ports,
- whether `/dev/kvm` is already passed into Docker,
- whether `socat` is already present,
- whether noVNC is already present,
- whether a launcher script already manages boot and APK installation.

Do not replace an existing architecture until it is understood.

---

# 2. KVM preflight

Run:

```bash
egrep -c '(vmx|svm)' /proc/cpuinfo
ls -l /dev/kvm 2>/dev/null || true
lsmod | grep -E '^kvm|kvm_' || true
```

A usable x86_64 Emulator should normally have:

- one or more `vmx` or `svm` CPU flags,
- `/dev/kvm`,
- `kvm_intel` or `kvm_amd`.

## VMware guest branch

If `systemd-detect-virt` reports VMware and either the CPU flag count is 0 or `/dev/kvm` is absent, stop and instruct the user to power off the VM and enable:

```text
VM Settings
  -> Processors
  -> Virtualize Intel VT-x/EPT or AMD-V/RVI
```

After reboot, rerun:

```bash
egrep -o 'vmx|svm' /proc/cpuinfo | head
ls -l /dev/kvm
lsmod | grep kvm
```

Do not continue with `-accel off` as an automatic workaround.

If helper packages are needed:

```bash
sudo apt update
sudo apt install -y qemu-kvm cpu-checker
```

Once Android Emulator exists, validate:

```bash
emulator -accel-check
```

Expected output contains:

```text
KVM (...) is installed and usable.
```

---

# 3A. Native Android Emulator setup

Use this path only when the Emulator should run directly on Ubuntu.

## Host prerequisites

```bash
sudo apt update
sudo apt install -y \
  curl \
  ca-certificates \
  unzip \
  default-jre-headless
```

## Install Android CLI

```bash
sudo mkdir -p /etc/apt/keyrings

curl -fsSL https://dl.google.com/linux/linux_signing_key.pub \
  | sudo tee /etc/apt/keyrings/google.asc >/dev/null

echo 'deb [arch=amd64 signed-by=/etc/apt/keyrings/google.asc] http://dl.google.com/android/cli/latest/debian/ stable main' \
  | sudo tee /etc/apt/sources.list.d/android-cli.list

sudo apt update
sudo apt install -y android-cli
```

Validate:

```bash
android --version
android info
```

Read the SDK root from `android info`. Do not assume the user is root.

## Install SDK components

Tested API 30 example:

```bash
android sdk install \
  platform-tools \
  emulator \
  system-images/android-30/google_apis/x86_64 \
  cmdline-tools/latest
```

If the project specifies another API level or image type, use the project values instead.

## Configure PATH

For the common SDK root `$HOME/Android/Sdk`:

```bash
export ANDROID_HOME="$HOME/Android/Sdk"
export PATH="$ANDROID_HOME/platform-tools:$ANDROID_HOME/emulator:$ANDROID_HOME/cmdline-tools/latest/bin:$PATH"
```

Validate:

```bash
command -v adb
command -v emulator
command -v avdmanager
```

Only persist these exports if the user requests a persistent shell setup.

## Create the AVD

Use the tested compatibility path:

```bash
echo no | avdmanager create avd \
  -n chv_api30 \
  -k "system-images;android-30;google_apis;x86_64"
```

Validate:

```bash
emulator -list-avds
```

Preserve project-required AVD names exactly.

## Check disk before first boot

```bash
df -h "$HOME"
df -h "$HOME/.android" 2>/dev/null || true
```

Inspect userdata size:

```bash
grep -E 'disk.dataPartition.path|disk.dataPartition.size' \
  "$HOME/.android/avd/chv_api30.avd/config.ini"
```

If free space is smaller than the requested userdata partition, do not start the Emulator.

For a disposable lab/CTF AVD, reducing the size to 4 GiB before first boot is acceptable:

```bash
sed -i \
  's/^disk.dataPartition.size=.*/disk.dataPartition.size=4G/' \
  "$HOME/.android/avd/chv_api30.avd/config.ini"
```

Do not resize a populated AVD blindly.

## Start native headless Emulator

Preferred configuration:

```bash
emulator \
  -avd chv_api30 \
  -no-window \
  -no-audio \
  -gpu swiftshader \
  -accel on \
  -no-snapshot
```

If an existing known-good project explicitly uses `swiftshader_indirect`, preserve it unless migration is part of the task.

## Validate boot

```bash
adb start-server
adb devices
```

`offline` during early boot is not a final failure.

Wait for framework boot:

```bash
adb wait-for-device

until [ "$(adb shell getprop sys.boot_completed 2>/dev/null | tr -d '\r')" = "1" ]; do
  sleep 1
done
```

Final checks:

```bash
adb devices
adb shell getprop sys.boot_completed
adb shell getprop ro.build.version.release
adb shell getprop ro.build.version.sdk
adb shell getprop ro.product.cpu.abi
```

Success requires `sys.boot_completed=1`.

---

# 3B. Dockerized Android Emulator

Use this path when Android SDK and Emulator should live inside Docker.

Do not install a host Android SDK merely because the image contains Android tooling.

## Host requirements

```bash
docker version
docker compose version
ls -l /dev/kvm
```

## Pass KVM into the container

Compose must contain:

```yaml
services:
  android-emulator:
    devices:
      - /dev/kvm:/dev/kvm
```

Validate after creation:

```bash
docker exec <emulator-container> ls -l /dev/kvm
```

If available inside the image:

```bash
docker exec <emulator-container> emulator -accel-check
```

## Keep bridge networking when using `ports:`

Correct pattern:

```yaml
services:
  android-emulator:
    ports:
      - "5554:5554"
      - "42069:5555"
```

Do not add runtime:

```yaml
network_mode: host
```

while expecting these `ports:` mappings to work.

`build.network: host` is a different setting and may be used for image-build networking if required.

## Handle loopback-only Emulator ports

Android Emulator may listen only on:

```text
127.0.0.1:5554
127.0.0.1:5555
```

Docker published-port traffic reaches the container interface, not container loopback.

If the existing startup script already uses `socat`, preserve it.

Tested relay pattern:

```bash
emulatorConsolePort=5554
adbPort=5555

containerIp=$(
  ip -4 route get 1.1.1.1 2>/dev/null |
  awk '{for (i = 1; i <= NF; i++) if ($i == "src") { print $(i + 1); exit }}'
)

if [ -z "$containerIp" ]; then
  containerIp=$(
    ip -4 -o addr show scope global 2>/dev/null |
    awk '{print $4}' |
    cut -d/ -f1 |
    head -1
  )
fi

if [ -n "$containerIp" ] && [ "$containerIp" != "127.0.0.1" ]; then
  socat \
    "TCP-LISTEN:${emulatorConsolePort},bind=${containerIp},reuseaddr,fork" \
    "TCP:127.0.0.1:${emulatorConsolePort}" &

  socat \
    "TCP-LISTEN:${adbPort},bind=${containerIp},reuseaddr,fork" \
    "TCP:127.0.0.1:${adbPort}" &
fi
```

Then host ADB uses:

```bash
adb connect localhost:42069
adb devices
```

Expected:

```text
localhost:42069    device
```

## Diagnose `localhost:42069` refusal

Do not guess. Inspect each hop:

```bash
docker inspect <emulator-container> \
  --format 'NetworkMode={{.HostConfig.NetworkMode}} Ports={{json .HostConfig.PortBindings}}'

docker exec <emulator-container> \
  sh -c 'ss -lntp 2>/dev/null | grep -E ":5554|:5555|:5037|:42069" || true'

docker exec <emulator-container> \
  sh -c 'ps -ef | grep "[s]ocat" || true'

ss -lntp | grep -E ':5554|:5555|:42069' || true
```

Expected design:

```text
host localhost:42069
  -> Docker published port
  -> container-ip:5555
  -> socat
  -> 127.0.0.1:5555
  -> Android Emulator ADB
```

Only modify Compose after identifying the missing hop.

---

# 4. noVNC GUI for Docker Emulator

Use this path when browser GUI access is required.

Prefer this over direct host-Wayland integration for a containerized Emulator.

## Install GUI packages in the image

```dockerfile
RUN apt-get update && apt-get install -y --no-install-recommends \
    xvfb \
    x11vnc \
    novnc \
    websockify \
    socat \
    && rm -rf /var/lib/apt/lists/*
```

## Publish noVNC

```yaml
ports:
  - "5554:5554"
  - "42069:5555"
  - "6080:6080"
```

## Start the GUI path

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

If a known-good project already uses `swiftshader_indirect`, preserve it unless migration is requested.

## Emulator flags for GUI mode

- Remove `-no-window`.
- Keep KVM enabled.
- Prefer software rendering in VMware.
- Add `-no-audio` if sound is unnecessary.

Example:

```bash
exec emulator \
  -avd android \
  -gpu "$GPU_MODE" \
  -memory "${MEMORY:-8192}" \
  -partition-size "${PARTITION_SIZE:-4096}" \
  -no-boot-anim \
  -cores "${CORES:-4}" \
  -no-audio \
  -no-snapshot \
  -no-snapshot-save \
  -no-snapshot-load \
  -no-metrics
```

Use 4 cores by default. Do not assume more vCPUs are better under nested virtualization.

## Validate noVNC

Inside the container:

```bash
ps -ef | grep -E '[X]vfb|[x]11vnc|[w]ebsockify|[q]emu|[e]mulator'
```

Host:

```bash
ss -lntp | grep 6080
```

Logs should show equivalents of:

```text
Using X display :99
Listening for VNC connections on TCP port 5900
Listen on 0.0.0.0:6080
proxying from 0.0.0.0:6080 to 127.0.0.1:5900
```

Open:

```text
http://localhost:6080/vnc.html
```

When accessing from another machine, use the Ubuntu VM's reachable IP instead of `localhost`.

---

# 5. Android Automotive hardware keyboard

Android Automotive AVDs may have:

```text
hw.keyboard = no
```

Then VNC mouse/touch works but the physical keyboard does not.

Inspect:

```bash
grep '^hw.keyboard' /data/android.avd/config.ini
```

Enable:

```bash
sed -i \
  's/^hw.keyboard *= *.*/hw.keyboard = yes/' \
  /data/android.avd/config.ini
```

If the key does not exist:

```bash
echo 'hw.keyboard = yes' >> /data/android.avd/config.ini
```

Restart the AVD after changing it.

For startup automation:

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

If hardware keyboard is already enabled but x11vnc key mapping is broken, test `-noxkb`. Do not add it preemptively.

---

# 6. APK installation and direct launch

Install:

```bash
adb install -r app.apk
```

Docker TCP ADB:

```bash
adb -s localhost:42069 install -r app.apk
```

Find package:

```bash
adb -s localhost:42069 shell pm list packages | grep -i '<keyword>'
```

Resolve launcher activity:

```bash
adb -s localhost:42069 shell cmd package resolve-activity \
  --brief com.example.app
```

Start explicitly:

```bash
adb -s localhost:42069 shell am start \
  -n com.example.app/.MainActivity
```

Android Automotive launchers may omit a normal application from the visible app category. Direct `am start` is valid.

---

# 7. Troubleshooting

## `/dev/kvm` absent and vmx/svm count is 0

Likely causes:

- BIOS virtualization disabled,
- VMware nested virtualization disabled.

Fix virtualization first. Do not default to `-accel off`.

## Emulator extremely slow

Check for TCG or explicit `-accel off`.

```bash
emulator -accel-check
```

Use KVM.

## `Not enough space to create userdata partition`

```bash
df -h /
df -h "$HOME"
```

Inspect AVD userdata size. Free disk or reduce it before first boot.

## Docker host port 5554 already in use

A native host Emulator may still be running.

```bash
adb devices
ss -lntp | grep -E ':5554|:5555'
```

Stop it:

```bash
adb emu kill
```

Do not kill unrelated processes.

## `adb connect localhost:42069` -> `Connection refused`

Inspect network mode, port bindings, container listeners, and `socat` before editing anything.

Do not add runtime host networking as a reflex.

## `Server is already active for display 0`

Use:

```bash
DISPLAY=:99
```

## x11vnc `XOpenDisplay` failure

Ensure Xvfb started first and both use the same display.

```bash
ps -ef | grep '[X]vfb'
echo "$DISPLAY"
```

Expected:

```text
:99
```

## `Your GPU cannot be used for hardware rendering`

Common in VMware.

Switch from:

```text
-gpu host
```

To:

```text
-gpu swiftshader
```

KVM CPU acceleration remains independent.

## noVNC works but keyboard does not

Check and fix `hw.keyboard`.

## `adb devices` shows `offline`

Wait through early boot, then check:

```bash
adb shell getprop sys.boot_completed
```

If it never progresses:

```bash
adb logcat -b all -d | grep -Ei \
  'FATAL EXCEPTION|SystemServer|ActivityManager|PackageManager|Watchdog|boot|avc: denied'
```

## PulseAudio connection refused

If audio is unnecessary, use:

```text
-no-audio
```

## Too many Emulator cores

Use 4 cores by default.

---

# 8. Disk and Docker cache management

Before a large Android image build:

```bash
df -h /
docker system df
```

Android SDK images and Docker build cache can consume tens of GB.

If build cache is the problem, explain the effect and obtain explicit approval before:

```bash
docker builder prune -a -f
```

Do not substitute broad cleanup such as:

```bash
docker system prune -a
```

unless the user explicitly requests broad Docker cleanup.

After cleanup:

```bash
df -h /
docker system df
```

---

# 9. Safe uninstall

First determine the requested scope:

- one AVD only,
- native Android tooling,
- Docker project,
- full purge.

Do not perform full purge by default.

## Stop native Emulator

```bash
adb devices
adb emu kill
adb disconnect 2>/dev/null || true
```

## Delete one AVD

```bash
avdmanager delete avd -n chv_api30
```

Inspect remaining AVDs:

```bash
ls -la "$HOME/.android/avd"
```

## Remove SDK components

```bash
android sdk remove \
  platform-tools \
  emulator \
  system-images/android-30/google_apis/x86_64 \
  cmdline-tools/latest
```

Adjust package names to what was actually installed.

## Remove Android CLI package

```bash
sudo apt remove --purge -y android-cli
sudo apt autoremove -y
```

If the repository is no longer needed:

```bash
sudo rm -f /etc/apt/sources.list.d/android-cli.list
sudo rm -f /etc/apt/keyrings/google.asc
sudo apt update
```

## Remove SDK root

First obtain the exact path:

```bash
android info
```

Only after explicit approval, remove that exact path.

Example:

```bash
rm -rf "$HOME/Android/Sdk"
```

Do not guess the path.

## Remove `$HOME/.android`

This may contain AVDs, ADB keys, and Android user state. Only delete after explicit approval:

```bash
rm -rf "$HOME/.android"
```

## Remove Docker project

Non-destructive stop:

```bash
docker compose down
```

Volume deletion requires approval:

```bash
docker compose down -v
```

Build-cache deletion requires approval:

```bash
docker builder prune -a -f
```

---

# 10. Completion criteria

Do not say setup is complete until all applicable checks pass.

## Native mode

```bash
emulator -accel-check
adb devices
adb shell getprop sys.boot_completed
```

Required result:

- KVM usable,
- Emulator state `device`,
- `sys.boot_completed` returns `1`.

## Docker mode

```bash
docker compose ps
docker exec <emulator-container> ls -l /dev/kvm
adb connect localhost:<published-adb-port>
adb devices
```

If GUI is requested:

```bash
ss -lntp | grep 6080
```

and noVNC must visibly render the Android display.

If an application is required, launch it and verify that its activity appears.

---

# 11. Final report format

Report:

1. Mode used: native or Docker.
2. Host architecture and OS.
3. KVM status.
4. Android API/image/ABI.
5. AVD name.
6. ADB endpoint.
7. GUI endpoint if configured.
8. Files modified.
9. Warnings intentionally left unresolved.
10. Exact uninstall scope and commands if removal was requested.

Never claim a workaround is the correct architecture until runtime behavior has been validated.

