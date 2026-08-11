import sys, time
from PyQt5.QtWidgets import QApplication, QWidget
from PyQt5.QtCore import QTimer
from PyQt5.QtGui import QColor, QPalette
from nova_unlock.ui.face_id_screen import FaceUnlockWidget, Sig

app = QApplication(sys.argv)

win = QWidget()
win.resize(600, 300)
pal = win.palette()
pal.setColor(QPalette.Window, QColor(245, 245, 247)) # light gray
win.setAutoFillBackground(True)
win.setPalette(pal)

sig = Sig()
w = FaceUnlockWidget(sig, demo_mode=True)
w.setParent(win)
w.move((600 - w.W) // 2, (300 - w.H) // 2)
w.show()
win.show()

def take_shot(name):
    pixmap = win.grab()
    pixmap.save(name)
    print(f"Saved {name}")

QTimer.singleShot(1500, lambda: take_shot("assets/facelock_scanning.png"))
QTimer.singleShot(3000, lambda: take_shot("assets/facelock_success.png"))
QTimer.singleShot(3500, app.quit)

app.exec_()
