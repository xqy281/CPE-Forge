import sys
from pathlib import Path
sys.path.insert(0, r'f:\Project\CPE-Forge')
from pipeline.auto_discovery import scan_directory
from pipeline.noise_reduction import flatten_and_deduplicate, reconstruct_timeline

p = Path(r'f:\Project\CPE-Forge\attachments\xiaoqianyun@jointelli.com')
v, r, e = scan_directory(p)
print(f"Valid: {len(v)}, Rejected: {len(r)}, Error: {len(e)}")

if v:
    dedup, _ = flatten_and_deduplicate(v)
    print(f"Deduped: {len(dedup)}")
    timeline = reconstruct_timeline(dedup)
    print(f"Timeline: {len(timeline)}")
