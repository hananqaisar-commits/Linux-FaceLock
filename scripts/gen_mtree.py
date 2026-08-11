#!/usr/bin/env python3
"""Generate a pacman-compatible .MTREE for a manually-built Arch package.

Walks ROOT and emits an mtree specification (sha256 + mode + size + mtime)
for every installed file/dir, EXCLUDING the package metadata files
(.PKGINFO, .MTREE, .INSTALL, .BUILDINFO) which are not tracked as installed
files by pacman.
"""
import os
import sys
import hashlib

SPECIAL = {".PKGINFO", ".MTREE", ".INSTALL", ".BUILDINFO"}


def main():
    root = sys.argv[1]
    out = sys.argv[2]
    lines = ["#mtree"]
    for dirpath, dirnames, filenames in os.walk(root):
        rel = os.path.relpath(dirpath, root)
        arc = "." if rel == "." else "./" + rel.replace(os.sep, "/")
        st = os.stat(dirpath)
        mode = oct(st.st_mode & 0o777)
        lines.append(f"{arc} type=dir mode={mode} time={st.st_mtime}.0")
        for fn in sorted(filenames):
            if fn in SPECIAL:
                continue
            fp = os.path.join(dirpath, fn)
            if not os.path.isfile(fp):
                continue
            relf = "./" + os.path.relpath(fp, root).replace(os.sep, "/")
            st = os.stat(fp)
            mode = oct(st.st_mode & 0o777)
            size = st.st_size
            h = hashlib.sha256()
            with open(fp, "rb") as f:
                for chunk in iter(lambda: f.read(65536), b""):
                    h.update(chunk)
            lines.append(
                f"{relf} type=file mode={mode} size={size} "
                f"sha256={h.hexdigest()} time={st.st_mtime}.0"
            )
    with open(out, "w") as f:
        f.write("\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
