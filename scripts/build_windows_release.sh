#!/bin/bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VERSION="${VERSION:-5.4}"
SOURCE_DIR="${WINDOWS_SOURCE_DIR:-$ROOT_DIR/build/win_release}"
RELEASE_DIR="$ROOT_DIR/build/release/windows-v$VERSION"
OUTPUT_ZIP="$ROOT_DIR/dist/nova_unlock_windows_v$VERSION.zip"
OUTPUT_EXE="$ROOT_DIR/dist/nova_unlock_windows_v$VERSION.exe"
MANIFEST="$ROOT_DIR/dist/nova_unlock_windows_v$VERSION.manifest.txt"
WINDOWS_PE_STUB="${WINDOWS_PE_STUB:-}"

echo "Building protected NovaUnlock Windows release..."

if [ ! -d "$SOURCE_DIR" ]; then
    echo "Windows source/build directory not found: $SOURCE_DIR" >&2
    echo "Set WINDOWS_SOURCE_DIR to a prepared Windows build directory." >&2
    exit 1
fi

rm -rf "$RELEASE_DIR"
mkdir -p "$RELEASE_DIR" "$ROOT_DIR/dist"

# Copy only runtime-safe files from an already prepared Windows build.
# This intentionally excludes C/C++/Python source so GitHub Releases get binaries only.
while IFS= read -r -d '' file; do
    rel="${file#"$SOURCE_DIR"/}"
    case "$rel" in
        *.py|*.pyw|*.c|*.cc|*.cpp|*.cxx|*.h|*.hh|*.hpp|*.hxx|*.def|*.sln|*.vcxproj|*.filters|CMakeLists.txt|*/CMakeLists.txt|README*|*/README*|*.md)
            continue
            ;;
    esac
    mkdir -p "$RELEASE_DIR/$(dirname "$rel")"
    cp -p "$file" "$RELEASE_DIR/$rel"
done < <(find "$SOURCE_DIR" -type f -print0)

cat > "$RELEASE_DIR/requirements.txt" << 'REQ'
numpy>=1.26.0
opencv-python>=4.9.0
face_recognition>=1.3.0
PyQt5>=5.15.0
PyYAML>=6.0
REQ

cat > "$RELEASE_DIR/install.bat" << 'BAT'
@echo off
setlocal EnableExtensions
title NovaUnlock Windows Installer

set "LOG=%TEMP%\NovaUnlockInstall.log"
echo NovaUnlock Windows installer started at %DATE% %TIME% > "%LOG%"

net session >nul 2>&1
if not "%errorLevel%"=="0" (
    echo [ERROR] Administrator privileges are required.
    echo Right-click the NovaUnlock Windows installer and choose Run as administrator.
    pause
    exit /b 1
)

set "PYTHON_VERSION=3.11.9"
set "PYTHON_INSTALLER_URL=https://www.python.org/ftp/python/%PYTHON_VERSION%/python-%PYTHON_VERSION%-amd64.exe"
set "PYTHON_INSTALLER=%TEMP%\python-%PYTHON_VERSION%-amd64.exe"

call :find_python
if not defined PY (
    echo [INFO] Python 3.11 was not found. Installing Python 3.11 runtime...
    call :install_python
    call :find_python
)
if not defined PY (
    echo [ERROR] Python 3.11 installation was not detected.
    echo Check internet access, then install Python 3.11 from python.org and run this installer again.
    echo See log: "%LOG%"
    pause
    exit /b 1
)
echo [INFO] Using Python command: %PY%

set "SRC=%~dp0"
set "NOVA_PATH=%ProgramData%\NovaUnlock"
set "STARTUP_FOLDER=%ProgramData%\Microsoft\Windows\Start Menu\Programs\StartUp"
set "PYTHONPATH=%NOVA_PATH%;%PYTHONPATH%"
set "PATH=%PATH%;%ProgramFiles%\Python311;%ProgramFiles%\Python311\Scripts;%LocalAppData%\Programs\Python\Python311;%LocalAppData%\Programs\Python\Python311\Scripts;%ProgramFiles%\CMake\bin"

if not exist "%SRC%nova_unlock" (
    echo [ERROR] Package is incomplete: nova_unlock is missing.
    echo See log: "%LOG%"
    pause
    exit /b 1
)
if not exist "%SRC%scripts" (
    echo [ERROR] Package is incomplete: scripts is missing.
    echo See log: "%LOG%"
    pause
    exit /b 1
)

if not exist "%NOVA_PATH%" mkdir "%NOVA_PATH%" || goto :mkdir_failed
if not exist "%NOVA_PATH%\data" mkdir "%NOVA_PATH%\data" || goto :mkdir_failed
if not exist "%NOVA_PATH%\data\faces" mkdir "%NOVA_PATH%\data\faces" || goto :mkdir_failed
if not exist "%NOVA_PATH%\config" mkdir "%NOVA_PATH%\config" || goto :mkdir_failed

echo [INFO] Copying NovaUnlock runtime files...
xcopy "%SRC%nova_unlock" "%NOVA_PATH%\nova_unlock\" /E /I /Y >> "%LOG%" 2>&1
if errorlevel 1 goto :copy_failed
xcopy "%SRC%scripts" "%NOVA_PATH%\scripts\" /E /I /Y >> "%LOG%" 2>&1
if errorlevel 1 goto :copy_failed
if exist "%SRC%credential_provider" (
    xcopy "%SRC%credential_provider" "%NOVA_PATH%\credential_provider\" /E /I /Y >> "%LOG%" 2>&1
    if errorlevel 1 goto :copy_failed
)

echo [INFO] Installing Windows runtime dependencies...
call :install_vc_runtime
call :install_python_dependencies
if errorlevel 1 (
    echo [WARN] Python dependency install failed. Installing build tools and retrying...
    call :install_build_dependencies
    call :install_python_dependencies
    if errorlevel 1 goto :pip_failed
)
call :verify_python_dependencies
if errorlevel 1 (
    echo [WARN] Dependency import check failed. Repairing dependencies and retrying...
    call :install_build_dependencies
    call :install_python_dependencies
    if errorlevel 1 goto :pip_failed
    call :verify_python_dependencies
    if errorlevel 1 goto :pip_failed
)

(
    echo [auth]
    echo windows_user=%USERNAME%
) > "%NOVA_PATH%\config\nova.conf"

echo [INFO] Enrolling Windows password secret for Credential Provider use.
echo You will be asked for the Windows password for %USERNAME%.
%PY% "%NOVA_PATH%\scripts\windows_enroll_password.pyc"
if not "%errorLevel%"=="0" (
    echo [ERROR] Password enrollment failed. Credential Provider registration was not completed.
    echo See log: "%LOG%"
    pause
    exit /b 1
)

echo [INFO] Enrolling face profile for %USERNAME%.
%PY% "%NOVA_PATH%\nova_unlock\ui\enrollment_wizard.pyc"
if not "%errorLevel%"=="0" (
    echo [WARN] Face enrollment did not complete. Credential Provider registration will continue.
    echo [WARN] After install, rerun: %PY% "%NOVA_PATH%\nova_unlock\ui\enrollment_wizard.pyc"
    echo [WARN] See log: "%LOG%"
)

set "DAEMON=%NOVA_PATH%\scripts\windows_daemon.pyc"
if not exist "%DAEMON%" (
    echo [WARN] Windows daemon bytecode not found: %DAEMON%
) else (
    powershell -NoProfile -ExecutionPolicy Bypass -Command "$s=(New-Object -COM WScript.Shell).CreateShortcut('%STARTUP_FOLDER%\NovaUnlockDaemon.lnk'); $s.TargetPath='pythonw.exe'; $s.Arguments='""%DAEMON%""'; $s.WorkingDirectory='%NOVA_PATH%'; $s.Save()" >> "%LOG%" 2>&1
    if errorlevel 1 echo [WARN] Could not create startup shortcut. See log: "%LOG%"
)

if exist "%NOVA_PATH%\credential_provider\NovaUnlockProvider.dll" (
    echo [INFO] ======================================================
    echo [INFO] Registering Credential Provider...
    echo [INFO] ======================================================

    echo [INFO] Step 1: Running regsvr32 on NovaUnlockProvider.dll...
    if exist "%windir%\Sysnative\regsvr32.exe" (
        echo [INFO]   Using 64-bit regsvr32 via Sysnative...
        "%windir%\Sysnative\regsvr32.exe" /s "%NOVA_PATH%\credential_provider\NovaUnlockProvider.dll"
        echo [INFO]   regsvr32 exit code: %errorlevel%
    ) else (
        echo [INFO]   Using default regsvr32...
        regsvr32 /s "%NOVA_PATH%\credential_provider\NovaUnlockProvider.dll"
        echo [INFO]   regsvr32 exit code: %errorlevel%
    )

    echo [INFO] Step 2: Writing registry keys as backup...
    reg add "HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\Authentication\Credential Providers\{A1234567-B890-12CD-34EF-567890ABCDEF}" /ve /d "NovaUnlockProvider" /f /reg:64 >> "%LOG%" 2>&1
    if errorlevel 1 (
        echo [ERROR] Failed to write Credential Provider registry key.
        echo [ERROR] errorlevel=%errorlevel%
        goto :credential_failed
    )
    reg add "HKLM\SOFTWARE\Classes\CLSID\{A1234567-B890-12CD-34EF-567890ABCDEF}" /ve /d "NovaUnlockProvider" /f /reg:64 >> "%LOG%" 2>&1
    if errorlevel 1 (
        echo [ERROR] Failed to write CLSID registry key.
        goto :credential_failed
    )
    reg add "HKLM\SOFTWARE\Classes\CLSID\{A1234567-B890-12CD-34EF-567890ABCDEF}\InprocServer32" /ve /d "%NOVA_PATH%\credential_provider\NovaUnlockProvider.dll" /f /reg:64 >> "%LOG%" 2>&1
    if errorlevel 1 (
        echo [ERROR] Failed to write InprocServer32 registry key.
        goto :credential_failed
    )
    reg add "HKLM\SOFTWARE\Classes\CLSID\{A1234567-B890-12CD-34EF-567890ABCDEF}\InprocServer32" /v "ThreadingModel" /d "Apartment" /f /reg:64 >> "%LOG%" 2>&1
    if errorlevel 1 (
        echo [ERROR] Failed to write ThreadingModel registry key.
        goto :credential_failed
    )

    echo [INFO] Step 3: Verifying registration...
    reg query "HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\Authentication\Credential Providers\{A1234567-B890-12CD-34EF-567890ABCDEF}" /reg:64 >nul 2>&1
    if errorlevel 1 (
        echo [ERROR] Verification FAILED: Credential Provider key not found in registry.
        echo [ERROR] This means the registration did not persist. Check UAC and admin rights.
        goto :credential_failed
    )
    reg query "HKLM\SOFTWARE\Classes\CLSID\{A1234567-B890-12CD-34EF-567890ABCDEF}\InprocServer32" /reg:64 >nul 2>&1
    if errorlevel 1 (
        echo [ERROR] Verification FAILED: CLSID\InprocServer32 key not found in registry.
        goto :credential_failed
    )
    echo [OK] Credential Provider registered and verified successfully!
    echo [OK] NovaUnlock Face Login will appear on the Lock Screen after next restart.
) else (
    echo [WARN] Native Credential Provider DLL not included. Base daemon files were installed only.
)

echo [OK] NovaUnlock Windows files installed to %NOVA_PATH%.
echo [OK] Install log: "%LOG%"
pause
exit /b 0

:mkdir_failed
echo [ERROR] Could not create %NOVA_PATH%. Run as Administrator and check disk permissions.
echo See log: "%LOG%"
pause
exit /b 1

:copy_failed
echo [ERROR] Could not copy packaged runtime files to %NOVA_PATH%.
echo See log: "%LOG%"
pause
exit /b 1

:pip_failed
echo [ERROR] Python dependency installation failed.
echo NovaUnlock tried to install Python packages, VC runtime, CMake, and Microsoft C++ Build Tools automatically.
echo Please check internet access and Windows Update, then run this installer again as Administrator.
echo See log: "%LOG%"
pause
exit /b 1

:credential_failed
echo [ERROR] Credential Provider registration failed.
echo Run the installer as Administrator and check log: "%LOG%"
pause
exit /b 1

:find_python
set "PY="
py -3.11 -c "import sys; raise SystemExit(0 if sys.version_info[:2] == (3, 11) else 1)" >nul 2>&1
if not errorlevel 1 (
    set "PY=py -3.11"
    exit /b 0
)
python -c "import sys; raise SystemExit(0 if sys.version_info[:2] == (3, 11) else 1)" >nul 2>&1
if not errorlevel 1 (
    set "PY=python"
    exit /b 0
)
python3 -c "import sys; raise SystemExit(0 if sys.version_info[:2] == (3, 11) else 1)" >nul 2>&1
if not errorlevel 1 (
    set "PY=python3"
    exit /b 0
)
if exist "%ProgramFiles%\Python311\python.exe" (
    "%ProgramFiles%\Python311\python.exe" -c "import sys; raise SystemExit(0 if sys.version_info[:2] == (3, 11) else 1)" >nul 2>&1
    if not errorlevel 1 (
        set "PY="%ProgramFiles%\Python311\python.exe""
        exit /b 0
    )
)
if exist "%LocalAppData%\Programs\Python\Python311\python.exe" (
    "%LocalAppData%\Programs\Python\Python311\python.exe" -c "import sys; raise SystemExit(0 if sys.version_info[:2] == (3, 11) else 1)" >nul 2>&1
    if not errorlevel 1 (
        set "PY="%LocalAppData%\Programs\Python\Python311\python.exe""
        exit /b 0
    )
)
exit /b 1

:install_python
where winget >nul 2>&1
if not errorlevel 1 (
    echo [INFO] Installing Python 3.11 with winget...
    winget install --id Python.Python.3.11 -e --silent --accept-package-agreements --accept-source-agreements >> "%LOG%" 2>&1
    if not errorlevel 1 exit /b 0
    echo [WARN] winget Python install failed. Falling back to python.org direct installer.
)

echo [INFO] Downloading Python 3.11 from python.org...
powershell -NoProfile -ExecutionPolicy Bypass -Command "[Net.ServicePointManager]::SecurityProtocol=[Net.SecurityProtocolType]::Tls12; Invoke-WebRequest -Uri '%PYTHON_INSTALLER_URL%' -OutFile '%PYTHON_INSTALLER%'" >> "%LOG%" 2>&1
if errorlevel 1 (
    echo [ERROR] Could not download Python 3.11 from python.org.
    echo See log: "%LOG%"
    exit /b 1
)
if not exist "%PYTHON_INSTALLER%" (
    echo [ERROR] Python installer download did not create %PYTHON_INSTALLER%.
    echo See log: "%LOG%"
    exit /b 1
)

echo [INFO] Installing Python 3.11 from downloaded installer...
"%PYTHON_INSTALLER%" /quiet InstallAllUsers=1 PrependPath=1 Include_launcher=1 Include_pip=1 Include_test=0 >> "%LOG%" 2>&1
if errorlevel 1 (
    echo [WARN] All-users Python install failed. Trying current-user install.
    "%PYTHON_INSTALLER%" /quiet InstallAllUsers=0 PrependPath=1 Include_launcher=1 Include_pip=1 Include_test=0 >> "%LOG%" 2>&1
)
exit /b 0

:install_vc_runtime
echo [INFO] Installing Microsoft Visual C++ Runtime...
where winget >nul 2>&1
if not errorlevel 1 (
    winget install --id Microsoft.VCRedist.2015+.x64 -e --silent --accept-package-agreements --accept-source-agreements >> "%LOG%" 2>&1
    if not errorlevel 1 exit /b 0
    echo [WARN] winget VC runtime install failed. Trying direct Microsoft download.
)
set "VC_REDIST=%TEMP%\vc_redist.x64.exe"
powershell -NoProfile -ExecutionPolicy Bypass -Command "[Net.ServicePointManager]::SecurityProtocol=[Net.SecurityProtocolType]::Tls12; Invoke-WebRequest -Uri 'https://aka.ms/vs/17/release/vc_redist.x64.exe' -OutFile '%VC_REDIST%'" >> "%LOG%" 2>&1
if errorlevel 1 (
    echo [WARN] Could not download Microsoft VC runtime. Continuing; it may already be installed.
    exit /b 0
)
if exist "%VC_REDIST%" (
    "%VC_REDIST%" /install /quiet /norestart >> "%LOG%" 2>&1
    if errorlevel 1 echo [WARN] Microsoft VC runtime installer returned a non-zero status. Continuing.
)
exit /b 0

:install_python_dependencies
echo [INFO] Installing Python package dependencies...
%PY% -m ensurepip --upgrade >> "%LOG%" 2>&1
if errorlevel 1 exit /b 1
%PY% -m pip install --upgrade pip setuptools wheel >> "%LOG%" 2>&1
if errorlevel 1 exit /b 1
%PY% -m pip install --upgrade --prefer-binary cmake >> "%LOG%" 2>&1
if errorlevel 1 echo [WARN] pip CMake package install failed. Continuing to main dependencies.
if exist "%SRC%requirements.txt" (
    %PY% -m pip install --upgrade --prefer-binary -r "%SRC%requirements.txt" >> "%LOG%" 2>&1
    if errorlevel 1 exit /b 1
)
exit /b 0

:verify_python_dependencies
%PY% -c "import cv2, numpy, face_recognition, PyQt5, yaml" >> "%LOG%" 2>&1
if errorlevel 1 exit /b 1
exit /b 0

:install_build_dependencies
echo [INFO] Installing CMake and Microsoft C++ Build Tools for native Python packages...
where winget >nul 2>&1
if not errorlevel 1 (
    winget install --id Kitware.CMake -e --silent --accept-package-agreements --accept-source-agreements >> "%LOG%" 2>&1
    if errorlevel 1 echo [WARN] winget CMake install failed. pip CMake package may still work.
    winget install --id Microsoft.VisualStudio.2022.BuildTools -e --silent --accept-package-agreements --accept-source-agreements --override "--quiet --wait --norestart --nocache --add Microsoft.VisualStudio.Workload.VCTools --includeRecommended" >> "%LOG%" 2>&1
    if not errorlevel 1 exit /b 0
    echo [WARN] winget Build Tools install failed. Trying direct Microsoft installer.
)

set "VS_BUILDTOOLS=%TEMP%\vs_BuildTools.exe"
powershell -NoProfile -ExecutionPolicy Bypass -Command "[Net.ServicePointManager]::SecurityProtocol=[Net.SecurityProtocolType]::Tls12; Invoke-WebRequest -Uri 'https://aka.ms/vs/17/release/vs_BuildTools.exe' -OutFile '%VS_BUILDTOOLS%'" >> "%LOG%" 2>&1
if errorlevel 1 (
    echo [WARN] Could not download Microsoft C++ Build Tools. Dependency retry may still fail.
    exit /b 0
)
if exist "%VS_BUILDTOOLS%" (
    "%VS_BUILDTOOLS%" --quiet --wait --norestart --nocache --add Microsoft.VisualStudio.Workload.VCTools --includeRecommended >> "%LOG%" 2>&1
    if errorlevel 1 echo [WARN] Microsoft C++ Build Tools installer returned a non-zero status.
)
exit /b 0
BAT

if find "$RELEASE_DIR" -name '*.py' -print -quit | grep -q .; then
    echo "Release bundle still contains Python source files" >&2
    exit 1
fi
if find "$RELEASE_DIR" \( -name '*.cpp' -o -name '*.c' -o -name '*.h' -o -name '*.hpp' -o -name '*.def' -o -name 'CMakeLists.txt' -o -name '*.sln' -o -name '*.vcxproj' \) -print -quit | grep -q .; then
    echo "Release bundle still contains native source/project files" >&2
    exit 1
fi

cd "$RELEASE_DIR"
rm -f "$OUTPUT_ZIP"
zip -r "$OUTPUT_ZIP" . > /dev/null
cd "$ROOT_DIR"
sha256sum "$OUTPUT_ZIP" > "$OUTPUT_ZIP.sha256"

rm -f "$OUTPUT_EXE" "$OUTPUT_EXE.sha256"
if [ -n "$WINDOWS_PE_STUB" ]; then
    if [ ! -f "$WINDOWS_PE_STUB" ]; then
        echo "Windows PE stub not found: $WINDOWS_PE_STUB" >&2
        exit 1
    fi
    if ! head -c 2 "$WINDOWS_PE_STUB" | grep -q 'MZ'; then
        echo "Windows PE stub is not a valid Windows executable: $WINDOWS_PE_STUB" >&2
        exit 1
    fi
    zip_offset="$(7z l "$WINDOWS_PE_STUB" | awk '/^Offset = / {print $3; exit}')"
    if [ -z "$zip_offset" ] || ! printf '%s' "$zip_offset" | grep -Eq '^[0-9]+$'; then
        echo "Could not determine ZIP payload offset in Windows PE stub: $WINDOWS_PE_STUB" >&2
        exit 1
    fi
    head -c "$zip_offset" "$WINDOWS_PE_STUB" > "$OUTPUT_EXE"
    cat "$OUTPUT_ZIP" >> "$OUTPUT_EXE"
    chmod 755 "$OUTPUT_EXE"
    sha256sum "$OUTPUT_EXE" > "$OUTPUT_EXE.sha256"
else
    echo "Warning: WINDOWS_PE_STUB was not set; Windows EXE was not created." >&2
fi
{
    echo "NovaUnlock Windows v$VERSION"
    echo "Built: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
    echo "Source directory: $SOURCE_DIR"
    echo
    echo "Artifact audit:"
    echo "- Python source: none"
    echo "- Native source/project files: none"
    if [ -f "$OUTPUT_EXE" ]; then
        echo "- Self-extracting EXE: included"
    else
        echo "- Self-extracting EXE: missing"
    fi
    if [ -f "$RELEASE_DIR/credential_provider/NovaUnlockProvider.dll" ]; then
        echo "- Credential Provider DLL: included"
    else
        echo "- Credential Provider DLL: missing; installs base daemon only"
    fi
    echo
    echo "Files:"
    find "$RELEASE_DIR" -type f -printf '%P\n' | sort
} > "$MANIFEST"

echo
echo "Protected Windows release ready:"
echo "  $OUTPUT_ZIP"
echo "  $OUTPUT_ZIP.sha256"
if [ -f "$OUTPUT_EXE" ]; then
    echo "  $OUTPUT_EXE"
    echo "  $OUTPUT_EXE.sha256"
fi
echo "  $MANIFEST"
echo
echo "You can now upload this ZIP to your GitHub Releases."
