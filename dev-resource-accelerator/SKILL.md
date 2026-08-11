---
name: dev-resource-accelerator
description: 在中国大陆或受限、不稳定网络下，只要项目操作涉及公开 GitHub 仓库 clone、Release/Raw/archive 下载、从 GitHub 获取依赖、镜像 URL 改写、镜像探活或下载回退，就使用此技能。仅处理无需登录的公开资源；不得用于私有仓库、企业代码、OAuth、PAT、GitHub API、SSH 或任何带凭证请求。也用于用户提到 ghfast、gh-proxy、ghproxy、gitclone、GitHub 镜像或研发资源加速时。
---

# 研发资源加速

把公开 GitHub 资源访问统一为“镜像优先、逐级回退、官方直连兜底”。使用技能自带脚本，不在项目里重复拼接镜像 URL。

## 核心边界

- 仅处理公开、匿名、HTTPS GitHub 资源。
- 任何私有、未知可见性、带凭证、带令牌、API、OAuth 或 SSH 目标都走官方渠道，不经过第三方镜像。
- 不执行全局 `git config url.*.insteadOf`，不设置全局 HTTP/SOCKS 代理，不修改全局 pip/npm 配置。
- 不把公共 URL 镜像和 `proxy` 技能混为一谈。只有明确的 IP、地区或反爬问题才考虑 `proxy`。
- 把第三方镜像视为不可信传输层。重要二进制优先校验官方哈希或签名。

## 工作流

1. 确认目标是公开资源；无法确认时停止镜像改写。
2. 根据操作选择 `candidates`、`check`、`download` 或 `clone`。
3. 执行网络操作时显式传入 `--public`。
4. 保留脚本输出的候选、失败原因和最终来源，便于复盘。
5. 已有仓库默认保留原始 `origin`；不要静默改写 remote。若必须临时 fetch，先用 `candidates --kind clone` 生成 URL，并在单次命令中使用。

## 命令

从技能目录运行：

```bash
# 离线生成候选 URL
python3 scripts/accelerate.py candidates \
  https://github.com/owner/repo/releases/download/v1/file.zip

# 对真实目标逐个探活
python3 scripts/accelerate.py check \
  https://github.com/owner/repo/archive/refs/heads/main.zip --public

# 下载到临时文件，成功后原子替换目标
python3 scripts/accelerate.py download \
  https://github.com/owner/repo/releases/download/v1/file.zip ./file.zip --public

# 克隆到同级临时目录，成功后原子移动
python3 scripts/accelerate.py clone \
  https://github.com/owner/repo.git ./repo --public
```

需要 JSON 证据时，对 `candidates` 或 `check` 增加 `--json`。需要浅克隆时，对 `clone` 增加 `--depth 1`。

## 受限沙箱环境

目标目录不可写时（例如系统保护路径或受限工作区），`clone` 和 `download` 会先探测父目录权限。不可写时增加 `--fallback-dir`，命令会自动落到该目录并在输出中给出实际路径：

```bash
python3 scripts/accelerate.py clone \
  https://github.com/owner/repo.git ./repo \
  --public --fallback-dir /tmp/dev-accelerator
```

调用时优先选择已确认可写的路径（如当前工作区下的 `.analysis-tmp/` 或系统临时目录），不要先尝试受保护目录再被拒绝。需要授权时，仅针对最终目标位置申请，不让整个下载流程阻塞在授权上。

## 镜像维护

镜像地址和适用操作集中在 `references/mirrors.json`。调整地址时只修改该文件，并重新运行单元测试和真实小样本检查。公共镜像可用性随时变化，不根据主页状态宣称资源可用。

## 输出要求

向用户说明：

- 最终采用的来源及是否发生回退。
- 第三方镜像仅用于公开资源。
- 是否完成哈希或签名校验。
- 若全部失败，保留每个候选的失败摘要，不转而偷偷配置全局代理。
