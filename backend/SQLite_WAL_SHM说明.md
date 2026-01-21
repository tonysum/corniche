# SQLite WAL 和 SHM 文件说明

## 📋 概述

当你看到 `crypto_data.db-wal` 和 `crypto_data.db-shm` 文件时，说明 SQLite 数据库正在使用 **WAL（Write-Ahead Logging）模式**。

## 🔍 文件说明

### 1. `.db-wal` 文件（Write-Ahead Log）

**作用**：
- **预写日志文件**：记录所有对数据库的修改操作
- **提高并发性能**：允许多个读操作和一个写操作同时进行
- **提高写入性能**：写入操作先写入 WAL 文件，而不是直接修改主数据库文件

**工作原理**：
1. 当有写入操作时，SQLite 先将修改写入 WAL 文件
2. 读操作可以同时从主数据库文件读取（不需要等待写入完成）
3. 当 WAL 文件达到一定大小时，SQLite 会将修改合并回主数据库文件（这个过程叫 "checkpoint"）

**文件特点**：
- 文件大小会动态增长（随着写入操作增加）
- 正常情况下会自动清理（checkpoint 后）
- 如果程序异常退出，WAL 文件会保留，下次启动时自动恢复

### 2. `.db-shm` 文件（Shared Memory）

**作用**：
- **共享内存文件**：用于多个数据库连接之间的协调
- **锁管理**：管理数据库的读写锁
- **WAL 索引**：存储 WAL 文件的索引信息，加速查找

**工作原理**：
1. 多个进程/线程连接同一个数据库时，通过 SHM 文件协调
2. 记录哪些页面在 WAL 文件中，哪些在主数据库中
3. 管理读写锁，确保数据一致性

**文件特点**：
- 文件大小通常很小（几 KB 到几 MB）
- 只在数据库连接打开时存在
- 关闭所有连接后会自动删除

## ⚙️ 为什么使用 WAL 模式？

在你的代码中（`hm1new.py` 和 `hm1.py`），可以看到：

```python
self.crypto_conn.execute("PRAGMA journal_mode=WAL")  # 启用WAL模式，提高并发性能
```

### WAL 模式的优势

| 特性 | 传统模式（DELETE） | WAL 模式 |
|------|-------------------|----------|
| **并发读取** | 较差（写操作会阻塞读） | ✅ 优秀（读操作不阻塞） |
| **并发写入** | 差（一次只能一个写操作） | ✅ 较好（支持一个写+多个读） |
| **写入性能** | 一般 | ✅ 更好（批量写入） |
| **数据安全** | ✅ 高 | ✅ 高（事务完整性） |

### 适用场景

WAL 模式特别适合：
- ✅ **多进程/多线程访问**：多个程序同时读取数据库
- ✅ **读多写少**：大量查询操作，少量写入操作
- ✅ **需要高并发性能**：需要同时处理多个请求

## 📊 文件大小管理

### WAL 文件大小

WAL 文件的大小取决于：
1. **写入操作量**：写入越多，WAL 文件越大
2. **Checkpoint 频率**：checkpoint 会将 WAL 合并回主数据库
3. **Checkpoint 阈值**：默认是 1000 页（约 4MB）

### 查看 WAL 文件大小

```bash
# 查看 WAL 文件大小
ls -lh data/crypto_data.db-wal

# 查看 SHM 文件大小
ls -lh data/crypto_data.db-shm
```

### 手动触发 Checkpoint

如果 WAL 文件过大，可以手动触发 checkpoint：

```python
import sqlite3

conn = sqlite3.connect('data/crypto_data.db')
conn.execute('PRAGMA wal_checkpoint(TRUNCATE)')  # 合并并截断 WAL
conn.close()
```

或使用命令行：

```bash
sqlite3 data/crypto_data.db "PRAGMA wal_checkpoint(TRUNCATE);"
```

## 🔧 常见问题

### 1. WAL 文件很大，占用磁盘空间

**原因**：
- 大量写入操作，但 checkpoint 没有及时执行
- 程序异常退出，WAL 文件没有合并

**解决方案**：
```bash
# 手动触发 checkpoint
sqlite3 data/crypto_data.db "PRAGMA wal_checkpoint(TRUNCATE);"

# 或者使用 VACUUM（会合并 WAL 并压缩数据库）
sqlite3 data/crypto_data.db "VACUUM;"
```

### 2. 删除 WAL 文件会怎样？

**⚠️ 危险操作**：
- 如果数据库正在使用，**不要**手动删除 WAL 文件
- 可能导致数据丢失或数据库损坏

**安全删除方法**：
```bash
# 1. 确保没有程序在使用数据库
# 2. 触发 checkpoint 合并 WAL
sqlite3 data/crypto_data.db "PRAGMA wal_checkpoint(TRUNCATE);"
# 3. 关闭所有连接后，WAL 文件会自动删除（如果为空）
```

### 3. SHM 文件无法删除

**原因**：
- 有程序正在连接数据库
- 文件被锁定

**解决方案**：
```bash
# 1. 关闭所有使用数据库的程序
# 2. SHM 文件会自动删除
```

### 4. 迁移到 PostgreSQL 时 WAL 文件的影响

**迁移前建议**：
```bash
# 触发 checkpoint，确保所有数据都写入主数据库
sqlite3 data/crypto_data.db "PRAGMA wal_checkpoint(TRUNCATE);"

# 然后进行迁移
python migrate.py
```

这样可以确保迁移的数据是最新的。

## 📈 性能优化建议

### 1. 调整 Checkpoint 阈值

```python
# 设置 checkpoint 阈值（页数，默认 1000）
conn.execute('PRAGMA wal_autocheckpoint=2000')  # 增加到 2000 页
```

### 2. 定期手动 Checkpoint

对于写入频繁的场景，可以定期手动触发 checkpoint：

```python
# 每 1000 次写入后手动 checkpoint
if write_count % 1000 == 0:
    conn.execute('PRAGMA wal_checkpoint(TRUNCATE)')
```

### 3. 监控 WAL 文件大小

```bash
# 添加到监控脚本
watch -n 5 'ls -lh data/crypto_data.db-wal'
```

## 🔒 数据安全

### WAL 模式的数据安全性

- ✅ **事务完整性**：即使程序崩溃，事务也会完整恢复
- ✅ **数据一致性**：WAL 模式保证数据一致性
- ✅ **自动恢复**：下次打开数据库时，会自动从 WAL 恢复未提交的事务

### 备份建议

使用 WAL 模式时，备份数据库需要特殊处理：

```bash
# 方式1：使用 .backup 命令（推荐）
sqlite3 data/crypto_data.db ".backup backup.db"

# 方式2：触发 checkpoint 后复制文件
sqlite3 data/crypto_data.db "PRAGMA wal_checkpoint(TRUNCATE);"
cp data/crypto_data.db backup.db
```

## 📝 总结

| 文件 | 作用 | 是否可以删除 | 注意事项 |
|------|------|-------------|----------|
| `.db-wal` | 预写日志，提高并发性能 | ⚠️ 需要先 checkpoint | 删除前确保数据已合并 |
| `.db-shm` | 共享内存，协调多连接 | ✅ 关闭连接后自动删除 | 不要手动删除 |

## 🎯 最佳实践

1. **定期 Checkpoint**：对于写入频繁的数据库，定期触发 checkpoint
2. **监控文件大小**：关注 WAL 文件大小，避免占用过多磁盘空间
3. **备份前 Checkpoint**：备份数据库前先触发 checkpoint
4. **迁移前 Checkpoint**：迁移到 PostgreSQL 前先合并 WAL

## 🔗 相关命令

```bash
# 查看 WAL 模式状态
sqlite3 data/crypto_data.db "PRAGMA journal_mode;"

# 查看 WAL 文件信息
sqlite3 data/crypto_data.db "PRAGMA wal_checkpoint;"

# 手动触发 checkpoint
sqlite3 data/crypto_data.db "PRAGMA wal_checkpoint(TRUNCATE);"

# 压缩数据库（会合并 WAL）
sqlite3 data/crypto_data.db "VACUUM;"
```
