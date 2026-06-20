"""
NovaUnlock - Windows System Detection Module
Automatically detects Windows paths, user, and OS version.
"""

import os
import platform
from pathlib import Path
import configparser

def find_nova_root() -> Path:
    if os.environ.get("NOVA_ROOT"):
        return Path(os.environ["NOVA_ROOT"])
    
    user = get_real_user()
    appdata = os.environ.get("APPDATA", f"C:\\Users\\{user}\\AppData\\Roaming")
    
    config_paths = [
        Path(appdata) / "NovaUnlock",
        Path("C:\\Program Files\\NovaUnlock"),
        Path(__file__).parent.parent.parent,
    ]
    for p in config_paths:
        if p.exists() and (p / "config" / "nova.conf").exists():
            return p
    return Path(__file__).parent.parent.parent

def get_real_user() -> str:
    for env_var in ["USERNAME", "USERDOMAIN"]:
        user = os.environ.get(env_var, "").strip()
        if user:
            return user
    try:
        return os.getlogin()
    except Exception:
        return "user"

def get_desktop_env() -> str:
    return "windows"

def get_display_manager() -> str:
    return "winlogon"

def get_distro() -> dict:
    """
    Detect Windows version.
    Returns: {"id": "windows", "family": "nt", "version": "10/11"}
    """
    release, version, csd, ptype = platform.win32_ver()
    return {
        "id": "windows",
        "family": "nt",
        "pkg": "winget",
        "version": release,
        "build": version
    }

def load_config() -> dict:
    root = find_nova_root()
    conf_file = root / "config" / "nova.conf"
    config = {}
    if conf_file.exists():
        parser = configparser.ConfigParser()
        parser.read(str(conf_file))
        for section in parser.sections():
            for key, value in parser.items(section):
                config[key] = value
    return config

def setup_environment():
    user = get_real_user()
    root = find_nova_root()
    
    os.environ.setdefault("NOVA_ROOT", str(root))
    os.environ.setdefault("REAL_USER", user)
    
    return {
        "user": user,
        "nova_root": root,
        "desktop": get_desktop_env(),
        "display_manager": get_display_manager(),
        "distro": get_distro(),
    }
