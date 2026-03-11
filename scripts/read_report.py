import json
d = json.load(open(r'f:\Project\CPE-Forge\output\cleaning_report.json', encoding='utf-8'))
print("=== 总体统计 ===")
for k in ['总文件数','有效文件','被过滤文件','加密文件','损坏文件','Sheet总数','去重后Sheet数','重复组数','去重率']:
    print(f"  {k}: {d[k]}")
print("\n=== 员工明细 ===")
total = 0
for e, c in d['员工明细'].items():
    print(f"  {e}: {c}")
    total += c
print(f"  合计: {total}")
print(f"\n=== 加密文件 ({len(d['加密文件清单'])}个) ===")
for f in d['加密文件清单']:
    print(f"  {f.split(chr(92))[-1]}")
