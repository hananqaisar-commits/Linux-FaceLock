import os, json, time, platform
from pathlib import Path
from .crypto_engine import encrypt_data, decrypt_data


def _license_dir() -> Path:
    """Cross-platform license storage directory."""
    system = platform.system().lower()

    if system == "windows":
        base = Path(os.environ.get("APPDATA",
                    os.path.expanduser("~\\AppData\\Roaming")))
        return base / "NovaUnlock" / "license"
    elif system == "darwin":
        return Path.home() / "Library" / "Application Support" / "NovaUnlock" / "license"
    else:
        # Linux + BSD + others
        base = Path(os.environ.get("XDG_CONFIG_HOME",
                    str(Path.home() / ".config")))
        return base / "novaunlock" / "license"


class SecureStorage:
    def __init__(self):
        self.dir = _license_dir()
        self.dir.mkdir(parents=True, exist_ok=True)
        self.license_file = self.dir / "nova.lic"
        self.trial_file   = self.dir / "trial.dat"
        self.time_file    = self.dir / "lastrun.dat"

    def save_license(self, bundle):
        with open(self.license_file, 'w') as f:
            f.write(encrypt_data(json.dumps(bundle)))

    def load_license(self):
        if not self.license_file.exists():
            return None
        try:
            with open(self.license_file) as f:
                return json.loads(decrypt_data(f.read()))
        except Exception:
            return None

    def delete_license(self):
        if self.license_file.exists():
            self.license_file.unlink()

    def start_trial(self):
        data = {'install_date': time.time(), 'trial_started': True}
        with open(self.trial_file, 'w') as f:
            f.write(encrypt_data(json.dumps(data)))

    def get_trial_info(self):
        if not self.trial_file.exists():
            return None
        try:
            with open(self.trial_file) as f:
                return json.loads(decrypt_data(f.read()))
        except Exception:
            return None

    def update_last_run_time(self, t=None):
        with open(self.time_file, 'w') as f:
            f.write(encrypt_data(str(t or time.time())))

    def get_last_run_time(self):
        if not self.time_file.exists():
            return None
        try:
            with open(self.time_file) as f:
                return float(decrypt_data(f.read()))
        except Exception:
            return None
