#!/usr/bin/env bash
# Install pinned, disposable integration fixtures (Linux x86-64 only).
set -euo pipefail
fixture_dir="${1:?Usage: install-acme-test-tools.sh DIRECTORY}"
mkdir -p "$fixture_dir"
fixture_dir="$(cd "$fixture_dir" && pwd)"
for binary in pebble pebble-challtestsrv; do
    curl --fail --silent --show-error --location \
        "https://github.com/letsencrypt/pebble/releases/download/v2.10.1/${binary}-linux-amd64.tar.gz" \
        --output "$fixture_dir/${binary}.tar.gz"
done
(
    cd "$fixture_dir"
    sha256sum --check <<'SUMS'
4f2fcb5bca8c85c9cf73ad140fccfc0d2be40bd81ab99879c79b7b8a0b4f70ed  pebble.tar.gz
e93a5aa25ecdf3af2f9fbb2de32b0173e64a2eae81002a4ccfe35fa6f4f60b92  pebble-challtestsrv.tar.gz
SUMS
    for binary in pebble pebble-challtestsrv; do
        tar --no-same-owner -xzf "${binary}.tar.gz"
        cp "${binary}-linux-amd64/linux/amd64/${binary}" "$binary"
        chmod +x "$binary"
    done
)
git clone --quiet --depth 1 --branch v0.7.2 https://github.com/dehydrated-io/dehydrated.git "$fixture_dir/dehydrated"
test "$(git -C "$fixture_dir/dehydrated" rev-parse HEAD)" = fcca67b53c199d00463f3bc1a010c0a332d948f2
