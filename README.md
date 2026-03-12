# CPE-Forge

> **CPE 研发效能与人才画像 AIGC 分析平台**
>
> 通过 AIGC 技术深度解析 CPE 嵌入式软件团队的 Excel 周报数据，清洗去噪后转换为大模型友好的格式，最终输出包含「双层能力雷达图」和「成长时间轴」的分析报告。

---

## ✨ 核心功能

| 模块 | 说明 |
|------|------|
| **智能数据清洗** | 自动识别 Excel 周报、TF-IDF 去重、时间线重构 |
| **双层能力画像** | 外层 5 维度技术雷达（双轨：精力占比 + 投入深度）+ 内层 3 维度素养基石（含正负向证据标记） |
| **成长时间轴** | 问题闭环追踪 + 闭环质量5级评判 + 剥洋葱/表层收敛/乱试验模式识别 |
| **工程债务追踪** | 识别同模块长期反复修补未重构的技术债务积累，量化修补次数与跨越周数 |
| **团队大盘** | 全员能力雷达聚合 + 维度筛选 + 贡献者技术维度卡片（按贡献度排序） |
| **FAQ 智能对话** | 全量周报上下文注入，支持多轮对话 |
| **3D 可视化** | Three.js 水晶柱能力图谱 + 浮岛素养展示 |

---

## 🏗️ 技术栈

| 层 | 技术 |
|----|------|
| 后端 | Python 3.13+ / Flask / LiteLLM |
| 前端 | Vue 3 (Composition API) / Vite / Pinia / Three.js / Chart.js |
| AI | DeepSeek / GPT-4o / Claude / Gemini（通过 LiteLLM 统一调用） |
| 数据处理 | openpyxl / scikit-learn / tiktoken |

---

## 📁 目录结构

```
CPE-Forge/
├── pipeline/                # 核心管线代码
│   ├── api.py               #   统一 API 入口（清洗+分析+对话）
│   ├── eml_extractor.py     #   EML 邮件解析、附件提取、年份校准
│   ├── auto_discovery.py    #   Excel 智能识别与过滤
│   ├── noise_reduction.py   #   TF-IDF 去重与时间线重构
│   ├── llm_client.py        #   LLM 统一调用层（LiteLLM）
│   ├── llm_config.py        #   模型独立配置管理系统
│   ├── profile_extractor.py #   双层能力画像提取
│   ├── growth_analyzer.py   #   成长时间轴分析
│   ├── faq_chat.py          #   FAQ 智能对话引擎
│   ├── token_estimator.py   #   Token 预估
│   ├── models.py            #   数据模型定义
│   └── utils.py             #   工具函数
├── web/
│   ├── app.py               # Flask 应用入口
│   ├── api_routes.py        # RESTful API 路由（16+ 端点）
│   └── frontend/            # Vue 3 + Vite 前端
│       ├── src/
│       │   ├── views/       #   页面组件
│       │   ├── components/  #   公共组件（3D图谱、雷达图等）
│       │   ├── api/         #   API 请求封装
│       │   └── layouts/     #   布局组件
│       └── package.json
├── prompts/                 # LLM System Prompt 模板
├── config/models/           # 模型配置（运行时自动生成，含 API Key）
├── tests/                   # 单元测试（34+ 核心 pipeline 测试）
├── scripts/                 # 清洗管线与调试脚本
├── emails/                  # [需用户提供] 周报邮件 EML 文件（推荐）
├── attachments/             # [自动生成] 从 EML 提取的 Excel 附件
├── output/                  # [自动生成] 清洗结果与分析缓存
├── requirements.txt         # Python 依赖
├── start.bat                # Windows 一键启动脚本
└── README.md
```

---

## 📋 环境要求

| 依赖 | 版本 | 说明 |
|------|------|------|
| **Python** | 3.10+ | 后端运行时 |
| **Node.js** | 18+ | 前端构建（含 npm） |
| **Git** | 任意 | 克隆仓库 |

> ⚠️ Windows 用户请确保 `python` 和 `npm` 命令在系统 PATH 中可用。缺少 Node.js 时 `start.bat` 会自动降级为仅后端模式运行。

---

## 🚀 快速开始

### 方式一：一键启动（推荐）

```bash
# 克隆仓库
git clone git@github.com:xqy281/CPE-Forge.git
cd CPE-Forge

# 运行启动脚本（自动安装依赖、初始化配置、启动服务）
start.bat
```

### 方式二：手动启动

```bash
# 1. 创建 Python 虚拟环境
python -m venv .venv
.venv\Scripts\activate

# 2. 安装 Python 依赖
pip install -r requirements.txt

# 3. 初始化默认模型配置
python -c "from pipeline.llm_config import init_default_configs; init_default_configs()"

# 4. 安装前端依赖
cd web\frontend
npm install
cd ..\..

# 5. 数据清洗（从 EML 提取 + 年份校准 + 去重）
python scripts/run_pipeline.py --input attachments --output output --report --emails emails

# 6. 启动后端（端口 5000）
python -m web.app

# 7. 启动前端（另开终端，端口 5173）
cd web\frontend
npm run dev
```

启动后访问 **http://localhost:5173** 即可使用。

---

## 🌐 局域网共享

平台默认监听 `0.0.0.0`，同一局域网内的其他设备可以直接访问。

1. 查看本机 IP：

```bash
ipconfig    # Windows
```

2. 将地址分享给同事：

```
http://<你的IP>:5173
```

例如：`http://192.168.1.100:5173`

> ⚠️ 首次启动时 Windows 防火墙可能弹出放行提示，请点击「允许访问」。访问者需与你处于同一 WiFi / 有线网段。

---

## 📦 数据准备

### 方式一：EML 邮件（推荐）

将周报邮件的 `.eml` 文件放入 `emails/` 目录即可，启动时自动提取附件并校准日期：

```
emails/
├── 工作周报_张三(2025年1月6日~1月11日).eml
├── 工作周报_张三(2025年1月13日~1月17日).eml
└── ...
```

> 优势：邮件的 `Date` 头可自动校准附件文件名中的年份错误（如员工2026年的周报文件名误写为2025年）

### 方式二：直接放入 Excel

将员工周报 Excel 文件按发件人邮箱分目录放入 `attachments/`：

```
attachments/
├── zhangsan@company.com/
│   ├── 工作周报_张三(2025年1月6日~1月11日).xlsx
│   └── ...
├── lisi@company.com/
│   └── ...
```

### 2. 配置 LLM API Key

启动后进入 **模型配置** 页面（`/settings`），为需要使用的模型填入 API Key。

也可直接编辑 `config/models/` 下的 JSON 文件，修改 `api_key` 字段：

```json
{
  "model_id": "deepseek/deepseek-chat",
  "api_key": "sk-你的密钥",
  ...
}
```

---

## 🔌 API 端点一览

> 所有端点以 `/api` 为前缀

| 方法 | 端点 | 说明 |
|------|------|------|
| GET | `/api/employees` | 获取员工列表 |
| GET | `/api/employees/<email>/ranges` | 获取可用周报时间范围 |
| GET | `/api/models` | 获取所有模型配置 |
| PUT | `/api/models/<model_id>` | 更新模型配置 |
| POST | `/api/estimate-tokens` | Token 预估 |
| POST | `/api/analysis/full` | 触发完整分析 |
| POST | `/api/analysis/profile` | 仅画像提取 |
| POST | `/api/analysis/growth` | 仅成长分析 |
| GET | `/api/analysis/<email>/latest` | 最新分析结果 |
| GET | `/api/analysis/<email>/history` | 历史分析列表 |
| GET | `/api/analysis/status` | 全员缓存状态 |
| GET | `/api/analysis/all` | 团队大盘聚合 |
| GET | `/api/cleaning-report` | 数据清洗报告 |
| POST | `/api/chat/start` | 创建 FAQ 对话 |
| POST | `/api/chat/send` | 发送对话消息 |
| GET | `/api/chat/<session_id>/history` | 对话历史 |

---

## 🧪 运行测试

```bash
# 激活虚拟环境后
python -m pytest tests/ -v
```

---

## 📜 许可证

私有项目，仅限内部使用。
