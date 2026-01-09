# GitHub Fork 同步指南

## 📌 重要概念

### Fork 不会自动同步！

**关键点：**
- ❌ Fork 的仓库**不会**自动跟随原仓库更新
- ✅ Fork 是创建了一个**独立的副本**
- ✅ 需要**手动同步**才能获取原仓库的更新

---

## 🔍 Fork 的工作原理

```
原仓库 (tonysum/corniche)
    │
    ├─ 你更新代码
    │   └─ 推送到 GitHub
    │
    └─ 其他人 fork
        └─ 创建独立副本 (otheruser/corniche)
            └─ ❌ 不会自动收到你的更新
```

### 为什么不会自动更新？

1. **独立性**: Fork 的仓库是独立的，有自己的提交历史
2. **权限**: Fork 者拥有自己仓库的完全控制权
3. **设计**: GitHub 设计如此，避免意外覆盖别人的工作

---

## 🔄 如何同步更新

### 方法1: GitHub Web 界面同步（最简单）

**步骤：**

1. 进入你的 fork 仓库页面
   ```
   https://github.com/otheruser/corniche
   ```

2. 点击 "Sync fork" 或 "Fetch upstream" 按钮
   - 位置：仓库页面顶部，在 "Code" 按钮旁边

3. 如果有更新，会显示：
   ```
   This branch is X commits behind tonysum:main
   ```

4. 点击 "Update branch" 或 "Merge upstream" 按钮

5. 确认合并

**优点：**
- ✅ 最简单，无需命令行
- ✅ 可视化操作
- ✅ GitHub 自动处理合并

**缺点：**
- ❌ 只能同步到默认分支（通常是 main）
- ❌ 无法处理复杂冲突

---

### 方法2: 命令行同步（推荐，最灵活）

#### 首次设置（只需一次）

```bash
# 1. 克隆你的 fork（如果还没有）
git clone git@github.com:otheruser/corniche.git
cd corniche

# 2. 添加上游仓库（原仓库）
git remote add upstream git@github.com:tonysum/corniche.git

# 3. 验证配置
git remote -v
# 应该看到：
# origin    git@github.com:otheruser/corniche.git (fetch)
# origin    git@github.com:otheruser/corniche.git (push)
# upstream  git@github.com:tonysum/corniche.git (fetch)
# upstream  git@github.com:tonysum/corniche.git (push)
```

#### 每次同步更新

```bash
# 1. 确保在正确的分支
git checkout main

# 2. 获取上游仓库的更新
git fetch upstream

# 3. 合并上游的更新到当前分支
git merge upstream/main

# 4. 如果有冲突，解决冲突后：
git add .
git commit -m "Merge upstream updates"

# 5. 推送到你的 fork
git push origin main
```

#### 同步到其他分支

```bash
# 同步到 develop 分支
git checkout develop
git fetch upstream
git merge upstream/develop
git push origin develop
```

---

### 方法3: 使用同步脚本（自动化）

项目已包含同步脚本 `sync-fork.sh`：

```bash
# 使用同步脚本
./sync-fork.sh
```

脚本功能：
- ✅ 自动检查上游仓库配置
- ✅ 自动获取并合并更新
- ✅ 处理冲突提示
- ✅ 推送到你的 fork

---

## 📝 详细操作示例

### 场景1: 首次同步设置

```bash
# 1. 克隆你的 fork
git clone git@github.com:otheruser/corniche.git
cd corniche

# 2. 添加上游仓库
git remote add upstream git@github.com:tonysum/corniche.git

# 3. 验证
git remote -v
```

### 场景2: 定期同步更新

```bash
# 每次原仓库更新后，执行以下命令：

# 1. 切换到主分支
git checkout main

# 2. 拉取你的 fork 的最新代码（如果有其他设备推送过）
git pull origin main

# 3. 获取上游更新
git fetch upstream

# 4. 查看差异
git log HEAD..upstream/main --oneline

# 5. 合并更新
git merge upstream/main

# 6. 推送到你的 fork
git push origin main
```

### 场景3: 处理合并冲突

```bash
# 如果合并时出现冲突：

# 1. 查看冲突文件
git status

# 2. 手动解决冲突（编辑文件）
# 冲突标记：
# <<<<<<< HEAD
# 你的代码
# =======
# 上游的代码
# >>>>>>> upstream/main

# 3. 解决冲突后，标记为已解决
git add <冲突文件>

# 4. 完成合并
git commit -m "Merge upstream: resolve conflicts"

# 5. 推送
git push origin main
```

### 场景4: 使用 rebase 同步（保持线性历史）

```bash
# 使用 rebase 而不是 merge（可选）

git checkout main
git fetch upstream
git rebase upstream/main

# 如果有冲突，解决后：
git add .
git rebase --continue

# 推送到你的 fork（需要强制推送）
git push origin main --force-with-lease
```

**注意**: `--force-with-lease` 比 `--force` 更安全，会检查远程是否有其他人的提交。

---

## 🔧 高级操作

### 查看上游仓库的更新

```bash
# 查看上游有哪些新提交
git fetch upstream
git log HEAD..upstream/main --oneline

# 查看详细的差异
git diff HEAD..upstream/main

# 查看特定文件的差异
git diff HEAD..upstream/main -- path/to/file
```

### 只同步特定提交

```bash
# 如果你只想同步某个特定的提交
git fetch upstream
git cherry-pick <commit-hash>
git push origin main
```

### 创建同步分支

```bash
# 创建一个专门用于同步的分支
git checkout -b sync-upstream
git fetch upstream
git merge upstream/main
git push origin sync-upstream
```

### 删除上游仓库配置

```bash
# 如果不再需要同步
git remote remove upstream
```

---

## ⚠️ 常见问题

### Q1: 为什么我 fork 后看不到原仓库的更新？

**A:** Fork 是独立副本，不会自动同步。需要手动同步。

### Q2: 同步后我的修改会丢失吗？

**A:** 不会。同步是合并操作，会保留你的修改。如果有冲突，需要手动解决。

### Q3: 如何避免冲突？

**A:** 
- 定期同步，不要等太久
- 在同步前先提交你的更改
- 使用单独的分支进行开发

### Q4: 我可以直接修改原仓库吗？

**A:** 如果你有原仓库的写入权限，可以直接推送。否则需要通过 Pull Request。

### Q5: 如何贡献代码回原仓库？

**A:** 
1. 在你的 fork 中修改代码
2. 推送到你的 fork
3. 在 GitHub 上创建 Pull Request
4. 原仓库维护者审查并合并

---

## 📋 最佳实践

### 1. 定期同步

```bash
# 建议每周至少同步一次
git fetch upstream
git merge upstream/main
```

### 2. 使用分支开发

```bash
# 在主分支保持同步，在功能分支开发
git checkout main
git pull upstream main
git checkout -b feature-branch
# 开发功能...
```

### 3. 同步前先提交

```bash
# 同步前确保工作已保存
git add .
git commit -m "Save work before sync"
git fetch upstream
git merge upstream/main
```

### 4. 使用别名简化命令

```bash
# 添加到 ~/.gitconfig
git config --global alias.sync '!git fetch upstream && git merge upstream/main'

# 使用
git sync
```

---

## 🎯 快速参考

### 一次性设置

```bash
git remote add upstream git@github.com:tonysum/corniche.git
```

### 每次同步

```bash
git fetch upstream
git merge upstream/main
git push origin main
```

### 使用脚本

```bash
./sync-fork.sh
```

---

## 📚 相关资源

- [GitHub Fork 文档](https://docs.github.com/en/pull-requests/collaborating-with-pull-requests/working-with-forks)
- [Git 远程仓库管理](https://git-scm.com/book/zh/v2/Git-基础-远程仓库的使用)
- [Git 合并冲突解决](https://git-scm.com/book/zh/v2/Git-工具-高级合并)

---

## 💡 总结

**记住三个要点：**

1. ✅ Fork **不会**自动同步
2. ✅ 需要**手动**同步更新
3. ✅ 使用 `upstream` 远程仓库配置同步

**推荐工作流：**

```bash
# 1. 设置（只需一次）
git remote add upstream <原仓库URL>

# 2. 定期同步（每次原仓库更新后）
git fetch upstream
git merge upstream/main
git push origin main
```
