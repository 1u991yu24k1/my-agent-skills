---
name: build-php-by-sanitizer
description: Build PHP Interpreter by clang with ASan, and UBSan with debug symbols
---

## preliminalies
Check the following packages are installed. (`apt` based naming)

* git
* build-essential
* clang
* llvm
* autoconf
* automake
* bison 
* re2c
* pkg-config
* libxml2-dev
* libsqlite3-dev
* libssl-dev
* libcurl4-openssl-dev
* libonig-dev
* libzip-dev
* libz-dev
* libreadline-dev

## Workflow 
Build PHP interpreter by ASAN, UBSAN enabled with debug symbol 

1. Get Target Source Code
  - [github](https://github.com/php/php-src.git)
    - `git clone https://github.com/php/php-src.git`
    - Optional: checkout branch, tag, or commit id for your attractive version.

2. set build flag.
  - set clang compiler as builder.
    ```shell
    export CC=clang
    export CXX=clang++

    export CFLAGS="-O0 -g3 -fno-omit-frame-pointer"
    export CXXFLAGS="-O0 -g3 -fno-omit-frame-pointer"
    export LDFLAGS="-fsanitize=address,undefined"
    ```  

  - configure build config (replace `<path>/<to>/<php-src>`, `<path>/<to>/<php-build>` to your paths)
    ```shell
    mkdir -p <path>/<to>/<php-build>
    cd <path>/<to>/<php-src>
    ./buildconf --force
    ./configure \
      --prefix=<path>/<to>/<php-build> \
      --enable-debug \
      --enable-cli \ 
      --enable-fpm \
      --disable-cgi \
      --enable-address-sanitizer \
      --enable-undefined-sanitizer \
      --without-pear
    ```

3. Build source by your config
  - invoke `make`, `make install` 
    ```shell
    make -j$(nproc)
    make install 
    ```
4. check sanitizer is enabled
  - check commands
    * `ls -al <path>/<to>/<php-build>`
    * `nm <path>/<to>/<php-build>/sbin/php-fpm | grep -E '__asan__init|__ubsan_handle'  # check if symbol exists.`
    * `file <path>/<to>/php-build>/sbin/php-fpm | grep debug_info                       # check if grep matches`
    * ```shell
      ASAN_OPTIONS="verbosity=1:detect_leaks=0" ./sbin/php-fpm -v 2>&1 | grep -E 'AddressSanitizer Init done|SHADOW_OFFSET|SHADOW_SCALE'
      # output example
      # root@Ubu2604x64:php-asan# ASAN_OPTIONS="verbosity=1:detect_leaks=0" ./sbin/php-fpm -v 2>&1 | grep -E 'AddressSanitizer Init done|SHADOW_OFFSET|SHADOW_SCALE'
      # SHADOW_SCALE: 3
      # SHADOW_OFFSET: 0x00007fff8000
      # ==1154844==AddressSanitizer Init done
      # root@Ubu2604x64:php-asan# 
      ```
## Environment 
You can debug php interpreter both with apache and nginx, or debug by standalone.

### You debug with apache


### You debug with nginx (likely recommended)
Use php-fpm config template (See @configs/php-fpm.conf).

```shell
cp ./configs/php-fpm.conf <path>/<to>/<your_config_dir>/php-fpm.conf
ASAN_OPTIONS="detect_leaks=0:abort_on_error=1:symbolize=1:log_path=/tmp/php-asan-log" \
  <path>/<to>/<php-build>/sbin/php-fpm \
  --nodaemonize \
  --fpm-config <path>/<to>/<your_config_dir>/php-fpm.conf
```

### You can debug by standalone
PHP interpreter has own webserver for development.

```shell
cd <path>/<to>/<php-build>
./bin/php -S localhost:8080  # start webserver 

# Optimize for santized debugging
USE_ZEND_ALLOC=0 \
ASAN_OPTIONS="detect_leaks=0:abort_on_error=1:symbolize=1" \
./bin/php -S localhost:8080 
```

check in another terminal.
```shell
curl http://localhost:8080/index.php?foo=bar
```
