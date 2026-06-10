#!/usr/bin/env python3
"""Auto-patch face_recognition_models for Python 3.13"""
import sysconfig
from pathlib import Path

target = Path(sysconfig.get_paths()["purelib"]) / "face_recognition_models" / "__init__.py"

if target.exists():
    target.write_text('''import os

_models = os.path.join(os.path.dirname(__file__), "models")

def pose_predictor_model_location():
    return os.path.join(_models, "shape_predictor_68_face_landmarks.dat")

def pose_predictor_five_point_model_location():
    return os.path.join(_models, "shape_predictor_5_face_landmarks.dat")

def face_recognition_model_location():
    return os.path.join(_models, "dlib_face_recognition_resnet_model_v1.dat")

def cnn_face_detector_model_location():
    return os.path.join(_models, "mmod_human_face_detector.dat")
''')
    print(f"✅ Patched: {target}")
else:
    print(f"❌ Not found: {target}")
