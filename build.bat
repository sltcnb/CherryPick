@echo off
REM Build triager.exe (single file, UAC-admin) via PyInstaller.
REM Bundles capabilities.yaml, vendored contracts\, and generated gRPC stubs.
setlocal
cd /d "%~dp0"

set BINARY_NAME=triager
set PYTHON=python

echo [*] Installing build dependencies...
%PYTHON% -m pip install -q -r requirements-build.txt

echo [*] Building %BINARY_NAME%.exe ...
%PYTHON% -m PyInstaller ^
    --onefile ^
    --name %BINARY_NAME% ^
    --clean ^
    --uac-admin ^
    --add-data "capabilities.yaml;." ^
    --add-data "contracts;contracts" ^
    --add-data "grpc_stubs;grpc_stubs" ^
    triager.py

echo [+] Done: dist\%BINARY_NAME%.exe
endlocal
