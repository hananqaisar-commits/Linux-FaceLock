# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['installer_main.py'],
    pathex=[],
    binaries=[],
    datas=[('install.sh', '.'), ('data', 'data'), ('config', 'config'), ('nova_bundle', 'nova_bundle'), ('scripts', 'scripts'), ('systemd', 'systemd'), ('nova_unlock', 'nova_unlock'), ('requirements.txt', '.'), ('LICENSE', '.'), ('README.md', '.')],
    hiddenimports=['face_recognition', 'cv2', 'numpy', 'dlib', 'PyQt5', 'yaml', 'nova_unlock.ui.theme_manager', 'nova_unlock.vision.liveness'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='nova_unlock_installer_v5.3',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
