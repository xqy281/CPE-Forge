# CPE-Forge: 多智能体协同开发文档 (Agent Sync Doc)

> **文档说明**：本文档旨在解决多 Agent 会话窗口之间缺乏上下文同步的问题。当你或另一个 Agent 在新的环境/窗口中被唤醒时，请优先阅读本文档，以快速掌握项目架构、当前进度和接下来的任务目标。

## 1. 项目概况与背景

- **项目名称**: CPE-Forge (CPE研发效能与人才画像AIGC分析平台)
- **核心目标**: 通过 AIGC 技术深度解析 CPE 嵌入式软件团队的 Excel 周报数据，清洗去噪后，转换为大模型友好的格式，最终输出包含"双层能力雷达图"和"成长时间轴"的分析报告。
- **数据源**: `attachments/` 目录下约 710 份历史 Excel 附件，涉及 13 位员工。

## 2. 系统架构与当前状态

项目划分为以下几个主要阶段，目前 **阶段一至阶段三（PRD 第2章全部 + 第3章 3.1/3.2 基本面）已完成**。

### 已完成模块（数据清洗管线 PRD 2.1~2.2）

管线核心代码位于 `pipeline/` 目录中：

1. **智能识别与过滤 (`auto_discovery.py`)**: 从文件目录中抓取有效的 Excel 周报，使用表头特征命中的方式过滤掉非周报、测试表格。
2. **清洗与去重 (`noise_reduction.py`)**:
   - 将"进度"、"难点分析"等多列展平为纯文本。
   - 使用 TF-IDF + 余弦相似度 (94% 阈值) 跨文件交叉比对，识别重复冗余的"本周/上周"合并表格。
   - 执行"优胜劣汰"（保留最新修改、最长文本）后，重构时间线。
3. **数据类模型 (`models.py`)**: `SheetRecord` 对象在各阶段流转。
4. **单元测试 (`tests/`)**: 通过了 34 个严谨的单元测试。
5. **端到端脚本 (`scripts/run_pipeline.py`)**: 已经成功在 710 份数据上完成全链路跑批。

### 已完成模块（Token 预估 PRD 2.3）

6. **Token 预估 (`pipeline/token_estimator.py`)**:
   - 使用 `tiktoken` 精确计算 Token 数量
   - 支持多模型的上下文窗口限制查询
   - 水位线判定：🟢 绿色(<50k) / 🟡 黄色(50k~100k) / 🔴 红色(>100k)
   - API 层面已集成 `estimate_tokens()` 方法

### 已完成模块（AIGC 量化提取 PRD 3.1~3.2 基本面）

7. **LLM 统一调用层 (`pipeline/llm_client.py`)**:
   - 基于 LiteLLM 封装，支持 100+ 模型一行切换
   - 支持的模型：OpenAI GPT-4o / Claude / DeepSeek / Gemini 等
   - JSON 智能解析容错 + 指数退避重试机制
   - 支持 `temperature` 和 `top_p` 参数独立配置
   - `from_config()` 工厂方法：从配置文件自动加载模型参数
8. **LLM 模型独立配置系统 (`pipeline/llm_config.py`)**:
   - 每模型独立 JSON 配置文件，存放在 `config/models/` 目录
   - 配置项：`temperature`、`top_p`、`max_tokens`、`api_key`、`api_base`、`enabled` 等
   - 面向 Web UI 的完整 CRUD API：`list / load / save / update / delete`
   - `to_safe_dict()` 隐藏 API Key 仅显示末 4 位（前端安全展示）
   - 7 个默认预设：DeepSeek Chat / DeepSeek Reasoner(R1) / GPT-4o / GPT-4o Mini / Claude 3.5 Sonnet / Gemini 2.0 Flash / Gemini 2.5 Pro
   - 配置文件不覆盖用户修改（`init_default_configs` 幂等安全）
9. **双层能力画像提取 (`pipeline/profile_extractor.py`, PRD 3.1)**:
   - **外层雷达图采用双轨制**：每维度输出 `proportion`（归一化精力占比，和=1.0）+ `depth`（绝对投入深度 0~5 独立评分）
   - 5维度：系统平台/底层驱动/上层应用/无线通信/SQA
   - 内层3维度：求真/务实/严谨（Lv1~Lv5 + 证据链）
   - System Prompt 模板：`prompts/profile_system.md`（可热插拔调试）
   - 兼容旧格式纯浮点数输入，自动转换为双轨结构
10. **成长时间轴分析 (`pipeline/growth_analyzer.py`, PRD 3.2)**:
    - 功能1：问题闭环追踪（跨周 issue 故事线）
    - 功能2：剥洋葱/乱试验模式识别
    - System Prompt 模板：`prompts/growth_system.md`（可热插拔调试）
11. **端到端调试脚本 (`scripts/run_llm_analysis.py`)**:
    - `--token-only`: 仅 Token 预估，不调用 LLM
    - `--profile-only`: 仅画像提取，调试 profile prompt
    - `--growth-only`: 仅成长分析，调试 growth prompt
    - `--from-file`: 直接从 Markdown 文件读取，跳过清洗管线
    - `--prompt-file`: 使用自定义 System Prompt 文件
    - `--init-configs`: 初始化默认模型配置文件到 `config/models/`
    - `--list-models`: 列出所有已配置模型及其参数
12. **单元测试**: 全部 82 个测试通过

### 按需清洗 API (`pipeline/api.py`)

- `get_employee_list()`: 获取所有人员列表
- `get_employee_report_ranges()`: 获取可用时间范围
- `generate_cleaned_markdown()`: 组装大模型可读的 Markdown
- `estimate_tokens()`: Token 预估预检

### 已完成模块（集成 API 层 — 清洗+LLM 串联）

13. **统一分析入口 (`pipeline/api.py` 扩展)**:
    - `run_full_analysis(email, date_range_ids, model_id)`: 完整流程（清洗 → Token预估 → 画像提取 → 成长分析）
    - `run_profile_only()`: 仅画像提取独立入口
    - `run_growth_only()`: 仅成长分析独立入口
    - `get_analysis_result()`: 读取历史分析结果缓存
    - 返回 `AnalysisResult` 标准化数据结构，含 `to_web_response()` 方法
14. **`AnalysisResult` 数据模型 (`pipeline/models.py`)**:
    - 封装完整分析结果：`token_estimate` + `profile` + `growth` + `markdown_content`
    - `to_dict()` / `from_dict()` 支持 JSON 持久化
    - `to_web_response()` 输出精简前端结构（不含大体积 Markdown）
15. **集成调试脚本 (`scripts/run_integrated.py`)**:
    - 交互式/命令行模式，支持 `--token-only` / `--profile-only` / `--growth-only`
    - 结果自动持久化到 `output/<email>/<timestamp>_analysis.json`

### 已完成模块（PRD 3.3: 全量上下文 FAQ 智能对话）

16. **FAQ 对话引擎 (`pipeline/faq_chat.py`)**:
    - `FAQChatEngine`: 全量 Markdown 注入 System Prompt，连续多轮对话
    - 内部维护 `messages` 历史数组，每次请求自动携带完整上下文
    - Token 溢出保护：超过 `max_history_turns` 时自动裁剪最早轮次
    - `chat()` / `reset()` / `get_history()` / `turn_count`
17. **FAQ System Prompt (`prompts/faq_system.md`)**:
    - 角色：CPE 嵌入式团队内部顾问
    - 回答原则：据实回答、引用日期出处、保持连续对话、保留技术术语
18. **FAQ API 接口 (`pipeline/api.py` 扩展)**:
    - `start_chat_session(email, date_range_ids, model_id) → session_id`
    - `chat(session_id, message) → {role, content, turn}`
    - `get_chat_history(session_id) → [{role, content}, ...]`
19. **FAQ 终端 REPL (`scripts/run_chat.py`)**:
    - 特殊命令：`/quit` 退出、`/reset` 重置、`/history` 查看历史、`/turns` 轮次
20. **单元测试**: 全部 **139 个**测试通过（含 10 个 FAQ 测试 + 9 个集成测试）

### 关键目录结构

```
config/models/           ← 模型独立配置（每模型一个 JSON）
prompts/                 ← System Prompt 模板（profile / growth / faq）
pipeline/                ← 核心管线代码
scripts/                 ← 端到端调试/运行脚本
tests/                   ← 单元测试（139 个）
output/                  ← 清洗后 Markdown + 分析结果 JSON
```

---

## 4. Web UI 接口调用规范

前端 Web UI 只需调用以下 API 即可完成所有业务流程：

### 4.1 数据查询流程

```
GET  get_employee_list()
     → [{name, email}, ...]                    // 13 位员工

GET  get_employee_report_ranges(email)
     → [{start, end, id}, ...]                 // 可选时间范围列表

POST estimate_tokens(email, range_ids, model)
     → {token_count, model_limit, level_emoji}  // Token 预检（不调用 LLM）
```

### 4.2 分析流程

```
POST run_full_analysis(email, range_ids, model_id)
     → AnalysisResult                           // 完整分析（画像+成长）

POST run_profile_only(email, range_ids, model_id)
     → {radar_outer, radar_inner, summary}      // 仅画像

POST run_growth_only(email, range_ids, model_id)
     → {closed_loop_issues, growth_analysis}    // 仅成长
```

### 4.3 FAQ 对话流程

```
POST start_chat_session(email, range_ids, model_id)
     → session_id                               // 创建会话

POST chat(session_id, message)
     → {role, content, turn}                    // 发送消息

GET  get_chat_history(session_id)
     → [{role, content}, ...]                   // 对话历史
```

### 4.4 缓存查询

```
GET  get_analysis_result(email)
     → AnalysisResult | None                    // 最近一次分析结果
```

> **注意**：`AnalysisResult.to_web_response()` 返回不含大体积 `markdown_content` 的精简结构，适合前端渲染。

---

## 5. 真实 LLM API 验证记录

### 5.1 集成分析验证（萧倩云 52 个周报 + DeepSeek Reasoner）

| 阶段           | 耗时             | 结果                                          |
| -------------- | ---------------- | --------------------------------------------- |
| Markdown 生成  | <1s              | ✅ 51,409 字符                                |
| Token 预估     | <1s              | ✅ 36,813 tokens（🟢绿色 56.2%）              |
| 画像提取       | 51s              | ✅ proportion=1.00，5维度 ★★★★~★★★★★ |
| 成长分析       | 80s              | ✅ 6个闭环问题 + 3个递进分析                  |
| **总计** | **131.5s** | ✅ 持久化到 `*_analysis.json`               |

### 5.2 集成分析验证（赖灿辉 54 个周报 + DeepSeek Reasoner）

| 阶段     | 总耗时 | 结果                         |
| -------- | ------ | ---------------------------- |
| 完整分析 | 125.9s | ✅ 4个闭环问题 + 2个递进分析 |

### 5.3 FAQ 对话验证（萧倩云 + DeepSeek Reasoner）

| 轮次         | 用户问题                         | 回答质量                                           |
| ------------ | -------------------------------- | -------------------------------------------------- |
| 第1轮        | 「主要负责哪些技术方向？」       | ✅ 识别 OpenWrt/驱动/内存/Mesh等方向，引用具体日期 |
| 第2轮        | 「她在WiFi方面遇到过哪些难题？」 | ✅ 多轮上下文延续，按类别梳理WiFi难题              |
| `/history` | 查看对话历史                     | ✅ 正确显示 2 轮完整记录                           |

---

## 6. Web UI 前端（Vue 3 + Vite 重写版 ✅）

> 前端已从 Vanilla JS 完整重写为 **Vue 3 Composition API + Vite**，代码位于 `web/frontend/`。

### 6.1 技术栈

| 层 | 选择 |
|----|------|
| 构建 | Vite 7.x |
| 框架 | Vue 3 `<script setup>` |
| 路由 | Vue Router 4 (History Mode) |
| 状态 | Pinia |
| 图表 | Chart.js + 原生封装（团队大盘）<br>Three.js（个人画像 3D 图谱）|
| HTTP | axios |
| 图标 | Lucide Vue Next (SVG) |

### 6.2 设计风格

- **Swiss Modernism × 锻造暖色系**：主色 `#C2410C`（热铁橙），近黑文本 `#1C1917`，暖白表面 `#FFFBF7`
- **字体**: Inter + PingFang SC / Microsoft YaHei
- **无 emoji 图标**，全部使用 Lucide SVG
- **大量留白、精密间距（8px 网格）、12px 圆角卡片**

### 6.3 页面结构

| 页面 | 路由 | 组件 |
|------|------|------|
| 数据调度台 | `/console` | `ConsoleView.vue` |
| 团队大盘 | `/dashboard` | `DashboardView.vue` |
| 英雄榜 | `/roster` | `RosterView.vue` |
| 个人画像 | `/player/:email` | `PlayerView.vue` |
| 模型配置 | `/settings` | `SettingsView.vue` |

### 6.4 公共组件

| 组件 | 用途 |
|------|------|
| `AbilityChart3D.vue` | Three.js 3D 统一能力图谱（水晶柱 + 浮岛） |
| `ScorePanel.vue` | 打分解释面板（技术维度表 + 素养基石进度） |
| `RadarChart.vue` | 2D 双轨雷达图（团队大盘聚合用） |
| `TimelineCard.vue` | 技术攻坚故事线卡片 |
| `ChatWidget.vue` | FAQ 多轮对话浮窗 |
| `LoadingOverlay.vue` | 加载遮罩 |

### 6.5 运行方式

```bash
# 开发模式（Vite :5173 代理 → Flask :5000）
cd web/frontend && npm run dev

# 生产构建
cd web/frontend && npm run build  # 产物在 dist/
```

### 6.6 后端（Flask）完全保留

Flask 后端 (`web/app.py` + `web/api_routes.py`) 已稳定，重写不涉及后端。

---

## 7. 完整 HTTP API 端点清单（后端已实现，前端直接调用）

> 所有端点前缀为 `/api`，由 Flask Blueprint 注册。

### 7.1 数据查询（GET）

| 端点 | 说明 | 返回值 |
|------|------|--------|
| `GET /api/employees` | 获取所有员工列表 | `[{name, email}, ...]` |
| `GET /api/employees/<email>/ranges` | 获取某员工的可选时间范围 | `[{id, start, end}, ...]` |
| `GET /api/models` | 获取所有 LLM 模型配置 | `[{model_id, display_name, temperature, top_p, has_key, enabled}, ...]` |
| `GET /api/models/<model_id>` | 获取单个模型配置详情 | `{model_id, display_name, api_key(masked), temperature, ...}` |

### 7.2 分析结果查询（GET）

| 端点 | 说明 | 返回值 |
|------|------|--------|
| `GET /api/analysis/<email>/latest` | 最新分析结果 | `AnalysisResult.to_web_response()` 或 404 |
| `GET /api/analysis/<email>/history` | 历史分析文件列表 | `[{filename, generated_at, model_id, date_range_count, elapsed_seconds}, ...]` |
| `GET /api/analysis/status` | 全员缓存状态 | `{email: true/false, ...}` |
| `GET /api/analysis/all` | 全员聚合结果（团队大盘） | `{total_employees, analyzed_count, results: [...]}` |

### 7.3 分析触发（POST）

| 端点 | Body 参数 | 返回值 |
|------|-----------|--------|
| `POST /api/estimate-tokens` | `{email, date_range_ids, model_id}` | `{token_count, level, level_label, model_limit, utilization_pct}` |
| `POST /api/analysis/full` | `{email, date_range_ids, model_id}` | 完整 `AnalysisResult` |
| `POST /api/analysis/profile` | `{email, date_range_ids, model_id}` | 仅画像 `{profile: ...}` |
| `POST /api/analysis/growth` | `{email, date_range_ids, model_id}` | 仅成长 `{growth: ...}` |

### 7.4 模型配置（PUT）

| 端点 | Body 参数 | 说明 |
|------|-----------|------|
| `PUT /api/models/<model_id>` | `{api_key?, temperature?, top_p?}` | 更新模型配置 |

### 7.5 FAQ 对话（POST/GET）

| 端点 | 参数 | 返回值 |
|------|------|--------|
| `POST /api/chat/start` | `{email, date_range_ids, model_id}` | `{session_id, welcome_message}` |
| `POST /api/chat/send` | `{session_id, message}` | `{role, content, turn}` |
| `GET /api/chat/<session_id>/history` | — | `[{role, content}, ...]` |

### 7.6 API Key 校验机制

`/api/analysis/full`、`/api/analysis/profile`、`/api/analysis/growth`、`/api/chat/start` 四个端点在调用 LLM 前会检查 API Key：
- 未配置 → 返回 `400 {error: "...", need_config: true}`
- 前端应捕获 `need_config` 标志，引导用户前往模型配置页

---

## 8. 分析结果 JSON 关键数据结构

> `AnalysisResult.to_web_response()` 返回的精简结构（不含大体积 markdown_content）

```json
{
  "employee_email": "xxx@jointelli.com",
  "employee_name": "萧倩云",
  "date_range_ids": ["2025-01-06_2025-01-11", ...],
  "model_id": "deepseek/deepseek-reasoner",
  "elapsed_seconds": 123.93,
  "token_estimate": {
    "token_count": 36813,
    "level": "green",
    "level_label": "绿色",
    "level_emoji": "🟢",
    "model_limit": 65536,
    "utilization_pct": 56.17
  },
  "profile": {
    "radar_outer": {
      "system_platform": {"proportion": 0.2, "depth": 4},
      "driver_development": {"proportion": 0.25, "depth": 4},
      "application_software": {"proportion": 0.15, "depth": 4},
      "wireless_communication": {"proportion": 0.3, "depth": 5},
      "sqa_quality": {"proportion": 0.1, "depth": 4}
    },
    "radar_inner": {
      "truth_seeking": {"level": 5, "score": 0.9, "evidence": [...]},
      "pragmatic": {"level": 4, "score": 0.8, "evidence": [...]},
      "rigorous": {"level": 4, "score": 0.8, "evidence": [...]}
    },
    "summary": "该员工是一位技术全面且深度的..."
  },
  "growth": {
    "closed_loop_issues": [
      {
        "title": "M05/V18 固件压测恢复出厂设置PHY口芯片挂死问题",
        "first_appeared": "2025-01-12",
        "resolved_date": "2025-01-31",
        "duration_weeks": 3,
        "status": "resolved",
        "timeline": [
          {"date": "2025-01-12~2025-01-17", "progress": "80%", "description": "..."},
          ...
        ],
        "root_cause": "...",
        "solution": "...",
        "tags": ["硬件问题", "PHY驱动", ...]
      },
      ...
    ],
    "growth_analysis": {
      "recursive_logic": [
        {
          "task_name": "...",
          "pattern": "depth_first",
          "reasoning_chain": ["...", "..."],
          "label": "深度递进/求真严谨",
          "evidence_period": "2025-02-02~2025-02-13"
        },
        ...
      ]
    }
  }
}
```

### 8.1 关键字段映射（前端渲染时注意）

| 用途 | 正确字段路径 | ⚠️ 常见错误 |
|------|-------------|-------------|
| 执行力总评 | `profile.summary` | ❌ ~~`profile.comprehensive_summary`~~ |
| 故事线标题 | `growth.closed_loop_issues[].title` | ❌ ~~`issue_name`~~ |
| 故事线状态 | `growth.closed_loop_issues[].status` | ❌ ~~`issue_type`~~ |
| 故事线标签 | `growth.closed_loop_issues[].tags[]` | — |
| 外层雷达精力占比 | `profile.radar_outer[dim].proportion` | 值为 0~1 小数 |
| 外层雷达投入深度 | `profile.radar_outer[dim].depth` | 值为 0~5 整数 |
| 内层素养等级 | `profile.radar_inner[dim].level` | 值为整数（非字符串） |

### 8.2 维度中文名映射

| 英文 Key | 中文 | 类别 |
|----------|------|------|
| `system_platform` | 系统平台 | 外层雷达 |
| `driver_development` | 底层驱动 | 外层雷达 |
| `application_software` | 上层应用 | 外层雷达 |
| `wireless_communication` | 无线通信 | 外层雷达 |
| `sqa_quality` | SQA质量 | 外层雷达 |
| `truth_seeking` | 求真 | 内层素养 |
| `pragmatic` | 务实 | 内层素养 |
| `rigorous` | 严谨 | 内层素养 |

---

## 9. 前端重写指引（Vue 3 + Vite）

### 9.1 技术选型建议

| 层 | 推荐 | 理由 |
|----|------|------|
| 构建工具 | **Vite** | HMR 极快、零配置 TypeScript |
| 框架 | **Vue 3 Composition API** | SFC 单文件组件、响应式 |
| 路由 | **Vue Router 4** | 参数传递/嵌套路由/导航守卫 |
| 状态管理 | **Pinia** | 比 Vuex 轻量，TypeScript 友好 |
| 图表 | **Chart.js + vue-chartjs** | 复用现有雷达图逻辑 |
| UI 组件库 | **Element Plus** 或纯 CSS | 按需引入，不强制 |
| HTTP | **axios** 或 **fetch** | 封装统一请求层 |

### 9.2 页面/组件规划

```
views/
  ConsoleView.vue      ← 数据调度台（员工选择、时间范围、Token 预检、分析触发）
  DashboardView.vue    ← 团队大盘（聚合雷达 + 统计）
  RosterView.vue       ← 英雄榜（卡片网格 + 缓存状态 + 历史版本选择）
  PlayerView.vue       ← 个人画像（雷达图 + 素养 + 总评 + 故事线 + FAQ Chat）
  SettingsView.vue     ← 模型配置

components/
  RadarChart.vue       ← 双轨雷达图（proportion + depth）
  TimelineCard.vue     ← 单个故事线卡片
  ChatWidget.vue       ← FAQ 对话浮窗
  DateRangeSelector.vue ← 快捷选择 + 手动勾选
  LoadingPanel.vue     ← 分析等待动画
  HistoryDropdown.vue  ← 历史版本下拉

composables/
  useApi.ts            ← 统一 API 请求封装
  useAnalysis.ts       ← 分析状态管理
```

### 9.3 后端集成方式

**方式 A：Vite 代理（推荐开发阶段）**
```js
// vite.config.js
export default {
  server: {
    proxy: {
      '/api': 'http://localhost:5000'
    }
  }
}
```

**方式 B：生产部署**
- `npm run build` → 产物放入 `web/static/dist/`
- Flask 直接 serve 静态文件

### 9.4 关键注意事项

1. **报告时段显示**：`date_range_ids` 应解析为范围摘要（不要直接展示）
2. **雷达图双轨制**：外层雷达必须同时展示 `proportion` 和 `depth` 两条线
3. **API Key 拦截**：需全局处理 `need_config` 错误，引导用户配置
4. **email 参数**：包含 `@` 符号，路由传递需注意编码
5. **level 字段**：内层素养的 `level` 是整数类型，渲染前需转为字符串

---

## 10. 后续任务

- [x] PRD 2.1~2.2 数据清洗管线
- [x] PRD 2.3 Token 预估
- [x] PRD 3.1~3.2 画像提取 + 成长分析
- [x] PRD 3.3 FAQ 智能对话
- [x] Web 后端 API 层（16 个端点）
- [x] Web 前端 Vanilla JS 版（已废弃）
- [x] Web 前端 Vue 3 + Vite 重写（Swiss Modernism × 锻造暖色风格）
- [x] 3D 统一能力图谱（Three.js 水晶柱 + 浮岛可视化）
- [ ] 打磨 System Prompt 提取精度
- [ ] 更多员工数据批量验证

---

## 实时开发日志

---
### 🕒 2026-03-11 14:10 | 🖥️ 窗口/任务: 3D 统一能力图谱开发
- **已完成事项**：
  - 设计并实现了 Three.js 3D 统一能力图谱，替换个人画像页原 2D 雷达图
  - 水晶柱造型经 3 轮迭代：初版锥形 → 仿真六棱柱（82%柱身+18%短锥顶 + flatShading 棱角）
  - 三层基石浮岛（求真→务实→严谨）明确分离悬浮，间距 1.5 单位 + 呼吸动画
  - 色调从冷蓝科幻 → 暖琥珀铜橙色系，与 UI 主色 #C2410C 统一
  - ScorePanel 打分面板：精力占比（黄绿色条）+ 投入深度（橙色点阵）颜色对比分明
  - 新增后端 API: `/api/analysis/<email>/file/<filename>` 加载特定历史版本
  - RosterView 历史版本可点击跳转 PlayerView + ConsoleView 快捷时间范围选择
  - SettingsView/ConsoleView API Key 状态显示修复（has_key → api_key）
- **涉及文件**：
  - `web/frontend/src/components/AbilityChart3D.vue` [新增]
  - `web/frontend/src/components/ScorePanel.vue` [新增]
  - `web/frontend/src/views/PlayerView.vue` [修改：RadarChart → AbilityChart3D + ScorePanel]
  - `web/frontend/src/views/RosterView.vue` [修改：历史版本点击跳转]
  - `web/frontend/src/views/ConsoleView.vue` [修改：快捷时间选择 + API Key 判断]
  - `web/frontend/src/views/SettingsView.vue` [修改：API Key 判断]
  - `web/frontend/src/api/index.js` [修改：新增 getAnalysisByFile]
  - `web/api_routes.py` [修改：新增 file 端点]
- **关键决策/踩坑记录**：
  - LatheGeometry + sides=6 生成六棱水晶，flatShading=true 是棱角可见的关键
  - transmission 过高（>0.3）会让面融合太柔和看不出棱角
  - Vite dev server 需要 host: '0.0.0.0' 才能在 IPv4 上监听
  - 后端 to_safe_dict() 返回 api_key 字段，前端需检查 model.api_key 而非 model.has_key
- **给其他 Agent 的交接/下一步**：
  - DashboardView 团队大盘仍使用 2D Chart.js 聚合雷达图，暂未改为 3D
  - 旧 Vanilla JS 前端代码待用户确认后可移除
---

---
### 🕒 2026-03-11 14:31 | 🖥️ 窗口/任务: 团队大盘聚合策略优化
- **已完成事项**：
  - 修改团队大盘 `/api/analysis/all` 的报告选取策略：从「取时间戳最新的报告」改为「取覆盖周报范围最广（date_range_ids 数量最多）的报告」
  - 在 `pipeline/api.py` 新增 `get_widest_analysis_result(email)` 方法
  - `web/api_routes.py` 的 `get_all_analysis()` 端点切换调用新方法
- **涉及文件**：
  - `pipeline/api.py` [修改：新增 get_widest_analysis_result 方法]
  - `web/api_routes.py` [修改：/api/analysis/all 端点切换聚合逻辑]
- **关键决策/踩坑记录**：
  - 同等 date_range_ids 数量时，优先取文件名逆序最前（即最新生成）的报告
  - 前端 DashboardView.vue 和 RadarChart.vue 无需任何修改，数据结构完全兼容
- **给其他 Agent 的交接/下一步**：
  - `get_analysis_result()` 保持不变仍为「取最新」，仅团队大盘使用新方法
  - 个人画像页 PlayerView 的跳转仍使用 latest 端点，不受影响
---

---
### 🕒 2026-03-11 15:25 | 🖥️ 窗口/任务: 数据清洗状态 Web UI 展示
- **已完成事项**：
  - 后端新增 `GET /api/cleaning-report` 端点，读取 `output/cleaning_report.json` 并增强数据（员工中文名映射、加密文件按员工分组）
  - 前端新增 `CleaningView.vue` 数据清洗状态页面（概览卡片+管线指标+员工周报对照表+加密文件折叠清单）
  - 路由注册 `/cleaning`，侧栏导航新增「数据清洗」入口
  - 新增 2 个后端单元测试（22 个全通过）
  - 员工周报数按中位数标记状态：正常/偏少/严重缺失
- **涉及文件**：
  - `web/api_routes.py` [修改：新增 cleaning-report 端点]
  - `web/frontend/src/views/CleaningView.vue` [新增]
  - `web/frontend/src/router/index.js` [修改：新增 /cleaning 路由]
  - `web/frontend/src/layouts/AppLayout.vue` [修改：侧栏新增导航]
  - `web/frontend/src/api/index.js` [修改：新增 getCleaningReport]
  - `tests/test_web_api.py` [修改：新增 2 个测试]
- **关键决策/踩坑记录**：
  - 员工周报数量判定阈值：中位数 ×0.6 为严重缺失，×0.8 为偏少
  - cleaning_report.json 需要由清洗管线运行后生成到 output/ 目录
- **给其他 Agent 的交接/下一步**：
  - 页面仅展示静态清洗报告数据，不触发清洗操作
  - 若需支持在页面上重新运行清洗管线，可新增 POST 端点
---

---
### 🕒 2026-03-11 16:00 | 🖥️ 窗口/任务: 数据清洗日期解析 Bug 修复
- **已完成事项**：
  - 调查确认 hezongfeng 数据清洗问题根因：56附件→2加密→54文件→63 Sheet→去重→51条记录（数量正确）
  - 修复 `parse_date_from_text` 短日期跨年解析 Bug：增加从文本中动态提取 `reference_year` 的逻辑
  - 修复 `_parse_sheet_records` 日期提取优先级：Sheet名 > 文件名 > 内容A列
  - 新增 3 个单元测试（164 个全通过）
  - 端到端验证：51条/51唯一日期/0重复H2/4个修复日期全部正确
- **涉及文件**：
  - `pipeline/utils.py` [修改：parse_date_from_text 增加智能 reference_year 推断]
  - `pipeline/auto_discovery.py` [修改：_parse_sheet_records 日期提取优先级调整]
  - `tests/test_noise_reduction.py` [修改：新增 3 个日期解析测试]
- **关键决策/踩坑记录**：
  - `reference_year=2025` 硬编码导致 `12/30 ~ 1/3` 被解析为 2025-12-30 而非 2024-12-30
  - 日期优先级需区分多Sheet和单Sheet文件：Sheet名对多Sheet文件最精确（每Sheet有独立日期），文件名对单Sheet文件有效（Sheet名通常只是「周报」）
  - 首次将文件名设为最高优先级时产生副作用（多Sheet文件日期被覆盖），随后调整为 Sheet名 > 文件名 > 内容A列
- **给其他 Agent 的交接/下一步**：
  - 其他员工的缓存如有类似问题，需删除 `output/cache/<email>/` 目录后重新触发清洗
  - 如需全局重新跑批，可运行 `python scripts/run_pipeline.py`
---

---
### 🕒 2026-03-11 16:20 | 🖥️ 窗口/任务: liaohuaming 清洗核验 + 日期正则兼容性修复
- **已完成事项**：
  - 核验 liaohuaming：58附件→3加密→55有效→63 Sheet→去重8组→52条（非用户看到的28条，旧报告数据）
  - 修复 `parse_date_from_text` 正则：`日` 改为 `日?`（可选），支持 `2025年6月23-2025年6月29` 缺少「日」字的格式
  - 全量重跑清洗管线（`run_pipeline.py --report`），更新 `cleaning_report.json` 和全员 Markdown
- **涉及文件**：
  - `pipeline/utils.py` [修改：日期正则 `日` → `日?`]
  - `output/cleaning_report.json` [重新生成]
- **关键决策/踩坑记录**：
  - 用户 Web UI 看到的 28 份来自旧 `cleaning_report.json`，重跑后更新为 52 份
  - `parse_date_from_text` 的完整格式正则和短格式正则均需要 `日?` 可选匹配
- **给其他 Agent 的交接/下一步**：
  - `cleaning_report.json` 已全局更新，所有员工数据已基于最新代码重新生成
---

---
### 🕒 2026-03-11 16:32 | 🖥️ 窗口/任务: 去重阈值调整（0.94→0.98）+ wukaijian 核验
- **已完成事项**：
  - 核验 wukaijian：47份是去重组1（9月8日~10月11日 7份被合并）和组2（12月1日~12月20日 3份合并）导致
  - 根因：连续多周工作内容高度相似（同一项目持续Debug），被94%阈值合法去重
  - 将去重阈值从 0.94 提高到 0.98，wukaijian 从 47→49 份，zhangzhengqiang 从 50→51 份
  - 重跑全量管线并更新 `cleaning_report.json`
- **涉及文件**：
  - `pipeline/noise_reduction.py` [修改：`deduplicate_sheets` 和 `flatten_and_deduplicate` 默认阈值 0.94→0.98]
  - `scripts/run_pipeline.py` [修改：默认阈值和帮助文本同步更新]
  - `output/cleaning_report.json` [重新生成]
- **关键决策/踩坑记录**：
  - 98% 阈值仍能正确去重多Sheet文件中的完全重复Sheet（100%相似度），同时保留连续多周内容相似但不同周期的独立周报
  - 全量结果：746 Sheet → 609 去重后（89组），12 员工，164 测试全部通过
- **给其他 Agent 的交接/下一步**：
  - 如需进一步调整阈值，修改 `pipeline/noise_reduction.py` 中的默认值即可
  - Web UI 数据清洗页面刷新即可看到最新数据
---

---
### 🕒 2026-03-11 17:15 | 🖥️ 窗口/任务: 英雄榜历史列表增加周报时间范围显示
- **已完成事项**：
  - 后端 `/api/analysis/<email>/history` 端点新增返回 `date_range_ids` 字段
  - 前端 `RosterView.vue` 历史版本列表每行下方新增周报时间范围摘要（如 `2025-01-06 ~ 2026-01-09 · 52周`）
  - 新增 1 个后端单元测试（23 个全通过）
- **涉及文件**：
  - `web/api_routes.py` [修改：history 端点新增 date_range_ids 字段]
  - `web/frontend/src/views/RosterView.vue` [修改：新增 compressDateRanges 函数 + 时间范围行 + 样式]
  - `tests/test_web_api.py` [修改：新增 test_get_analysis_history_includes_date_range_ids]
- **关键决策/踩坑记录**：
  - Flask `debug=True` 的 werkzeug reloader 在 Windows 上首次文件修改未被检测到，导致长时间运行旧代码。需要二次修改文件或手动重启 Flask 来触发 reloader
  - 历史版本中 `date_range_ids` 最多可含 52+ 个元素，前端只提取所有日期的最小值和最大值压缩显示
- **给其他 Agent 的交接/下一步**：
  - 英雄榜历史列表现在可以直接看到每份报告覆盖的周报时间范围，无需点进去查看
---

---
### 🕒 2026-03-11 17:45 | 🖥️ 窗口/任务: 项目 Git 初始化与 GitHub 部署
- **已完成事项**：
  - 数据脱敏：清除 `deepseek_deepseek-reasoner.json` 中的明文 API Key
  - 旧 Vanilla JS 前端代码永久删除（`web/static/` + `web/templates/`）
  - `web/app.py` 重写：移除旧模板路由，新增 CORS 支持 + 模型配置自动初始化
  - 创建根目录 `.gitignore`：排除 attachments/、output/、config/models/*.json、__pycache__/、node_modules/ 等敏感/构建目录
  - `requirements.txt` 补充 flask + flask-cors 依赖
  - 编写 `README.md`（项目简介、技术栈、目录结构、快速开始、API 文档）
  - 编写 `start.bat` 一键启动脚本（自动创建虚拟环境、安装依赖、初始化配置、启动前后端）
  - 新增 `tests/test_empty_project.py` 空项目管线验证测试（7 个用例）
  - 全部 172 个测试通过（165 原有 + 7 新增）
  - Git 初始化并推送到 `git@github.com:xqy281/CPE-Forge.git`（75 个文件，16197 行）
- **涉及文件**：
  - `.gitignore` [新增]
  - `README.md` [新增]
  - `start.bat` [新增]
  - `tests/test_empty_project.py` [新增]
  - `web/app.py` [重写]
  - `requirements.txt` [修改]
  - `config/models/deepseek_deepseek-reasoner.json` [脱敏]
  - `web/static/` [删除]
  - `web/templates/` [删除]
- **关键决策/踩坑记录**：
  - `config/models/*.json` 整体纳入 .gitignore，新环境首次运行 `init_default_configs()` 自动生成空 Key 的默认预设
  - litellm 冷启动导入极慢（4+ 分钟），空项目管线验证采用 pytest 框架运行以复用已有 import 缓存
  - flask-cors 是新增的运行时依赖，用于开发模式下 Vite :5173 → Flask :5000 跨域访问
- **给其他 Agent 的交接/下一步**：
  - 新电脑克隆后运行 `start.bat` 即可一键启动
  - 需要将周报 Excel 数据拷贝到 `attachments/` 目录，并在模型配置页面设置 API Key
  - 如需在 output/ 下使用已有的分析缓存，需手动拷贝 output/ 目录
---

---
### 🕒 2026-03-11 18:55 | 🖥️ 窗口/任务: EML 邮件日期校准管线
- **已完成事项**：
  - 核查 xiaoqianyun 年份错误：6个「软件部」文件（2026年1~3月）文件名误写为 `2025年`
  - 新建 `pipeline/eml_extractor.py`：从 EML 构建「附件文件名→邮件发送日期」映射表
  - 集成到 `auto_discovery.py`：日期解析后自动校准年份，含跨年保护逻辑
  - 修改 `scripts/run_pipeline.py`：新增 `--emails` 参数，新增「阶段0: EML 校准映射」
  - 修改 `pipeline/api.py`：`CPEPipelineAPI.__init__()` 新增 `emails_dir` 参数
  - 修复跨年保护 Bug：12月文件+1月邮件不校准（如 `12月29日-01月09日` 在1月9日提交）
  - 662 个唯一附件映射构建，xiaoqianyun 6个错误年份全部校准为 2026
- **涉及文件**：
  - `pipeline/eml_extractor.py` [新建：EML 解析 + 校准映射 + 年份校准函数]
  - `pipeline/auto_discovery.py` [修改：集成 calibration_map 参数]
  - `pipeline/api.py` [修改：集成 emails_dir 参数]
  - `scripts/run_pipeline.py` [修改：新增 --emails 参数 + 阶段0]
- **关键决策/踩坑记录**：
  - 不使用 From 字段做员工识别（转发邮件的 From 是 dongshufeng 而非原始发送者）
  - 跨年保护：文件名月份 ≥11 且邮件发送在次年 1~2 月时跳过校准
  - 同一附件出现在多封邮件中时保留最早的发送日期（原始邮件通常最早）
- **给其他 Agent 的交接/下一步**：
  - 跑批命令更新：`python scripts/run_pipeline.py --input attachments --output output --report --emails emails`
  - Web API 初始化更新：`CPEPipelineAPI(attachments_dir, output_dir, emails_dir="emails")`
  - `web/app.py` 中已同步传入 emails_dir ✅
---

---
### 🕒 2026-03-11 19:04 | 🖥️ 窗口/任务: 空项目启动流程集成（只需 emails/ 即可一键启动）
- **已完成事项**：
  - `start.bat` 新增步骤5「数据准备」：自动检测 emails/ → 提取附件 → 运行清洗管线
  - `web/app.py` 新增 `EMAILS_DIR` 路径配置并注入 Flask config
  - `web/api_routes.py` 的 `get_pipeline()` 传入 `emails_dir` 启用运行时年份校准
  - 智能跳过逻辑：attachments 已有数据则跳过提取，cleaning_report.json 已存在则跳过清洗
- **涉及文件**：
  - `start.bat` [修改：6步流程，新增步骤5数据准备]
  - `web/app.py` [修改：新增 EMAILS_DIR]
  - `web/api_routes.py` [修改：get_pipeline 传入 emails_dir]
- **关键决策/踩坑记录**：
  - 空项目启动流程：emails/ → extract.py 提取 → run_pipeline.py 清洗 → Flask 启动
  - 每个步骤都有幂等检测（已存在则跳过），多次重启不会重复执行
- **给其他 Agent 的交接/下一步**：
  - 从空项目部署只需：代码 + emails/ 目录 + `start.bat` 一键启动
  - 如需强制重跑清洗：删除 `output/cleaning_report.json` 后重启
---

---
### 🕒 2026-03-14 15:30 | 🖥️ 窗口/任务: start.bat 彻底重写与部署修复
- **已完成事项**：
  - 彻底重写 `start.bat`：**去除所有中文消息**（chcp 65001 下 cmd.exe 对 UTF-8 中文字节解析不稳定），全英文输出
  - 用 **`goto` 跳转**替代所有嵌套 `if/else` 块（cmd.exe 嵌套 if 中括号/特殊字符会被错误解析）
  - 新增**后端健康检查轮询**：每 5 秒用 Python urllib 探测 `http://127.0.0.1:5000/api/employees`，最多等 5 分钟。确保 Flask 就绪后才启动前端
  - `web/app.py` Flask host `0.0.0.0` → `127.0.0.1`（修复虚拟网卡环境 ECONNREFUSED）
  - `vite.config.js` proxy target `localhost` → `127.0.0.1`
  - `.gitattributes` 强制 `*.bat eol=crlf`
  - 全流程验证通过：6 步全部成功，无乱码，后端就绪后前端正常启动
- **涉及文件**：
  - `start.bat` [彻底重写：goto 流程 + 英文消息 + 后端轮询]
  - `web/app.py` [修改：host 127.0.0.1]
  - `web/frontend/vite.config.js` [修改：proxy 127.0.0.1]
  - `.gitattributes` [新增]
- **关键决策/踩坑记录**：
  - `chcp 65001` + cmd.exe 对中文 UTF-8 字节不稳定：`或`、`（）` 等汉字的字节恰好构成可执行命令名或语法符号
  - `.bat` 文件必须 CRLF，LF 会导致 cmd.exe 无声退出（exit code 1 无输出）
  - `::` 在 `if/for` 块内是标签会破坏块结构；嵌套 `if/else` 中括号也易出错 → 统一用 `goto`
  - litellm 首次导入需 4+ 分钟，固定 2 秒等待远远不够 → 用健康检查轮询
- **给其他 Agent 的交接/下一步**：
  - 全新部署：`git clone` + 放入 `emails/` + 双击 `start.bat` 即可
  - 目标机器需预装 Python 3.10+ 和 Node.js 18+
---

---
### 🕒 2026-03-12 08:30 | 🖥️ 窗口/任务: 修复 EML 提取转发邮件分类错误（dongshufeng 问题）
- **已完成事项**：
  - 克隆环境全新跑批时多出 `dongshufeng@jointelli.com` 目录（1份周报）
  - 根因：`extract_attachments_from_eml_dir()` 用 `From` 头做目录分类，转发邮件的 From 是转发者
  - 当前环境不复现是因为 attachments/ 已有正确数据，跳过了提取步骤
  - 重写为两步走策略：
    1. 第一遍：从非转发邮件学习「员工姓名→邮箱」映射（如 `吴开健→wukaijian@jointelli.com`）
    2. 第二遍：用附件文件名中的员工姓名查映射表确定正确邮箱目录
  - 验证通过：13个正确目录，dongshufeng 不再出现，37个测试全部通过
- **涉及文件**：
  - `pipeline/eml_extractor.py` [修改：重写 extract_attachments_from_eml_dir 两步走策略]
- **关键决策/踩坑记录**：
  - 转发邮件 EML 文件名通常包含「转发」关键词，可用于识别跳过（第一遍映射构建时跳过）
  - 映射表查不到时 fallback 到 From 头（安全兜底）
  - 利用 `pipeline.utils.extract_employee_name_from_filename` 从附件文件名提取员工中文姓名
- **给其他 Agent 的交接/下一步**：
  - 克隆环境重跑：删除 `attachments/` 和 `output/cleaning_report.json`，重新执行 `start.bat`
  - 如需新增员工，确保至少有一封该员工的非转发邮件，映射才能自动建立
---

---
### 🕒 2026-03-12 09:00 | 🖥️ 窗口/任务: 局域网访问支持
- **已完成事项**：
  - Flask 后端 `host` 从 `127.0.0.1` 改回 `0.0.0.0`，允许局域网内其他设备通过本机 IP 访问后端 API
  - Vite 前端已有 `host: '0.0.0.0'` 配置，无需修改
  - CORS 已配置 `origins: "*"`，局域网跨域无障碍
- **涉及文件**：
  - `web/app.py` [修改：host 127.0.0.1 → 0.0.0.0]
- **关键决策/踩坑记录**：
  - 之前因 WSL/Hyper-V 虚拟网卡问题将 host 改为 127.0.0.1，现在用户有局域网共享需求，改回 0.0.0.0
  - Vite 的 `/api` 代理是服务端侧转发（Vite→Flask），代理目标保持 `127.0.0.1:5000` 不影响
  - Windows 防火墙首次监听 0.0.0.0 时会弹出放行提示，需用户点击「允许访问」
- **给其他 Agent 的交接/下一步**：
  - 局域网用户访问 `http://<本机IP>:5173` 即可使用完整平台
  - 如遇虚拟网卡绑定问题，可考虑指定具体网卡 IP 而非 0.0.0.0
---

---
### 🕒 2026-03-12 10:40 | 🖥️ 窗口/任务: System Prompt 工程素养量化精度打磨
- **已完成事项**：
  - 全面重写 `prompts/profile_system.md`，提升内层素养（工程素养成熟度）评分精度
  - 新增「⚠️ 自我美化偏差警告」段落，教 LLM 穿透"解决了XX"的表面叙述
  - 重写三维度等级定义表（Lv1~Lv5），Lv4 锚定为「需有重构/解耦/抽象证据」
  - 新增「反模式信号词典」（9 类反模式），基于全员 13 人周报 grep 提取
  - 反模式类别：阻塞式补丁、关注点耦合、状态回避、旁路劫持、结构扭曲、修而不治、临时方案长期化、暴力覆盖、延时调参法
  - 新增 3 个反例 Few-Shot + 1 个正例 Few-Shot（示例三~六）
  - 证据格式改为 `[+]`/`[-]` 前缀标记正负向，评级是博弈结果
  - 新增 1 个单元测试（`test_prompt_contains_anti_pattern_framework`），13 个测试全通过
- **涉及文件**：
  - `prompts/profile_system.md` [重写：反模式检测框架 + 话术免疫 + 精细等级定义]
  - `tests/test_profile_extractor.py` [修改：新增 Prompt 关键段落检测测试]
- **关键决策/踩坑记录**：
  - 反模式词典不能只基于单一员工，需覆盖全员：liuzhibin 大量延时补丁、linyi sleep 但承认根因未究、xiaoqianyun 有重构也有临时 patch、yetianxiang 消除硬编码改配置化
  - JSON 输出格式完全不变，前端无需修改
  - 旧提取结果（如 hezongfeng Lv4/Lv4/Lv4）需重新跑 LLM 才会更新
- **给其他 Agent 的交接/下一步**：
  - 用户需手动重跑 LLM 分析：`python scripts/run_llm_analysis.py --email hezongfeng@jointelli.com --profile-only`
  - 建议全员批量重跑以更新所有分析缓存
  - 如评分区分度仍不够，可进一步调整反模式信号的严重程度阈值
---

---
### 🕒 2026-03-12 11:10 | 🖥️ 窗口/任务: Growth System Prompt 精度打磨
- **已完成事项**：
  - 全面重写 `prompts/growth_system.md`，提升成长分析提取精度
  - 新增**闭环质量评判** `closure_quality`（5级：root_fix / systematic_fix / workaround / escalated / inconclusive）
  - 新增**中间模式** `surface_patch`（排查有序但方案治标），补充 depth_first 和 trial_error 之间的空白
  - 新增**反复修补时间线洞察** `recurring_fix_patterns`（识别同模块跨多周反复 bug fix 无重构的模式）
  - 扩展 `growth_analyzer.py` 校验逻辑：closure_quality 合法值校验、surface_patch pattern、recurring_fix_patterns 校验
  - 新增 8 个单元测试，全部 34 个测试通过
- **涉及文件**：
  - `prompts/growth_system.md` [重写：闭环质量 + 中间模式 + 反复修补]
  - `pipeline/growth_analyzer.py` [修改：新增校验逻辑]
  - `tests/test_growth_analyzer.py` [修改：新增 8 个测试]
- **关键决策**：
  - JSON 输出格式向后兼容：新增字段有默认值，旧格式数据不受影响
  - 旧 growth 分析结果需重新跑 LLM 才会包含新增字段
---

---
### 🕒 2026-03-12 12:00 | 🖥️ 窗口/任务: 画像页面 UI 适配新增量化字段
- **已完成事项**：
  - **ScorePanel 证据正负向颜色区分**：展示全部证据（移除截断），`[+]` 绿色圆形图标+浅绿背景，`[-]` 红色圆形图标+浅红背景
  - **TimelineCard 闭环质量标签**：新增五色标签（`根因修复`绿 / `体系化优化`蓝 / `临时规避`橙 / `上报原厂`灰 / `未定论`浅灰）
  - **工程债务追踪板块**：新增整个板块展示 `recurring_fix_patterns`，包含模块名+修补次数+跨越周数+重构标记+风险横幅
  - 成长递进分析 badge 新增 `surface_patch`（排查有序/方案治标）中间模式支持
- **涉及文件**：
  - `web/frontend/src/components/ScorePanel.vue` [修改：证据正负向渲染]
  - `web/frontend/src/components/TimelineCard.vue` [修改：闭环质量标签]
  - `web/frontend/src/views/PlayerView.vue` [修改：新增工程债务追踪板块]
- **关键决策**：
  - `has_refactor=false` 时卡片顶部显示红色「工程债务风险区」横幅 + 数字变红
  - `has_refactor=true` 时显示绿色「已重构」标签，视为正向成长弧线
---

---
### 🕒 2026-03-12 12:24 | 🖥️ 窗口/任务: 团队大盘贡献者卡片功能
- **已完成事项**：
  - 新增 `ContributorCard.vue` 贡献者技术维度卡片组件（精简版 ScorePanel，仅 5 维度打分）
  - 重写 `DashboardView.vue`：雷达图上方增加 pill 样式维度筛选按钮组 + 下方贡献者卡片网格
  - 默认展示全部贡献者卡片，标题「全部贡献者（N人）」+ 提示文案
  - 点击维度筛选按钮后筛选 proportion > 0 的贡献者，**按该维度 proportion 降序排序**，雷达图聚合数据联动更新
  - 再次点击取消筛选，卡片切换使用 transition-group 动画
  - 贡献者姓名可点击跳转个人画像页面
- **涉及文件**：
  - `web/frontend/src/components/ContributorCard.vue` [新增]
  - `web/frontend/src/views/DashboardView.vue` [重写]
- **关键决策/踩坑记录**：
  - 后端 API 无修改，现有 `/api/analysis/all` 返回的 results 已包含完整 profile 数据
  - 雷达图聚合数据基于 filteredContributors 计算（筛选联动效果）
  - ContributorCard 不含工程素养基石，证据链内容在大盘展示不合适
- **给其他 Agent 的交接/下一步**：
  - 目前仅 3 位员工有分析数据，更多员工跑完 LLM 分析后卡片会自动增加
  - 如需按其他条件筛选（如按素养等级），可扩展 selectedDim 逻辑
---
