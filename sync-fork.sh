#!/bin/bash

# GitHub Fork 同步脚本
# 用于将上游仓库（原仓库）的更新同步到你的 fork

set -e

# 颜色输出
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${GREEN}=== GitHub Fork 同步工具 ===${NC}\n"

# 检查是否在 git 仓库中
if ! git rev-parse --git-dir > /dev/null 2>&1; then
    echo -e "${RED}错误: 当前目录不是 git 仓库${NC}"
    exit 1
fi

# 检查上游仓库是否已配置
if ! git remote | grep -q upstream; then
    echo -e "${YELLOW}未找到 upstream 远程仓库，正在添加...${NC}"
    read -p "请输入上游仓库 URL (例如: git@github.com:tonysum/corniche.git): " UPSTREAM_URL
    if [ -z "$UPSTREAM_URL" ]; then
        echo -e "${RED}错误: 上游仓库 URL 不能为空${NC}"
        exit 1
    fi
    git remote add upstream "$UPSTREAM_URL"
    echo -e "${GREEN}已添加上游仓库: $UPSTREAM_URL${NC}\n"
fi

# 显示当前远程仓库配置
echo -e "${GREEN}当前远程仓库配置:${NC}"
git remote -v
echo ""

# 获取当前分支
CURRENT_BRANCH=$(git branch --show-current)
echo -e "${GREEN}当前分支: $CURRENT_BRANCH${NC}\n"

# 检查是否有未提交的更改
if ! git diff-index --quiet HEAD --; then
    echo -e "${YELLOW}警告: 检测到未提交的更改${NC}"
    read -p "是否先提交更改？(y/n): " COMMIT_CHANGES
    if [ "$COMMIT_CHANGES" = "y" ]; then
        git add .
        read -p "请输入提交信息: " COMMIT_MSG
        git commit -m "$COMMIT_MSG"
    else
        echo -e "${YELLOW}建议先提交或暂存更改，避免冲突${NC}"
        read -p "继续同步？(y/n): " CONTINUE
        if [ "$CONTINUE" != "y" ]; then
            exit 0
        fi
    fi
fi

# 获取上游仓库的更新
echo -e "${GREEN}正在获取上游仓库更新...${NC}"
git fetch upstream

# 显示上游仓库的更新
echo -e "\n${GREEN}上游仓库更新情况:${NC}"
git log HEAD..upstream/$CURRENT_BRANCH --oneline 2>/dev/null || echo "没有新更新"

# 检查是否有更新
LOCAL=$(git rev-parse HEAD)
REMOTE=$(git rev-parse upstream/$CURRENT_BRANCH 2>/dev/null || echo "")

if [ -z "$REMOTE" ]; then
    echo -e "${YELLOW}警告: 上游仓库没有 $CURRENT_BRANCH 分支${NC}"
    read -p "是否查看所有上游分支？(y/n): " SHOW_BRANCHES
    if [ "$SHOW_BRANCHES" = "y" ]; then
        echo -e "${GREEN}上游仓库分支列表:${NC}"
        git branch -r | grep upstream
    fi
    exit 0
fi

if [ "$LOCAL" = "$REMOTE" ]; then
    echo -e "${GREEN}✓ 你的 fork 已经是最新的，无需同步${NC}"
    exit 0
fi

# 合并上游更新
echo -e "\n${GREEN}正在合并上游更新...${NC}"
if git merge upstream/$CURRENT_BRANCH --no-edit; then
    echo -e "${GREEN}✓ 合并成功${NC}"
else
    echo -e "${RED}✗ 合并失败，存在冲突${NC}"
    echo -e "${YELLOW}请手动解决冲突后，运行: git push origin $CURRENT_BRANCH${NC}"
    exit 1
fi

# 推送到你的 fork
echo -e "\n${GREEN}正在推送到你的 fork...${NC}"
read -p "是否推送到 origin/$CURRENT_BRANCH？(y/n): " PUSH
if [ "$PUSH" = "y" ]; then
    git push origin $CURRENT_BRANCH
    echo -e "${GREEN}✓ 同步完成！${NC}"
else
    echo -e "${YELLOW}已合并但未推送，可以稍后手动推送${NC}"
fi

echo -e "\n${GREEN}=== 同步完成 ===${NC}"
