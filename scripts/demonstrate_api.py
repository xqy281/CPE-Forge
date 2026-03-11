import sys
from pathlib import Path
sys.path.insert(0, str(Path(r'f:\Project\CPE-Forge')))

from pipeline.api import CPEPipelineAPI

def main():
    api = CPEPipelineAPI(
        attachments_dir=Path(r'f:\Project\CPE-Forge\attachments'),
        output_dir=Path(r'f:\Project\CPE-Forge\output')
    )

    print("=== 1. 获取所有人员列表 ===")
    employees = api.get_employee_list()
    for emp in employees[:3]:
        print(f"  - {emp['name']} ({emp['email']})")
    print(f"  ... 共 {len(employees)} 人\n")

    if not employees:
        return

    test_email = 'xiaoqianyun@jointelli.com'
    print(f"=== 2. 获取 '{test_email}' 可选的时间范围 ===")
    print("  [首次查询可能较慢，自动在后台触发清洗并构建该人的数据缓存]")
    ranges = api.get_employee_report_ranges(test_email)
    for r in ranges[:5]:
        print(f"  - ID: {r['id']}, 时间: {r['start']} ~ {r['end']}")
    print(f"  ... 共 {len(ranges)} 个周期\n")

    if not ranges:
        print("无可用范围")
        return

    print("=== 3. 提取选定片段并组装 Markdown 上下文 ===")
    # 模拟大模型端选择了最后 2 个周期的周报
    target_ids = [r['id'] for r in ranges[-2:]]
    print(f"  选定的时间端: {target_ids}")
    out_file = api.generate_cleaned_markdown(test_email, target_ids)
    
    print(f"  成功！缓存已重组，请供 AIGC 读取文件: {out_file}\n")
    print("=== 预览其中 200 个字符 ===")
    with open(out_file, 'r', encoding='utf-8') as f:
        print(f.read()[:200] + "...")

if __name__ == '__main__':
    # 强制控制台 utf-8 输出
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    main()
