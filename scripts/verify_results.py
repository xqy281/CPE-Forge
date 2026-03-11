"""验证关键去重场景"""
import json
import sys
sys.path.insert(0, r'f:\Project\CPE-Forge')
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

from pathlib import Path
from pipeline.auto_discovery import scan_directory
from pipeline.noise_reduction import flatten_and_deduplicate

# 验证1: _1 后缀重复文件是否被去重
print("=" * 60)
print("验证1: _1 后缀重复文件去重检查")
print("=" * 60)

# 萧倩云有已知的 _1 后缀重复文件
xqy_dir = Path(r'f:\Project\CPE-Forge\attachments\xiaoqianyun@jointelli.com')
dup_pairs = []
for f in sorted(xqy_dir.iterdir()):
    if '_1.xlsx' in f.name:
        original_name = f.name.replace('_1.xlsx', '.xlsx')
        original = xqy_dir / original_name
        if original.exists():
            dup_pairs.append((original.name, f.name, original.stat().st_size, f.stat().st_size))

if dup_pairs:
    print(f"  发现 {len(dup_pairs)} 对 _1 重复文件：")
    for orig, dup, s1, s2 in dup_pairs:
        size_match = "✓ 大小一致" if s1 == s2 else "✗ 大小不同"
        print(f"    {orig} ({s1}B) vs {dup} ({s2}B) → {size_match}")
else:
    print("  未发现 _1 重复文件对")

# 验证2: 清洗后周报数 vs 原始文件数
print()
print("=" * 60)
print("验证2: 清洗压缩比")
print("=" * 60)

report = json.load(open(r'f:\Project\CPE-Forge\output\cleaning_report.json', encoding='utf-8'))
attachments_dir = Path(r'f:\Project\CPE-Forge\attachments')
for emp_dir in sorted(attachments_dir.iterdir()):
    if emp_dir.is_dir():
        file_count = len(list(emp_dir.glob('*.xlsx')))
        clean_count = report['员工明细'].get(emp_dir.name, 0)
        ratio = (1 - clean_count / max(file_count, 1)) * 100 if file_count > 0 else 0
        print(f"  {emp_dir.name}: {file_count}文件 → {clean_count}份周报 (压缩 {ratio:.0f}%)")

# 验证3: 被过滤的非周报文件是否合理
print()
print("=" * 60)
print("验证3: 被过滤的非周报文件 (前10个)")
print("=" * 60)

valid, rejected, errors = scan_directory(attachments_dir)
for r in rejected[:10]:
    print(f"  [REJECTED] {r.filepath.parent.name}/{r.filepath.name} (score={r.match_score:.2f})")
print(f"  ... 共 {len(rejected)} 个被过滤")
