@echo off
chcp 65001 >nul
setlocal EnableDelayedExpansion

echo ================================================
echo win-computer-use 一键安装
echo ================================================

REM 检查 Python 是否已安装
python --version >nul 2>&1
if errorlevel 1 (
    echo [错误] 未找到 Python，请先安装 Python 3.10+
    echo 下载地址：https://www.python.org/downloads/
    pause
    exit /b 1
)

REM 检查 Python 版本
for /f "tokens=2" %%i in ('python --version 2^>^&1') do set PY_VERSION=%%i
echo [信息] 检测到 Python %PY_VERSION%

REM 创建虚拟环境（可选）
set /p CREATE_VENV="是否创建虚拟环境？(Y/N，推荐 Y): "
if /i "!CREATE_VENV!"=="Y" (
    if not exist .venv (
        echo [1/3] 创建 Python 虚拟环境...
        python -m venv .venv
    )
    echo [2/3] 激活虚拟环境并安装依赖...
    call .venv\Scripts\activate.bat
    pip install --upgrade pip
    pip install -e .
) else (
    echo [2/3] 在全局环境安装依赖...
    pip install --upgrade pip
    pip install -e .
)

REM 可选：安装 FastAPI（服务器模式）
echo [3/3] 是否安装 FastAPI 服务器？(Y/N)
set /p INSTALL_FASTAPI=
if /i "!INSTALL_FASTAPI!"=="Y" (
    pip install -e ".[server]"
    echo FastAPI 已安装
)

echo ================================================
echo 安装完成！
echo ================================================
echo.
echo 现在可以运行：
echo   win-computer-use --help
echo   win-computer-use screenshot --output test.png
echo   win-computer-use-server  (启动 HTTP 服务器)
echo.
pause
