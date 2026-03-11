import os
from pathlib import Path
directory = Path(r'f:\Project\CPE-Forge\attachments\xiaoqianyun@jointelli.com')
print("Exists:", directory.exists())
for root, _, files in os.walk(directory):
    print("Files found:", len(files))
    for f in files[:3]:
        print(" ", f)
    break
