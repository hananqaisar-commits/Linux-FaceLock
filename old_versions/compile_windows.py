import os
import py_compile
import shutil

src_dir = 'nova_unlock'
dst_dir = 'build/win_release/nova_unlock'

for root, _, files in os.walk(src_dir):
    for f in files:
        if f.endswith('.py'):
            src_file = os.path.join(root, f)
            rel_path = os.path.relpath(src_file, src_dir)
            dst_file = os.path.join(dst_dir, rel_path + 'c')
            
            os.makedirs(os.path.dirname(dst_file), exist_ok=True)
            py_compile.compile(src_file, cfile=dst_file)
            print(f"Compiled {src_file} -> {dst_file}")
