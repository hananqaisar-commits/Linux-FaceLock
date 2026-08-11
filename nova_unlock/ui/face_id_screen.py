#!/usr/bin/env python3
"""
NovaUnlock — Dynamic Island Face ID Screen (Clean, Fast & Lightweight).

This module re-exports the canonical fast Dynamic Island Face ID UI implementation
from `nova_unlock.ui.face_unlock_widget`.
"""
import sys
from nova_unlock.ui.face_unlock_widget import (  # noqa: F401
    Sig,
    Spring,
    FaceUnlockWidget,
    FaceWorker,
    FaceIDLoginApp,
    play,
    demo,
    SND_POP,
    SND_OK,
    SND_FAIL,
    SND_COLLAPSE,
)

__all__ = [
    "Sig",
    "Spring",
    "FaceUnlockWidget",
    "FaceWorker",
    "FaceIDLoginApp",
    "play",
    "demo",
    "SND_POP",
    "SND_OK",
    "SND_FAIL",
    "SND_COLLAPSE",
]

if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--demo", action="store_true")
    ap.add_argument("--test", action="store_true")
    args = ap.parse_args()
    if args.test:
        print(f"User: {FaceIDLoginApp().run()}")
    else:
        demo()
