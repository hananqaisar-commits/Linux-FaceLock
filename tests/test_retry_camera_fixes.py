#!/usr/bin/env python3
"""
Regression & UI tests for Linux-FaceLock (Dynamic Island Face ID).
"""
import sys
from pathlib import Path
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from PyQt5.QtWidgets import QApplication

@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])

def test_widget_creation(app):
    from nova_unlock.ui.face_id_screen import Sig, FaceUnlockWidget
    sig = Sig()
    w = FaceUnlockWidget(sig, demo_mode=True)
    assert w is not None
    assert w.W == 420
    assert w.H == 160

def test_faceworker_initialization():
    from nova_unlock.ui.face_id_screen import Sig, FaceWorker
    sig = Sig()
    worker = FaceWorker(sig)
    assert worker.on is True

def test_open_camera_opens_real_device():
    """open_camera() probes available video devices."""
    try:
        from nova_unlock.vision.camera_detector import open_camera
        cap = open_camera(max_index=6, width=320, height=240, fps=30)
        if cap is None:
            pytest.skip("no camera available on this host")
        try:
            assert cap.isOpened()
        finally:
            cap.release()
    except ImportError:
        pytest.skip("camera_detector module not in current path")
