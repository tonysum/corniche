# Ubuntu 服务器 Git Clone 指南

本文档介绍如何在 Ubuntu 服务器上使用 Git 克隆 corniche 仓库。

## 📋 目录

1. [前置准备](#前置准备)
2. [安装 Git](#安装-git)
3. [配置 Git（可选）](#配置-git可选)
4. [克隆仓库](#克隆仓库)
5. [SSH 密钥配置](#ssh-密钥配置)
6. [常见问题](#常见问题)
7. [后续操作](#后续操作)

---

## 前置准备

### 1. 连接到服务器

```bash
# 使用 SSH 连接服务器
ssh username@server-ip

# 或使用密钥文件
ssh -i /path/to/key.pem username@server-ip
```

### 2. 检查 Git 是否已安装

```bash
git --version
```

如果显示版本号（如 `git version 2.34.1`），说明已安装，可以跳过安装步骤。

---

## 安装 Git

### Ubuntu/Debian

```bash
# 更新软件包列表
sudo apt-get update

# 安装 Git
sudo apt-get install -y git

# 验证安装
git --version
```

### CentOS/RHEL

```bash
# 安装 Git
sudo yum install -y git

# 或使用 dnf (CentOS 8+)
sudo dnf install -y git

# 验证安装
git --version
```

---

## 配置 Git（可选）

虽然不配置也能克隆公开仓库，但建议配置用户信息，便于后续提交：

```bash
# 配置用户名
git config --global user.name "Your Name"

# 配置邮箱
git config --global user.email "your.email@example.com"

# 查看配置
git config --list

# 查看特定配置
git config user.name
git config user.email
```

---

## 克隆仓库

### 方法1: 使用 HTTPS（最简单，推荐）

**优点：**
- ✅ 无需配置 SSH 密钥
- ✅ 适合公开仓库
- ✅ 操作简单

**缺点：**
- ❌ 私有仓库需要输入用户名和密码（或 Personal Access Token）

#### 克隆公开仓库

```bash
# 克隆到当前目录
git clone https://github.com/tonysum/corniche.git

# 克隆到指定目录
git clone https://github.com/tonysum/corniche.git /opt/corniche

# 克隆到当前目录并重命名
git clone https://github.com/tonysum/corniche.git my-corniche
```

#### 克隆私有仓库（需要认证）

**方式1: 使用 Personal Access Token**

```bash
# 克隆时会提示输入用户名和密码
# 用户名: 你的 GitHub 用户名
# 密码: 使用 Personal Access Token（不是 GitHub 密码）

git clone https://github.com/tonysum/corniche.git
```

**创建 Personal Access Token:**
1. GitHub → Settings → Developer settings → Personal access tokens → Tokens (classic)
2. Generate new token (classic)
3. 选择权限（至少需要 `repo`）
4. 复制生成的 token（只显示一次）

**方式2: 在 URL 中包含 token（不推荐，不安全）**

```bash
# 不推荐：token 会出现在命令历史中
git clone https://token@github.com/tonysum/corniche.git
```

---

### 方法2: 使用 SSH（推荐，更安全）

**优点：**
- ✅ 无需每次输入密码
- ✅ 更安全
- ✅ 适合频繁操作

**缺点：**
- ❌ 需要配置 SSH 密钥

#### 步骤1: 检查是否已有 SSH 密钥

```bash
# 检查是否存在 SSH 密钥
ls -la ~/.ssh

# 如果看到 id_rsa 和 id_rsa.pub，说明已有密钥
```

#### 步骤2: 生成 SSH 密钥（如果没有）

```bash
# 生成新的 SSH 密钥
ssh-keygen -t ed25519 -C "your_email@example.com"

# 如果系统不支持 ed25519，使用 RSA
ssh-keygen -t rsa -b 4096 -C "your_email@example.com"

# 按提示操作：
# - 密钥保存位置: 直接回车（使用默认 ~/.ssh/id_rsa）
# - 密码: 可以设置密码或直接回车（不设置密码）
```

#### 步骤3: 查看公钥

```bash
# 显示公钥内容
cat ~/.ssh/id_ed25519.pub
# 或
cat ~/.ssh/id_rsa.pub

# 复制整个公钥内容（从 ssh-ed25519 或 ssh-rsa 开始到邮箱结束）
```

#### 步骤4: 添加 SSH 密钥到 GitHub

1. 登录 GitHub
2. Settings → SSH and GPG keys → New SSH key
3. Title: 填写描述（如 "Ubuntu Server"）
4. Key: 粘贴刚才复制的公钥
5. Add SSH key

#### 步骤5: 测试 SSH 连接

```bash
# 测试 GitHub SSH 连接
ssh -T git@github.com

# 如果成功，会看到：
# Hi tonysum! You've successfully authenticated, but GitHub does not provide shell access.
```

#### 步骤6: 使用 SSH 克隆

```bash
# 使用 SSH URL 克隆
git clone git@github.com:tonysum/corniche.git

# 克隆到指定目录
git clone git@github.com:tonysum/corniche.git /opt/corniche
```

---

## SSH 密钥配置

### 使用多个 SSH 密钥

如果服务器上有多个 GitHub 账户，可以配置多个 SSH 密钥：

#### 1. 生成不同名称的密钥

```bash
# 为第二个账户生成密钥
ssh-keygen -t ed25519 -C "second_email@example.com" -f ~/.ssh/id_ed25519_second
```

#### 2. 配置 SSH config

```bash
# 编辑 SSH 配置文件
nano ~/.ssh/config
```

添加以下内容：

```
# GitHub 主账户
Host github.com
    HostName github.com
    User git
    IdentityFile ~/.ssh/id_ed25519

# GitHub 第二个账户
Host github-second
    HostName github.com
    User git
    IdentityFile ~/.ssh/id_ed25519_second
```

#### 3. 使用不同的 Host 克隆

```bash
# 使用主账户
git clone git@github.com:tonysum/corniche.git

# 使用第二个账户
git clone git@github-second:otheruser/corniche.git
```

---

## 常见问题

### Q1: 提示 "Permission denied (publickey)"

**原因**: SSH 密钥未配置或未添加到 GitHub

**解决方法**:
```bash
# 1. 检查 SSH 密钥是否存在
ls -la ~/.ssh

# 2. 如果不存在，生成密钥
ssh-keygen -t ed25519 -C "your_email@example.com"

# 3. 添加公钥到 GitHub（见上面的步骤）

# 4. 测试连接
ssh -T git@github.com
```

---

### Q2: 提示 "fatal: repository not found"

**可能原因**:
1. 仓库不存在或名称错误
2. 仓库是私有的，但没有权限
3. 使用了错误的 URL

**解决方法**:
```bash
# 1. 检查仓库 URL 是否正确
# 公开仓库: https://github.com/tonysum/corniche.git
# 私有仓库: 确保已配置 SSH 密钥或使用 Personal Access Token

# 2. 使用 HTTPS 方式测试
git clone https://github.com/tonysum/corniche.git

# 3. 检查仓库是否存在
curl -I https://github.com/tonysum/corniche
```

---

### Q3: 提示 "Host key verification failed"

**原因**: SSH 首次连接需要确认主机密钥

**解决方法**:
```bash
# 手动添加 GitHub 到 known_hosts
ssh-keyscan github.com >> ~/.ssh/known_hosts

# 或直接确认（输入 yes）
ssh -T git@github.com
```

---

### Q4: 克隆速度很慢

**解决方法**:

**方式1: 使用镜像源（国内服务器推荐）**

```bash
# 使用 Gitee 镜像（如果有）
git clone https://gitee.com/tonysum/corniche.git

# 或使用 GitHub 镜像
git clone https://github.com.cnpmjs.org/tonysum/corniche.git
```

**方式2: 配置 Git 代理**

```bash
# 设置 HTTP 代理
git config --global http.proxy http://proxy.example.com:8080
git config --global https.proxy https://proxy.example.com:8080

# 取消代理
git config --global --unset http.proxy
git config --global --unset https.proxy
```

**方式3: 使用浅克隆（只克隆最新提交）**

```bash
# 只克隆最新的一次提交
git clone --depth 1 https://github.com/tonysum/corniche.git

# 后续需要完整历史时
git fetch --unshallow
```

---

### Q5: 磁盘空间不足

**解决方法**:
```bash
# 1. 检查磁盘空间
df -h

# 2. 清理不需要的文件
sudo apt-get clean
sudo apt-get autoremove

# 3. 克隆到有足够空间的分区
git clone https://github.com/tonysum/corniche.git /mnt/large-disk/corniche
```

---

### Q6: 网络连接超时

**解决方法**:
```bash
# 1. 检查网络连接
ping github.com

# 2. 检查 DNS 解析
nslookup github.com

# 3. 使用 IP 地址（不推荐，IP 可能变化）
# 先查询 GitHub IP
nslookup github.com
# 然后修改 /etc/hosts（临时方案）
```

---

## 后续操作

### 1. 进入项目目录

```bash
cd corniche
# 或
cd /opt/corniche
```

### 2. 查看项目结构

```bash
ls -la
tree  # 如果安装了 tree 命令
```

### 3. 查看分支

```bash
# 查看所有分支
git branch -a

# 切换到其他分支
git checkout branch-name
```

### 4. 更新代码

```bash
# 拉取最新更新
git pull origin main

# 或指定分支
git pull origin develop
```

### 5. 查看提交历史

```bash
# 查看提交历史
git log --oneline

# 查看最近 10 条提交
git log -10 --oneline
```

---

## 完整示例

### 示例1: 首次克隆（HTTPS）

```bash
# 1. 更新系统
sudo apt-get update

# 2. 安装 Git
sudo apt-get install -y git

# 3. 配置 Git（可选）
git config --global user.name "Server User"
git config --global user.email "server@example.com"

# 4. 克隆仓库
cd /opt
sudo mkdir -p corniche
sudo chown $USER:$USER corniche
git clone https://github.com/tonysum/corniche.git /opt/corniche

# 5. 进入项目目录
cd /opt/corniche

# 6. 查看项目结构
ls -la
```

### 示例2: 使用 SSH 克隆

```bash
# 1. 安装 Git
sudo apt-get update && sudo apt-get install -y git

# 2. 生成 SSH 密钥
ssh-keygen -t ed25519 -C "server@example.com"
# 直接回车使用默认设置

# 3. 显示公钥
cat ~/.ssh/id_ed25519.pub
# 复制输出的内容

# 4. 将公钥添加到 GitHub（在浏览器中操作）
# GitHub → Settings → SSH and GPG keys → New SSH key

# 5. 测试 SSH 连接
ssh -T git@github.com

# 6. 克隆仓库
git clone git@github.com:tonysum/corniche.git /opt/corniche

# 7. 进入项目目录
cd /opt/corniche
```

### 示例3: 克隆到特定目录并设置权限

```bash
# 1. 创建项目目录
sudo mkdir -p /opt/corniche
sudo chown $USER:$USER /opt/corniche

# 2. 克隆到该目录
git clone https://github.com/tonysum/corniche.git /opt/corniche

# 3. 设置权限（如果需要）
cd /opt/corniche
chmod -R 755 .

# 4. 查看项目信息
git remote -v
git branch
```

---

## 快速参考

### 常用命令

```bash
# 安装 Git
sudo apt-get install -y git

# 克隆仓库（HTTPS）
git clone https://github.com/tonysum/corniche.git

# 克隆仓库（SSH）
git clone git@github.com:tonysum/corniche.git

# 克隆到指定目录
git clone https://github.com/tonysum/corniche.git /opt/corniche

# 更新代码
git pull origin main

# 查看状态
git status

# 查看分支
git branch -a
```

### 仓库 URL 格式

```
HTTPS: https://github.com/tonysum/corniche.git
SSH:   git@github.com:tonysum/corniche.git
```

---

## 相关文档

- [Linux服务器安装指南.md](./Linux服务器安装指南.md) - 完整的服务器部署指南
- [文件上传指南.md](./文件上传指南.md) - 其他文件上传方式
- [GitHub_Fork同步指南.md](./GitHub_Fork同步指南.md) - Fork 仓库同步方法

---

## 总结

**最简单的克隆方式（公开仓库）:**

```bash
sudo apt-get update && sudo apt-get install -y git
git clone https://github.com/tonysum/corniche.git
cd corniche
```

**推荐的克隆方式（私有仓库或频繁操作）:**

```bash
# 1. 安装 Git
sudo apt-get install -y git

# 2. 配置 SSH 密钥
ssh-keygen -t ed25519 -C "your_email@example.com"
cat ~/.ssh/id_ed25519.pub  # 复制并添加到 GitHub

# 3. 测试连接
ssh -T git@github.com

# 4. 克隆仓库
git clone git@github.com:tonysum/corniche.git
```
