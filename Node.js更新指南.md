# Node.js 更新指南

本文档介绍如何在不同操作系统和环境下更新 Node.js。

## 📋 目录

1. [检查当前版本](#检查当前版本)
2. [macOS 更新方法](#macos-更新方法)
3. [Linux 更新方法](#linux-更新方法)
4. [Windows 更新方法](#windows-更新方法)
5. [使用 NVM 管理版本（推荐）](#使用-nvm-管理版本推荐)
6. [Docker 环境更新](#docker-环境更新)
7. [常见问题](#常见问题)

---

## 检查当前版本

```bash
# 查看当前 Node.js 版本
node --version
# 或
node -v

# 查看 npm 版本
npm --version
# 或
npm -v

# 查看所有相关信息
node -p "process.versions"
```

---

## macOS 更新方法

### 方法1: 使用 Homebrew（推荐）

```bash
# 更新 Homebrew
brew update

# 升级 Node.js
brew upgrade node

# 如果未安装，先安装
brew install node
```

### 方法2: 使用 NVM（推荐，可管理多个版本）

```bash
# 安装 NVM（如果还没有）
curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.0/install.sh | bash

# 重新加载 shell 配置
source ~/.zshrc  # 或 source ~/.bash_profile

# 查看可用的 Node.js 版本
nvm list-remote

# 安装最新 LTS 版本
nvm install --lts

# 安装最新版本
nvm install node

# 切换到新版本
nvm use node

# 设置为默认版本
nvm alias default node
```

### 方法3: 从官网下载安装包

1. 访问 [Node.js 官网](https://nodejs.org/)
2. 下载最新的安装包（.pkg 文件）
3. 运行安装包，按提示安装

### 方法4: 使用 MacPorts

```bash
sudo port selfupdate
sudo port upgrade nodejs18  # 或 nodejs20
```

---

## Linux 更新方法

### Ubuntu/Debian

#### 方法1: 使用 NodeSource 仓库（推荐）

```bash
# 1. 清除旧的 Node.js（可选）
sudo apt-get remove nodejs npm

# 2. 添加 NodeSource 仓库（以 Node.js 20.x 为例）
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -

# 3. 安装 Node.js
sudo apt-get install -y nodejs

# 4. 验证安装
node --version
npm --version
```

**不同版本的仓库：**
- Node.js 18.x: `setup_18.x`
- Node.js 20.x: `setup_20.x`
- Node.js 22.x: `setup_22.x`

#### 方法2: 使用 NVM（推荐，可管理多个版本）

```bash
# 安装 NVM
curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.0/install.sh | bash

# 重新加载 shell 配置
source ~/.bashrc  # 或 source ~/.zshrc

# 安装最新 LTS 版本
nvm install --lts

# 使用新版本
nvm use --lts

# 设置为默认版本
nvm alias default node
```

#### 方法3: 使用 Snap

```bash
# 安装最新版本
sudo snap install node --classic

# 更新到最新版本
sudo snap refresh node
```

#### 方法4: 使用 APT（Ubuntu 官方仓库）

```bash
# 更新软件包列表
sudo apt-get update

# 升级 Node.js
sudo apt-get upgrade nodejs

# 注意：Ubuntu 官方仓库的版本可能不是最新的
```

### CentOS/RHEL

#### 方法1: 使用 NodeSource 仓库

```bash
# 添加 NodeSource 仓库（以 Node.js 20.x 为例）
curl -fsSL https://rpm.nodesource.com/setup_20.x | sudo bash -

# 安装 Node.js
sudo yum install -y nodejs

# 或使用 dnf (CentOS 8+)
sudo dnf install -y nodejs
```

#### 方法2: 使用 NVM

```bash
# 安装 NVM
curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.0/install.sh | bash

# 重新加载配置
source ~/.bashrc

# 安装最新版本
nvm install node
nvm use node
```

### 其他 Linux 发行版

**Arch Linux:**
```bash
sudo pacman -S nodejs npm
```

**Fedora:**
```bash
sudo dnf install nodejs npm
```

**openSUSE:**
```bash
sudo zypper install nodejs npm
```

---

## Windows 更新方法

### 方法1: 从官网下载安装包（推荐）

1. 访问 [Node.js 官网](https://nodejs.org/)
2. 下载最新的 Windows 安装包（.msi 文件）
3. 运行安装包，按提示安装
4. 安装程序会自动替换旧版本

### 方法2: 使用 Chocolatey

```bash
# 更新 Chocolatey
choco upgrade chocolatey

# 更新 Node.js
choco upgrade nodejs
```

### 方法3: 使用 NVM for Windows

1. 下载 [nvm-windows](https://github.com/coreybutler/nvm-windows/releases)
2. 安装后，在命令行执行：

```bash
# 查看可用版本
nvm list available

# 安装最新版本
nvm install latest

# 或安装 LTS 版本
nvm install lts

# 使用新版本
nvm use <version>
```

### 方法4: 使用 Winget

```bash
# 更新 Node.js
winget upgrade OpenJS.NodeJS
```

---

## 使用 NVM 管理版本（推荐）

NVM (Node Version Manager) 可以轻松管理多个 Node.js 版本，非常适合开发环境。

### 安装 NVM

**macOS/Linux:**
```bash
curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.0/install.sh | bash
```

**Windows:**
下载并安装 [nvm-windows](https://github.com/coreybutler/nvm-windows/releases)

### NVM 常用命令

```bash
# 查看已安装的版本
nvm list
# 或
nvm ls

# 查看可用的远程版本
nvm list-remote
# 或
nvm ls-remote

# 安装特定版本
nvm install 20.10.0
nvm install 18.19.0

# 安装最新 LTS 版本
nvm install --lts

# 安装最新版本
nvm install node

# 切换到特定版本
nvm use 20.10.0
nvm use --lts
nvm use node

# 设置默认版本
nvm alias default 20.10.0
nvm alias default node

# 查看当前使用的版本
nvm current

# 卸载特定版本
nvm uninstall 18.19.0

# 查看 Node.js 版本
node --version

# 查看 npm 版本
npm --version
```

### NVM 使用示例

```bash
# 1. 安装最新 LTS 版本
nvm install --lts

# 2. 使用该版本
nvm use --lts

# 3. 设置为默认版本
nvm alias default --lts

# 4. 验证
node --version
npm --version
```

---

## Docker 环境更新

### 更新 Dockerfile 中的 Node.js 版本

```dockerfile
# 使用最新 LTS 版本
FROM node:20-lts

# 或指定具体版本
FROM node:20.10.0

# 或使用 Alpine 版本（更小）
FROM node:20-alpine
```

### 更新运行中的容器

```bash
# 1. 修改 Dockerfile 中的 Node.js 版本
# 2. 重新构建镜像
docker build -t myapp:latest .

# 3. 重启容器
docker-compose down
docker-compose up -d --build
```

---

## 更新 npm

Node.js 安装包通常包含 npm，但也可以单独更新：

```bash
# 更新到最新版本
npm install -g npm@latest

# 更新到特定版本
npm install -g npm@10.2.0

# 查看当前版本
npm --version

# 查看可用版本
npm view npm versions
```

---

## 验证更新

更新后，验证安装：

```bash
# 检查 Node.js 版本
node --version

# 检查 npm 版本
npm --version

# 检查所有版本信息
node -p "process.versions"

# 测试 Node.js 是否正常工作
node -e "console.log('Node.js is working!')"
```

---

## 常见问题

### Q1: 更新后版本没有变化

**可能原因：**
1. 多个 Node.js 安装路径
2. PATH 环境变量配置问题
3. 需要重启终端

**解决方法：**

```bash
# 查找 Node.js 安装位置
which node
whereis node  # Linux
where node    # Windows

# 检查 PATH 环境变量
echo $PATH  # macOS/Linux
echo %PATH% # Windows

# 清除缓存并重新加载
hash -r  # macOS/Linux
```

---

### Q2: 权限错误（Permission denied）

**解决方法：**

```bash
# macOS/Linux: 使用 sudo（不推荐）或修复权限
sudo chown -R $(whoami) /usr/local/lib/node_modules
sudo chown -R $(whoami) /usr/local/bin

# 或使用 NVM（推荐，不需要 sudo）
nvm install node
```

---

### Q3: 更新后项目无法运行

**可能原因：**
- Node.js 版本不兼容
- 依赖包需要重新安装

**解决方法：**

```bash
# 1. 检查项目要求的 Node.js 版本
cat .nvmrc  # 如果使用 NVM
cat package.json | grep engines

# 2. 删除 node_modules 并重新安装
rm -rf node_modules package-lock.json
npm install

# 3. 使用项目指定的 Node.js 版本（如果使用 NVM）
nvm use
```

---

### Q4: 如何降级 Node.js？

**使用 NVM：**

```bash
# 安装旧版本
nvm install 18.19.0

# 切换到旧版本
nvm use 18.19.0

# 设置为默认版本
nvm alias default 18.19.0
```

**其他方式：**
- 从官网下载旧版本安装包
- 使用包管理器安装特定版本

---

### Q5: 如何同时使用多个 Node.js 版本？

**使用 NVM（推荐）：**

```bash
# 安装多个版本
nvm install 18.19.0
nvm install 20.10.0
nvm install 22.0.0

# 在不同项目中使用不同版本
cd project1
nvm use 18.19.0

cd ../project2
nvm use 20.10.0

# 或创建 .nvmrc 文件
echo "18.19.0" > .nvmrc
nvm use  # 自动使用 .nvmrc 中的版本
```

---

## 最佳实践

### 1. 使用 NVM 管理版本

- ✅ 可以轻松切换版本
- ✅ 不需要 sudo 权限
- ✅ 适合开发环境

### 2. 使用 LTS 版本

- ✅ 长期支持，更稳定
- ✅ 适合生产环境

### 3. 在项目中指定 Node.js 版本

**创建 `.nvmrc` 文件：**
```
20.10.0
```

**在 `package.json` 中指定：**
```json
{
  "engines": {
    "node": ">=18.0.0",
    "npm": ">=9.0.0"
  }
}
```

---

## 快速参考

### macOS

```bash
# 使用 Homebrew
brew upgrade node

# 使用 NVM（推荐）
nvm install --lts
nvm use --lts
```

### Linux (Ubuntu/Debian)

```bash
# 使用 NodeSource
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt-get install -y nodejs

# 使用 NVM（推荐）
nvm install --lts
nvm use --lts
```

### Windows

```bash
# 从官网下载安装包
# 或使用 NVM for Windows
nvm install latest
nvm use latest
```

---

## 相关资源

- [Node.js 官网](https://nodejs.org/)
- [NVM GitHub](https://github.com/nvm-sh/nvm)
- [npm 官网](https://www.npmjs.com/)
- [Node.js 版本发布说明](https://nodejs.org/en/blog/release/)

---

## 总结

**推荐更新方式：**

1. **开发环境**: 使用 NVM 管理多个版本
2. **生产环境**: 使用 LTS 版本
3. **Docker**: 在 Dockerfile 中指定版本

**快速更新命令：**

```bash
# macOS/Linux (使用 NVM)
nvm install --lts && nvm use --lts && nvm alias default --lts

# macOS (使用 Homebrew)
brew upgrade node

# Linux (使用 NodeSource)
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash - && sudo apt-get install -y nodejs
```
