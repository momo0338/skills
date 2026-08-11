# 研发资源加速技能执行方案

状态：已审核并执行完成  
权威实现目录：`/Users/zhugx/src/skills/dev-resource-accelerator`

## 1. 目标

建立一个由技能仓库统一维护的研发资源加速能力，使 Codex 在中国大陆或受限网络中处理公开 GitHub 仓库、Release、Raw 文件和源码归档时，默认采用“镜像优先、逐级回退、官方直连兜底”的可恢复流程。

第一版必须做到：

1. 自动识别 GitHub clone、download、raw 三类公开资源。
2. 从独立镜像清单生成候选 URL，不在各项目脚本中重复硬编码。
3. 按候选顺序执行，失败后自动尝试下一个，最终回退 GitHub 官方地址。
4. 拒绝带凭证、令牌、SSH、GitHub API 或非 GitHub URL。
5. 克隆失败不在目标目录留下半成品。
6. 不修改全局 Git URL rewrite、HTTP/SOCKS 代理、pip 或 npm 配置。
7. 通过技能描述和 Codex 全局指令实现默认触发。

## 2. 非目标

- 不为私有仓库、企业代码、登录流程、OAuth、PAT 或 GitHub API 提供第三方镜像。
- 不承诺任何公共镜像永久可用或可信。
- 不把现有 `proxy` 技能合并进来；公共 URL 镜像与 HTTP/SOCKS 代理继续分工。
- 第一版不自动改写 npm、PyPI、Go、Maven 或 Docker 的全局配置；后续按相同路由模型扩展。
- 不立刻批量改造所有已有项目脚本；先提供统一入口和迁移规则，再按项目逐步接入。

## 3. 权威结构

```text
dev-resource-accelerator/
├── SKILL.md
├── agents/openai.yaml
├── references/mirrors.json
├── scripts/accelerate.py
└── tests/test_accelerate.py
```

仓库是唯一权威源。Codex 通过现有自动配置脚本建立软链接，不再维护另一份可漂移的实体副本。

## 4. 路由规则

### 4.1 公共 GitHub 下载与 Raw 文件

默认候选：

1. `https://ghfast.top/<原始 URL>`
2. `https://gh-proxy.com/<原始 URL>`
3. `https://ghproxy.vip/<原始 URL>`
4. `https://gh-fast.com/<原始 URL>`
5. `https://mirror.ghproxy.com/<原始 URL>`
6. GitHub 官方原始 URL

### 4.2 公共仓库 clone

默认候选：

1. 支持 clone 的 URL 前缀镜像
2. `https://gitclone.com/github.com/<owner>/<repo>.git`
3. GitHub 官方 HTTPS URL

每次执行仍以真实成功为准，静态顺序不是可用性承诺。

## 5. 命令接口

```bash
# 仅生成候选，不访问网络
python3 scripts/accelerate.py candidates <github-url> --kind auto

# 下载公开资源，自动回退
python3 scripts/accelerate.py download <github-url> <output> --public

# 克隆公开仓库，自动回退
python3 scripts/accelerate.py clone <github-url> <destination> --public

# 对真实目标进行轻量探活
python3 scripts/accelerate.py check <github-url> --kind auto --public
```

`--public` 是有意设置的安全确认：执行网络请求时必须显式声明目标是公开资源。候选生成可离线运行，但同样拒绝明显敏感 URL。

## 6. 执行工作包

### WP1：建立技能骨架

- 使用官方 `skill-creator` 初始化 `dev-resource-accelerator`。
- 生成匹配技能内容的 `agents/openai.yaml`。
- 保持 `SKILL.md` 简洁，只放核心工作流和安全规则。

### WP2：实现确定性路由器

- 使用 Python 标准库读取镜像清单、校验 URL 和编排命令。
- 下载调用系统 `curl`，启用重定向、HTTP 失败检测、连接超时和临时文件。
- clone 调用系统 `git`，先克隆到目标同级临时目录，成功后原子移动。
- 所有失败都输出镜像名、失败类型和最终回退结果。

### WP3：接入技能仓库

- README 技能数量从 20 更新为 21，并增加技能表格行。
- `SKILL_DEPS` 增加 `curl`、`git` 依赖声明。
- `scripts/test_deps.py` 增加技能发现断言。
- 保留用户现有 `.gitignore` 修改，不覆盖或回滚。

### WP4：默认触发与旧技能收敛

- 在 Codex 全局 `AGENTS.md` 增加最小默认规则。
- 用仓库自动配置脚本将新技能链接到 Codex 技能目录。
- 暂不破坏性删除旧 `github-accelerator`；先停用其隐式触发或保留为可恢复备份，确认新技能生效后再清理。

### WP5：验证

- 运行 `quick_validate.py`。
- 运行路由器单元测试。
- 运行 `scripts/check_skill_sync.py`。
- 运行 `scripts/test_deps.py` 和仓库相关 pytest。
- 用小型公开仓库/归档验证镜像成功、镜像失败回退和官方直连兜底。
- 验证敏感 URL、SSH、令牌和已存在 clone 目标均被拒绝。

## 7. 方案审核

| 风险 | 审核结论 | 控制措施 |
|---|---|---|
| 第三方镜像泄露私有代码或凭证 | 高风险，必须阻断 | 仅 HTTPS GitHub 公共资源；执行必须传 `--public`；拒绝凭证、token、API、SSH |
| 公共镜像随时失效 | 必然发生 | 独立 JSON 清单、逐级回退、官方直连兜底、真实目标探活 |
| clone 失败留下脏目录 | 不可接受 | 同级临时目录克隆，成功后原子移动；目标已存在则拒绝 |
| 全局 URL rewrite 误伤私有仓库 | 不可接受 | 不执行 `git config --global url.*.insteadOf` |
| 与 `proxy` 技能职责冲突 | 可避免 | 本技能只做公开资源 URL 镜像；代理技能继续处理 IP/地区限制 |
| 新旧技能同时隐式触发 | 中风险 | 全局规则显式指向新技能；新技能验收后停用旧技能隐式触发 |
| 技能散落在用户目录造成漂移 | 已存在 | 仓库作为唯一权威源，用户目录只使用软链接或停用项 |
| 范围扩张到所有生态导致复杂化 | 中风险 | 第一版只完整实现 GitHub；其他生态后续按适配器增量加入 |

审核结果：方案通过。实施时不得删除用户文件、不得覆盖已有配置块、不得以主页返回 200 代替真实资源验证。

## 8. 验收门

只有同时满足以下条件才算完成：

- 技能结构校验通过。
- 离线候选生成和安全拒绝测试全部通过。
- 下载与 clone 的镜像失败回退测试通过。
- 技能仓库磁盘、README、注册表三方一致。
- 新技能已被 Codex 发现，且全局默认规则已加载。
- Git 工作树中除用户原有 `.gitignore` 外，只出现本方案授权的变更。

## 9. 执行记录（2026-08-11）

实施结果：

- 已创建 `dev-resource-accelerator` 技能、镜像注册表、确定性路由器和回归测试。
- 已将 README 技能数量更新为 21，并同步 `SKILL_DEPS` 与依赖测试发现列表。
- 已在 `/Users/zhugx/.codex/skills/dev-resource-accelerator` 建立指向仓库权威目录的软链接。
- 已在 `/Users/zhugx/.codex/AGENTS.md` 增加带起止标记的全局默认触发规则。
- 已保留旧 `github-accelerator`，并将其 `allow_implicit_invocation` 设为 `false`，避免与新技能竞争；未删除旧文件。
- 未修改全局 Git URL rewrite、HTTP/SOCKS 代理或包管理器镜像配置。
- 用户原有 `.gitignore` 修改保持原样。

验证结果：

- 新技能单元测试：17 passed。
- 仓库脚本 pytest：5 passed。
- 完整依赖与同步检查：71 passed，0 failed。
- `quick_validate.py`：通过。
- `check_skill_sync.py`：21 个技能三方一致。
- 真实公开归档检查：`ghfast.top`、`gh-proxy.com`、`ghproxy.vip` 和 GitHub 直连成功；`gh-fast.com`、`mirror.ghproxy.com` 在本机当前链路 TLS 失败。
- 真实公开下载和浅克隆：均通过 `ghfast.top` 成功，ZIP 完整性和 Git 工作树已验证。

暂缓项：npm、PyPI、Go、Maven、Docker 仅保留后续扩展方向，未在第一版中增加全局改写或自动执行。

## 10. 沙箱体验改进（2026-08-11 追加）

问题：将公开仓库直接克隆到受保护目录被沙箱拦截，且授权申请被自动审核拒绝，导致用户感知到多次尝试。

改进：

- `clone` 与 `download` 新增 `--fallback-dir`：目标父目录不可写时自动降级到可写回退目录，并打印实际落盘路径。
- `SKILL.md` 增加“受限沙箱环境”规则：优先选择可写路径，不先尝试受保护目录。
- 新增 3 项单元测试覆盖文件/目录回退解析与无回退目录时的报错。

验证：`pytest` 通过；在不可写父目录下使用 `--fallback-dir` 实际克隆成功。
