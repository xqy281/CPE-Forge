import json
import pytest
from datetime import date, datetime
from pathlib import Path
from pipeline.models import SheetRecord, TaskRow, PlanRow, FileResult, FileStatus
from pipeline.api import CPEPipelineAPI

def test_sheet_record_serialization():
    # Setup test data
    record = SheetRecord(
        employee_name="萧倩云",
        employee_email="xiaoqianyun@jointelli.com",
        source_file=Path("attachments/xiaoqianyun@jointelli.com/test.xlsx"),
        sheet_name="Sheet1",
        date_range=(date(2025, 1, 6), date(2025, 1, 11)),
        tasks=[
            TaskRow(seq=1, description="任务1", progress=1.0, analysis="分析1")
        ],
        plans=[
            PlanRow(seq=1, content="计划1", planned_time="一周", description="描述1")
        ],
        raw_text="测试纯文本",
        char_count=10,
        file_modified_time=datetime(2025, 1, 12, 10, 0, 0)
    )

    # 序列化为 dict
    d = record.to_dict()
    assert d["employee_name"] == "萧倩云"
    assert d["source_file"] == "attachments\\xiaoqianyun@jointelli.com\\test.xlsx" or d["source_file"] == "attachments/xiaoqianyun@jointelli.com/test.xlsx"
    assert d["date_range"] == ["2025-01-06", "2025-01-11"]
    assert d["tasks"][0]["progress"] == 1.0
    assert d["file_modified_time"] == "2025-01-12T10:00:00"

    # Json dump 测试，确保支持 JSON
    json_str = json.dumps(d, ensure_ascii=False)
    assert "萧倩云" in json_str

    # 反序列化
    restored = SheetRecord.from_dict(d)
    assert restored.employee_name == record.employee_name
    assert restored.source_file == record.source_file
    assert restored.date_range == record.date_range
    assert restored.file_modified_time == record.file_modified_time
    assert len(restored.tasks) == 1
    assert restored.tasks[0].description == "任务1"

def test_api_get_employee_list(tmp_path):
    attachments_dir = tmp_path / "attachments"
    attachments_dir.mkdir()
    (attachments_dir / "xiaoqianyun@jointelli.com").mkdir()
    (attachments_dir / "zhangzhengqiang@jointelli.com").mkdir()
    output_dir = tmp_path / "output"
    output_dir.mkdir()
    
    api = CPEPipelineAPI(attachments_dir, output_dir)
    employees = api.get_employee_list()
    assert len(employees) == 2
    assert {"email": "xiaoqianyun@jointelli.com", "name": "xiaoqianyun"} in employees

def test_api_get_employee_report_ranges(tmp_path, monkeypatch):
    """测试第一次读取时触发全量清洗并缓存"""
    attachments_dir = tmp_path / "attachments"
    attachments_dir.mkdir()
    (attachments_dir / "xiaoqianyun@jointelli.com").mkdir()
    output_dir = tmp_path / "output"
    output_dir.mkdir()
    
    api = CPEPipelineAPI(attachments_dir, output_dir)
    
    # Mock flatten_and_deduplicate
    call_count = 0
    def mock_flatten_and_deduplicate(files):
        nonlocal call_count
        call_count += 1
        # 返回 (dict[email → records], dup_groups) 格式
        return {
            "xiaoqianyun@jointelli.com": [
                SheetRecord(
                    employee_name="萧倩云",
                    employee_email="xiaoqianyun@jointelli.com",
                    source_file=Path("dummy.xlsx"),
                    sheet_name="Test",
                    date_range=(date(2025, 1, 1), date(2025, 1, 7))
                )
            ]
        }, []
    
    monkeypatch.setattr("pipeline.api.flatten_and_deduplicate", mock_flatten_and_deduplicate)
    # scan_directory mock 需要返回 FileResult 对象（含 .sheets 属性）
    mock_file_result = FileResult(
        filepath=Path("dummy.xlsx"),
        status=FileStatus.VALID,
        sheets=[],  # flatten_and_deduplicate 已 mock，此处无需真实 sheets
    )
    monkeypatch.setattr("pipeline.api.scan_directory", lambda d, specific_email=None: ([mock_file_result], [], []))

    # 第一次调用，期望 call_count == 1，且写入缓存
    ranges = api.get_employee_report_ranges("xiaoqianyun@jointelli.com")
    assert call_count == 1
    assert len(ranges) == 1
    assert ranges[0]["start"] == "2025-01-01"
    assert ranges[0]["end"] == "2025-01-07"
    assert ranges[0]["id"] == "2025-01-01_2025-01-07"
    
    # 缓存文件应存在
    cache_file = output_dir / "cache" / "xiaoqianyun@jointelli.com" / "_meta.json"
    assert cache_file.exists()
    
    # 第二次调用，期望从缓存读取，call_count 保持为 1
    ranges2 = api.get_employee_report_ranges("xiaoqianyun@jointelli.com")
    assert call_count == 1
    assert ranges == ranges2

def test_api_generate_cleaned_markdown(tmp_path):
    attachments_dir = tmp_path / "attachments"
    attachments_dir.mkdir()
    output_dir = tmp_path / "output"
    output_dir.mkdir()
    
    api = CPEPipelineAPI(attachments_dir, output_dir)
    
    # 预设缓存
    cache_dir = output_dir / "cache" / "test@jointelli.com"
    cache_dir.mkdir(parents=True)
    
    record = SheetRecord(
        employee_name="Test",
        employee_email="test@jointelli.com",
        source_file=Path("dummy.xlsx"),
        sheet_name="Test",
        date_range=(date(2025, 1, 1), date(2025, 1, 7)),
        tasks=[TaskRow(1, "Test Task")]
    )
    
    with open(cache_dir / "_meta.json", "w", encoding="utf-8") as f:
        json.dump([record.to_dict()], f)
        
    # 测试生成 markdown
    out_file = api.generate_cleaned_markdown("test@jointelli.com", ["2025-01-01_2025-01-07"])
    assert out_file.exists()
    assert out_file.name == "2025-01-01_2025-01-07.md"
    content = out_file.read_text(encoding="utf-8")
    assert "Test Task" in content
    assert "Test" in content
