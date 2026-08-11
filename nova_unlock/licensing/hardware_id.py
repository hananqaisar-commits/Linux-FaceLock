import subprocess, hashlib, uuid, platform, os
from pathlib import Path


def _linux_fingerprint():
    """Linux hardware fingerprint from stable identifiers."""
    parts = []

    # 1. Machine ID (most stable — set by systemd)
    try:
        mid = Path("/etc/machine-id").read_text().strip()
        parts.append(mid)
    except Exception:
        try:
            mid = Path("/var/lib/dbus/machine-id").read_text().strip()
            parts.append(mid)
        except Exception:
            parts.append("NA_MID")

    # 2. Product UUID (BIOS)
    try:
        uid = Path("/sys/class/dmi/id/product_uuid").read_text().strip()
        parts.append(uid)
    except Exception:
        parts.append("NA_UUID")

    # 3. Product serial (BIOS)
    try:
        ser = Path("/sys/class/dmi/id/product_serial").read_text().strip()
        parts.append(ser)
    except Exception:
        parts.append("NA_SER")

    # 4. First MAC address (network hardware)
    try:
        for iface in sorted(os.listdir("/sys/class/net")):
            if iface == "lo":
                continue
            mac = Path(f"/sys/class/net/{iface}/address").read_text().strip()
            if mac and mac != "00:00:00:00:00:00":
                parts.append(mac)
                break
        else:
            parts.append("NA_MAC")
    except Exception:
        parts.append("NA_MAC")

    # 5. CPU info (model)
    try:
        with open("/proc/cpuinfo") as f:
            for line in f:
                if line.startswith("model name"):
                    parts.append(line.split(":", 1)[1].strip())
                    break
    except Exception:
        parts.append("NA_CPU")

    return parts


def _windows_fingerprint():
    """Windows hardware fingerprint from wmic + registry."""
    parts = []

    for cmd in [
        ["wmic", "cpu", "get", "ProcessorId"],
        ["wmic", "diskdrive", "get", "SerialNumber"],
        ["wmic", "baseboard", "get", "SerialNumber"],
    ]:
        try:
            r = subprocess.run(
                cmd, capture_output=True, text=True, timeout=5)
            lines = [l.strip() for l in r.stdout.split('\n')
                     if l.strip() and l.strip() != cmd[-1]]
            parts.append(lines[0] if lines else 'NA')
        except Exception:
            parts.append('NA')

    try:
        import winreg
        key = winreg.OpenKey(
            winreg.HKEY_LOCAL_MACHINE,
            r'SOFTWARE\Microsoft\Cryptography')
        guid, _ = winreg.QueryValueEx(key, 'MachineGuid')
        parts.append(guid)
    except Exception:
        parts.append(str(uuid.getnode()))

    return parts


def _macos_fingerprint():
    """macOS hardware fingerprint."""
    parts = []
    try:
        r = subprocess.run(
            ["ioreg", "-rd1", "-c", "IOPlatformExpertDevice"],
            capture_output=True, text=True, timeout=5)
        for line in r.stdout.split("\n"):
            if "IOPlatformUUID" in line or "IOPlatformSerialNumber" in line:
                parts.append(line.split("=")[-1].strip().strip('"'))
    except Exception:
        parts.append("NA")
    return parts or [str(uuid.getnode())]


def get_hardware_fingerprint():
    """
    Cross-platform hardware fingerprint.
    Returns 32-char hex string.
    """
    system = platform.system().lower()

    if system == "linux":
        parts = _linux_fingerprint()
    elif system == "windows":
        parts = _windows_fingerprint()
    elif system == "darwin":
        parts = _macos_fingerprint()
    else:
        parts = [str(uuid.getnode()), platform.node()]

    # Ensure non-empty fallback
    if not parts or all(p.startswith("NA") for p in parts):
        parts.append(str(uuid.getnode()))
        parts.append(platform.node())

    combined = '|'.join(parts)
    fp = hashlib.sha256(combined.encode()).hexdigest()[:32].upper()
    return fp


def get_short_hw_id():
    """Human-readable short hardware ID (e.g. ABCD1234-5678-9ABC)."""
    f = get_hardware_fingerprint()
    return f[:8] + '-' + f[8:12] + '-' + f[12:16]
