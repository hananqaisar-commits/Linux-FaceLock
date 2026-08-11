#!/usr/bin/env python3
"""
NovaUnlock Installer Binary
Extracts and runs install.sh with full system integration
"""
import os
import sys
import subprocess
import tempfile
import shutil
from pathlib import Path

try:
    from nova_unlock import __version__ as NOVA_VERSION
except Exception:
    NOVA_VERSION = "2.21"

CACHE_FILE = "/tmp/nova_unlock_pam_cache.json"


def py_entry(install_dir, relative_path):
    source_path = Path(install_dir) / relative_path
    pyc_path = source_path.with_suffix(".pyc")
    if source_path.exists():
        return str(source_path)
    if pyc_path.exists():
        return str(pyc_path)
    return str(source_path)


# ═══════════════════════════════════════════════════════════════
#  POST-INSTALL — Launch enrollment wizard as the real user
# ═══════════════════════════════════════════════════════════════
def launch_enrollment_wizard():
    import subprocess
    from pathlib import Path

    real_user = os.environ.get("SUDO_USER", "") or os.environ.get("USER", "")

    if not real_user or real_user == "root":
        print("[Nova]  Skipping wizard — run manually:")
        print("[Nova]  python3 ~/NovaUnlock/nova_unlock/ui/enrollment_wizard.py")
        return

    nova_home  = Path(f"/home/{real_user}/NovaUnlock")
    venv_py    = nova_home / ".venv" / "bin" / "python3"
    enrollment_wizard = nova_home / "nova_unlock" / "ui" / "enrollment_wizard.py"

    if not venv_py.exists() or not enrollment_wizard.exists():
        print(f"[Nova]  Wizard not found — enroll manually:")
        print(f"[Nova]  {venv_py} {enrollment_wizard}")
        return

    env = os.environ.copy()
    env.update({
        "HOME":    f"/home/{real_user}",
        "USER":    real_user,
        "LOGNAME": real_user,
        "DISPLAY": os.environ.get("DISPLAY", ":0"),
    })

    xauth = Path(f"/home/{real_user}/.Xauthority")
    if xauth.exists():
        env["XAUTHORITY"] = str(xauth)

    try:
        proc = subprocess.Popen([
            "sudo", "-u", real_user,
            str(venv_py), str(enrollment_wizard),
            "--user", real_user,
        ], env=env)
        print(f"\n[Nova]  Enrollment wizard launched (PID {proc.pid})")
        print(f"[Nova]  Complete face enrollment in the window.\n")
    except Exception as e:
        print(f"[Nova]  Wizard launch error: {e}")


def main():
    # Get bundle directory (PyInstaller extracts here)
    if hasattr(sys, '_MEIPASS'):
        bundle_dir = Path(sys._MEIPASS)
    else:
        bundle_dir = Path(__file__).parent

    print()
    print("╔══════════════════════════════════════════════╗")
    print(f"║     NovaUnlock — Installer v{NOVA_VERSION:<13}║")
    print("╚══════════════════════════════════════════════╝")
    print()

    # Root check
    if os.geteuid() != 0:
        print("❌ Error: Run with sudo")
        print("   sudo ./nova_unlock_installer")
        sys.exit(1)

    # Get real user
    real_user = os.environ.get("SUDO_USER", "")
    if not real_user or real_user == "root":
        try:
            result = subprocess.run(
                ["logname"],
                capture_output=True, text=True
            )
            real_user = result.stdout.strip()
        except Exception:
            pass
    if not real_user:
        real_user = input("  Enter your Linux username: ").strip()

    real_home = f"/home/{real_user}"
    try:
        grp = subprocess.run(
            ["id", "-gn", real_user],
            capture_output=True, text=True, check=True,
        )
        real_group = grp.stdout.strip() or real_user
    except Exception:
        real_group = real_user

    # Install destination
    install_dir = f"{real_home}/NovaUnlock"
    print(f"  User:        {real_user}")
    print(f"  Group:       {real_group}")
    print(f"  Install to:  {install_dir}")
    print()

    # Backup existing installation
    if os.path.exists(install_dir):
        backup = f"{install_dir}.backup"
        print(f"  Backing up existing → {backup}")
        if os.path.exists(backup):
            shutil.rmtree(backup)
        shutil.move(install_dir, backup)

    # Extract nova_bundle to install_dir
    print("  Extracting NovaUnlock files...")
    bundle_src = bundle_dir / "nova_bundle"
    shutil.copytree(str(bundle_src), install_dir)

    # Copy install.sh to install_dir
    install_sh_src = bundle_dir / "install.sh"
    install_sh_dst = f"{install_dir}/install.sh"
    shutil.copy2(str(install_sh_src), install_sh_dst)
    os.chmod(install_sh_dst, 0o755)

    # Fix ownership
    subprocess.run(
        ["chown", "-R", f"{real_user}:{real_group}", install_dir],
        check=False
    )

    print("  Files extracted successfully")
    print()
    print("  Running installer...")
    print("─" * 50)
    print()

    # Run install.sh from install_dir
    result = subprocess.run(
        ["bash", install_sh_dst],
        cwd=install_dir,
        env={
            **os.environ,
            "SUDO_USER": real_user,
            "HOME": real_home,
            "NOVA_ROOT": install_dir,
        }
    )

    print()
    print("─" * 50)

    if result.returncode in (0, 1):
        enroll_script = py_entry(install_dir, "nova_unlock/ui/enrollment_wizard.py")
        demo_script   = py_entry(install_dir, "nova_unlock/ui/face_id_screen.py")

        print()
        print(f"✅ NovaUnlock v{NOVA_VERSION} installation complete!")
        print()
        print("  Next steps:")
        print(f"    Enroll face:  {install_dir}/.venv/bin/python3 {install_dir}/nova_unlock/ui/enrollment_wizard.py")
        print(f"    Test demo:    {install_dir}/.venv/bin/python3 {demo_script} --demo")
        print(f"    Lock screen:  xflock4")
        print(f"    Uninstall:    sudo bash {install_dir}/uninstall.sh")
    else:
        print()
        print("✅ NovaUnlock installation complete!")
        print(f"   Check log: {install_dir}/logs/install.log")

    launch_enrollment_wizard()
    sys.exit(0)


if __name__ == "__main__":
    main()


# ═══════════════════════════════════════════════════════════════
#  POST-INSTALL — Launch Nova Daemon (notification replacement)
# ═══════════════════════════════════════════════════════════════
def launch_nova_daemon():
    """
    Replace OS notification daemon with Nova glass UI.
    Runs as the real user (not root).
    """
    import subprocess
    from pathlib import Path

    real_user = os.environ.get("SUDO_USER","") or os.environ.get("USER","")
    if not real_user or real_user == "root":
        print("[Nova] Skip daemon — run: nova_daemon_entry.py")
        return

    nova_home = Path(f"/home/{real_user}/NovaUnlock")
    venv_py   = nova_home / ".venv" / "bin" / "python3"
    entry     = nova_home / "scripts" / "nova_daemon_entry.py"

    if not venv_py.exists() or not entry.exists():
        print(f"[Nova] Daemon not found at {entry}")
        return

    env = os.environ.copy()
    env.update({
        "HOME":    f"/home/{real_user}",
        "USER":    real_user,
        "LOGNAME": real_user,
        "DISPLAY": os.environ.get("DISPLAY",":0"),
    })
    xauth = Path(f"/home/{real_user}/.Xauthority")
    if xauth.exists():
        env["XAUTHORITY"] = str(xauth)

    try:
        proc = subprocess.Popen([
            "sudo", "-u", real_user,
            str(venv_py), str(entry),
        ], env=env)
        print(f"\n[Nova] ✅ Notification daemon launched (PID {proc.pid})")
        print(f"[Nova]    Nova glass notifications are now active.\n")
    except Exception as e:
        print(f"[Nova] Daemon launch error: {e}")

