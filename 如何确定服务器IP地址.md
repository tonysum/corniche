# 如何确定服务器 IP 地址

本文档介绍如何查找和确定服务器的 IP 地址。

## 📋 目录

1. [云服务商控制台查看](#云服务商控制台查看)
2. [在服务器上查看](#在服务器上查看)
3. [从本地连接信息查看](#从本地连接信息查看)
4. [使用域名的情况](#使用域名的情况)
5. [常见场景](#常见场景)

---

## 云服务商控制台查看

### 1. 阿里云 ECS

**步骤：**
1. 登录 [阿里云控制台](https://ecs.console.aliyun.com/)
2. 进入 **云服务器 ECS** → **实例**
3. 找到你的服务器实例
4. 查看 **公网IP** 或 **内网IP**

**公网IP vs 内网IP：**
- **公网IP**: 用于从互联网访问服务器（如：`47.xxx.xxx.xxx`）
- **内网IP**: 用于同一地域内的服务器间通信（如：`172.16.xxx.xxx`）

---

### 2. 腾讯云 CVM

**步骤：**
1. 登录 [腾讯云控制台](https://console.cloud.tencent.com/)
2. 进入 **云服务器** → **实例**
3. 找到你的服务器实例
4. 查看 **公网IP** 或 **内网IP**

---

### 3. AWS EC2

**步骤：**
1. 登录 [AWS 控制台](https://console.aws.amazon.com/)
2. 进入 **EC2** → **Instances**
3. 选择你的实例
4. 在详情面板查看 **Public IPv4 address** 或 **Private IPv4 address**

**注意：**
- 如果实例重启，弹性IP（Elastic IP）会保持不变
- 普通公网IP在实例停止后可能会变化

---

### 4. 华为云 ECS

**步骤：**
1. 登录 [华为云控制台](https://console.huaweicloud.com/)
2. 进入 **弹性云服务器 ECS**
3. 找到你的服务器实例
4. 查看 **弹性公网IP** 或 **私有IP**

---

### 5. 其他云服务商

- **Google Cloud Platform**: Compute Engine → VM instances
- **Azure**: Virtual machines
- **DigitalOcean**: Droplets
- **Vultr**: Servers
- **Linode**: Linodes

---

## 在服务器上查看

### 方法1: 使用 ip 命令（推荐）

```bash
# 查看所有网络接口
ip addr show
# 或简写
ip a

# 查看公网IP（需要连接到外网）
curl ifconfig.me
curl ipinfo.io/ip
curl icanhazip.com

# 查看内网IP
hostname -I
ip addr show | grep "inet " | grep -v 127.0.0.1
```

---

### 方法2: 使用 ifconfig 命令

```bash
# 安装 net-tools（如果没有）
sudo apt-get install net-tools  # Ubuntu/Debian
sudo yum install net-tools       # CentOS/RHEL

# 查看网络接口
ifconfig

# 查看特定接口
ifconfig eth0
ifconfig ens33
```

**输出示例：**
```
eth0: flags=4163<UP,BROADCAST,RUNNING,MULTICAST>  mtu 1500
        inet 172.16.0.100  netmask 255.255.0.0  broadcast 172.16.255.255
        ...
```

---

### 方法3: 使用 hostname 命令

```bash
# 查看主机名和IP
hostname -I

# 查看完整主机名
hostname -f
```

---

### 方法4: 查看路由表

```bash
# 查看默认网关（通常是内网IP段）
ip route show
route -n

# 查看公网IP
curl ifconfig.me
```

---

## 从本地连接信息查看

### 方法1: 查看 SSH 连接信息

如果你已经通过 SSH 连接到服务器，可以从连接命令中看到：

```bash
# 查看当前SSH连接
who am i
w

# 查看SSH配置
cat ~/.ssh/config

# 查看已知主机
cat ~/.ssh/known_hosts | grep server-name
```

---

### 方法2: 从连接命令中提取

如果你之前连接过服务器，IP地址可能在：
- 命令历史中
- SSH配置文件（`~/.ssh/config`）
- 保存的连接信息

```bash
# 查看命令历史
history | grep ssh

# 查看SSH配置
cat ~/.ssh/config
```

---

### 方法3: 使用 ping 或 nslookup

如果你知道域名：

```bash
# 使用 ping
ping example.com

# 使用 nslookup
nslookup example.com

# 使用 dig
dig example.com +short
```

---

## 使用域名的情况

### 1. 使用域名代替IP

如果你有域名，可以直接使用域名：

```bash
# 使用域名连接
ssh username@example.com
scp file.txt username@example.com:/path/

# 域名会自动解析为IP地址
```

---

### 2. 查看域名对应的IP

```bash
# 方法1: 使用 ping
ping example.com
# 输出: PING example.com (47.xxx.xxx.xxx) ...

# 方法2: 使用 nslookup
nslookup example.com
# 输出: Address: 47.xxx.xxx.xxx

# 方法3: 使用 dig
dig example.com +short
# 输出: 47.xxx.xxx.xxx

# 方法4: 使用 host
host example.com
```

---

## 常见场景

### 场景1: 首次连接服务器

**步骤：**

1. **从云服务商控制台获取IP**
   - 登录云服务商控制台
   - 找到服务器实例
   - 复制公网IP地址

2. **测试连接**
   ```bash
   # 测试SSH连接
   ssh username@47.xxx.xxx.xxx
   
   # 或使用密钥文件
   ssh -i /path/to/key.pem username@47.xxx.xxx.xxx
   ```

3. **保存到SSH配置**
   ```bash
   # 编辑SSH配置
   nano ~/.ssh/config
   
   # 添加配置
   Host myserver
       HostName 47.xxx.xxx.xxx
       User username
       IdentityFile ~/.ssh/key.pem
   
   # 之后可以直接使用
   ssh myserver
   ```

---

### 场景2: 忘记服务器IP

**方法1: 查看云服务商控制台**
- 登录控制台，查看实例列表

**方法2: 查看SSH配置**
```bash
cat ~/.ssh/config
```

**方法3: 查看命令历史**
```bash
history | grep ssh
history | grep scp
```

**方法4: 查看已知主机**
```bash
cat ~/.ssh/known_hosts
```

---

### 场景3: 区分公网IP和内网IP

**公网IP（Public IP）:**
- 用于从互联网访问
- 在云服务商控制台显示
- 可以通过 `curl ifconfig.me` 查看
- 格式通常是：`47.xxx.xxx.xxx`、`123.xxx.xxx.xxx` 等

**内网IP（Private IP）:**
- 用于同一地域/网络内的服务器间通信
- 在服务器上通过 `ip addr` 查看
- 格式通常是：
  - `10.0.0.0/8`
  - `172.16.0.0/12`
  - `192.168.0.0/16`

**使用场景：**
- **上传文件到服务器**: 使用公网IP
- **服务器间通信**: 使用内网IP（更快、免费）

---

### 场景4: 动态IP地址

某些云服务商的实例重启后IP会变化：

**解决方法：**

1. **使用弹性IP（Elastic IP）**
   - AWS: 分配并绑定Elastic IP
   - 阿里云: 使用弹性公网IP
   - 腾讯云: 使用弹性公网IP

2. **使用域名**
   - 配置域名解析指向服务器IP
   - 即使IP变化，只需更新DNS记录

3. **查看最新IP**
   ```bash
   # 在服务器上查看
   curl ifconfig.me
   
   # 或从控制台查看
   ```

---

## 实用脚本

### 脚本1: 快速查看服务器IP信息

创建 `check_server_ip.sh`:

```bash
#!/bin/bash

echo "=== 服务器IP地址信息 ==="
echo ""

echo "1. 内网IP地址:"
hostname -I
echo ""

echo "2. 详细网络接口信息:"
ip addr show | grep "inet " | grep -v 127.0.0.1
echo ""

echo "3. 公网IP地址:"
curl -s ifconfig.me
echo ""
echo ""

echo "4. IP地理位置信息:"
curl -s ipinfo.io
```

使用：
```bash
chmod +x check_server_ip.sh
./check_server_ip.sh
```

---

### 脚本2: 测试服务器连接

创建 `test_connection.sh`:

```bash
#!/bin/bash

read -p "请输入服务器IP或域名: " SERVER
read -p "请输入用户名: " USERNAME

echo "测试连接..."

# 测试SSH连接
if ssh -o ConnectTimeout=5 -o BatchMode=yes $USERNAME@$SERVER echo "SSH连接成功" 2>/dev/null; then
    echo "✓ SSH连接正常"
else
    echo "✗ SSH连接失败"
fi

# 测试端口
echo "测试常用端口..."
for port in 22 80 443 8001 8002 8003; do
    if timeout 2 bash -c "echo >/dev/tcp/$SERVER/$port" 2>/dev/null; then
        echo "✓ 端口 $port 开放"
    else
        echo "✗ 端口 $port 关闭或无法访问"
    fi
done
```

---

## 快速参考

### 查看IP地址的命令

| 命令 | 说明 | 示例 |
|------|------|------|
| `ip addr show` | 查看所有网络接口 | `ip a` |
| `hostname -I` | 查看内网IP | `172.16.0.100` |
| `curl ifconfig.me` | 查看公网IP | `47.xxx.xxx.xxx` |
| `ifconfig` | 查看网络接口（需安装） | `ifconfig eth0` |
| `ip route show` | 查看路由表 | `ip route` |

### 云服务商控制台位置

| 服务商 | 控制台位置 |
|--------|-----------|
| 阿里云 | 云服务器ECS → 实例 → 公网IP |
| 腾讯云 | 云服务器 → 实例 → 公网IP |
| AWS | EC2 → Instances → Public IPv4 |
| 华为云 | 弹性云服务器 → 弹性公网IP |

---

## 常见问题

### Q1: 找不到服务器IP地址

**解决方法：**
1. 检查云服务商控制台
2. 检查邮件通知（创建服务器时的邮件）
3. 联系云服务商客服

---

### Q2: IP地址无法连接

**可能原因：**
1. 安全组未开放端口
2. 防火墙阻止
3. IP地址错误
4. 服务器未启动

**解决方法：**
```bash
# 1. 检查服务器是否运行
ping server-ip

# 2. 检查端口是否开放
telnet server-ip 22
# 或
nc -zv server-ip 22

# 3. 检查安全组规则（在云服务商控制台）
```

---

### Q3: 公网IP和内网IP的区别

**公网IP：**
- 全球唯一
- 可以从互联网访问
- 通常需要付费

**内网IP：**
- 在同一网络内唯一
- 只能在同一网络内访问
- 免费

**使用建议：**
- 上传文件、SSH连接：使用公网IP
- 服务器间通信：使用内网IP（更快、免费）

---

### Q4: IP地址会变化吗？

**普通公网IP：**
- 实例重启后可能变化
- 实例删除后释放

**弹性IP：**
- 固定不变
- 可以绑定到不同实例
- 通常需要付费

---

## 总结

**确定服务器IP的常用方法：**

1. **最简单**: 登录云服务商控制台查看
2. **在服务器上**: `curl ifconfig.me`（公网）或 `hostname -I`（内网）
3. **从本地**: 查看SSH配置或命令历史
4. **使用域名**: `nslookup domain.com` 或 `ping domain.com`

**推荐流程：**

```bash
# 1. 从控制台获取IP（或域名）
# 2. 测试连接
ping server-ip
ssh username@server-ip

# 3. 保存到SSH配置（方便后续使用）
# 编辑 ~/.ssh/config
```
