#!/bin/bash

# 启动所有微服务的脚本
#
# 使用方法:
#   ./start-services.sh          # 正常启动（生产模式）
#   ./start-services.sh --reload # 开发模式启动（启用自动重载）
#
# 说明:
#   - 正常模式：直接运行Python文件，性能更好
#   - --reload模式：使用uvicorn命令行启动，代码修改后自动重启服务

# 检查是否使用 --reload 参数
RELOAD_FLAG=""
if [[ "$1" == "--reload" ]]; then
    RELOAD_FLAG="--reload"
    echo "启动微服务 (开发模式，启用自动重载)..."
else
    echo "启动微服务..."
fi

# 检查并激活 conda 环境 "tiger"
PYTHON_CMD="python3"
USE_CONDA_RUN=false

if command -v conda &> /dev/null; then
    # 初始化 conda（如果还没有初始化）
    if [[ -z "$CONDA_DEFAULT_ENV" ]]; then
        # 尝试常见的 conda 初始化路径
        if [[ -f "$HOME/miniconda3/etc/profile.d/conda.sh" ]]; then
            source "$HOME/miniconda3/etc/profile.d/conda.sh"
        elif [[ -f "$HOME/anaconda3/etc/profile.d/conda.sh" ]]; then
            source "$HOME/anaconda3/etc/profile.d/conda.sh"
        elif [[ -f "/opt/conda/etc/profile.d/conda.sh" ]]; then
            source "/opt/conda/etc/profile.d/conda.sh"
        else
            # 尝试通过 conda info 获取 base 路径
            CONDA_BASE=$(conda info --base 2>/dev/null)
            if [[ -n "$CONDA_BASE" ]] && [[ -f "$CONDA_BASE/etc/profile.d/conda.sh" ]]; then
                source "$CONDA_BASE/etc/profile.d/conda.sh"
            fi
        fi
    fi
    
    # 检查当前是否已经激活了 "tiger" 环境
    if [[ "$CONDA_DEFAULT_ENV" != "tiger" ]]; then
        echo "检测到 conda，正在激活环境 'tiger'..."
        # 尝试激活 conda 环境
        if [[ -n "$CONDA_PREFIX" ]] || command -v conda &> /dev/null; then
            # 确保 conda 函数可用
            if [[ -z "$(type -t conda)" ]] || [[ "$(type -t conda)" != "function" ]]; then
                CONDA_BASE=$(conda info --base 2>/dev/null)
                if [[ -n "$CONDA_BASE" ]] && [[ -f "$CONDA_BASE/etc/profile.d/conda.sh" ]]; then
                    source "$CONDA_BASE/etc/profile.d/conda.sh"
                fi
            fi
            
            # 尝试激活环境
            conda activate tiger 2>/dev/null
            if [[ $? -eq 0 ]] && [[ "$CONDA_DEFAULT_ENV" == "tiger" ]]; then
                echo "已激活 conda 环境: tiger"
                # 获取激活环境后的 Python 路径（使用完整路径以确保后台进程也能使用）
                PYTHON_CMD="$(which python)"
                if [[ -z "$PYTHON_CMD" ]]; then
                    PYTHON_CMD="$(conda run -n tiger which python 2>/dev/null || echo "python3")"
                fi
            else
                echo "警告: 无法直接激活 conda 环境 'tiger'，将使用 conda run 运行命令"
                USE_CONDA_RUN=true
                PYTHON_CMD="conda run -n tiger python"
            fi
        else
            echo "警告: conda 未正确初始化，将使用 conda run 运行命令"
            USE_CONDA_RUN=true
            PYTHON_CMD="conda run -n tiger python"
        fi
    else
        echo "conda 环境 'tiger' 已激活"
        PYTHON_CMD="$(which python)"
        if [[ -z "$PYTHON_CMD" ]]; then
            PYTHON_CMD="python3"
        fi
    fi
else
    echo "未检测到 conda，跳过环境激活"
fi

# 验证 Python 命令是否可用
if [[ "$USE_CONDA_RUN" == false ]]; then
    if ! command -v "$PYTHON_CMD" &> /dev/null && ! "$PYTHON_CMD" --version &> /dev/null 2>&1; then
        echo "警告: 无法使用指定的 Python 命令 '$PYTHON_CMD'，回退到 python3"
        PYTHON_CMD="python3"
    fi
fi

echo "使用 Python: $PYTHON_CMD"

# 检查Python是否安装
if [[ "$USE_CONDA_RUN" == true ]]; then
    # 如果使用 conda run，验证 conda 和 tiger 环境是否存在
    if ! conda env list | grep -q "tiger"; then
        echo "错误: conda 环境 'tiger' 不存在"
        echo "请创建环境: conda create -n tiger python=3.x"
        exit 1
    fi
    # 测试 conda run 是否工作
    if ! conda run -n tiger python --version &> /dev/null; then
        echo "错误: 无法在 conda 环境 'tiger' 中运行 Python"
        exit 1
    fi
else
    if ! command -v "$PYTHON_CMD" &> /dev/null && ! "$PYTHON_CMD" --version &> /dev/null 2>&1; then
        echo "错误: 未找到 Python 解释器: $PYTHON_CMD"
        exit 1
    fi
fi

# 检查uvicorn是否安装（如果使用--reload需要）
if [[ -n "$RELOAD_FLAG" ]]; then
    if ! "$PYTHON_CMD" -c "import uvicorn" &> /dev/null; then
        echo "错误: 未找到 uvicorn，无法使用 --reload 参数"
        echo "请安装: pip install uvicorn[standard]"
        exit 1
    fi
fi

# 获取脚本所在目录（backend目录）
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR" || exit 1

# 数据管理服务已独立为单独项目，不再在此启动
# 如果需要数据管理功能，请启动独立的数据管理服务

# 启动回测服务（端口8002）
echo "启动回测服务 (端口 8002)..."
if [[ -n "$RELOAD_FLAG" ]]; then
    # 使用 uvicorn 命令行启动，支持 --reload
    "$PYTHON_CMD" -m uvicorn services.backtest_service.main:app --host 0.0.0.0 --port 8002 $RELOAD_FLAG &
    BACKTEST_SERVICE_PID=$!
else
    # 直接运行 Python 文件
    "$PYTHON_CMD" services/backtest_service/main.py &
    BACKTEST_SERVICE_PID=$!
fi

# 等待服务启动
sleep 2

# 启动订单服务（端口8003）
echo "启动订单服务 (端口 8003)..."
if [[ -n "$RELOAD_FLAG" ]]; then
    # 使用 uvicorn 命令行启动，支持 --reload
    "$PYTHON_CMD" -m uvicorn services.order_service.main:app --host 0.0.0.0 --port 8003 $RELOAD_FLAG &
    ORDER_SERVICE_PID=$!
else
    # 直接运行 Python 文件
    "$PYTHON_CMD" services/order_service/main.py &
    ORDER_SERVICE_PID=$!
fi

# 等待服务启动
sleep 2

echo ""
echo "所有服务已启动！"
echo "回测服务 PID: $BACKTEST_SERVICE_PID (端口 8002)"
echo "订单服务 PID: $ORDER_SERVICE_PID (端口 8003)"
echo ""
echo "API文档:"
echo "  回测服务: http://localhost:8002/docs"
echo "  订单服务: http://localhost:8003/docs"
echo ""
echo "注意: 数据管理服务已独立为单独项目，请单独启动"
echo ""
echo "按 Ctrl+C 停止所有服务"

# 等待用户中断
# 保持脚本运行
wait

