@echo off
chcp 65001 >nul
title CPE-Forge 一键启动

echo ============================================
echo   CPE-Forge 研发效能与人才画像 AIGC 平台
echo ============================================
echo.

:: 获取脚本所在目录作为项目根目录
set "PROJECT_DIR=%~dp0"
cd /d "%PROJECT_DIR%"

:: ============================================
:: 1. Python 虚拟环境
:: ============================================
echo [1/6] 检查 Python 虚拟环境...
if not exist ".venv\Scripts\activate.bat" (
    echo       创建虚拟环境中...
    python -m venv .venv
    if errorlevel 1 (
        echo [错误] 创建虚拟环境失败，请确保已安装 Python 3.10+
        pause
        exit /b 1
    )
    echo       虚拟环境已创建
) else (
    echo       已存在
)
call .venv\Scripts\activate.bat

:: ============================================
:: 2. Python 依赖
:: ============================================
echo [2/6] 安装 Python 依赖...
pip install -r requirements.txt -q
if errorlevel 1 (
    echo [错误] Python 依赖安装失败
    pause
    exit /b 1
)
echo       完成

:: ============================================
:: 3. 初始化模型配置
:: ============================================
echo [3/6] 初始化默认模型配置...
python -c "from pipeline.llm_config import init_default_configs; init_default_configs()"
echo       完成（配置文件位于 config/models/）

:: ============================================
:: 4. 前端依赖
:: ============================================
echo [4/6] 检查前端依赖...
set "SKIP_FRONTEND=0"
where npm >nul 2>nul
if errorlevel 1 (
    echo.
    echo [警告] 未检测到 Node.js / npm！前端界面无法启动。
    echo        请从以下地址下载安装 Node.js 18+：
    echo        https://nodejs.org/
    echo.
    echo        安装完成后重新运行本脚本即可。
    echo        现在将以「仅后端」模式继续启动...
    echo.
    set "SKIP_FRONTEND=1"
) else (
    if not exist "web\frontend\node_modules" (
        echo       安装 npm 依赖中...
        cd web\frontend
        call npm install
        if errorlevel 1 (
            echo [错误] npm install 失败
            pause
            exit /b 1
        )
        cd ..\..
        echo       完成
    ) else (
        echo       已存在
    )
)

:: 创建必要目录
if not exist "attachments" mkdir attachments
if not exist "output" mkdir output

:: ============================================
:: 5. 数据准备（清洗管线 — 含 EML 提取 + 年份校准）
:: ============================================
echo [5/6] 数据准备...

:: 如果 cleaning_report.json 不存在，运行清洗管线
:: run_pipeline.py 会自动检测 attachments 为空时从 EML 提取附件
if not exist "output\cleaning_report.json" (
    if exist "emails" (
        echo       运行清洗管线（含 EML 附件提取 + 年份校准）...
        .venv\Scripts\python.exe scripts/run_pipeline.py --input attachments --output output --report --emails emails
    ) else if exist "attachments" (
        echo       运行清洗管线...
        .venv\Scripts\python.exe scripts/run_pipeline.py --input attachments --output output --report
    ) else (
        echo       未检测到 emails/ 或 attachments/ 目录，跳过清洗
    )
) else (
    echo       清洗报告已存在，跳过清洗
)
echo       完成

:: ============================================
:: 6. 启动服务
:: ============================================
echo [6/6] 启动服务...

:: 后台启动 Flask 后端
echo       启动后端 (Flask :5000)...
start "CPE-Forge Backend" cmd /c "cd /d %PROJECT_DIR% && .venv\Scripts\python.exe -m web.app"

:: 等待后端启动
timeout /t 2 /nobreak >nul

if "%SKIP_FRONTEND%"=="0" (
    REM 后台启动 Vite 前端
    echo       启动前端 (Vite :5173^)...
    start "CPE-Forge Frontend" cmd /c "cd /d %PROJECT_DIR%\web\frontend && npm run dev"

    REM 等待前端启动
    timeout /t 3 /nobreak >nul

    REM 打开浏览器
    echo.
    echo ============================================
    echo   服务已启动！
    echo   前端地址: http://localhost:5173
    echo   后端地址: http://localhost:5000
    echo ============================================
    start http://localhost:5173
) else (
    echo.
    echo ============================================
    echo   后端已启动！（前端未启动 — 缺少 Node.js）
    echo   后端地址: http://localhost:5000/api/employees
    echo   请安装 Node.js 18+ 后重新运行以启用 Web 界面
    echo ============================================
)
echo.
echo   首次使用请：
echo   1. 将周报 EML 放入 emails/ 目录，重启即自动提取和清洗
echo   2. 也可将周报 Excel 直接放入 attachments/ 目录
echo   3. 在「模型配置」页面设置 API Key
echo ============================================

echo.
echo 按任意键关闭此窗口（不影响已启动的服务）
pause >nul
