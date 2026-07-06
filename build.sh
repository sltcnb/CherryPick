#!/usr/bin/env bash
# Build triager as a self-contained Linux ELF via PyInstaller.
# Bundles capabilities.yaml, the vendored contracts/, and generated gRPC stubs.
#
#   chmod +x build.sh && ./build.sh
# Output: dist/triager
set -euo pipefail
cd "$(dirname "$0")"

BINARY_NAME="triager"
PYTHON="${PYTHON:-python3}"

echo "[*] Installing build dependencies…"
"$PYTHON" -m pip install -q -r requirements-build.txt

echo "[*] Generating gRPC stubs…"
./generate_stubs.sh || echo "    (skipped: grpcio-tools not installed)"

echo "[*] Building ${BINARY_NAME} ELF…"
"$PYTHON" -m PyInstaller \
    --onefile \
    --name "$BINARY_NAME" \
    --strip \
    --clean \
    --add-data "capabilities.yaml:." \
    --add-data "contracts:contracts" \
    $([ -d grpc_stubs ] && echo "--add-data grpc_stubs:grpc_stubs") \
    triager.py

echo ""
echo "[+] Done:  dist/${BINARY_NAME}"
echo "    Size:  $(du -sh "dist/${BINARY_NAME}" | cut -f1)"
