import os

def write(path, content):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)
    print(f"Created: {path}")

# ============================================================
# LICENSING SYSTEM
# ============================================================

write('nova_unlock/licensing/__init__.py', '''
from .license_validator import LicenseValidator
from .activation_manager import ActivationManager
from .hardware_id import get_hardware_fingerprint
''')

write('nova_unlock/licensing/hardware_id.py', '''
import subprocess
import hashlib
import uuid
import platform

def get_hardware_fingerprint():
    parts = []

    # CPU ID
    try:
        r = subprocess.run(["wmic","cpu","get","ProcessorId"],
                           capture_output=True, text=True, timeout=5)
        lines = [l.strip() for l in r.stdout.split("\\n")
                 if l.strip() and "ProcessorId" not in l]
        parts.append(lines[0] if lines else "NO_CPU")
    except:
        parts.append("NO_CPU")

    # Disk Serial
    try:
        r = subprocess.run(["wmic","diskdrive","get","SerialNumber"],
                           capture_output=True, text=True, timeout=5)
        lines = [l.strip() for l in r.stdout.split("\\n")
                 if l.strip() and "SerialNumber" not in l]
        parts.append(lines[0] if lines else "NO_DISK")
    except:
        parts.append("NO_DISK")

    # Machine GUID
    try:
        import winreg
        key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,
                             r"SOFTWARE\\Microsoft\\Cryptography")
        guid, _ = winreg.QueryValueEx(key, "MachineGuid")
        parts.append(guid)
    except:
        parts.append(str(uuid.getnode()))

    # Motherboard Serial
    try:
        r = subprocess.run(["wmic","baseboard","get","SerialNumber"],
                           capture_output=True, text=True, timeout=5)
        lines = [l.strip() for l in r.stdout.split("\\n")
                 if l.strip() and "SerialNumber" not in l]
        parts.append(lines[0] if lines else "NO_MB")
    except:
        parts.append("NO_MB")

    combined = "|".join(parts)
    fingerprint = hashlib.sha256(combined.encode()).hexdigest()[:32].upper()
    return fingerprint


def get_short_hw_id():
    full = get_hardware_fingerprint()
    return full[:8] + "-" + full[8:12] + "-" + full[12:16]
''')

write('nova_unlock/licensing/crypto_engine.py', '''
import base64
import json
import hashlib
import hmac
import os

# This secret key is embedded in app (obfuscated in production)
# In real release: use RSA or keep this in compiled .pyd
SECRET_KEY = b"NovaUnlock-SecretKey-2025-HananQaisar-DO-NOT-SHARE"

def sign_license(license_data: dict) -> str:
    data_str = json.dumps(license_data, sort_keys=True)
    sig = hmac.new(SECRET_KEY, data_str.encode(), hashlib.sha256).digest()
    return base64.b64encode(sig).decode()

def verify_license(license_data: dict, signature: str) -> bool:
    try:
        expected = sign_license(license_data)
        return hmac.compare_digest(expected, signature)
    except:
        return False

def encrypt_data(data: str) -> str:
    key = SECRET_KEY[:16]
    result = []
    for i, c in enumerate(data.encode()):
        result.append(c ^ key[i % len(key)])
    return base64.b64encode(bytes(result)).decode()

def decrypt_data(data: str) -> str:
    key = SECRET_KEY[:16]
    decoded = base64.b64decode(data)
    result = []
    for i, c in enumerate(decoded):
        result.append(c ^ key[i % len(key)])
    return bytes(result).decode()
''')

write('nova_unlock/licensing/storage.py', '''
import os
import json
import time
from .crypto_engine import encrypt_data, decrypt_data

LICENSE_DIR  = r"C:\\ProgramData\\NovaUnlock\\license"
LICENSE_FILE = os.path.join(LICENSE_DIR, "nova.lic")
TRIAL_FILE   = os.path.join(LICENSE_DIR, "trial.dat")
TIME_FILE    = os.path.join(LICENSE_DIR, "lastrun.dat")

class SecureStorage:
    def __init__(self):
        os.makedirs(LICENSE_DIR, exist_ok=True)

    def save_license(self, license_bundle: dict):
        raw = json.dumps(license_bundle)
        enc = encrypt_data(raw)
        with open(LICENSE_FILE, "w") as f:
            f.write(enc)

    def load_license(self):
        if not os.path.exists(LICENSE_FILE):
            return None
        try:
            with open(LICENSE_FILE) as f:
                enc = f.read()
            raw = decrypt_data(enc)
            return json.loads(raw)
        except:
            return None

    def delete_license(self):
        if os.path.exists(LICENSE_FILE):
            os.remove(LICENSE_FILE)

    def start_trial(self):
        data = {"install_date": time.time(), "trial_started": True}
        raw = json.dumps(data)
        with open(TRIAL_FILE, "w") as f:
            f.write(encrypt_data(raw))

    def get_trial_info(self):
        if not os.path.exists(TRIAL_FILE):
            return None
        try:
            with open(TRIAL_FILE) as f:
                raw = decrypt_data(f.read())
            return json.loads(raw)
        except:
            return None

    def update_last_run_time(self, t=None):
        t = t or time.time()
        with open(TIME_FILE, "w") as f:
            f.write(encrypt_data(str(t)))

    def get_last_run_time(self):
        if not os.path.exists(TIME_FILE):
            return None
        try:
            with open(TIME_FILE) as f:
                return float(decrypt_data(f.read()))
        except:
            return None
''')

write('nova_unlock/licensing/license_validator.py', '''
import time
from datetime import datetime, timezone
from .hardware_id import get_hardware_fingerprint
from .crypto_engine import verify_license
from .storage import SecureStorage

TRIAL_DAYS = 30

class LicenseValidator:
    def __init__(self):
        self.storage = SecureStorage()
        self.hw_id   = get_hardware_fingerprint()

    def validate(self) -> dict:
        # Clock rollback check first
        if self._clock_rollback():
            return {
                "valid": False,
                "reason": "System clock tampering detected",
                "code": "CLOCK_TAMPER"
            }

        self.storage.update_last_run_time()

        bundle = self.storage.load_license()

        if not bundle:
            return self._check_trial()

        lic  = bundle.get("data", {})
        sig  = bundle.get("signature", "")

        # Signature check
        if not verify_license(lic, sig):
            return {"valid": False, "reason": "License signature invalid", "code": "SIG_FAIL"}

        # Hardware check
        if lic.get("hardware_id") != self.hw_id:
            return {"valid": False, "reason": "License bound to different device", "code": "HW_MISMATCH"}

        # Expiry check
        expiry_ts = lic.get("expiry_timestamp")
        if expiry_ts:
            now = time.time()
            grace_end = expiry_ts + (3 * 86400)  # 3 day grace
            if now > grace_end:
                return {"valid": False, "reason": "License expired", "code": "EXPIRED"}
            if now > expiry_ts:
                days_grace = int((grace_end - now) / 86400) + 1
                return {
                    "valid": True,
                    "grace": True,
                    "days_grace_left": days_grace,
                    "license": lic
                }

        return {"valid": True, "license": lic}

    def _check_trial(self):
        info = self.storage.get_trial_info()
        if not info:
            self.storage.start_trial()
            return {"valid": True, "trial": True, "days_left": TRIAL_DAYS}

        elapsed_days = int((time.time() - info["install_date"]) / 86400)
        days_left    = max(0, TRIAL_DAYS - elapsed_days)

        if days_left == 0:
            return {
                "valid": False,
                "trial_expired": True,
                "days_left": 0,
                "code": "TRIAL_EXPIRED"
            }

        return {"valid": True, "trial": True, "days_left": days_left}

    def _clock_rollback(self):
        last = self.storage.get_last_run_time()
        now  = time.time()
        if last and now < last - 120:
            return True
        return False
''')

write('nova_unlock/licensing/license_generator.py', '''
"""
DEVELOPER TOOL ONLY — Never ship this to customers
Run this on YOUR machine to generate license keys
"""
import json
import time
import uuid
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from nova_unlock.licensing.crypto_engine import sign_license
from nova_unlock.licensing.storage import SecureStorage

LICENSE_TYPES = {
    "trial":    {"days": 30,    "price": 0,     "label": "Trial"},
    "monthly":  {"days": 30,    "price": 4.99,  "label": "Monthly"},
    "yearly":   {"days": 365,   "price": 29.99, "label": "Yearly"},
    "lifetime": {"days": 36500, "price": 79.99, "label": "Lifetime"},
}

def generate_license(
    customer_name: str,
    customer_email: str,
    hardware_id: str,
    license_type: str = "monthly",
    version_lock: str = "7.x"
):
    if license_type not in LICENSE_TYPES:
        raise ValueError(f"Invalid type. Choose: {list(LICENSE_TYPES.keys())}")

    ltype = LICENSE_TYPES[license_type]
    now   = time.time()
    exp   = now + (ltype["days"] * 86400)

    license_data = {
        "license_id":     str(uuid.uuid4()).upper(),
        "customer_name":  customer_name,
        "customer_email": customer_email,
        "hardware_id":    hardware_id,
        "license_type":   license_type,
        "version_lock":   version_lock,
        "issued_at":      now,
        "expiry_timestamp": exp if license_type != "lifetime" else None,
        "price_paid":     ltype["price"],
        "currency":       "USD",
    }

    signature = sign_license(license_data)

    bundle = {
        "data":      license_data,
        "signature": signature,
        "format":    "nova-v1"
    }

    print("=" * 60)
    print(f"LICENSE GENERATED — {ltype[\'label\'].upper()}")
    print("=" * 60)
    print(f"Customer : {customer_name}")
    print(f"Email    : {customer_email}")
    print(f"HW ID    : {hardware_id}")
    print(f"Type     : {license_type}")
    print(f"Expires  : {\'Never\' if license_type == \'lifetime\' else time.strftime(\'%Y-%m-%d\', time.localtime(exp))}")
    print(f"License ID: {license_data[\'license_id\']}")
    print("=" * 60)

    return bundle


def save_license_to_file(bundle: dict, output_path: str):
    import json
    with open(output_path, "w") as f:
        json.dump(bundle, f, indent=2)
    print(f"License saved: {output_path}")


if __name__ == "__main__":
    # Example usage
    hw_id = input("Enter customer Hardware ID: ").strip()
    name  = input("Customer name: ").strip()
    email = input("Customer email: ").strip()
    ltype = input("License type (trial/monthly/yearly/lifetime): ").strip()

    bundle = generate_license(name, email, hw_id, ltype)
    out    = f"license_{name.replace(chr(32), \'_\')}_{ltype}.json"
    save_license_to_file(bundle, out)
''')

write('nova_unlock/licensing/activation_manager.py', '''
import json
import os
from .license_validator import LicenseValidator
from .storage import SecureStorage
from .hardware_id import get_hardware_fingerprint, get_short_hw_id

class ActivationManager:
    def __init__(self):
        self.validator = LicenseValidator()
        self.storage   = SecureStorage()

    def get_hardware_id(self) -> str:
        return get_short_hw_id()

    def activate_from_file(self, license_file_path: str) -> dict:
        try:
            with open(license_file_path) as f:
                bundle = json.load(f)
        except Exception as e:
            return {"success": False, "error": f"Cannot read license file: {e}"}

        result = self._validate_bundle(bundle)
        if result["success"]:
            self.storage.save_license(bundle)

        return result

    def activate_from_string(self, license_json: str) -> dict:
        try:
            bundle = json.loads(license_json)
        except:
            return {"success": False, "error": "Invalid license format"}

        result = self._validate_bundle(bundle)
        if result["success"]:
            self.storage.save_license(bundle)

        return result

    def _validate_bundle(self, bundle: dict) -> dict:
        hw = get_hardware_fingerprint()
        lic_hw = bundle.get("data", {}).get("hardware_id", "")

        if lic_hw != hw:
            return {
                "success": False,
                "error": "This license is for a different device.",
                "your_hw_id": self.get_hardware_id()
            }

        status = self.validator.validate()
        if status.get("valid"):
            return {"success": True, "license": bundle["data"]}
        else:
            return {"success": False, "error": status.get("reason", "Invalid license")}

    def deactivate(self):
        self.storage.delete_license()
        return {"success": True}

    def get_status(self) -> dict:
        return self.validator.validate()
''')

# ============================================================
# WINDOWS SERVICE (Lockscreen Fix)
# ============================================================

write('scripts/nova_service.py', '''
"""
NovaUnlock Windows Service
Fixes lockscreen UI issue — runs daemon in background
Auto-starts with Windows
"""
import sys
import os
import time
import threading
import subprocess
import logging

log_path = r"C:\\ProgramData\\NovaUnlock\\logs\\service.log"
os.makedirs(os.path.dirname(log_path), exist_ok=True)
logging.basicConfig(
    filename=log_path,
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)

NOVA_HOME  = r"C:\\ProgramData\\NovaUnlock"
PYTHON_EXE = sys.executable  # Python that installed this

try:
    import win32serviceutil
    import win32service
    import win32event
    import servicemanager
    HAS_WIN32 = True
except ImportError:
    HAS_WIN32 = False
    logging.warning("pywin32 not found — running in standalone mode")


class NovaUnlockService:
    if HAS_WIN32:
        _svc_name_        = "NovaUnlockService"
        _svc_display_name_ = "NovaUnlock Face Authentication Service"
        _svc_description_  = "Provides face-based login for NovaUnlock"

    def __init__(self, args=None):
        if HAS_WIN32:
            win32serviceutil.ServiceFramework.__init__(self, args)
            self.stop_event = win32event.CreateEvent(None, 0, 0, None)
        self.running = False

    def SvcStop(self):
        logging.info("Service stopping...")
        self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
        win32event.SetEvent(self.stop_event)
        self.running = False

    def SvcDoRun(self):
        logging.info("NovaUnlock Service started")
        servicemanager.LogMsg(
            servicemanager.EVENTLOG_INFORMATION_TYPE,
            servicemanager.PYS_SERVICE_STARTED,
            (self._svc_name_, "")
        )
        self.running = True
        self.main_loop()

    def main_loop(self):
        """Main service loop — starts credential bridge"""
        bridge_script = os.path.join(NOVA_HOME, "scripts", "credential_bridge.py")
        process = None

        while self.running:
            # Restart bridge if it crashes
            if process is None or process.poll() is not None:
                logging.info("Starting credential bridge...")
                try:
                    process = subprocess.Popen(
                        [PYTHON_EXE, bridge_script],
                        cwd=NOVA_HOME,
                        creationflags=subprocess.CREATE_NO_WINDOW
                    )
                    logging.info(f"Bridge started PID={process.pid}")
                except Exception as e:
                    logging.error(f"Bridge start failed: {e}")

            time.sleep(5)

        if process:
            process.terminate()
        logging.info("Service stopped")


def run_standalone():
    """Run without Windows service wrapper"""
    logging.info("Running in standalone mode")
    service = NovaUnlockService()
    service.running = True
    service.main_loop()


if __name__ == "__main__":
    if len(sys.argv) == 1:
        if HAS_WIN32:
            servicemanager.Initialize()
            servicemanager.PrepareToHostSingle(NovaUnlockService)
            servicemanager.StartServiceCtrlDispatcher()
        else:
            run_standalone()
    elif HAS_WIN32:
        win32serviceutil.HandleCommandLine(NovaUnlockService)
''')

write('scripts/credential_bridge.py', '''
"""
Credential Bridge — connects C++ DLL with Python face auth
The DLL sends a command via named pipe
This script runs face recognition and returns result
"""
import os
import sys
import time
import json
import logging
import threading

NOVA_HOME = r"C:\\ProgramData\\NovaUnlock"
sys.path.insert(0, NOVA_HOME)

log_path = os.path.join(NOVA_HOME, "logs", "bridge.log")
os.makedirs(os.path.dirname(log_path), exist_ok=True)
logging.basicConfig(
    filename=log_path,
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)

PIPE_NAME = r"\\\\.\\pipe\\NovaUnlockPipe"


def run_face_auth() -> dict:
    """Run face recognition and return result"""
    try:
        from nova_unlock.licensing.license_validator import LicenseValidator
        validator = LicenseValidator()
        status = validator.validate()

        if not status.get("valid"):
            code = status.get("code", "UNKNOWN")
            if code in ("TRIAL_EXPIRED", "EXPIRED"):
                return {
                    "success": False,
                    "error": "license_expired",
                    "message": "Please purchase a license at novaunlock.com"
                }
            return {"success": False, "error": status.get("reason")}

        # Run face recognition
        from nova_unlock.vision.face_recognizer import FaceRecognizer
        recognizer = FaceRecognizer()
        result = recognizer.authenticate(timeout=15)

        if result.get("authenticated"):
            logging.info(f"Face auth SUCCESS: {result.get(\'user\', \'unknown\')}")
            return {"success": True, "user": result.get("user", "user")}
        else:
            logging.warning("Face auth FAILED")
            return {"success": False, "error": "face_not_recognized"}

    except Exception as e:
        logging.error(f"Face auth error: {e}")
        return {"success": False, "error": str(e)}


def show_face_ui_overlay():
    """Show PyQt5 face auth UI"""
    try:
        from nova_unlock.ui.face_id_screen import FaceIDScreen
        from PyQt5.QtWidgets import QApplication
        import sys

        app = QApplication.instance() or QApplication(sys.argv)
        screen = FaceIDScreen()
        screen.show_on_top()
        result = screen.wait_for_result()
        return result
    except Exception as e:
        logging.error(f"UI error: {e}")
        return run_face_auth()  # Fallback to headless


def pipe_server():
    """Listen for DLL commands via named pipe"""
    try:
        import win32pipe
        import win32file

        while True:
            logging.info("Waiting for DLL connection on pipe...")
            pipe = win32pipe.CreateNamedPipe(
                PIPE_NAME,
                win32pipe.PIPE_ACCESS_DUPLEX,
                win32pipe.PIPE_TYPE_MESSAGE | win32pipe.PIPE_WAIT,
                1, 65536, 65536, 0, None
            )

            win32pipe.ConnectNamedPipe(pipe, None)
            logging.info("DLL connected!")

            try:
                _, data = win32file.ReadFile(pipe, 4096)
                command = data.decode().strip()
                logging.info(f"DLL command: {command}")

                if command == "AUTH_REQUEST":
                    result = show_face_ui_overlay()
                    response = json.dumps(result)
                    win32file.WriteFile(pipe, response.encode())
                    logging.info(f"Sent to DLL: {response}")

            except Exception as e:
                logging.error(f"Pipe error: {e}")
            finally:
                win32file.CloseHandle(pipe)

    except ImportError:
        logging.warning("win32pipe not available — using fallback mode")
        fallback_loop()


def fallback_loop():
    """Fallback: watch for lock screen via WTS"""
    try:
        import ctypes
        import ctypes.wintypes

        logging.info("Running in WTS session monitor mode")
        last_state = None

        while True:
            # Check if workstation is locked
            hdesk = ctypes.windll.user32.OpenDesktopW(
                "Default", 0, False, 0x0100
            )
            locked = (hdesk == 0)
            if hdesk:
                ctypes.windll.user32.CloseDesktop(hdesk)

            if locked and last_state != "locked":
                logging.info("Lock screen detected — showing face auth")
                last_state = "locked"
                result = show_face_ui_overlay()
                if result.get("success"):
                    # Unlock via stored credentials
                    unlock_workstation()

            elif not locked:
                last_state = "unlocked"

            time.sleep(1)

    except Exception as e:
        logging.error(f"Fallback error: {e}")
        time.sleep(10)


def unlock_workstation():
    """Simulate credential entry to unlock"""
    try:
        import win32security
        import win32api
        # Load stored Windows password and replay it
        cred_file = os.path.join(NOVA_HOME, "data", "win_cred.enc")
        if os.path.exists(cred_file):
            from nova_unlock.licensing.crypto_engine import decrypt_data
            with open(cred_file) as f:
                password = decrypt_data(f.read())
            os.system(f\'powershell -Command "(New-Object -COM Shell.Application).Windows()"\')
            logging.info("Unlock attempted")
    except Exception as e:
        logging.error(f"Unlock error: {e}")


if __name__ == "__main__":
    logging.info("Credential bridge started")
    pipe_server()
''')

# ============================================================
# LICENSE UI DIALOG
# ============================================================

write('nova_unlock/ui/license_dialog.py', '''
"""
License Dialog — shows when trial expires or activation needed
"""
import sys
import os
from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout,
                              QLabel, QPushButton, QLineEdit,
                              QFileDialog, QMessageBox, QFrame)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont, QColor

NOVA_HOME = r"C:\\ProgramData\\NovaUnlock"
sys.path.insert(0, NOVA_HOME)

class LicenseDialog(QDialog):
    PLANS = [
        {"name": "Monthly",  "price": "$4.99/mo",  "type": "monthly"},
        {"name": "Yearly",   "price": "$29.99/yr", "type": "yearly"},
        {"name": "Lifetime", "price": "$79.99",    "type": "lifetime"},
    ]

    def __init__(self, status: dict, parent=None):
        super().__init__(parent)
        self.status = status
        self.setWindowTitle("NovaUnlock — Activate")
        self.setFixedSize(520, 600)
        self.setStyleSheet("""
            QDialog    { background: #0d0d0d; color: #ffffff; }
            QLabel     { color: #ffffff; }
            QPushButton{
                background: #1a1a2e; color: #00d4ff;
                border: 1px solid #00d4ff; border-radius: 8px;
                padding: 10px 20px; font-size: 14px;
            }
            QPushButton:hover { background: #00d4ff; color: #000; }
            QLineEdit  {
                background: #1a1a2e; color: #fff;
                border: 1px solid #333; border-radius: 6px;
                padding: 8px; font-size: 13px;
            }
        """)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        layout.setContentsMargins(30, 30, 30, 30)

        # Title
        title = QLabel("NovaUnlock")
        title.setFont(QFont("Arial", 24, QFont.Bold))
        title.setStyleSheet("color: #00d4ff;")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

        # Status message
        if self.status.get("trial_expired"):
            msg = "Your 30-day free trial has ended."
            sub = "Purchase a license to continue using NovaUnlock."
        elif self.status.get("grace"):
            days = self.status.get("days_grace_left", 0)
            msg = f"Your license expired — {days} day grace period remaining."
            sub = "Renew now to avoid interruption."
        else:
            msg = "Activate NovaUnlock"
            sub = "Choose a plan or enter your license key."

        msg_label = QLabel(msg)
        msg_label.setFont(QFont("Arial", 13))
        msg_label.setAlignment(Qt.AlignCenter)
        msg_label.setStyleSheet("color: #ff6b6b;" if "expired" in msg.lower() else "color: #aaa;")
        layout.addWidget(msg_label)

        sub_label = QLabel(sub)
        sub_label.setFont(QFont("Arial", 11))
        sub_label.setAlignment(Qt.AlignCenter)
        sub_label.setStyleSheet("color: #666;")
        layout.addWidget(sub_label)

        layout.addSpacing(10)

        # Hardware ID
        hw_label = QLabel("Your Hardware ID (send to developer to get license):")
        hw_label.setStyleSheet("color: #888; font-size: 11px;")
        layout.addWidget(hw_label)

        try:
            sys.path.insert(0, NOVA_HOME)
            from nova_unlock.licensing.hardware_id import get_short_hw_id
            hw_id = get_short_hw_id()
        except:
            hw_id = "HW-ID-UNAVAILABLE"

        hw_edit = QLineEdit(hw_id)
        hw_edit.setReadOnly(True)
        hw_edit.setStyleSheet("color: #00d4ff; background: #111; font-family: monospace;")
        layout.addWidget(hw_edit)

        layout.addSpacing(10)

        # Plans
        plan_label = QLabel("Choose a Plan:")
        plan_label.setFont(QFont("Arial", 12, QFont.Bold))
        layout.addWidget(plan_label)

        for plan in self.PLANS:
            btn = QPushButton(f"{plan[\'name\']}  —  {plan[\'price\']}")
            btn.clicked.connect(lambda _, p=plan: self._open_purchase(p))
            layout.addWidget(btn)

        layout.addSpacing(10)

        # Divider
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setStyleSheet("color: #333;")
        layout.addWidget(line)

        # License file import
        import_label = QLabel("Already have a license file?")
        import_label.setStyleSheet("color: #888; font-size: 11px;")
        layout.addWidget(import_label)

        import_btn = QPushButton("Import License File (.json)")
        import_btn.clicked.connect(self._import_license)
        layout.addWidget(import_btn)

        # Later button
        later_btn = QPushButton("Continue Trial" if not self.status.get("trial_expired") else "Exit")
        later_btn.setStyleSheet("""
            QPushButton {
                background: transparent; color: #555;
                border: 1px solid #333; border-radius: 8px; padding: 8px;
            }
            QPushButton:hover { color: #888; }
        """)
        later_btn.clicked.connect(self._later)
        layout.addWidget(later_btn)

    def _open_purchase(self, plan):
        import webbrowser
        url = f"https://novaunlock.app/buy?plan={plan[\'type\']}"
        webbrowser.open(url)
        QMessageBox.information(self, "Purchase",
            f"Opening browser for {plan[\'name\']} plan ({plan[\'price\']})\\n\\n"
            "After payment you will receive a license file.\\n"
            "Click \'Import License File\' to activate.")

    def _import_license(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Select License File", "", "License Files (*.json)"
        )
        if not path:
            return

        try:
            from nova_unlock.licensing.activation_manager import ActivationManager
            mgr = ActivationManager()
            result = mgr.activate_from_file(path)

            if result.get("success"):
                QMessageBox.information(self, "Activated!",
                    "NovaUnlock activated successfully!\\n\\nEnjoy face login!")
                self.accept()
            else:
                QMessageBox.critical(self, "Activation Failed",
                    f"Error: {result.get(\'error\', \'Unknown error\')}\\n\\n"
                    f"Your HW ID: {result.get(\'your_hw_id\', \'N/A\')}")
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))

    def _later(self):
        if self.status.get("trial_expired"):
            self.reject()
        else:
            self.accept()


def check_and_show_license_dialog():
    """Call this at app startup — shows dialog if needed"""
    try:
        from nova_unlock.licensing.license_validator import LicenseValidator
        v = LicenseValidator()
        status = v.validate()

        if status.get("valid") and not status.get("grace"):
            return True  # All good

        # Show dialog
        from PyQt5.QtWidgets import QApplication
        app = QApplication.instance() or QApplication(sys.argv)
        dialog = LicenseDialog(status)
        result = dialog.exec_()

        if status.get("trial_expired") and result != QDialog.Accepted:
            return False  # Block app launch

        return True

    except Exception as e:
        print(f"License check error: {e}")
        return True  # Fail open during dev
''')

# ============================================================
# UPDATED INSTALL.BAT
# ============================================================

write('build/release/windows-v1.32/install.bat', r"""@echo off
echo ========================================
echo   NovaUnlock V1.32 - Windows Installer
echo ========================================
echo.

net session >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: Run as Administrator!
    pause & exit /b 1
)

echo [1/10] Checking Python 3.11...
python --version 2>nul | findstr "3.11" >nul
if %errorlevel% neq 0 (
    echo Downloading Python 3.11...
    curl -L "https://www.python.org/ftp/python/3.11.9/python-3.11.9-amd64.exe" -o "%TEMP%\py311.exe" --progress-bar
    "%TEMP%\py311.exe" /quiet InstallAllUsers=1 PrependPath=1 Include_test=0
    echo Python installed — restart installer!
    pause & exit /b 0
)
echo Python 3.11 OK.

echo [2/10] Visual C++ Runtime...
curl -L "https://aka.ms/vs/17/release/vc_redist.x64.exe" -o "%TEMP%\vc.exe" --silent
"%TEMP%\vc.exe" /install /quiet /norestart 2>nul
echo Done.

echo [3/10] Python packages...
pip install numpy opencv-python PyQt5 PyYAML pywin32 pywin32-ctypes --quiet
if %errorlevel% neq 0 goto ERROR

echo [4/10] Installing dlib (pre-built)...
pip install "%~dp0wheels\dlib_bin-20.0.1-cp311-cp311-win_amd64.whl" --quiet
if %errorlevel% neq 0 goto ERROR

echo [5/10] Installing face_recognition...
pip install face_recognition==1.3.0 face_recognition_models==0.3.0 --quiet
if %errorlevel% neq 0 goto ERROR

echo [6/10] Copying app files...
mkdir "C:\ProgramData\NovaUnlock" 2>nul
mkdir "C:\ProgramData\NovaUnlock\credential_provider" 2>nul
mkdir "C:\ProgramData\NovaUnlock\data\faces" 2>nul
mkdir "C:\ProgramData\NovaUnlock\logs" 2>nul
mkdir "C:\ProgramData\NovaUnlock\license" 2>nul
xcopy /E /I /Y "%~dp0nova_unlock" "C:\ProgramData\NovaUnlock\nova_unlock\" >nul
xcopy /E /I /Y "%~dp0scripts"     "C:\ProgramData\NovaUnlock\scripts\" >nul
copy  /y "%~dp0credential_provider\*" "C:\ProgramData\NovaUnlock\credential_provider\" >nul
echo Files copied.

echo [7/10] Registering Credential Provider...
copy /y "%~dp0credential_provider\NovaUnlockProvider.dll" "%WINDIR%\System32\" >nul
copy /y "%~dp0credential_provider\libgcc_s_seh-1.dll"    "%WINDIR%\System32\" >nul
copy /y "%~dp0credential_provider\libstdc++-6.dll"        "%WINDIR%\System32\" >nul
copy /y "%~dp0credential_provider\libwinpthread-1.dll"    "%WINDIR%\System32\" >nul
regedit /s "%~dp0credential_provider\register.reg"
if %errorlevel% neq 0 (
    echo ERROR: Registry failed! Must be Admin!
    goto ERROR
)
echo Credential Provider registered OK!

echo [8/10] Disabling conflicting credential providers...
reg add "HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\Authentication\Credential Providers\{60b78e88-ead8-445c-9cfd-0b87f74ea6cd}" /v "Disabled" /t REG_DWORD /d 1 /f >nul 2>&1
echo Done.

echo [9/10] Installing Windows Service...
python "C:\ProgramData\NovaUnlock\scripts\nova_service.py" install >nul 2>&1
python "C:\ProgramData\NovaUnlock\scripts\nova_service.py" start  >nul 2>&1
echo Service installed and started.

echo [10/10] Verifying...
python -c "import dlib; print('dlib OK')"
python -c "import face_recognition; print('face_recognition OK')"
python -c "import cv2; print('OpenCV OK')"
python -c "import win32api; print('pywin32 OK')"

