#!/bin/bash

# Ubuntu Node.js 更新脚本

set -e

# 颜色输出
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${GREEN}=== Ubuntu Node.js 更新工具 ===${NC}\n"

# 检查当前版本
echo "当前 Node.js 版本:"
CURRENT_NODE=$(node --version 2>/dev/null || echo "未安装")
echo -e "${YELLOW}$CURRENT_NODE${NC}"

echo ""
echo "当前 npm 版本:"
CURRENT_NPM=$(npm --version 2>/dev/null || echo "未安装")
echo -e "${YELLOW}$CURRENT_NPM${NC}\n"

# 选择更新方式
echo "请选择更新方式:"
echo "1. 使用 NodeSource 仓库（推荐，获得最新版本）"
echo "2. 使用 NVM（推荐，可管理多版本）"
echo "3. 使用 Snap"
echo "4. 仅更新 npm"
read -p "请选择 (1-4): " METHOD

case $METHOD in
    1)
        echo ""
        echo -e "${GREEN}使用 NodeSource 仓库更新...${NC}"
        echo "选择 Node.js 版本:"
        echo "1. Node.js 20.x (LTS，推荐)"
        echo "2. Node.js 22.x (最新)"
        echo "3. Node.js 18.x (旧版 LTS)"
        read -p "请选择 (1-3): " VERSION
        
        case $VERSION in
            1) SETUP_SCRIPT="setup_20.x" ;;
            2) SETUP_SCRIPT="setup_22.x" ;;
            3) SETUP_SCRIPT="setup_18.x" ;;
            *) echo -e "${YELLOW}无效选择，使用默认 20.x${NC}"; SETUP_SCRIPT="setup_20.x" ;;
        esac
        
        echo ""
        echo "正在添加 NodeSource 仓库..."
        curl -fsSL https://deb.nodesource.com/setup_${SETUP_SCRIPT} | sudo -E bash -
        
        echo ""
        echo "正在安装 Node.js..."
        sudo apt-get install -y nodejs
        
        echo ""
        echo -e "${GREEN}✓ 安装完成${NC}"
        ;;
    2)
        echo ""
        echo -e "${GREEN}使用 NVM 更新...${NC}"
        
        # 检查是否已安装 NVM
        if ! command -v nvm &> /dev/null; then
            echo "安装 NVM..."
            curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.0/install.sh | bash
            export NVM_DIR="$HOME/.nvm"
            [ -s "$NVM_DIR/nvm.sh" ] && \. "$NVM_DIR/nvm.sh"
        fi
        
        echo "安装最新 LTS 版本..."
        nvm install --lts
        nvm use --lts
        nvm alias default --lts
        
        echo ""
        echo -e "${GREEN}✓ 安装完成${NC}"
        ;;
    3)
        echo ""
        echo -e "${GREEN}使用 Snap 更新...${NC}"
        sudo snap refresh node
        
        echo ""
        echo -e "${GREEN}✓ 更新完成${NC}"
        ;;
    4)
        echo ""
        echo -e "${GREEN}更新 npm...${NC}"
        sudo npm install -g npm@latest
        
        echo ""
        echo -e "${GREEN}✓ 更新完成${NC}"
        ;;
    *)
        echo -e "${RED}无效选择${NC}"
        exit 1
        ;;
esac

echo ""
echo -e "${GREEN}=== 更新结果 ===${NC}"
echo "Node.js 版本:"
NEW_NODE=$(node --version 2>/dev/null || echo "未安装")
echo -e "${GREEN}$NEW_NODE${NC}"

echo ""
echo "npm 版本:"
NEW_NPM=$(npm --version 2>/dev/null || echo "未安装")
echo -e "${GREEN}$NEW_NPM${NC}"

echo ""
echo -e "${GREEN}=== 完成 ===${NC}"
