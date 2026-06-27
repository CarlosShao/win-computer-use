@echo off
REM start_server.bat - 启动 win-computer-use FastAPI 服务
REM 需要在项目根目录下运行

set PORT=8000
set HOST=127.0.0.1

if not "%1"=="" set PORT=%1

echo [win-computer-use] 正在启动 FastAPI 服务...
echo [win-computer-use] 地址: http://%HOST%:%PORT%
echo [win-computer-use] 按 Ctrl+C 停止服务
echo.

.venv\Scripts\python.exe scripts\server.py --port %PORT% --host %HOST%
