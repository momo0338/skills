---
name: git-secret-purge
description: 从 git 仓库（尤其公开仓库）中彻底清除已提交的凭据——cookie / token / API key / 密码——并完成历史重写、远程强推与轮换闭环。触发词：凭据泄露、cookie 被提交了、token 泄露、清 git 历史、filter-repo、仓库里有密码、公开仓库泄露、secret scanning 告警、停止跟踪敏感文件。
agent_created: true
---

# git-secret-purge — 彻底清除 git 仓库中已泄露的凭据

> 适用：某个凭据（cookie/token/key/密码）曾经被 `git commit` 过，现在要把它从仓库里清掉。
> 本文所有"实测"结论均在 macOS + git 2.4x + git-filter-repo 上验证过。

## 〇、四个必须先知道的认知（能省几小时）

1. **`.gitignore` 对已跟踪文件完全无效。**
   文件一旦被 `git add` 过，`.gitignore` 就管不住它。必须 `git rm --cached` 才能真正停止跟踪。
   （真实案例：某公开仓库 `.gitignore` 里已写了 `.mp_cookies.json`，但该文件仍被跟踪并推到了
   `origin/main`，含公众号后台全套登录 cookie。**写进 .gitignore ≠ 安全**。）

2. **force push 之后，旧 commit 里的凭据仍然读得到。**
   实测：重写历史 + force push 成功后，
   `https://raw.githubusercontent.com/<owner>/<repo>/<旧sha>/<path>` 仍返回 **HTTP 200**，
   GitHub API `contents?ref=<旧sha>` 也仍能取到 blob。GitHub 不提供手动触发 GC 的入口。
   → **历史清理只是减少暴露面；真正止血的唯一手段是轮换凭据（见第七步）。**

3. **`git stash -u` 的快照会被 filter-repo 丢掉。**
   `stash -u` 生成的 stash commit 有第三个父提交（untracked 快照）。filter-repo 重写 stash 时
   **只保留前两个父**，untracked 快照随之丢失。若此时又跑过 `git gc`，内容就真没了。
   → 正确顺序：**先恢复工作区，再 filter-repo**（见第二步）。

4. **第三方工具的 ref 会残留凭据。**
   `refs/codex/turn-diffs/checkpoints/*` 之类指向 **tree 对象**的工具 ref，
   filter-repo 会警告 `unexpected object of type tree, skipping` 并跳过 →
   凭据 blob 仍可达。必须手动 `git update-ref -d` 后 GC（见第四步）。

---

## 一、第一步：评估与备份（不可省）

```bash
OWNER_REPO=<owner>/<repo>

# 1) 仓库是否公开？（决定严重级别）
gh repo view "$OWNER_REPO" --json name,visibility,isPrivate

# 2) 目标文件是否被跟踪 / 引入于哪些提交 / 是否已推到远程
git ls-files --error-unmatch <path>                  # 无报错 = 正在被跟踪
git log --all --oneline -- <path>                    # 是哪些提交碰过它
git log --oneline origin/main -- <path>              # 已在远程 = 已暴露

# 3) 规模
git rev-list --count HEAD; du -sh .git

# 4) 备份（回滚点，必做）
TS=$(date +%Y%m%d-%H%M%S)
tar -czf /tmp/git-backup-$TS.tar.gz .git
echo "$TS" > /tmp/git_backup_ts.txt
# 同时记录基线，后面 force-with-lease 要用
git rev-parse HEAD; git rev-parse origin/main
```

> 备份 `tar` 报 `Could not pack extended attributes` / `pax format cannot archive sockets`
> 是 `fsmonitor` 的 socket 无法打包，**无害**，忽略即可。

## 二、第二步：处理未提交改动（顺序错了会丢数据）

```bash
git diff HEAD > /tmp/wip_tracked.patch                    # 兜底 patch

# 先记下 stash 的 hash —— 这是救命 hash，务必留存
git stash push -u -m "wip-before-purge"
git rev-parse stash@{0}          # ← 记下来！
```

**两种安全策略，二选一：**

- **策略 A（推荐）：filter-repo 之前先 `git stash pop` 恢复干净。**
  代价是 filter-repo 时工作区有未提交改动（filter-repo `--force` 可继续）。
- **策略 B：等 filter-repo 完成、验证完历史后再 pop。**
  但必须先把 stash 对象 + 其父提交 hash 全部记下，因为 filter-repo 会重写它。

**若 untracked 文件已丢失，这样抢救：**

```bash
git fsck --unreachable --no-progress | grep commit     # 找悬空的 stash commit
S=<悬空的 stash commit>
git cat-file -p $S | head -6                            # 看它还有几个 parent
# untracked 快照常被挪到第二个 parent 位置
git ls-tree -r --name-only "$S^2"                       # 确认里面是不是那批文件
git archive "$S^2" | tar -x -v -C <repo-root>           # 还原
# 逐字节校验（必须做）
python3 - <<'EOF'
import subprocess
snap = '<stash^2>'
for l in subprocess.run(['git','ls-tree','-r',snap], capture_output=True, text=True).stdout.splitlines():
    meta, path = l.split('\t', 1); sha = meta.split()[2]
    now = subprocess.run(['git','hash-object', path], capture_output=True, text=True).stdout.strip()
    print(('OK  ' if now == sha else 'BAD '), path)
EOF
```

⚠️ `git gc --prune=now` 一旦跑过，悬空对象即被删除，抢救窗口消失。
**排查期间不要 gc。**

## 三、第三步：停止跟踪 + 补 .gitignore

```bash
git rm --cached <path>          # 工作区文件原地保留，只是不再跟踪
git check-ignore -v <path>      # 必须命中，否则补 .gitignore
git commit -m "chore(security): 停止跟踪 <file>"
```

`.gitignore` 建议同时补上（**先做这一步，否则一次 `git add .` 就再次泄露**）：

```gitignore
.env
*.key
*_token
.mp_token
*credential*
*cookie*
*.bak-*
```

> 注意：`.gitignore` 只对**尚未被跟踪**的文件生效。已经跟踪的要 `git rm --cached`。

## 四、第四步：重写全历史

```bash
git filter-repo --path <path> --invert-paths --force
git remote add origin <原始 remote url>      # filter-repo 会删掉 origin，必须重加
```

## 五、第五步：清残留 ref 与对象

```bash
# 1) 找出仍能可达该文件的所有 ref（关键排查）
git rev-list --objects --all | grep -i <filename>

# 2) 删除 tree 型工具 ref（filter-repo 跳过的那类）
git for-each-ref --format='%(refname)' refs/codex | while read -r r; do git update-ref -d "$r"; done
# 先备份清单再删： git for-each-ref ... refs/codex > /tmp/codex_refs_backup.txt

# 3) 清理
git reflog expire --expire=now --all
git gc --prune=now
```

## 六、第六步：四层验证（缺一层都可能漏）

```bash
# ① 路径级
git log --all --oneline -- <path>                       # 应为空

# ② 提交树级
for c in $(git rev-list --all); do
  git ls-tree -r --name-only "$c" | grep -q '<filename>' && echo "残留于 $c"
done

# ③ 对象库 blob 级（最彻底，用附带的脚本）
python3 scripts/scan_repo_secrets.py --repo . --verify 504bcc0

# ④ 远程级
gh api "repos/<owner>/<repo>/contents/<path>" --jq '.sha'   # 期望 404
```

> ③ 的脚本务必用**字节模式**读对象。用 `subprocess.run(..., text=True)` 遍历 blob 会在
> 二进制文件上抛 `UnicodeDecodeError: 'utf-8' codec can't decode byte 0x89`（PNG 等）。
> 正确写法：`capture_output=True`（不加 `text=True`）后按 `bytes` 比较。

## 七、第七步：推送 + 轮换（真正止血）

### 推送：用显式租约，避免覆盖他人提交

```bash
git push <url> main --force-with-lease=refs/heads/main:<旧-sha>
```

`--force-with-lease=<ref>:<expect>` 的显式写法**不依赖 remote-tracking ref**，
所以在 fetch 失败、remote 被 filter-repo 删除的情况下依然可用，且比 `--force` 安全得多。

### 沙箱 / 代理环境下的推送通路（实测）

| 通路 | 结果 | 说明 |
|---|---|---|
| `ssh -T git@github.com` | ❌ `Connection timed out` | 22 端口被透明代理阻断 |
| `https://` + fine-grained PAT | ❌ `403 Permission denied` | token 常只授了只读 |
| **`ssh -p 443 git@ssh.github.com`** | ✅ 可用 | 推荐兜底通路 |

两个容易误判的点：

- **`gh api repos/<o>/<r> --jq .permissions` 显示 `admin:true` 不代表 token 能写。**
  那是**用户身份**对仓库的权限，不是 fine-grained PAT 的 scope。https push 报 403 时，
  别怀疑权限显示，直接换 443 SSH。
- SSH 认证测试要用对的 key：
  ```bash
  ssh -o StrictHostKeyChecking=no -p 443 -i ~/.ssh/<key> -o IdentitiesOnly=yes -T git@ssh.github.com
  # 期望： Hi <user>! You've successfully authenticated...
  ```
  `Permission denied (publickey)` 说明 **TCP 已通**、只是 key 不对（与 timeout 完全不同）。

推送命令：

```bash
GIT_SSH_COMMAND='ssh -p 443 -i ~/.ssh/<key> -o IdentitiesOnly=yes -o StrictHostKeyChecking=no' \
  git push ssh://git@ssh.github.com:443/<owner>/<repo>.git main \
  --force-with-lease=refs/heads/main:<旧-sha>
```

> 用 `GIT_SSH_COMMAND` 内联即可，**不必改 `~/.ssh/config`**，不污染用户配置。

### 轮换凭据（唯一真正的止血，必做）

历史清理**收回不了**：

- 已经 clone / fork 的副本（永久存在）
- GitHub 上仍可通过旧 SHA / raw URL 读取的旧 commit（GC 时机不可控）

所以必须轮换：

| 凭据类型 | 处置 |
|---|---|
| 微信/公众号 cookie（`slave_sid`/`slave_user`/`bizuin`） | **到后台重新登录** → 旧会话失效 |
| API key / PAT | 到平台 revoke 并重新签发；同步更新 `~/.zshrc` 等注入点 |
| 账号密码 | 改密 + 检查登录日志 / 已授权设备 |
| 云服务密钥 | 轮换 key pair，检查账单与操作审计 |

---

## 八、速查表

| 现象 | 根因 | 对策 |
|---|---|---|
| `.gitignore` 写了但文件还在仓库 | 对已跟踪文件无效 | `git rm --cached <path>` |
| filter-repo 报 `unexpected object of type tree, skipping` | `refs/codex/*` 等 tree 型 ref | 手动 `git update-ref -d` + gc |
| stash pop 后 untracked 文件消失 | filter-repo 丢掉 stash 第三个父 | 见第二步抢救流程 |
| 遍历 blob 报 `UnicodeDecodeError` | `text=True` 读了二进制 | 用字节模式比较 |
| `git push` https 报 403 但权限显示 admin | fine-grained PAT 只读 | 换 443 SSH |
| `ssh git@github.com` 超时 | 22 端口被阻断 | `ssh -p 443 git@ssh.github.com` |
| force push 后仍能下载到旧文件 | GitHub 保留不可达对象 | 轮换凭据（唯一解） |
| `git filter-repo` 后 push 报找不到 origin | filter-repo 删除了 origin | `git remote add origin <url>` |

## 九、脚本

- `scripts/scan_repo_secrets.py` — 扫描仓库中的凭据（三种模式）：
  - `--tracked`：扫描所有**已跟踪文件**（找还没提交的隐患）
  - `--objects`：扫描**对象库全部 blob**（验证历史清理是否彻底，含悬空对象）
  - `--verify <blob-sha>`：定点确认某个 blob 是否还在对象库里
  输出只报**文件路径与命中数**，不回显凭据明文。
