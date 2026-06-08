"""
NovaUnlock - System Detection Module
Automatically detects user, display, DE, DM
"""

import os
import subprocess
from pathlib import Path
import configparser


def find_nova_root() -> Path:
    if os.environ.get("NOVA_ROOT"):
        return Path(os.environ["NOVA_ROOT"])
    user = get_real_user()
    config_paths = [
        Path(f"/home/{user}/.local/share/nova-unlock"),
        Path("/opt/nova-unlock"),
        Path("/usr/local/share/nova-unlock"),
        Path(__file__).parent.parent.parent,
    ]
    for p in config_paths:
        if p.exists() and (p / "config" / "nova.conf").exists():
            return p
    return Path(__file__).parent.parent.parent


def get_real_user() -> str:
    for env_var in ["SUDO_USER", "USER", "LOGNAME"]:
        user = os.environ.get(env_var, "").strip()
        if user and user != "root":
            return user
    try:
        result = subprocess.run(
            ["loginctl", "list-sessions", "--no-legend"],
            capture_output=True, text=True, timeout=3
        )
        for line in result.stdout.strip().split('\n'):
            parts = line.split()
            if len(parts) >= 3 and parts[2] != "root":
                return parts[2]
    except Exception:
        pass
    import pwd
    try:
        return pwd.getpwuid(os.getuid()).pw_name
    except Exception:
        return "user"


def get_display() -> str:
    display = os.environ.get("DISPLAY", "").strip()
    if display:
        return display
    user = get_real_user()
    try:
        result = subprocess.run(
            ["w", "-hs", user], capture_output=True, text=True, timeout=3
        )
        for line in result.stdout.split('\n'):
            parts = line.split()
            for part in parts:
                if part.startswith(":"):
                    return part
    except Exception:
        pass
    return ":0"


def get_xauthority(user: str = None) -> str:
    xauth = os.environ.get("XAUTHORITY", "").strip()
    if xauth and Path(xauth).exists():
        return xauth
    if user is None:
        user = get_real_user()
    uid = ""
    try:
        import pwd
        uid = str(pwd.getpwnam(user).pw_uid)
    except Exception:
        pass
    candidates = [
        f"/home/{user}/.Xauthority",
        f"/var/run/lightdm/{user}/xauthority",
        f"/run/user/{uid}/gdm/Xauthority" if uid else "",
        "/tmp/.Xauthority",
    ]
    for path in candidates:
        if path and Path(path).exists():
            return path
    return f"/home/{user}/.Xauthority"


def get_desktop_env() -> str:
    checks = [
        os.environ.get("XDG_CURRENT_DESKTOP", ""),
        os.environ.get("DESKTOP_SESSION", ""),
        os.environ.get("GDMSESSION", ""),
        os.environ.get("XDG_SESSION_DESKTOP", ""),
    ]
    combined = " ".join(checks).upper()
    if "GNOME" in combined or "UNITY" in combined:
        return "gnome"
    elif "KDE" in combined or "PLASMA" in combined:
        return "kde"
    elif "XFCE" in combined:
        return "xfce"
    elif "MATE" in combined:
        return "mate"
    elif "CINNAMON" in combined:
        return "cinnamon"
    elif "LXDE" in combined:
        return "lxde"
    elif "LXQT" in combined:
        return "lxqt"
    elif "I3" in combined:
        return "i3"
    elif "SWAY" in combined:
        return "sway"
    else:
        return "unknown"


def get_display_manager() -> str:
    dm_checks = [
        ("lightdm", "lightdm"),
        ("gdm3", "gdm"),
        ("gdm", "gdm"),
        ("sddm", "sddm"),
        ("slim", "slim"),
        ("lxdm", "lxdm"),
    ]
    for service, dm_name in dm_checks:
        try:
            result = subprocess.run(
                ["systemctl", "is-active", service],
                capture_output=True, text=True, timeout=3
            )
            if result.stdout.strip() == "active":
                return dm_name
        except Exception:
            pass
    try:
        result = subprocess.run(
            ["ps", "-aux"], capture_output=True, text=True, timeout=3
        )
        for proc, dm_name in dm_checks:
            if f"/{proc}" in result.stdout or f" {proc}" in result.stdout:
                return dm_name
    except Exception:
        pass
    ddm_file = Path("/etc/X11/default-display-manager")
    if ddm_file.exists():
        content = ddm_file.read_text().strip()
        for proc, dm_name in dm_checks:
            if proc in content:
                return dm_name
    return "unknown"


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




def get_distro() -> dict:
    """
    Detect Linux distribution.
    Returns: {"id": "ubuntu", "family": "debian", "pkg": "apt"}
    """
    info = {"id": "unknown", "family": "unknown", "pkg": "unknown", "version": ""}

    # Method 1: /etc/os-release (most reliable)
    try:
        with open("/etc/os-release") as f:
            for line in f:
                line = line.strip()
                if line.startswith("ID="):
                    info["id"] = line.split("=", 1)[1].strip('"').lower()
                elif line.startswith("ID_LIKE="):
                    info["family"] = line.split("=", 1)[1].strip('"').lower()
                elif line.startswith("VERSION_ID="):
                    info["version"] = line.split("=", 1)[1].strip('"')
    except Exception:
        pass

    # Normalize family
    distro_id = info["id"]
    family = info["family"]

    # DEB based
    if distro_id in ("ubuntu", "debian", "kali", "linuxmint", "pop",
                      "elementary", "zorin", "mx", "lmde", "parrot"):
        info["family"] = "debian"
        info["pkg"] = "apt"
    elif "debian" in family or "ubuntu" in family:
        info["family"] = "debian"
        info["pkg"] = "apt"

    # RPM based
    elif distro_id in ("fedora", "rhel", "centos", "rocky", "alma",
                        "oracle", "scientific"):
        info["family"] = "redhat"
        info["pkg"] = "dnf"
    elif "rhel" in family or "fedora" in family:
        info["family"] = "redhat"
        info["pkg"] = "dnf"

    # openSUSE
    elif distro_id in ("opensuse-leap", "opensuse-tumbleweed", "sles"):
        info["family"] = "suse"
        info["pkg"] = "zypper"
    elif "suse" in family:
        info["family"] = "suse"
        info["pkg"] = "zypper"

    # Arch based
    elif distro_id in ("arch", "manjaro", "endeavouros", "garuda",
                        "artix", "arcolinux"):
        info["family"] = "arch"
        info["pkg"] = "pacman"
    elif "arch" in family:
        info["family"] = "arch"
        info["pkg"] = "pacman"

    # Void
    elif distro_id == "void":
        info["family"] = "void"
        info["pkg"] = "xbps"

    # Alpine
    elif distro_id == "alpine":
        info["family"] = "alpine"
        info["pkg"] = "apk"

    # Gentoo
    elif distro_id == "gentoo":
        info["family"] = "gentoo"
        info["pkg"] = "emerge"

    return info


def get_packages_for_distro(distro: dict) -> tuple:
    """
    Returns (install_command, package_list) for given distro.
    """
    pkg = distro["pkg"]

    # Common packages (distro-specific names)
    packages = {
        "apt": {
            "cmd": ["apt-get", "install", "-y"],
            "pre": ["apt-get", "update", "-qq"],
            "pkgs": [
                "libpam-script",
                "xdotool",
                "python3-xlib",
                "alsa-utils",
                "pulseaudio-utils",
                "x11-utils",
                "python3-venv",
                "python3-pip",
                "cmake",
                "build-essential",
                "python3-dev",
            ]
        },
        "dnf": {
            "cmd": ["dnf", "install", "-y"],
            "pre": None,
            "pkgs": [
                "pam",
                "xdotool",
                "python3-xlib",
                "alsa-utils",
                "pulseaudio-utils",
                "xdpyinfo",
                "python3-pip",
                "python3-devel",
                "cmake",
                "gcc-c++",
                "make",
            ]
        },
        "pacman": {
            "cmd": ["pacman", "-S", "--noconfirm"],
            "pre": ["pacman", "-Sy"],
            "pkgs": [
                "pam",
                "xdotool",
                "python-xlib",
                "alsa-utils",
                "pulseaudio",
                "xorg-xdpyinfo",
                "python-pip",
                "cmake",
                "base-devel",
            ]
        },
        "zypper": {
            "cmd": ["zypper", "install", "-y"],
            "pre": ["zypper", "refresh"],
            "pkgs": [
                "pam",
                "xdotool",
                "python3-xlib",
                "alsa-utils",
                "pulseaudio-utils",
                "xdpyinfo",
                "python3-pip",
                "python3-devel",
                "cmake",
                "gcc-c++",
            ]
        },
    }

    if pkg in packages:
        return packages[pkg]
    else:
        # Fallback: try apt
        return packages["apt"]


def setup_environment():
    user = get_real_user()
    display = get_display()
    xauth = get_xauthority(user)
    root = find_nova_root()
    os.environ.setdefault("DISPLAY", display)
    os.environ.setdefault("XAUTHORITY", xauth)
    os.environ.setdefault("NOVA_ROOT", str(root))
    os.environ.setdefault("REAL_USER", user)
    os.environ.setdefault("HOME", f"/home/{user}")

    # ── Audio environment for lock screen / greeter ──
    try:
        import pwd
        uid = str(pwd.getpwnam(user).pw_uid)
        xdg = f"/run/user/{uid}"
        os.environ.setdefault("XDG_RUNTIME_DIR", xdg)
        os.environ.setdefault("PULSE_SERVER",
                              f"unix:{xdg}/pulse/native")
    except Exception:
        pass

    return {
        "user": user,
        "display": display,
        "xauthority": xauth,
        "nova_root": root,
        "desktop": get_desktop_env(),
        "display_manager": get_display_manager(),
        "distro": get_distro(),
    }
