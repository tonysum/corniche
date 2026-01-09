# 解决 "sudo: command not found" 问题

## 问题原因

`sudo: command not found` 错误通常出现在以下情况：
1. **Docker 容器中** - 容器通常不包含 sudo
2. **最小化 Linux 系统** - 某些精简版系统未安装 sudo
3. **已经是 root 用户** - root 用户不需要 sudo

---

## 快速解决方案

### 方案1: 检查是否已经是 root 用户

```bash
# 检查当前用户
whoami

# 如果是 root，直接执行命令（不需要 sudo）
# 例如：
apt-get update  # 而不是 sudo apt-get update
```

---

### 方案2: 安装 sudo（如果不是 root 用户）

#### Ubuntu/Debian

```bash
# 切换到 root 用户
su -

# 安装 sudo
apt-get update
apt-get install -y sudo

# 将当前用户添加到 sudo 组
usermod -aG sudo $USER

# 退出 root
exit

# 重新登录后生效
```

#### CentOS/RHEL

```bash
# 切换到 root 用户
su -

# 安装 sudo
yum install -y sudo
# 或 (CentOS 8+)
dnf install -y sudo

# 将用户添加到 sudo 组
usermod -aG wheel $USER

# 退出 root
exit
```

#### Alpine Linux

```bash
# 切换到 root
su -

# 安装 sudo
apk add sudo

# 配置 sudo
echo "$USER ALL=(ALL) ALL" >> /etc/sudoers

# 退出 root
exit
```

---

### 方案3: Docker 容器中（推荐直接使用 root）

在 Docker 容器中，通常直接使用 root 用户，不需要 sudo：

```bash
# 直接执行命令，不加 sudo
apt-get update
apt-get install -y nodejs

# 或使用 apt（Ubuntu 22.04+）
apt update
apt install -y nodejs
```

---

## 针对 Node.js 更新的解决方案

### 情况1: 已经是 root 用户

```bash
# 直接执行，不需要 sudo
curl -fsSL https://deb.nodesource.com/setup_20.x | bash -
apt-get install -y nodejs
```

### 情况2: Docker 容器中

```bash
# 方法1: 直接使用 root（推荐）
curl -fsSL https://deb.nodesource.com/setup_20.x | bash -
apt-get install -y nodejs

# 方法2: 使用 NVM（不需要 sudo）
curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.0/install.sh | bash
source ~/.bashrc
nvm install --lts
```

### 情况3: 普通用户需要 sudo

```bash
# 先安装 sudo（需要 root 权限）
su -
apt-get install -y sudo
usermod -aG sudo $USER
exit

# 然后使用 sudo
sudo apt-get update
sudo apt-get install -y nodejs
```

---

## 修改后的 Ubuntu Node.js 更新脚本

创建 `update_nodejs_ubuntu_no_sudo.sh`:

```bash
#!/bin/bash

# Ubuntu Node.js 更新脚本（不需要 sudo）

set -e

# 检查是否是 root 用户
if [ "$EUID" -eq 0 ]; then
    SUDO_CMD=""
    echo "检测到 root 用户，不需要 sudo"
else
    # 检查是否有 sudo
    if command -v sudo &> /dev/null; then
        SUDO_CMD="sudo"
        echo "使用 sudo 执行命令"
    else
        echo "警告: 未找到 sudo，尝试直接执行（需要 root 权限）"
        SUDO_CMD=""
    fi
fi

echo "=== Ubuntu Node.js 更新工具 ==="
echo ""

# 检查当前版本
echo "当前 Node.js 版本:"
node --version 2>/dev/null || echo "未安装"
echo ""

# 选择更新方式
echo "请选择更新方式:"
echo "1. 使用 NodeSource 仓库（推荐）"
echo "2. 使用 NVM（推荐，不需要 root）"
read -p "请选择 (1-2): " METHOD

case $METHOD in
    1)
        echo ""
        echo "使用 NodeSource 仓库更新..."
        echo "选择 Node.js 版本:"
        echo "1. Node.js 20.x (LTS)"
        echo "2. Node.js 22.x (最新)"
        read -p "请选择 (1-2): " VERSION
        
        case $VERSION in
            1) SETUP_SCRIPT="setup_20.x" ;;
            2) SETUP_SCRIPT="setup_22.x" ;;
            *) SETUP_SCRIPT="setup_20.x" ;;
        esac
        
        curl -fsSL https://deb.nodesource.com/setup_${SETUP_SCRIPT} | $SUDO_CMD bash -
        $SUDO_CMD apt-get install -y nodejs
        ;;
    2)
        echo ""
        echo "使用 NVM 更新（不需要 root 权限）..."
        
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
        ;;
    *)
        echo "无效选择"
        exit 1
        ;;
esac

echo ""
echo "=== 更新完成 ==="
node --version
npm --version
```

---

## 快速参考

### 检查用户身份

```bash
# 检查当前用户
whoami

# 检查用户ID（root 是 0）
id -u

# 检查是否有 sudo
command -v sudo
```

### 根据情况选择命令

| 情况 | 命令格式 |
|------|----------|
| root 用户 | `apt-get install nodejs` |
| 有 sudo | `sudo apt-get install nodejs` |
| 无 sudo，非 root | 先安装 sudo 或使用 NVM |
| Docker 容器 | `apt-get install nodejs`（直接 root） |

---

## 推荐方案

### Docker 容器中（最常见）

```bash
# 直接使用 root，不需要 sudo
curl -fsSL https://deb.nodesource.com/setup_20.x | bash -
apt-get install -y nodejs
```

### 普通 Linux 系统

```bash
# 使用 NVM（不需要 sudo，推荐）
curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.0/install.sh | bash
source ~/.bashrc
nvm install --lts
```

---

## 常见问题

### Q1: 如何判断是否需要 sudo？

```bash
# 检查是否是 root
if [ "$EUID" -eq 0 ]; then
    echo "是 root，不需要 sudo"
else
    echo "不是 root，需要 sudo"
fi
```

### Q2: Docker 容器中如何更新 Node.js？

```bash
# 直接使用 root 权限
apt-get update
apt-get install -y nodejs

# 或使用 NVM（推荐，不需要 root）
curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.0/install.sh | bash
source ~/.bashrc
nvm install --lts
```

### Q3: 如何安装 sudo？

```bash
# 切换到 root
su -

# 安装 sudo
apt-get install -y sudo  # Ubuntu/Debian
yum install -y sudo      # CentOS/RHEL
apk add sudo              # Alpine

# 添加用户到 sudo 组
usermod -aG sudo $USER   # Ubuntu/Debian
usermod -aG wheel $USER  # CentOS/RHEL
```

---

## 总结

**遇到 "sudo: command not found" 时：**

1. **检查用户身份** - `whoami`
2. **如果是 root** - 直接执行命令，不加 sudo
3. **如果不是 root** - 使用 NVM（推荐）或安装 sudo
4. **Docker 容器** - 直接使用 root，不需要 sudo

**推荐方案：使用 NVM（不需要 sudo）**

```bash
curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.0/install.sh | bash
source ~/.bashrc
nvm install --lts
```
