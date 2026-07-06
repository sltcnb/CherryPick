#!/usr/bin/env bash
# Generate the gRPC Python stubs for the Collector service from FH's vendored proto.
# Requires: pip install grpcio grpcio-tools
# Stubs land in grpc_stubs/ (gitignored, build-time generated).
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
OUT="$HERE/grpc_stubs"
mkdir -p "$OUT"
python -m grpc_tools.protoc \
  -I "$HERE/contracts" \
  --python_out="$OUT" \
  --grpc_python_out="$OUT" \
  "$HERE/contracts/collector.proto"
# Ensure the stubs dir is an importable package.
touch "$OUT/__init__.py"
echo "Generated collector_pb2.py + collector_pb2_grpc.py in $OUT"
