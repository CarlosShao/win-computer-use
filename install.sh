#!/bin/bash
set -e

echo "================================================"
echo "win-computer-use 一键安装"
echo "================================================"

# 检查 Python 是否已安装
if ! command -v python3 &> /dev/null; then
    echo "[错误] 未找到 Python，请先安装 Python 3.10+"
    echo "下载地址：https://www.python.org/downloads/"
    exit 1
fi

PYTHON=python3
PYTHON_VERSION=$($PYTHON --version)
echo "[信息] 检测到 $PYTHON_VERSION"

# 创建虚拟环境（可选）
read -p "是否创建虚拟环境？(Y/N，推荐 Y): " CREATE_VENV
if [[ "$CREATE_VENV" =~ ^[Yy]$ ]]; then
    if [ ! -d ".venv" ]; then
        echo "[1/3] 创建 Python 虚拟环境..."
        $PYTHON -m venv .venv
    fi
    echo "[2/3] 激活虚拟环境并安装依赖..."
    source .venv/bin/activate
    pip install --upgrade pip
    pip install -e .
else
    echo "[2/3] 在全局环境安装依赖..."
    pip install --upgrade pip
    pip install -e .
fi

# 可选：安装 FastAPI（服务器模式）
read -p "[3/3] 是否安装 FastAPI 服务器？(Y/N): " INSTALL_FASTAPI
if [[ "$INSTALL_FASTAPI" =~ ^[Yy]$ ]]; then
    pip install -e ".[server]"
    echo "FastAPI 已安装"
fi

echo "================================================"
echo "安装完成！"
echo "================================================"
echo ""
echo "现在可以运行："
echo "  win-computer-use --help"
echo "  win-computer-use screenshot --output test.png"
echo "  win-computer-use-server  (启动 HTTP 服务器)"
echo ""

# 提示用户
if [[ "$CREATE_VENV" =~ ^[Yy]$ ]]; then
    echo "提示：下次使用前请先激活虚拟环境："
    echo "  source .venv/bin/activate"
fi
