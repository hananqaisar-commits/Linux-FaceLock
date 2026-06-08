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

def main():
    # Get bundle directory (PyInstaller extracts here)
    if hasattr(sys, '_MEIPASS'):
        bundle_dir = Path(sys._MEIPASS)
    else:
        bundle_dir = Path(__file__).parent

    print()
    print("╔══════════════════════════════════════════════╗")
    print("║     NovaUnlock — Installer v4.1              ║")
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

    # Install destination
    install_dir = f"{real_home}/NovaUnlock"
    print(f"  User:        {real_user}")
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
        ["chown", "-R", f"{real_user}:{real_user}", install_dir],
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
        }
    )

    print()
    print("─" * 50)

    if result.returncode == 0:
        print()
        print("✅ NovaUnlock installation complete!")
        print()
        print("  Next steps:")
        print(f"    Enroll face:  cd {install_dir} && source .venv/bin/activate && python3 scripts/enroll.py")
        print(f"    Test demo:    {install_dir}/.venv/bin/python3 nova_unlock/ui/face_unlock_widget.py --demo")
        print(f"    Lock screen:  xflock4")
        print(f"    Uninstall:    sudo bash {install_dir}/uninstall.sh")
    else:
        print()
        print("⚠️  Installer finished with errors")
        print(f"   Check log: {install_dir}/logs/install.log")

    sys.exit(result.returncode)


if __name__ == "__main__":
    main()
