import json
import logging
import time
from datetime import datetime
from pathlib import Path
from pipeline.models import SheetRecord, AnalysisResult
from pipeline.auto_discovery import scan_directory
from pipeline.eml_extractor import build_date_calibration_map
from pipeline.noise_reduction import flatten_and_deduplicate, reconstruct_timeline
from pipeline.token_estimator import estimate_markdown_tokens, TokenEstimate
from pipeline.llm_client import CPELLMClient
from pipeline.profile_extractor import extract_profile
from pipeline.growth_analyzer import analyze_growth
from pipeline.faq_chat import FAQChatEngine

logger = logging.getLogger(__name__)

class CPEPipelineAPI:
    def __init__(self, attachments_dir: str | Path, output_dir: str | Path, emails_dir: str | Path | None = None):
        self.attachments_dir = Path(attachments_dir)
        self.output_dir = Path(output_dir)
        self.emails_dir = Path(emails_dir) if emails_dir else None
        self.cache_dir = self.output_dir / "cache"
        if not self.cache_dir.exists():
            self.cache_dir.mkdir(parents=True)
        # 构建 EML 邮件日期校准映射表（仅在提供了 emails_dir 时）
        self._calibration_map = None
        if self.emails_dir and self.emails_dir.exists():
            self._calibration_map = build_date_calibration_map(self.emails_dir)

    def get_employee_list(self) -> list[dict[str, str]]:
        """获取附件目录下所有可用的人员列表"""
        employees = []
        if not self.attachments_dir.exists():
            return employees
            
        for path in self.attachments_dir.iterdir():
            if path.is_dir() and "@" in path.name:
                emp_email = path.name
                emp_name = emp_email.split("@")[0]
                employees.append({
                    "name": emp_name,
                    "email": emp_email
                })
        return employees

    def get_employee_report_ranges(self, email: str) -> list[dict[str, str]]:
        """
        获取指定人员名下可供大模型查询的周报时间范围列表。
        首次调用时会触发该名下的数据清洗和去重，并建立缓存。
        """
        cache_file = self.cache_dir / email / "_meta.json"
        
        # 1. 检查是否存在缓存，若不存在则全局清洗一次
        if not cache_file.exists():
            self._build_cache_for_employee(email)
            
        # 2. 读取缓存
        if not cache_file.exists():
            return []
            
        with open(cache_file, "r", encoding="utf-8") as f:
            records_data = json.load(f)
            
        ranges = []
        for rd in records_data:
            dr = rd.get("date_range")
            if dr:
                r_id = f"{dr[0]}_{dr[1]}"
                ranges.append({
                    "start": dr[0],
                    "end": dr[1],
                    "id": r_id
                })
        return ranges

    def _build_cache_for_employee(self, email: str):
        """核心私有方法：扫描此员工名下的所有 Excel，去重并生成 _meta.json"""
        emp_dir = self.attachments_dir / email
        if not emp_dir.exists():
            return
            
        # 1. auto_discovery 模块寻找并过滤
        valid_files, _, _ = scan_directory(
            self.attachments_dir,
            specific_email=email,
            calibration_map=self._calibration_map,
        )
        if not valid_files:
            return
            
        # 2. noise_reduction 模块去重及排序（内含组装 timeline）
        all_sheets = []
        for file_res in valid_files:
            all_sheets.extend(file_res.sheets)
            
        employee_timelines, _ = flatten_and_deduplicate(all_sheets)
        sorted_records = employee_timelines.get(email, [])
        
        # 3. 序列化并缓存
        emp_cache_dir = self.cache_dir / email
        if not emp_cache_dir.exists():
            emp_cache_dir.mkdir(parents=True)
            
        cache_file = emp_cache_dir / "_meta.json"
        json_data = [r.to_dict() for r in sorted_records]
        with open(cache_file, "w", encoding="utf-8") as f:
            json.dump(json_data, f, ensure_ascii=False, indent=2)

    def generate_cleaned_markdown(self, email: str, date_range_ids: list[str]) -> Path:
        """
        根据前端传回的时间片段列表，从缓存中捞出对应数据并生成大模型可阅读的 Markdown 文件
        """
        cache_file = self.cache_dir / email / "_meta.json"
        if not cache_file.exists():
            raise FileNotFoundError(f"未找到员工 {email} 的缓存数据，请先调用 get_employee_report_ranges()")
            
        with open(cache_file, "r", encoding="utf-8") as f:
            records_data = json.load(f)
            
        # 将请求的 IDs 转为 set 方便匹配
        target_ids = set(date_range_ids)
        selected_records = []
        
        for rd in records_data:
            dr = rd.get("date_range")
            if dr:
                r_id = f"{dr[0]}_{dr[1]}"
                if r_id in target_ids:
                    selected_records.append(SheetRecord.from_dict(rd))
                    
        # 格式化成 Markdown
        out_dir = self.output_dir / email
        if not out_dir.exists():
            out_dir.mkdir(parents=True)
            
        if not target_ids:
            # 如果没指定范围，这里默认给个 fallback 名字
            out_name = "report.md"
        elif len(target_ids) == 1:
            out_name = f"{list(target_ids)[0]}.md"
        else:
            # 取最早和最晚
            sorted_ranges = sorted(list(target_ids))
            first = sorted_ranges[0].split('_')[0]
            last = sorted_ranges[-1].split('_')[1]
            out_name = f"{first}_to_{last}.md"
            
        out_path = out_dir / out_name
        
        employee_name = selected_records[0].employee_name if selected_records else email
        
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(f"# {employee_name} 清洗后周报汇总\n\n")
            for record in selected_records:
                if record.date_range:
                    f.write(f"\n## {record.date_range[0].strftime('%Y-%m-%d')} ~ {record.date_range[1].strftime('%Y-%m-%d')}\n\n")
                else:
                    f.write("\n## [未知周期]\n\n")
                    
                f.write(f"来源: `{record.source_file.name}` / `{record.sheet_name}`\n\n")
                
                if record.tasks:
                    f.write("\n| 序号 | 任务描述 | 进度 | 难点分析 |\n")
                    f.write("|------|----------|------|----------|\n")
                    for t in record.tasks:
                        prog = f"{t.progress*100:.0f}%" if t.progress is not None else ""
                        desc = t.description.replace("\n", "<br>")
                        analysis = t.analysis.replace("\n", "<br>")
                        f.write(f"| {t.seq} | {desc} | {prog} | {analysis} |\n")
                        
                if record.plans:
                    f.write("\n| 序号 | 计划内容 | 计划时间 | 描述 |\n")
                    f.write("|------|----------|----------|------|\n")
                    for p in record.plans:
                        p_desc = p.description.replace("\n", "<br>")
                        p_content = p.content.replace("\n", "<br>")
                        f.write(f"| {p.seq} | {p_content} | {p.planned_time} | {p_desc} |\n")
                f.write("\n")
                
        return out_path

    def estimate_tokens(
        self,
        email: str,
        date_range_ids: list[str],
        model: str = "gpt-4o",
    ) -> dict:
        """
        对指定员工和时间范围的周报进行 Token 预估（不发起 LLM 请求）。

        Args:
            email: 员工邮箱
            date_range_ids: 时间范围 ID 列表
            model: 目标模型名称

        Returns:
            Token 预估结果字典
        """
        # 组装 Markdown 上下文
        md_path = self.generate_cleaned_markdown(email, date_range_ids)
        markdown_content = md_path.read_text(encoding="utf-8")

        # 计算 Token 预估
        estimate = estimate_markdown_tokens(markdown_content, model=model)
        return estimate.to_dict()

    # ========================================================================
    # 集成 API：数据清洗管线 + LLM 分析管线串联入口
    # ========================================================================

    def run_full_analysis(
        self,
        email: str,
        date_range_ids: list[str],
        model_id: str = "deepseek/deepseek-chat",
    ) -> AnalysisResult:
        """
        完整分析流程：清洗 → Token 预估 → 画像提取 → 成长分析。

        这是面向 Web UI 的主入口，前端只需传入 email + 时间范围 + 模型 ID，
        即可获得完整的分析结果。

        Args:
            email: 员工邮箱
            date_range_ids: 选中的时间范围 ID 列表
            model_id: LLM 模型标识（如 "deepseek/deepseek-chat"）

        Returns:
            AnalysisResult: 完整分析结果

        Raises:
            ValueError: 时间范围为空
            FileNotFoundError: 员工缓存数据不存在
        """
        if not date_range_ids:
            raise ValueError("时间范围不能为空，请至少选择一个周报时间段")

        t0 = time.perf_counter()
        logger.info("开始完整分析: %s (模型: %s, %d 个时间段)", email, model_id, len(date_range_ids))

        # 1. 生成清洗后的 Markdown
        md_path = self.generate_cleaned_markdown(email, date_range_ids)
        markdown_content = md_path.read_text(encoding="utf-8")
        logger.info("Markdown 已生成: %s (%d 字符)", md_path.name, len(markdown_content))

        # 从 Markdown 第一行提取员工姓名
        employee_name = email.split("@")[0]
        first_line = markdown_content.split("\n")[0] if markdown_content else ""
        if first_line.startswith("# ") and "清洗后周报汇总" in first_line:
            employee_name = first_line.replace("# ", "").replace(" 清洗后周报汇总", "").strip()

        # 2. Token 预估
        token_info = estimate_markdown_tokens(markdown_content, model=model_id)
        token_dict = token_info.to_dict()
        logger.info("Token 预估完成: %d tokens (水位线: %s)", token_dict["token_count"], token_dict["level_label"])

        # 3. 创建 LLM 客户端（复用同一实例避免重复加载配置）
        client = CPELLMClient.from_config(model_id)

        # 4. 画像提取
        logger.info("开始画像提取...")
        profile_result = extract_profile(markdown_content, client)
        logger.info("画像提取完成")

        # 5. 成长分析
        logger.info("开始成长时间轴分析...")
        growth_result = analyze_growth(markdown_content, client)
        logger.info("成长分析完成")

        elapsed = time.perf_counter() - t0

        # 6. 组装结果
        result = AnalysisResult(
            employee_email=email,
            employee_name=employee_name,
            date_range_ids=list(date_range_ids),
            model_id=model_id,
            token_estimate=token_dict,
            profile=profile_result,
            growth=growth_result,
            markdown_content=markdown_content,
            generated_at=datetime.now().isoformat(),
            elapsed_seconds=round(elapsed, 2),
        )

        # 7. 持久化到本地（供 Web UI 后续加载或缓存查询）
        self._save_analysis_result(result)
        logger.info("完整分析完成，总耗时: %.1fs", elapsed)

        return result

    def run_profile_only(
        self,
        email: str,
        date_range_ids: list[str],
        model_id: str = "deepseek/deepseek-chat",
    ) -> dict:
        """
        仅画像提取的独立入口，面向 Web UI 按需调用。

        Args:
            email: 员工邮箱
            date_range_ids: 选中的时间范围 ID 列表
            model_id: LLM 模型标识

        Returns:
            画像提取结果字典（含 radar_outer / radar_inner / summary）
        """
        if not date_range_ids:
            raise ValueError("时间范围不能为空")

        md_path = self.generate_cleaned_markdown(email, date_range_ids)
        markdown_content = md_path.read_text(encoding="utf-8")

        client = CPELLMClient.from_config(model_id)
        return extract_profile(markdown_content, client)

    def run_growth_only(
        self,
        email: str,
        date_range_ids: list[str],
        model_id: str = "deepseek/deepseek-chat",
    ) -> dict:
        """
        仅成长分析的独立入口，面向 Web UI 按需调用。

        Args:
            email: 员工邮箱
            date_range_ids: 选中的时间范围 ID 列表
            model_id: LLM 模型标识

        Returns:
            成长分析结果字典（含 closed_loop_issues / growth_analysis）
        """
        if not date_range_ids:
            raise ValueError("时间范围不能为空")

        md_path = self.generate_cleaned_markdown(email, date_range_ids)
        markdown_content = md_path.read_text(encoding="utf-8")

        client = CPELLMClient.from_config(model_id)
        return analyze_growth(markdown_content, client)

    def get_analysis_result(self, email: str) -> AnalysisResult | None:
        """
        从本地缓存读取最近一次的分析结果。

        Args:
            email: 员工邮箱

        Returns:
            AnalysisResult 或 None（未找到历史结果时）
        """
        result_dir = self.output_dir / email
        if not result_dir.exists():
            return None

        # 查找最近的 _analysis.json 文件
        result_files = sorted(result_dir.glob("*_analysis.json"), reverse=True)
        if not result_files:
            return None

        try:
            with open(result_files[0], "r", encoding="utf-8") as f:
                data = json.load(f)
            return AnalysisResult.from_dict(data)
        except Exception as e:
            logger.warning("读取分析结果缓存失败: %s", e)
            return None

    def get_widest_analysis_result(self, email: str) -> AnalysisResult | None:
        """
        从本地缓存中选取周报覆盖范围最广的分析结果（用于团队大盘聚合）。

        选择策略：遍历所有历史分析文件，选取 date_range_ids 数量最多的那份，
        如果数量相同则优先取最新生成的文件。

        Args:
            email: 员工邮箱

        Returns:
            AnalysisResult 或 None（未找到历史结果时）
        """
        result_dir = self.output_dir / email
        if not result_dir.exists():
            return None

        # 按文件名逆序排列（最新的在前），便于同等范围数时优先取最新
        result_files = sorted(result_dir.glob("*_analysis.json"), reverse=True)
        if not result_files:
            return None

        best_file = None
        best_range_count = -1

        for fpath in result_files:
            try:
                with open(fpath, "r", encoding="utf-8") as f:
                    data = json.load(f)
                range_count = len(data.get("date_range_ids", []))
                if range_count > best_range_count:
                    best_range_count = range_count
                    best_file = (fpath, data)
            except Exception:
                continue

        if best_file is None:
            return None

        try:
            return AnalysisResult.from_dict(best_file[1])
        except Exception as e:
            logger.warning("解析最广范围分析结果失败: %s", e)
            return None

    def _save_analysis_result(self, result: AnalysisResult):
        """将分析结果持久化到 output/<email>/ 目录"""
        out_dir = self.output_dir / result.employee_email
        out_dir.mkdir(parents=True, exist_ok=True)

        # 使用时间戳命名，便于 Web UI 查询历史记录
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        out_path = out_dir / f"{timestamp}_analysis.json"

        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(result.to_dict(), f, ensure_ascii=False, indent=2)

        logger.info("分析结果已保存: %s", out_path)

    # ========================================================================
    # FAQ 智能对话 API（PRD 3.3）
    # ========================================================================

    # 内存中的活跃会话池 {session_id → FAQChatEngine}
    _chat_sessions: dict[str, FAQChatEngine] = {}

    def start_chat_session(
        self,
        email: str,
        date_range_ids: list[str],
        model_id: str = "deepseek/deepseek-chat",
    ) -> str:
        """
        创建 FAQ 对话会话。

        将指定员工的选定时间范围周报作为全量上下文注入，
        创建一个新的对话会话。

        Args:
            email: 员工邮箱
            date_range_ids: 选中的时间范围 ID 列表
            model_id: LLM 模型标识

        Returns:
            session_id: 会话唯一标识（前端后续用此 ID 发送消息）
        """
        if not date_range_ids:
            raise ValueError("时间范围不能为空")

        # 生成清洗后的 Markdown 上下文
        md_path = self.generate_cleaned_markdown(email, date_range_ids)
        markdown_content = md_path.read_text(encoding="utf-8")

        # 创建 LLM 客户端
        client = CPELLMClient.from_config(model_id)

        # 创建对话引擎
        engine = FAQChatEngine(
            markdown_content=markdown_content,
            llm_client=client,
        )

        # 注册到会话池
        self._chat_sessions[engine.session_id] = engine
        logger.info(
            "FAQ 对话会话已创建: session=%s, 员工=%s, 模型=%s",
            engine.session_id[:8], email, model_id,
        )

        return engine.session_id

    def chat(self, session_id: str, message: str) -> dict:
        """
        在指定会话中发送消息。

        Args:
            session_id: 会话 ID（由 start_chat_session 返回）
            message: 用户问题

        Returns:
            {"role": "assistant", "content": "...", "turn": N}

        Raises:
            KeyError: 会话不存在
        """
        engine = self._chat_sessions.get(session_id)
        if engine is None:
            raise KeyError(f"会话 {session_id} 不存在或已过期")

        reply = engine.chat(message)
        return {
            "role": "assistant",
            "content": reply,
            "turn": engine.turn_count,
        }

    def get_chat_history(self, session_id: str) -> list[dict]:
        """
        获取指定会话的完整对话历史。

        Args:
            session_id: 会话 ID

        Returns:
            对话记录列表 [{role, content}, ...]

        Raises:
            KeyError: 会话不存在
        """
        engine = self._chat_sessions.get(session_id)
        if engine is None:
            raise KeyError(f"会话 {session_id} 不存在或已过期")

        return engine.get_history()
