# Ubuntu 更新 Node.js 指南

本文档专门介绍在 Ubuntu 系统上更新 Node.js 的方法。

## 📋 目录

1. [检查当前版本](#检查当前版本)
2. [方法1: 使用 NodeSource 仓库（推荐）](#方法1-使用-nodesource-仓库推荐)
3. [方法2: 使用 NVM（推荐，可管理多版本）](#方法2-使用-nvm推荐可管理多版本)
4. [方法3: 使用 Snap](#方法3-使用-snap)
5. [方法4: 使用 APT（官方仓库）](#方法4-使用-apt官方仓库)
6. [完全卸载后重新安装](#完全卸载后重新安装)
7. [常见问题](#常见问题)

---

## 检查当前版本

```bash
# 查看 Node.js 版本
node --version
node -v

# 查看 npm 版本
npm --version
npm -v

# 查看安装位置
which node
which npm
```

---

## 方法1: 使用 NodeSource 仓库（推荐）

这是 Ubuntu 上更新 Node.js 最常用的方法，可以获得最新版本。

### 更新到 Node.js 20.x（LTS）

```bash
# 1. 清除旧的 Node.js（可选，如果之前用其他方式安装）
sudo apt-get remove nodejs npm -y

# 2. 更新系统包
sudo apt-get update

# 3. 安装必要的工具
sudo apt-get install -y curl

# 4. 添加 NodeSource 仓库（Node.js 20.x）
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -

# 5. 安装 Node.js
sudo apt-get install -y nodejs

# 6. 验证安装
node --version
npm --version
```

### 更新到 Node.js 22.x（最新）

```bash
curl -fsSL https://deb.nodesource.com/setup_22.x | sudo -E bash -
sudo apt-get install -y nodejs
```

### 更新到 Node.js 18.x（旧版 LTS）

```bash
curl -fsSL https://deb.nodesource.com/setup_18.x | sudo -E bash -
sudo apt-get install -y nodejs
```

### 更新已安装的 Node.js

```bash
# 1. 更新仓库信息
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -

# 2. 更新 Node.js
sudo apt-get update
sudo apt-get upgrade nodejs -y

# 3. 验证
node --version
```

---

## 方法2: 使用 NVM（推荐，可管理多版本）

NVM 可以让你轻松管理多个 Node.js 版本，非常适合开发环境。

### 安装 NVM

```bash
# 下载并安装 NVM
curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.0/install.sh | bash

# 重新加载 shell 配置
source ~/.bashrc
# 或
source ~/.zshrc

# 验证安装
nvm --version
```

### 使用 NVM 更新 Node.js

```bash
# 1. 查看已安装的版本
nvm list

# 2. 查看可用的远程版本
nvm list-remote

# 3. 安装最新 LTS 版本
nvm install --lts

# 4. 安装最新版本
nvm install node

# 5. 切换到新版本
nvm use node
# 或
nvm use --lts

# 6. 设置为默认版本
nvm alias default node
# 或
nvm alias default --lts

# 7. 验证
node --version
npm --version
```

### NVM 常用命令

```bash
# 查看所有已安装版本
nvm list

# 安装特定版本
nvm install 20.10.0
nvm install 18.19.0

# 切换到特定版本
nvm use 20.10.0

# 设置默认版本
nvm alias default 20.10.0

# 查看当前版本
nvm current

# 卸载特定版本
nvm uninstall 18.19.0
```

---

## 方法3: 使用 Snap

Snap 是 Ubuntu 的包管理系统，可以轻松安装和更新 Node.js。

### 安装/更新 Node.js

```bash
# 安装最新版本
sudo snap install node --classic

# 更新到最新版本
sudo snap refresh node

# 安装特定版本（如 20）
sudo snap install node --channel=20/stable --classic

# 切换到不同版本
sudo snap switch node --channel=20/stable
```

### 查看可用版本

```bash
# 查看已安装版本
snap list | grep node

# 查看可用通道
snap info node
```

---

## 方法4: 使用 APT（官方仓库）

Ubuntu 官方仓库的 Node.js 版本可能不是最新的，但更新简单。

```bash
# 更新软件包列表
sudo apt-get update

# 升级 Node.js
sudo apt-get upgrade nodejs -y

# 如果未安装，先安装
sudo apt-get install nodejs npm -y

# 验证
node --version
```

**注意：** Ubuntu 官方仓库的版本通常较旧，建议使用 NodeSource 或 NVM。

---

## 完全卸载后重新安装

如果需要完全清理后重新安装：

### 步骤1: 卸载旧版本

```bash
# 卸载通过 apt 安装的版本
sudo apt-get remove nodejs npm -y
sudo apt-get purge nodejs npm -y
sudo apt-get autoremove -y

# 如果使用 NVM 安装，卸载 NVM
rm -rf ~/.nvm

# 如果使用 Snap 安装
sudo snap remove node

# 清理残留文件
sudo rm -rf /usr/local/bin/node
sudo rm -rf /usr/local/bin/npm
sudo rm -rf /usr/local/lib/node_modules
```

### 步骤2: 重新安装

选择一种方法重新安装（推荐 NodeSource 或 NVM）。

---

## 更新 npm

Node.js 安装包通常包含 npm，但也可以单独更新：

```bash
# 更新 npm 到最新版本
sudo npm install -g npm@latest

# 或使用 npm 自更新
sudo npm install -g npm

# 验证版本
npm --version

# 查看可用版本
npm view npm versions
```

---

## 一键更新脚本

创建 `update_nodejs_ubuntu.sh`:

```bash
#!/bin/bash

echo "=== Ubuntu Node.js 更新工具 ==="
echo ""

# 检查当前版本
echo "当前 Node.js 版本:"
node --version 2>/dev/null || echo "未安装"
echo ""

# 选择更新方式
echo "请选择更新方式:"
echo "1. 使用 NodeSource 仓库（推荐，获得最新版本）"
echo "2. 使用 NVM（推荐，可管理多版本）"
echo "3. 使用 Snap"
read -p "请选择 (1-3): " METHOD

case $METHOD in
    1)
        echo ""
        echo "使用 NodeSource 仓库更新..."
        echo "选择 Node.js 版本:"
        echo "1. Node.js 20.x (LTS)"
        echo "2. Node.js 22.x (最新)"
        echo "3. Node.js 18.x (旧版 LTS)"
        read -p "请选择 (1-3): " VERSION
        
        case $VERSION in
            1) SETUP_SCRIPT="setup_20.x" ;;
            2) SETUP_SCRIPT="setup_22.x" ;;
            3) SETUP_SCRIPT="setup_18.x" ;;
            *) echo "无效选择，使用默认 20.x"; SETUP_SCRIPT="setup_20.x" ;;
        esac
        
        curl -fsSL https://deb.nodesource.com/setup_${SETUP_SCRIPT} | sudo -E bash -
        sudo apt-get install -y nodejs
        ;;
    2)
        echo ""
        echo "使用 NVM 更新..."
        
        # 检查是否已安装 NVM
        if ! command -v nvm &> /dev/null; then
            echo "安装 NVM..."
            curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.0/install.sh | bash
            source ~/.bashrc
        fi
        
        echo "安装最新 LTS 版本..."
        nvm install --lts
        nvm use --lts
        nvm alias default --lts
        ;;
    3)
        echo ""
        echo "使用 Snap 更新..."
        sudo snap refresh node
        ;;
    *)
        echo "无效选择"
        exit 1
        ;;
esac

echo ""
echo "=== 更新完成 ==="
echo "Node.js 版本:"
node --version
echo "npm 版本:"
npm --version
```

使用：

```bash
chmod +x update_nodejs_ubuntu.sh
./update_nodejs_ubuntu.sh
```

---

## 常见问题

### Q1: 更新后版本没有变化

**解决方法：**

```bash
# 1. 检查是否有多个 Node.js 安装
which node
which npm

# 2. 检查 PATH 环境变量
echo $PATH

# 3. 清除命令缓存
hash -r

# 4. 重新加载 shell 配置
source ~/.bashrc
```

---

### Q2: 权限错误

**解决方法：**

```bash
# 方法1: 使用 sudo（不推荐用于全局包）
sudo npm install -g npm@latest

# 方法2: 修复 npm 权限
mkdir ~/.npm-global
npm config set prefix '~/.npm-global'
echo 'export PATH=~/.npm-global/bin:$PATH' >> ~/.bashrc
source ~/.bashrc

# 方法3: 使用 NVM（推荐，不需要 sudo）
nvm install node
```

---

### Q3: 更新后项目无法运行

**解决方法：**

```bash
# 1. 检查项目要求的 Node.js 版本
cat .nvmrc 2>/dev/null || echo "未找到 .nvmrc"
cat package.json | grep engines

# 2. 删除 node_modules 并重新安装
rm -rf node_modules package-lock.json
npm install

# 3. 使用项目指定的版本（如果使用 NVM）
nvm use
```

---

### Q4: 如何降级到旧版本？

**使用 NVM：**

```bash
# 安装旧版本
nvm install 18.19.0

# 切换到旧版本
nvm use 18.19.0

# 设置为默认
nvm alias default 18.19.0
```

**使用 NodeSource：**

```bash
# 添加旧版本的仓库
curl -fsSL https://deb.nodesource.com/setup_18.x | sudo -E bash -
sudo apt-get install -y nodejs
```

---

### Q5: 更新 npm 时出错

**解决方法：**

```bash
# 1. 清除 npm 缓存
npm cache clean --force

# 2. 重新安装 npm
sudo npm install -g npm@latest

# 3. 如果还是失败，使用 NVM
nvm install node
```

---

## 快速参考

### 最常用的更新命令

```bash
# 方法1: NodeSource（推荐，简单快速）
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt-get install -y nodejs

# 方法2: NVM（推荐，可管理多版本）
nvm install --lts
nvm use --lts
nvm alias default --lts

# 方法3: Snap
sudo snap refresh node
```

### 验证更新

```bash
# 检查版本
node --version
npm --version

# 测试 Node.js
node -e "console.log('Node.js is working!')"
```

---

## 推荐方案

### 开发环境

**推荐使用 NVM：**
- ✅ 可以管理多个版本
- ✅ 不需要 sudo 权限
- ✅ 适合不同项目使用不同版本

```bash
# 安装 NVM
curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.0/install.sh | bash
source ~/.bashrc

# 安装最新 LTS
nvm install --lts
nvm use --lts
nvm alias default --lts
```

### 生产环境

**推荐使用 NodeSource：**
- ✅ 系统级安装
- ✅ 稳定可靠
- ✅ 易于管理

```bash
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt-get install -y nodejs
```

---

## 总结

**Ubuntu 上更新 Node.js 的三种推荐方法：**

1. **NodeSource** - 最简单，适合生产环境
2. **NVM** - 最灵活，适合开发环境
3. **Snap** - Ubuntu 原生，简单易用

**快速更新命令：**

```bash
# 使用 NodeSource 更新到 Node.js 20.x
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash - && sudo apt-get install -y nodejs
```
