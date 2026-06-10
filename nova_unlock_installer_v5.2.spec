# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['installer_main.py'],
    pathex=[],
    binaries=[],
    datas=[('data', 'data'), ('config', 'config'), ('nova_bundle', 'nova_bundle'), ('scripts', 'scripts'), ('systemd', 'systemd'), ('shape_predictor_68_face_landmarks.dat', '.')],
    hiddenimports=['face_recognition', 'cv2', 'numpy', 'dlib', 'mediapipe', 'PyQt5', 'yaml', 'nova_unlock.core.config_manager', 'nova_unlock.core.system_detect', 'nova_unlock.vision.face_recognizer', 'nova_unlock.vision.liveness', 'nova_unlock.vision.camera_detector', 'nova_unlock.ui.greeter', 'nova_unlock.ui.enrollment_wizard', 'nova_unlock.ui.face_id_screen', 'nova_unlock.ui.face_id_embed', 'nova_unlock.ui.password_fallback', 'nova_unlock.ui.jarvis_overlay', 'nova_unlock.ui.theme_manager', 'nova_unlock.security.face_auth_pam'],
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
    name='nova_unlock_installer_v5.2',
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
