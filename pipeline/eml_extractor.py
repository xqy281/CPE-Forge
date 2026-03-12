"""
EML 邮件解析与附件日期校准模块。

从 .eml 文件中提取邮件发送时间和附件信息，构建「附件文件名 → 邮件发送日期」
映射表，用于校准附件中周报年份错误（如员工2026年的周报文件名误写为2025年）。

注意：
  - 邮件可能是转发的（From 是转发者而非原始发送者），所以**不使用 From 做员工识别**。
  - 员工身份由附件文件名或 attachments 目录结构决定。
  - 本模块仅提取 Date 头作为附件的时间校准依据。
"""
from __future__ import annotations

import email
import email.header
import email.utils
import logging
import re
from datetime import datetime
from pathlib import Path
from typing import NamedTuple

logger = logging.getLogger(__name__)


class EmlAttachmentInfo(NamedTuple):
    """单个附件的元信息"""
    filename: str          # 附件原始文件名
    email_sent_date: datetime  # 邮件发送日期（含时区）
    email_subject: str     # 邮件主题（调试用）


def _decode_header(raw: str) -> str:
    """解码 MIME 编码的邮件头（如 Subject、附件文件名）"""
    if not raw:
        return ""
    decoded_parts = email.header.decode_header(raw)
    result = []
    for part, charset in decoded_parts:
        if isinstance(part, bytes):
            result.append(part.decode(charset or "utf-8", errors="replace"))
        else:
            result.append(part)
    return "".join(result)


def _sanitize_filename(name: str) -> str:
    """清理文件名中 Windows 不允许的字符"""
    return re.sub(r'[\\/:*?"<>|]', '_', name)


def parse_single_eml(eml_path: Path) -> list[EmlAttachmentInfo]:
    """
    解析单个 .eml 文件，提取其中所有 Excel 附件的元信息。

    Args:
        eml_path: .eml 文件路径

    Returns:
        附件元信息列表（可能为空，如果该邮件无 Excel 附件）
    """
    try:
        with open(eml_path, "rb") as f:
            msg = email.message_from_binary_file(f)
    except Exception as e:
        logger.warning("解析 EML 失败: %s — %s", eml_path.name, e)
        return []

    # 解析发送日期
    date_str = msg.get("Date", "")
    try:
        sent_date = email.utils.parsedate_to_datetime(date_str) if date_str else None
    except Exception:
        sent_date = None

    if sent_date is None:
        logger.warning("EML 缺少有效 Date 头: %s", eml_path.name)
        return []

    # 解析主题（调试用）
    subject = _decode_header(msg.get("Subject", ""))

    # 提取 Excel 附件
    results = []
    for part in msg.walk():
        content_disp = part.get("Content-Disposition", "")
        if "attachment" not in content_disp:
            continue

        raw_filename = part.get_filename()
        if not raw_filename:
            continue

        filename = _decode_header(raw_filename)
        if not filename.lower().endswith((".xls", ".xlsx")):
            continue

        results.append(EmlAttachmentInfo(
            filename=filename,
            email_sent_date=sent_date,
            email_subject=subject,
        ))

    return results


def _get_unique_filepath(folder: Path, filename: str) -> Path:
    """如果文件已存在，在文件名后添加序号以避免覆盖（如 data_1.xlsx）"""
    base_name = Path(filename).stem
    ext = Path(filename).suffix
    save_path = folder / filename
    counter = 1
    while save_path.exists():
        save_path = folder / f"{base_name}_{counter}{ext}"
        counter += 1
    return save_path


def extract_attachments_from_eml_dir(
    eml_dir: Path,
    output_dir: Path,
) -> dict[str, datetime]:
    """
    从 EML 目录提取所有 Excel 附件到 output_dir，按员工邮箱分目录。

    同时返回日期校准映射表（附件文件名 → 邮件发送日期）。
    此函数替代原 extract.py 脚本。

    **关键设计**：不直接使用 From 头做目录分类（转发邮件的 From 是
    转发者而非原始发送者）。改为：
    1. 第一遍：扫描全部 EML，建立「员工姓名 → 发件人邮箱」映射
       （从非转发邮件中学习，附件文件名含员工姓名）
    2. 第二遍：提取附件时，优先用文件名中的员工姓名查映射表确定
       正确的邮箱目录；映射表查不到时才 fallback 到 From 头

    Args:
        eml_dir: EML 邮件目录
        output_dir: 附件输出目录（如 attachments/）

    Returns:
        日期校准映射表 { "附件文件名": 邮件发送日期 }
    """
    import email as _email
    from email import policy as _policy
    from email.parser import BytesParser
    from email.utils import parseaddr
    from pipeline.utils import extract_employee_name_from_filename

    if not eml_dir.exists():
        logger.warning("EML 目录不存在: %s", eml_dir)
        return {}

    output_dir.mkdir(parents=True, exist_ok=True)

    # ── 第一遍：构建「员工姓名 → 邮箱」映射 ──────────────────────
    # 从非转发邮件中学习：附件文件名包含员工姓名，From 头是可信的
    name_to_email: dict[str, str] = {}
    eml_files = sorted(eml_dir.glob("*.eml"))
    logger.info("EML 提取: 扫描 %d 个文件，构建员工映射...", len(eml_files))

    for eml_path in eml_files:
        # 跳过转发/回复邮件（From 不可信）
        eml_name_lower = eml_path.name.lower()
        if any(kw in eml_name_lower for kw in ("转发", "回复", "re_", "fw_", "fwd_")):
            continue

        try:
            with open(eml_path, "rb") as f:
                msg = BytesParser(policy=_policy.default).parse(f)
        except Exception:
            continue

        _, sender_email = parseaddr(msg.get("From", ""))
        if not sender_email or "@" not in sender_email:
            continue

        # 从附件文件名提取员工姓名
        for part in msg.walk():
            if part.get_content_disposition() != "attachment":
                continue
            att_fn = part.get_filename()
            if not att_fn:
                continue
            att_fn = _decode_header(att_fn) if isinstance(att_fn, str) else att_fn
            if not att_fn.lower().endswith((".xls", ".xlsx")):
                continue
            emp_name = extract_employee_name_from_filename(att_fn)
            if emp_name and emp_name not in name_to_email:
                name_to_email[emp_name] = sender_email

    logger.info("员工映射: %d 个姓名 → 邮箱", len(name_to_email))
    for name, em in sorted(name_to_email.items()):
        logger.info("  %s → %s", name, em)

    # ── 第二遍：提取附件 ──────────────────────────────────────
    calibration_map: dict[str, datetime] = {}
    extracted_count = 0

    for eml_path in eml_files:
        try:
            with open(eml_path, "rb") as f:
                msg = BytesParser(policy=_policy.default).parse(f)
        except Exception as e:
            logger.warning("解析 EML 失败: %s — %s", eml_path.name, e)
            continue

        # 解析发送日期
        date_str = msg.get("Date", "")
        try:
            sent_date = _email.utils.parsedate_to_datetime(date_str) if date_str else None
        except Exception:
            sent_date = None

        # 获取 From（仅作 fallback）
        _, sender_email = parseaddr(msg.get("From", ""))
        if not sender_email:
            sender_email = "unknown_sender"

        # 提取 Excel 附件
        for part in msg.walk():
            if part.get_content_disposition() != "attachment":
                continue
            att_filename = part.get_filename()
            if not att_filename:
                continue
            att_filename = _decode_header(att_filename) if isinstance(att_filename, str) else att_filename
            if not att_filename.lower().endswith((".xls", ".xlsx")):
                continue

            # 确定目标邮箱目录：优先用附件文件名中的员工姓名查映射表
            emp_name = extract_employee_name_from_filename(att_filename)
            target_email = name_to_email.get(emp_name, sender_email) if emp_name else sender_email
            safe_target = _sanitize_filename(target_email)

            # 保存附件
            target_dir = output_dir / safe_target
            target_dir.mkdir(parents=True, exist_ok=True)
            save_path = _get_unique_filepath(target_dir, att_filename)
            payload = part.get_payload(decode=True)
            if payload:
                save_path.write_bytes(payload)
                extracted_count += 1

            # 构建校准映射（用最早的发送日期）
            if sent_date:
                existing = calibration_map.get(att_filename)
                if existing is None or sent_date < existing:
                    calibration_map[att_filename] = sent_date

    logger.info(
        "EML 附件提取完成: %d 个文件提取到 %s (校准映射: %d 个)",
        extracted_count, output_dir, len(calibration_map),
    )
    return calibration_map


def build_date_calibration_map(
    eml_dir: Path,
) -> dict[str, datetime]:
    """
    扫描 EML 目录，构建「附件文件名 → 邮件发送日期」映射表。

    此映射表用于校准附件文件名中的年份错误：
    当文件名中解析出的年份与邮件实际发送年份不一致时，以邮件年份为准。

    注意：
      - 不使用 From 字段（转发邮件中 From 是转发者，不是原始发送者）
      - 同一附件可能出现在多封邮件中（如原始邮件和转发邮件都有），
        取最早的发送日期（原始邮件通常更早）

    Args:
        eml_dir: 存放 .eml 文件的目录

    Returns:
        { "附件文件名": 邮件发送时间 }
    """
    if not eml_dir.exists():
        logger.warning("EML 目录不存在: %s", eml_dir)
        return {}

    calibration_map: dict[str, datetime] = {}
    eml_files = sorted(eml_dir.glob("*.eml"))
    logger.info("扫描 EML 目录: %s (%d 个文件)", eml_dir, len(eml_files))

    total_attachments = 0
    for eml_path in eml_files:
        for info in parse_single_eml(eml_path):
            total_attachments += 1
            existing = calibration_map.get(info.filename)
            # 同一附件出现在多封邮件中时，保留最早的发送日期（原始邮件）
            if existing is None or info.email_sent_date < existing:
                calibration_map[info.filename] = info.email_sent_date

    logger.info(
        "EML 校准映射表构建完成: %d 个唯一附件 (共扫描 %d 个附件引用)",
        len(calibration_map), total_attachments,
    )

    return calibration_map


def calibrate_year(
    parsed_year: int,
    attachment_filename: str,
    calibration_map: dict[str, datetime] | None,
    parsed_month: int | None = None,
) -> int:
    """
    用邮件发送日期校准从文件名解析出的年份。

    如果附件文件名在映射表中，且文件名解析出的年份与邮件发送年份不一致，
    则返回邮件发送年份。

    跨年保护：当文件名月份是 12 月、邮件发送在次年 1 月时，属于合理的
    跨年提交（如 12月29日的周报在1月9日提交），不校准。

    Args:
        parsed_year: 从文件名/Sheet名解析出的年份
        attachment_filename: 附件文件名（用于查找映射表）
        calibration_map: 「附件文件名 → 发送日期」映射表（可为 None）
        parsed_month: 从文件名/Sheet名解析出的起始月份（用于跨年保护）

    Returns:
        校准后的年份
    """
    if not calibration_map:
        return parsed_year

    sent_date = calibration_map.get(attachment_filename)
    if sent_date is None:
        return parsed_year

    email_year = sent_date.year
    if parsed_year == email_year:
        return parsed_year

    # 跨年保护：文件名月份12月 + 邮件次年1月 → 合理的跨年提交，不校准
    if parsed_month is not None:
        email_month = sent_date.month
        # 12月的周报在次年1月提交（如 12/29~1/9 的周报在 1月9日提交）
        if parsed_month >= 11 and email_month <= 2 and email_year == parsed_year + 1:
            return parsed_year
        # 1月的周报在前年12月提交（极端情况，如提前提交）
        if parsed_month <= 2 and email_month >= 11 and email_year == parsed_year - 1:
            return parsed_year

    logger.info(
        "年份校准: %s 中解析年份 %d → 邮件年份 %d (邮件发送: %s)",
        attachment_filename, parsed_year, email_year,
        sent_date.strftime("%Y-%m-%d"),
    )
    return email_year

