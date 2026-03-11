"""
数据模型定义 — 管线各阶段的数据载体

所有核心数据结构使用 dataclass 定义，确保类型安全和可读性。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from enum import Enum
from pathlib import Path
from typing import Optional


class FileStatus(Enum):
    """文件处理状态枚举"""
    VALID = "valid"                  # 有效周报
    REJECTED = "rejected"            # 非周报文件
    CORRUPT = "corrupt"              # 损坏文件（无法解析）
    ENCRYPTED = "encrypted"          # 加密/TSD 格式文件
    ERROR = "error"                  # 其他错误


class DeduplicateAction(Enum):
    """去重操作类型"""
    KEEP = "keep"                    # 保留（优胜者）
    DISCARD = "discard"              # 丢弃（冗余）


@dataclass
class TaskRow:
    """单行任务记录（本周完成工作）"""
    seq: int                         # 序号
    description: str                 # 任务描述
    progress: Optional[float] = None # 进度 (0.0 ~ 1.0)
    analysis: str = ""               # 难点分析/详细描述/总结/心得

    def to_dict(self) -> dict:
        return {
            "seq": self.seq,
            "description": self.description,
            "progress": self.progress,
            "analysis": self.analysis
        }
        
    @classmethod
    def from_dict(cls, data: dict) -> "TaskRow":
        return cls(**data)


@dataclass
class PlanRow:
    """单行计划记录（下周工作计划）"""
    seq: int                         # 序号
    content: str                     # 内容
    planned_time: str = ""           # 计划时间
    description: str = ""            # 描述

    def to_dict(self) -> dict:
        return {
            "seq": self.seq,
            "content": self.content,
            "planned_time": self.planned_time,
            "description": self.description
        }
        
    @classmethod
    def from_dict(cls, data: dict) -> "PlanRow":
        return cls(**data)


@dataclass
class SheetRecord:
    """
    单个 Sheet 的完整解析结果。
    这是管线中流转的核心数据单元。
    """
    employee_name: str               # 员工姓名（中文）
    employee_email: str              # 员工邮箱（目录名）
    source_file: Path                # 原始文件路径
    sheet_name: str                  # Sheet 名称
    date_range: Optional[tuple[date, date]] = None  # 解析出的日期区间
    tasks: list[TaskRow] = field(default_factory=list)
    plans: list[PlanRow] = field(default_factory=list)
    raw_text: str = ""               # 拼接后的纯文本（用于相似度计算）
    char_count: int = 0              # 有效字符数
    file_modified_time: Optional[datetime] = None  # 文件最后修改时间

    def to_dict(self) -> dict:
        return {
            "employee_name": self.employee_name,
            "employee_email": self.employee_email,
            "source_file": str(self.source_file),
            "sheet_name": self.sheet_name,
            "date_range": [self.date_range[0].isoformat(), self.date_range[1].isoformat()] if self.date_range else None,
            "tasks": [t.to_dict() for t in self.tasks],
            "plans": [p.to_dict() for p in self.plans],
            "raw_text": self.raw_text,
            "char_count": self.char_count,
            "file_modified_time": self.file_modified_time.isoformat() if self.file_modified_time else None
        }
        
    @classmethod
    def from_dict(cls, data: dict) -> "SheetRecord":
        d = data.copy()
        d["source_file"] = Path(d["source_file"])
        if d.get("date_range"):
            d["date_range"] = (date.fromisoformat(d["date_range"][0]), date.fromisoformat(d["date_range"][1]))
        if d.get("file_modified_time"):
            d["file_modified_time"] = datetime.fromisoformat(d["file_modified_time"])
        d["tasks"] = [TaskRow.from_dict(t) for t in d.get("tasks", [])]
        d["plans"] = [PlanRow.from_dict(p) for p in d.get("plans", [])]
        return cls(**d)


@dataclass
class FileResult:
    """单个文件的处理结果"""
    filepath: Path                   # 文件路径
    status: FileStatus               # 处理状态
    sheets: list[SheetRecord] = field(default_factory=list)  # 有效 Sheet 列表
    match_score: float = 0.0         # 表头匹配率
    error_message: str = ""          # 错误信息
    file_format: str = ""            # 检测到的文件格式


@dataclass
class DuplicateGroup:
    """一组被判定为重复的 Sheet"""
    survivor: SheetRecord            # 保留的（优胜者）
    discarded: list[SheetRecord] = field(default_factory=list)  # 被丢弃的
    similarity_scores: list[float] = field(default_factory=list)  # 组内相似度


@dataclass
class CleaningReport:
    """清洗管线的最终报告"""
    total_files: int = 0             # 总文件数
    valid_files: int = 0             # 有效周报文件数
    rejected_files: int = 0          # 被过滤的非周报文件数
    corrupt_files: int = 0           # 损坏文件数
    encrypted_files: int = 0         # 加密文件数
    total_sheets: int = 0            # 总 Sheet 数
    unique_sheets: int = 0           # 去重后 Sheet 数
    duplicate_groups: int = 0        # 重复组数
    employees: dict[str, int] = field(default_factory=dict)  # 每人清洗后周报数
    encrypted_file_list: list[str] = field(default_factory=list)  # 加密文件清单


@dataclass
class AnalysisResult:
    """
    完整分析结果 —— Web UI 渲染的唯一数据源。

    将清洗管线产出的 Markdown、Token 预估、双层画像提取、成长时间轴分析
    四个维度的结果统一封装，面向前端 API 一次性返回。
    """
    employee_email: str = ""             # 员工邮箱
    employee_name: str = ""              # 员工姓名（中文）
    date_range_ids: list[str] = field(default_factory=list)  # 选中的时间范围 ID
    model_id: str = ""                   # 使用的 LLM 模型标识
    token_estimate: dict = field(default_factory=dict)       # Token 预估结果
    profile: dict = field(default_factory=dict)              # 双层能力画像 JSON
    growth: dict = field(default_factory=dict)               # 成长时间轴分析 JSON
    markdown_content: str = ""           # 清洗后 Markdown 全文（用于 FAQ 对话上下文）
    generated_at: str = ""               # 生成时间戳 (ISO 格式)
    elapsed_seconds: float = 0.0         # 总耗时（秒）

    def to_dict(self) -> dict:
        """序列化为字典（用于 JSON 持久化）"""
        return {
            "employee_email": self.employee_email,
            "employee_name": self.employee_name,
            "date_range_ids": self.date_range_ids,
            "model_id": self.model_id,
            "token_estimate": self.token_estimate,
            "profile": self.profile,
            "growth": self.growth,
            "markdown_content": self.markdown_content,
            "generated_at": self.generated_at,
            "elapsed_seconds": self.elapsed_seconds,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "AnalysisResult":
        """从字典反序列化"""
        valid_fields = {f.name for f in cls.__dataclass_fields__.values()}
        filtered = {k: v for k, v in data.items() if k in valid_fields}
        return cls(**filtered)

    def to_web_response(self) -> dict:
        """
        输出面向前端渲染的精简结构。

        不包含 markdown_content（体积过大），前端如需上下文可单独请求。
        """
        return {
            "employee_email": self.employee_email,
            "employee_name": self.employee_name,
            "date_range_ids": self.date_range_ids,
            "model_id": self.model_id,
            "token_estimate": self.token_estimate,
            "profile": self.profile,
            "growth": self.growth,
            "generated_at": self.generated_at,
            "elapsed_seconds": self.elapsed_seconds,
        }
