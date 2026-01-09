#!/bin/bash

# Ubuntu Node.js 更新脚本（自动检测是否需要 sudo）

set -e

# 颜色输出
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${GREEN}=== Ubuntu Node.js 更新工具 ===${NC}\n"

# 检查是否是 root 用户
if [ "$EUID" -eq 0 ]; then
    SUDO_CMD=""
    echo -e "${GREEN}检测到 root 用户，不需要 sudo${NC}"
else
    # 检查是否有 sudo
    if command -v sudo &> /dev/null; then
        SUDO_CMD="sudo"
        echo -e "${YELLOW}使用 sudo 执行命令${NC}"
    else
        echo -e "${YELLOW}警告: 未找到 sudo，尝试直接执行（需要 root 权限）${NC}"
        echo -e "${YELLOW}如果失败，建议使用 NVM 方法（不需要 root）${NC}"
        SUDO_CMD=""
    fi
fi

echo ""

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
echo "1. 使用 NodeSource 仓库（需要 root 权限）"
echo "2. 使用 NVM（推荐，不需要 root 权限）"
read -p "请选择 (1-2): " METHOD

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
            *) SETUP_SCRIPT="setup_20.x" ;;
        esac
        
        echo ""
        echo "正在添加 NodeSource 仓库..."
        curl -fsSL https://deb.nodesource.com/setup_${SETUP_SCRIPT} | $SUDO_CMD bash -
        
        echo ""
        echo "正在安装 Node.js..."
        $SUDO_CMD apt-get update
        $SUDO_CMD apt-get install -y nodejs
        
        echo ""
        echo -e "${GREEN}✓ 安装完成${NC}"
        ;;
    2)
        echo ""
        echo -e "${GREEN}使用 NVM 更新（不需要 root 权限）...${NC}"
        
        # 检查是否已安装 NVM
        if ! command -v nvm &> /dev/null; then
            echo "安装 NVM..."
            curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.0/install.sh | bash
            
            # 加载 NVM
            export NVM_DIR="$HOME/.nvm"
            [ -s "$NVM_DIR/nvm.sh" ] && \. "$NVM_DIR/nvm.sh"
            
            # 如果 .bashrc 存在，添加到其中
            if [ -f ~/.bashrc ]; then
                echo "" >> ~/.bashrc
                echo 'export NVM_DIR="$HOME/.nvm"' >> ~/.bashrc
                echo '[ -s "$NVM_DIR/nvm.sh" ] && \. "$NVM_DIR/nvm.sh"' >> ~/.bashrc
            fi
        fi
        
        # 确保 NVM 已加载
        export NVM_DIR="$HOME/.nvm"
        [ -s "$NVM_DIR/nvm.sh" ] && \. "$NVM_DIR/nvm.sh"
        
        echo "安装最新 LTS 版本..."
        nvm install --lts
        nvm use --lts
        nvm alias default --lts
        
        echo ""
        echo -e "${GREEN}✓ 安装完成${NC}"
        echo -e "${YELLOW}提示: 如果命令未生效，请运行: source ~/.bashrc${NC}"
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
if [ "$NEW_NODE" != "未安装" ]; then
    echo -e "${GREEN}$NEW_NODE${NC}"
else
    echo -e "${RED}$NEW_NODE${NC}"
    echo -e "${YELLOW}提示: 如果使用 NVM，请运行: source ~/.bashrc${NC}"
fi

echo ""
echo "npm 版本:"
NEW_NPM=$(npm --version 2>/dev/null || echo "未安装")
if [ "$NEW_NPM" != "未安装" ]; then
    echo -e "${GREEN}$NEW_NPM${NC}"
else
    echo -e "${RED}$NEW_NPM${NC}"
fi

echo ""
echo -e "${GREEN}=== 完成 ===${NC}"
