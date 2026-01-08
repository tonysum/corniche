#!/bin/bash

# Linux 服务器自动安装脚本
# 使用方法: ./install.sh [docker|direct]

set -e

INSTALL_MODE=${1:-docker}  # 默认使用 docker 方式

# 颜色输出
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 检测操作系统
detect_os() {
    if [ -f /etc/os-release ]; then
        . /etc/os-release
        OS=$ID
        VER=$VERSION_ID
    else
        echo -e "${RED}无法检测操作系统${NC}"
        exit 1
    fi
    echo -e "${BLUE}检测到操作系统: $OS $VER${NC}"
}

# 安装 Docker (Ubuntu/Debian)
install_docker_ubuntu() {
    echo -e "${YELLOW}安装 Docker (Ubuntu/Debian)...${NC}"
    
    # 更新系统
    sudo apt-get update
    
    # 安装必要依赖
    sudo apt-get install -y \
        ca-certificates \
        curl \
        gnupg \
        lsb-release
    
    # 添加 Docker GPG 密钥
    sudo mkdir -p /etc/apt/keyrings
    curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
    
    # 添加 Docker 仓库
    echo \
      "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
      $(lsb_release -cs) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
    
    # 安装 Docker
    sudo apt-get update
    sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
    
    # 启动 Docker
    sudo systemctl start docker
    sudo systemctl enable docker
    
    # 将当前用户添加到 docker 组（可选，避免每次使用 sudo）
    sudo usermod -aG docker $USER
    
    echo -e "${GREEN}Docker 安装完成${NC}"
}

# 安装 Docker (CentOS/RHEL)
install_docker_centos() {
    echo -e "${YELLOW}安装 Docker (CentOS/RHEL)...${NC}"
    
    # 安装必要依赖
    sudo yum install -y yum-utils
    
    # 添加 Docker 仓库
    sudo yum-config-manager --add-repo https://download.docker.com/linux/centos/docker-ce.repo
    
    # 安装 Docker
    sudo yum install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
    
    # 启动 Docker
    sudo systemctl start docker
    sudo systemctl enable docker
    
    # 将当前用户添加到 docker 组
    sudo usermod -aG docker $USER
    
    echo -e "${GREEN}Docker 安装完成${NC}"
}

# 安装系统依赖（直接安装方式）
install_system_deps() {
    echo -e "${YELLOW}安装系统依赖...${NC}"
    
    if [ "$OS" = "ubuntu" ] || [ "$OS" = "debian" ]; then
        sudo apt-get update
        sudo apt-get install -y \
            python3.11 \
            python3.11-venv \
            python3-pip \
            nodejs \
            npm \
            sqlite3 \
            build-essential \
            gcc
    elif [ "$OS" = "centos" ] || [ "$OS" = "rhel" ]; then
        sudo yum install -y \
            python3.11 \
            python3-pip \
            nodejs \
            npm \
            sqlite \
            gcc \
            gcc-c++ \
            make
    fi
    
    echo -e "${GREEN}系统依赖安装完成${NC}"
}

# 安装 Node.js（如果需要）
install_nodejs() {
    echo -e "${YELLOW}检查 Node.js 版本...${NC}"
    
    if command -v node &> /dev/null; then
        NODE_VERSION=$(node -v | cut -d'v' -f2 | cut -d'.' -f1)
        if [ "$NODE_VERSION" -lt 18 ]; then
            echo -e "${YELLOW}Node.js 版本过低，安装 Node.js 18+...${NC}"
            curl -fsSL https://deb.nodesource.com/setup_18.x | sudo -E bash -
            sudo apt-get install -y nodejs
        else
            echo -e "${GREEN}Node.js 版本满足要求${NC}"
        fi
    else
        echo -e "${YELLOW}安装 Node.js...${NC}"
        curl -fsSL https://deb.nodesource.com/setup_18.x | sudo -E bash -
        sudo apt-get install -y nodejs
    fi
}

# Docker 方式安装
install_docker() {
    echo -e "${GREEN}========================================${NC}"
    echo -e "${GREEN}使用 Docker 方式安装${NC}"
    echo -e "${GREEN}========================================${NC}"
    
    # 检测并安装 Docker
    if ! command -v docker &> /dev/null; then
        echo -e "${YELLOW}Docker 未安装，开始安装...${NC}"
        if [ "$OS" = "ubuntu" ] || [ "$OS" = "debian" ]; then
            install_docker_ubuntu
        elif [ "$OS" = "centos" ] || [ "$OS" = "rhel" ]; then
            install_docker_centos
        else
            echo -e "${RED}不支持的操作系统，请手动安装 Docker${NC}"
            exit 1
        fi
    else
        echo -e "${GREEN}Docker 已安装${NC}"
    fi
    
    # 创建必要目录
    echo -e "${YELLOW}创建必要目录...${NC}"
    mkdir -p db
    mkdir -p backtrade_records
    chmod -R 755 db
    chmod -R 755 backtrade_records
    
    # 构建并启动服务
    echo -e "${YELLOW}构建并启动 Docker 服务...${NC}"
    
    # 询问是否使用国内镜像源
    read -p "是否使用国内镜像源？(y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        COMPOSE_FILE="docker-compose.cn.yml"
    else
        COMPOSE_FILE="docker-compose.yml"
    fi
    
    docker compose -f "$COMPOSE_FILE" up -d --build
    
    echo -e "${GREEN}Docker 服务启动完成${NC}"
    echo -e "${BLUE}等待服务启动...${NC}"
    sleep 10
    
    # 检查服务状态
    docker compose -f "$COMPOSE_FILE" ps
    
    echo -e "\n${GREEN}========================================${NC}"
    echo -e "${GREEN}安装完成！${NC}"
    echo -e "${GREEN}========================================${NC}"
    echo ""
    echo "访问前端: http://$(hostname -I | awk '{print $1}'):3000"
    echo "访问后端: http://$(hostname -I | awk '{print $1}'):8000"
    echo "API 文档: http://$(hostname -I | awk '{print $1}'):8000/docs"
    echo ""
    echo "查看日志: docker compose -f $COMPOSE_FILE logs -f"
    echo "停止服务: docker compose -f $COMPOSE_FILE down"
}

# 直接安装方式
install_direct() {
    echo -e "${GREEN}========================================${NC}"
    echo -e "${GREEN}使用直接安装方式${NC}"
    echo -e "${GREEN}========================================${NC}"
    
    # 安装系统依赖
    install_system_deps
    
    # 安装 Node.js
    if [ "$OS" = "ubuntu" ] || [ "$OS" = "debian" ]; then
        install_nodejs
    fi
    
    # 创建 Python 虚拟环境
    echo -e "${YELLOW}创建 Python 虚拟环境...${NC}"
    python3.11 -m venv venv
    source venv/bin/activate
    
    # 安装 Python 依赖
    echo -e "${YELLOW}安装 Python 依赖...${NC}"
    pip install --upgrade pip
    pip install -r requirements.txt
    
    # 安装前端依赖
    echo -e "${YELLOW}安装前端依赖...${NC}"
    cd frontend
    npm install
    npm run build
    cd ..
    
    # 创建必要目录
    echo -e "${YELLOW}创建必要目录...${NC}"
    mkdir -p db
    mkdir -p backtrade_records
    chmod -R 755 db
    chmod -R 755 backtrade_records
    
    echo -e "\n${GREEN}========================================${NC}"
    echo -e "${GREEN}安装完成！${NC}"
    echo -e "${GREEN}========================================${NC}"
    echo ""
    echo "启动后端: source venv/bin/activate && uvicorn api_server:app --host 0.0.0.0 --port 8000"
    echo "启动前端: cd frontend && npm start"
    echo ""
    echo "建议使用 systemd 服务管理，参考 'Linux服务器安装指南.md'"
}

# 主函数
main() {
    echo -e "${BLUE}========================================${NC}"
    echo -e "${BLUE}加密货币回测系统安装脚本${NC}"
    echo -e "${BLUE}========================================${NC}"
    echo ""
    
    # 检测操作系统
    detect_os
    
    # 检查是否为 root 用户
    if [ "$EUID" -eq 0 ]; then
        echo -e "${RED}请不要使用 root 用户运行此脚本${NC}"
        exit 1
    fi
    
    # 检查 sudo 权限
    if ! sudo -n true 2>/dev/null; then
        echo -e "${YELLOW}需要 sudo 权限，请输入密码...${NC}"
        sudo -v
    fi
    
    # 根据安装方式执行
    if [ "$INSTALL_MODE" = "docker" ]; then
        install_docker
    elif [ "$INSTALL_MODE" = "direct" ]; then
        install_direct
    else
        echo -e "${RED}未知的安装方式: $INSTALL_MODE${NC}"
        echo "使用方法: ./install.sh [docker|direct]"
        exit 1
    fi
}

# 运行主函数
main

