@echo off
echo ==============================================
echo  NovaUnlock Windows 10/11 Installer
echo ==============================================

net session >nul 2>&1
if %errorLevel% == 0 (
    echo [OK] Running with Administrator privileges.
) else (
    echo [ERROR] Administrator privileges are required.
    echo Please right-click this script and select "Run as administrator".
    pause
    exit /b 1
)

echo Installing Python Dependencies...
pip install -r requirements.txt

set "NOVA_PATH=%APPDATA%\NovaUnlock"
if not exist "%NOVA_PATH%" mkdir "%NOVA_PATH%"
if not exist "%NOVA_PATH%\config" mkdir "%NOVA_PATH%\config"
if not exist "%NOVA_PATH%\data\faces" mkdir "%NOVA_PATH%\data\faces"

echo Copying configuration...
copy "config\nova.conf" "%NOVA_PATH%\config\nova.conf" >nul

echo Setting up Auto-Start Daemon...
set "STARTUP_FOLDER=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup"
set "DAEMON_SCRIPT=%~dp0windows_port\scripts\windows_daemon.py"

echo Set oWS = WScript.CreateObject("WScript.Shell") > CreateShortcut.vbs
echo sLinkFile = "%STARTUP_FOLDER%\NovaUnlockDaemon.lnk" >> CreateShortcut.vbs
echo Set oLink = oWS.CreateShortcut(sLinkFile) >> CreateShortcut.vbs
echo oLink.TargetPath = "pythonw.exe" >> CreateShortcut.vbs
echo oLink.Arguments = """%DAEMON_SCRIPT%""" >> CreateShortcut.vbs
echo oLink.Save >> CreateShortcut.vbs

cscript /nologo CreateShortcut.vbs
del CreateShortcut.vbs

echo.
echo ==============================================
echo [SUCCESS] NovaUnlock (Windows Base) Installed.
echo ==============================================
echo - Background daemon will now start on boot.
echo - Please see windows_port\credential_provider\README_WINDOWS_AUTH.md 
echo   for instructions on setting up native OS-level Face Login.
echo.
pause
