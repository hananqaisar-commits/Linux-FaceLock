# NovaUnlock Windows Credential Provider Integration

Windows 10 and 11 do not support Linux PAM modules. To achieve OS-level face unlock (the exact same working way as Linux), Windows requires a **Custom Credential Provider** written in C++ that hooks into the `Winlogon` process.

Since NovaUnlock is written in Python, the standard architecture for porting this functionality to Windows is:

1. **C++ Credential Provider (DLL):** A lightweight C++ wrapper that loads into the Windows Logon screen.
2. **Python Auth Bridge (`unlock_auth.py`):** The C++ wrapper spawns this Python script to perform the actual face recognition and liveness detection.
3. **Authentication Token:** If `unlock_auth.py` returns an exit code of `0`, the C++ Credential Provider logs the user in.

## How to use this directory
We have provided the `unlock_auth.py` script which acts as the bridge. 
To complete the OS-level integration, you will need to compile a boilerplate Credential Provider (like the open-source `pGina` or Microsoft's `V2 Credential Provider Sample`) using Visual Studio, and configure it to execute `pythonw.exe unlock_auth.py`.

If you do not compile the Credential Provider, the `windows_daemon.py` will still function to auto-lock your PC when your face leaves the camera, but unlocking will require your Windows PIN/Password.
