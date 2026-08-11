#!/usr/bin/env python3
"""Nova Daemon entry point — installed as autostart."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from nova_unlock.daemon.nova_daemon import main
if __name__ == "__main__": main()
