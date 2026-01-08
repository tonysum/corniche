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

# 检查Python是否安装
if ! command -v python3 &> /dev/null; then
    echo "错误: 未找到 python3"
    exit 1
fi

# 检查uvicorn是否安装（如果使用--reload需要）
if [[ -n "$RELOAD_FLAG" ]]; then
    if ! python3 -c "import uvicorn" &> /dev/null; then
        echo "错误: 未找到 uvicorn，无法使用 --reload 参数"
        echo "请安装: pip install uvicorn[standard]"
        exit 1
    fi
fi

# 获取脚本所在目录（backend目录）
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR" || exit 1

# 启动数据管理服务（端口8001）
echo "启动数据管理服务 (端口 8001)..."
if [[ -n "$RELOAD_FLAG" ]]; then
    # 使用 uvicorn 命令行启动，支持 --reload
    # 注意：需要在backend目录下运行，因为服务文件中有路径设置
    python3 -m uvicorn services.data_service.main:app --host 0.0.0.0 --port 8001 $RELOAD_FLAG &
    DATA_SERVICE_PID=$!
else
    # 直接运行 Python 文件
    python3 services/data_service/main.py &
    DATA_SERVICE_PID=$!
fi

# 等待服务启动
sleep 2

# 启动回测服务（端口8002）
echo "启动回测服务 (端口 8002)..."
if [[ -n "$RELOAD_FLAG" ]]; then
    # 使用 uvicorn 命令行启动，支持 --reload
    python3 -m uvicorn services.backtest_service.main:app --host 0.0.0.0 --port 8002 $RELOAD_FLAG &
    BACKTEST_SERVICE_PID=$!
else
    # 直接运行 Python 文件
    python3 services/backtest_service/main.py &
    BACKTEST_SERVICE_PID=$!
fi

# 等待服务启动
sleep 2

# 启动订单服务（端口8003）
echo "启动订单服务 (端口 8003)..."
if [[ -n "$RELOAD_FLAG" ]]; then
    # 使用 uvicorn 命令行启动，支持 --reload
    python3 -m uvicorn services.order_service.main:app --host 0.0.0.0 --port 8003 $RELOAD_FLAG &
    ORDER_SERVICE_PID=$!
else
    # 直接运行 Python 文件
    python3 services/order_service/main.py &
    ORDER_SERVICE_PID=$!
fi

# 等待服务启动
sleep 2

echo ""
echo "所有服务已启动！"
echo "数据管理服务 PID: $DATA_SERVICE_PID (端口 8001)"
echo "回测服务 PID: $BACKTEST_SERVICE_PID (端口 8002)"
echo "订单服务 PID: $ORDER_SERVICE_PID (端口 8003)"
echo ""
echo "API文档:"
echo "  数据管理服务: http://localhost:8001/docs"
echo "  回测服务: http://localhost:8002/docs"
echo "  订单服务: http://localhost:8003/docs"
echo ""
echo "按 Ctrl+C 停止所有服务"

# 等待用户中断
trap "echo ''; echo '正在停止所有服务...'; kill $DATA_SERVICE_PID $BACKTEST_SERVICE_PID $ORDER_SERVICE_PID; exit" INT TERM

# 保持脚本运行
wait

