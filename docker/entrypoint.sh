#!/bin/bash
# entrypoint.sh — camouchat-whatsapp container startup
#
# 1. Copies the Camoufox browser binary from the image layer to /data/cache on first boot.
# 2. Ensures /data directory structure exists with correct ownership.
# 3. Execs your application command.
#
# The Camoufox binary was baked into the base image at /opt/cache/camoufox.
# At runtime XDG_CACHE_HOME=/data/cache, so Camoufox looks for the binary at
# /data/cache/camoufox. We copy it once to that location so it's found without
# re-downloading anything.

set -e

BINARY_SRC="/opt/cache/camoufox"
BINARY_DST="${XDG_CACHE_HOME:-/data/cache}/camoufox"

# Copy binary from the baked image layer to the volume on first boot.
if [ -d "${BINARY_SRC}" ] && [ ! -d "${BINARY_DST}" ]; then
    echo "[entrypoint] First boot: copying Camoufox binary to volume..."
    mkdir -p "$(dirname "${BINARY_DST}")"
    cp -r "${BINARY_SRC}" "${BINARY_DST}"
    echo "[entrypoint] Camoufox binary ready at ${BINARY_DST}"
fi

# Ensure all XDG directories exist under /data.
mkdir -p \
    "${XDG_DATA_HOME:-/data/share}" \
    "${XDG_CACHE_HOME:-/data/cache}" \
    "${XDG_STATE_HOME:-/data/state}"

echo "[entrypoint] Starting: $*"
exec "$@"
