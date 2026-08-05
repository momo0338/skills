# LIVE RUNBOOK · dy-fanpai 受控 Live 详细操作手册

> 版本：1.0  日期：2026-08-03
> 配套：`LIVE_PREREQUISITES.md`（前置清单）、`EXECUTION_PLAN.md` §0.6（预算规则）。
> 用法：从「第 0 步」开始逐节照做；每节有可复制命令 + 验证方式 + 常见问题。
> 纪律：Live 默认关闭；一次只批一个 Provider、一段、一次提交；`max_submits` 代码硬执行；
> 未批准只能 Mock/dry-run；真实素材放 `~/dy_fp/runs/<scene>/inputs/`，不入 Git。

---

## 第 0 步 · 环境基线(5 分钟)

```bash
cd /Users/zhugx/src/skills/dy-fanpai
.venv/bin/python -m pytest -q          # 期望: 204 passed, 1 skipped
.venv/bin/dy-fanpai --help             # 期望: 8 命令组 doctor/new/status/run/approve/retry/deliver/clean
ffmpeg -version | head -1              # 期望: ffmpeg version 8.1.2 (需在 PATH)
```

验证通过说明代码与工具链就绪，进入凭证配置。

---

## 第 1 步 · 即梦 Dreamina CLI(口播生成必须,优先级最高)

> 用途：人物口播(multimodal2video)+ 纯产品 image2video；**口播口型只有它能做**。
> 计费：月度积分池，非 token。需要 Dreamina 账号(建议开通 maestro VIP)。

```bash
# 1) 安装 CLI(写入 ~/.local/bin,即 config.py 默认 dreamina_bin)
curl -fsSL https://jimeng.jianying.com/cli | bash

# 2) 确认二进制就位
ls -l ~/.local/bin/dreamina
~/.local/bin/dreamina --help | head -20    # 期望打印子命令列表

# 3) 登录(网页扫码)
~/.local/bin/dreamina login

# 4) 验证登录态 + 积分池
~/.local/bin/dreamina query_credit 2>/dev/null || ~/.local/bin/dreamina credit 2>/dev/null || true
```

**验证**：`dy-fanpai doctor` 中即梦相关不再 WARN。
**常见问题**：
- `dreamina: command not found` → 检查 `~/.local/bin` 是否在 PATH（macOS 默认不在，用全路径或 `export PATH="$HOME/.local/bin:$PATH"`）。
- 登录失败/过期 → 重跑 `dreamina login`；CLI 登录态通常长期有效，过期需重新扫码。
- 提示需 VIP → 即梦 CLI 生成功能需开通相应会员套餐。

---

## 第 2 步 · 火山方舟 Ark(反推 Seed + 评委 + 可选生成)

> 用途三合一：`seed_reverse`（反推 Seed 2.1 Pro）、`judge`（双视频评委，默认后端）、
> 纯产品 i2v 生成（Seedance 2.0，可选）。按 token 计费。

```bash
# 1) 开通(网页操作,约 10 分钟)
#    a. 打开火山方舟控制台 https://console.volcengine.com/ark
#    b. 完成实名认证 + 开通模型服务
#    c. 在「API Key 管理」创建 key → 复制(只显示一次,保存好)

# 2) 配置到本机(二选一)
#    方式 A: 写入 shell 配置(zshrc,注意 key 会进 shell 历史,建议方式 B)
#    echo 'export ARK_API_KEY="<你的key>"' >> ~/.zshrc && source ~/.zshrc
#    方式 B: 写入用户配置目录(config.py 读取优先级:环境变量 → ~/.config/dy-fanpai/)
mkdir -p ~/.config/dy-fanpai
echo -n "<你的key>" > ~/.config/dy-fanpai/ark_api_key   # 注意文件名小写

# 3) 确认模型可访问(默认模型名已冻结,可先不管,但建议核对账号区域)
echo "ARK_SEED_MODEL=$ARK_SEED_MODEL"    # 默认 doubao-seed-2-1-pro-260628
```

**验证**：`dy-fanpai doctor` 中 `ARK_API_KEY` 不再 WARN。
**常见问题**：
- key 无效 → 确认 key 创建于**开通了对应模型**的账号；Seed 系列与 Seedance 系列需分别开通。
- 区域：国内默认 `cn-beijing`（`config.py` 已硬编码该 endpoint，无需配置）。
- `require_key` 抛错 → 未写入环境变量且未写入 `~/.config/dy-fanpai/ark_api_key`，按上面任选其一补上。

---

## 第 3 步 · Kimi K3(双反推腿2,可选)

> 用途：Seed + Kimi 双反推时 Kimi 补充时序/运镜。单反推可不配，但配了无副作用。

```bash
# 1) 开通: https://platform.moonshot.cn 创建 API key
# 2) 配置(与 Ark 同理,二选一)
echo 'export KIMI_API_KEY="<你的key>"' >> ~/.zshrc && source ~/.zshrc
# 或
echo -n "<你的key>" > ~/.config/dy-fanpai/kimi_api_key

# 可选覆盖(默认已冻结,一般不用改)
# export KIMI_BASE_URL=https://api.moonshot.cn/v1
# export KIMI_K3_MODEL=kimi-k3
```

**验证**：`dy-fanpai doctor` 中 `KIMI_API_KEY` 不再 WARN。

## 第 3.5 步 · 通义千问 Qwen(反推腿3,阿里云百炼原生视频输入;已实测冒烟)

> 用途：Seed 之外的第三反推腿——百炼 `qwen3.7-plus` 等**原生支持视频输入**
> （2 小时/2GB/64 个视频，OpenAI 兼容接口，本地视频以 base64 data URI 直传）。
> ✅ **已实测冒烟**（2026-08-03 合成视频真实反推成功，shot 字段质量正确）；
> 真实带货视频完整验收仍需合法素材与预算（Live 前置 U6）。实现见 `reverse/qwen.py`
> （与 seed/kimi 同契约，可参与 merge 合并，alt 名称用 `Qwen`）。

```bash
# 1) 开通: 阿里云百炼 https://bailian.console.aliyun.com → 模型服务 → 创建 API Key
# 2) 配置(与 Ark 同理,二选一)
echo 'export DASHSCOPE_API_KEY="<你的key>"' >> ~/.zshrc && source ~/.zshrc
# 或
echo -n "<你的key>" > ~/.config/dy-fanpai/dashscope_api_key

# 可选覆盖(默认已冻结,一般不用改)
# export QWEN_MODEL=qwen3.7-plus          # 默认
# export QWEN_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1   # 默认
```

**验证**：`dy-fanpai doctor` 中 `DASHSCOPE_API_KEY` 不再 WARN（doctor 新增该键检查后生效）。
**跑法**：`python -m dy_fanpai.reverse.qwen` 的反推入口与 seed/kimi 同契约（`reverse(video, out, cuts)`）。

---

## 第 4 步 · 小云雀 XYQ(纯产品 i2v 第三后端,可选)

> 用途：纯产品 image2video 的第三条腿（独立 credits 池）。CLI 已装，只缺 key。

```bash
# 1) CLI 已在 PATH 确认(若没装则执行)
which pippit-tool-cli || npx @pippit-dev/cli@latest install

# 2) 配置 key(环境变量或配置文件)
echo 'export XYQ_ACCESS_KEY="<你的key>"' >> ~/.zshrc && source ~/.zshrc
# 或
echo -n "<你的key>" > ~/.config/dy-fanpai/xyq_access_key

# 3) 可选覆盖模型(默认 Seedance_2.0_mini_lite)
# export XYQ_VIDEO_MODEL=<你的模型名>
```

**验证**：`dy-fanpai doctor` 中 `XYQ_ACCESS_KEY` 不再 WARN。

---

## 第 5 步 · 素材与授权(A 类 MVP 最小集)

> 首轮 MVP 只需 **1 支 A 类视频 + 对应产品图 + 主播锚图**。放工作区不入 Git。

```bash
# 1) 建工作区(用 A 类真实视频)
cd /Users/zhugx/src/skills/dy-fanpai
.venv/bin/dy-fanpai new --video /绝对/路径/参考视频.mp4 --workspace ~/dy_fp/runs/mvp_a

# 2) 放素材(工作区内,路径记到 assets.json)
#    参考: tests/fixtures/scenarios/A/assets.json 的键结构
mkdir -p ~/dy_fp/runs/mvp_a/inputs/assets
cp /路径/主播锚图.jpg ~/dy_fp/runs/mvp_a/inputs/assets/host.jpg
cp /路径/产品正面.jpg   ~/dy_fp/runs/mvp_a/inputs/assets/hero.jpg
cp /路径/包装图.png     ~/dy_fp/runs/mvp_a/inputs/assets/礼盒.png
# 3) 写产品档案(参照 fixture 结构)
#    ~/dy_fp/runs/mvp_a/inputs/assets.json:
#    { "host_anchor": "inputs/assets/host.jpg",
#      "host_desc": "主播外形一句话(钉死跨段一致)",
#      "product_desc": "产品名,包装特征",
#      "products": {"hero": "inputs/assets/hero.jpg", "礼盒": "inputs/assets/礼盒.png"},
#      "forms": {"hero": ["别名1"], "礼盒": ["别名2"]},      // 换品类必配
#      "product_verbs": ["掰","撕","涂抹"] }                  // 该品类操作动词
```

**授权要求（G1 闸口前必须确认）**：
- 参考视频：有权使用（自产或授权），且确认会上传到哪些 Provider（即梦/Ark/Kimi/小云雀）。
- 主播锚图：肖像授权；声音：使用授权（若走 TTS/换声）。
- 产品图/价格/活动/赠品：真实可核，**禁止编造**（方案 §S07）。
- 记录方式：`dy-fanpai approve ~/dy_fp/runs/mvp_a rights` 或手动确认 `rights-and-consent` 字段。

---

## 第 6 步 · 受控 Live 首轮执行(MVP:A 类 + 原音 + 即梦 + Ark 评委)

> 预算纪律：`max_submits` 是**代码硬执行**的上限（超限抛 `MaxSubmitsExceeded`）。
> 实际 CLI 的四个闸口名是 `rights / plan / cost / qc`（`approve <ws> <gate>`），
> 与方案的 G1~G4 一一对应；`live` 与 `max_submits` 写入 `run.json`（§0.8：Live 开关不靠全局环境变量）。

```bash
# 1) 体检(确认密钥/工具就位)
.venv/bin/dy-fanpai doctor

# 2) 建工作区(离线安全;live 默认 false → Provider 返回桩数据,可先离线跑通全流程)
.venv/bin/dy-fanpai new --video /绝对/路径/参考视频.mp4 --workspace ~/dy_fp/runs/mvp_a

# 3) 首次提交前:开启 Live 并设硬上限(编辑 ~/dy_fp/runs/mvp_a/run.json)
#    把 "live": false → true; "max_submits": 0 → 1  (只允许一次真实提交)
#    ⚠ 这是人工动作,每次扩大段数/重试都必须重新修改并重新批准 cost 闸口

# 4) 权利闸(人工确认) → 状态推进
.venv/bin/dy-fanpai approve ~/dy_fp/runs/mvp_a rights

# 5) 跑到第一个闸口(反推→规划,遇闸口自动停)
#    ⚠ 反推腿默认 seed(需 ARK_API_KEY);用 Qwen 则加 --leg qwen(需 DASHSCOPE_API_KEY)
.venv/bin/dy-fanpai run ~/dy_fp/runs/mvp_a
#    或 .venv/bin/dy-fanpai run ~/dy_fp/runs/mvp_a --stage reverse --leg qwen
#    预期停在 G2 计划审核,先人审 ~/dy_fp/runs/mvp_a/planning/segments.md(分段/动作/锚图/台词/前3秒/合规)

# 6) 批准计划
.venv/bin/dy-fanpai approve ~/dy_fp/runs/mvp_a plan

# 7) 继续跑到费用闸(音频→生成审批)
.venv/bin/dy-fanpai run ~/dy_fp/runs/mvp_a
#    预期停在 G3 费用审批,核对 run.json 中: live=true / max_submits=1 / 段 ID / 后端

# 8) 批准生成费用(只批 S1 一段,即梦,1 次提交)
.venv/bin/dy-fanpai approve ~/dy_fp/runs/mvp_a cost
#    ⚠ 人物口播段由 route_backend 强制走 dreamina(口型驱动);纯产品 i2v 才可选 ark/xyq

# 9) 生成 + 装配 + 质检(继续 run 直到 G4)
.venv/bin/dy-fanpai run ~/dy_fp/runs/mvp_a
#    完成后检查: generation/clips/S1.mp4 可解码; output/FULL.mp4 无字幕无BGM

# 10) 双视频评委(Ark,如已配 key)+ 人工审片
.venv/bin/dy-fanpai run ~/dy_fp/runs/mvp_a
#    人工核对: 人物/商品/包装/动作/口型/合规 六项,分开记录(不能以技术通过代替)

# 11) 批准最终 QC + 交付
.venv/bin/dy-fanpai approve ~/dy_fp/runs/mvp_a qc
.venv/bin/dy-fanpai deliver ~/dy_fp/runs/mvp_a --mode final    # final 先出(剪映草稿见第 7 步)
```

**每轮 Live 必须记录**（写回 `run.json` 或验收记录）：task ID、usage、产物哈希、验收结果（§12.7）。
**完成后回填**：`tests/fixtures/scenarios/A/acceptance_record.md`（日期/run id/四闸口审批人/QC 结论/追溯字段）。

---

## 第 7 步 · 剪映草稿(门 8,需 Windows/WSL 验收机)

> 本机( macOS)只能产出 JSON 规格(`engine=json`,交付到 `delivery/jianying/`),
> 真机写草稿 + 剪映真实打开需指定机器。

```bash
# A. 本机产出可照抄规格(离线可用)
.venv/bin/dy-fanpai deliver ~/dy_fp/runs/mvp_a --mode jianying
#    产物: delivery/jianying/draft_info.json(视频/原声/字幕/贴纸/BGM 五轨)

# B. 真机验收(在 Windows/WSL 验收机上)
# 1) 安装剪映 + pyJianYingDraft(独立环境,不进入 core)
pip install pyjianyingdraft
# 2) 配置草稿目录与 Python
export DY_FANPAI_JY_DRAFTS="/mnt/c/Users/<你>/JianyingPro Drafts"
export DY_FANPAI_JY_PYTHON="/path/to/venv-jianying/bin/python"
# 3) 在验收机重跑 deliver --mode jianying(engine=pyjianying 真机写)
# 4) 打开剪映草稿箱 → 五轨可见(视频/配音/字幕/贴字参考/空BGM) → 编辑并保存一次
```

---

## 第 8 步 · TTS / 换声(门 7 可选路径,需合法音色)

```bash
# CosyVoice(TTS 合成)——独立环境
git clone https://github.com/FunAudioLLM/CosyVoice.git ~/CosyVoice
cd ~/CosyVoice && python -m venv .venv && .venv/bin/pip install -e .
export COSYVOICE_HOME=~/CosyVoice

# Seed-VC(换声不换演)——独立仓库 + venv
git clone https://github.com/Plachtaa/seed-vc.git ~/seed-vc
cd ~/seed-vc && python -m venv .venv && .venv/bin/pip install -r requirements.txt
export DY_FANPAI_SEEDVC_HOME=~/seed-vc

# 合法目标音色:必须有权使用(自录或授权),放 ~/dy_fp/runs/<scene>/inputs/,不入 Git
```

**验证**：`dy-fanpai doctor` 中 CosyVoice/Seed-VC 状态函数返回就绪。
**注意**：无合法音色时不得宣称换声/TTS Live 验收完成（`DEGRADATION.md` 降级项 4/5）。

---

## 第 9 步 · Skill 实机宿主验证(全新会话自然语言闸口)

> 在选定宿主(本机 WorkBuddy 等)全新会话验证：发现 → 自然语言触发 → 四闸口暂停 → 批准恢复。

```text
1. 全新会话输入:「抖音翻拍,复刻这条带货视频: <视频路径>,用我的产品重做」
2. 期望: 自动识别 ../SKILL.md 触发 → 收集素材 → 跑到 G1 权利闸停止
3. 人工批准 → 继续 → G2 计划闸停止(审 segments.md)→ 批准 → G3 费用闸(核对段数/后端/上限)
4. 批准生成 → G4 人工 QC → 交付
5. 全程: 不自动装重型依赖、不自动用真实密钥测试、不自动扩大段数/费用
```

**验收证据**：触发记录、每个闸口停止/批准的时间点、恢复路径。写入 `tests/live/` 或验收记录。

---

## 第 10 步 · 后续扩容(按 MVP 通过顺序)

| 顺序 | 内容 | 前置 |
|---|---|---|
| 1 | 产品迁移场景 | A 类通过 + 新品的图/事实 |
| 2 | B 模式(私有方法论) | 需私有千川方法论包(U4),否则按公开规则 + 标记未完整 parity |
| 3 | 群戏/旁白/纯产品 | 对应真实素材 + 群戏人数约束 |
| 4 | Ark 纯产品 i2v | ARK_API_KEY(第 2 步) |
| 5 | 小云雀纯产品 | XYQ_ACCESS_KEY(第 4 步) |
| 6 | TTS / 换声 | CosyVoice/Seed-VC + 合法音色(第 8 步) |
| 7 | 剪映草稿 | Windows/WSL 验收机(第 7 步) |

每扩一项：`LIVE_PREREQUISITES.md` 勾选 + `ACCEPTANCE.md` 对应门推进 + `acceptance_record.md` 回填。

---

## 常见问题速查

| 症状 | 原因 | 解法 |
|---|---|---|
| doctor WARN 三个 key | 未配置凭证 | 第 1~4 步任选 |
| `dreamina` 找不到 | `~/.local/bin` 不在 PATH | `export PATH="$HOME/.local/bin:$PATH"` |
| `require_key` 抛错 | 环境变量与配置文件都没写 | 二选一补齐 |
| run 停在闸口不动 | 这是设计行为 | `approve <ws> rights/plan/cost/qc` 后继续 `run` |
| run 提示"离线模式跳过" | `run.json` 中 `live=false` | 编辑 run.json 设 `live=true` 后重跑 |
| `MaxSubmitsExceeded` | 费用硬上限生效(代码层) | 修改 run.json `max_submits` 并重新 `approve cost` |
| 烧字幕失败 | macOS ffmpeg 缺 libass | 用 `--mode final` 兜底(无烧字幕+SRT)或装带 libass 的 ffmpeg |
| 人物段路由报错 | 人物口播只允许即梦 | `route_backend` 强制 mm→dreamina,勿把人物段给 Ark |
| 新建工作区没 live | `new` 默认离线(桩数据) | 手动编辑 `~/dy_fp/runs/<ws>/run.json` 开启 |

## 第 4.5 步 · MiniMax H3(纯产品 i2v 第四后端 + 口播实验;需 key)

> 用途：`--i2v-backend minimax` 让**纯产品段**走 MiniMax H3（2K 直出、9:16 支持）。
> ⚠ 口播段（mm）默认仍走即梦；MiniMax `reference_audio` 口型能力未实测，
> 实测通过前不切换 mm 段（experimental）。实现见 `generation/minimax.py`。

```bash
# 1) 开通: https://platform.minimaxi.com → 账户管理 → 接口密钥 → 创建
# 2) 配置(与 Ark 同理,二选一)
echo 'export MINIMAX_API_KEY="<你的key>"' >> ~/.zshrc && source ~/.zshrc
# 或
echo -n "<你的key>" > ~/.config/dy-fanpai/minimax_api_key

# 可选覆盖(默认已冻结,一般不用改)
# export MINIMAX_MODEL=MiniMax-H3              # 默认
# export MINIMAX_BASE_URL=https://api.minimaxi.com   # 默认(国内端;海外用 api.minimax.io)

# 3) 生成时指定后端(纯产品段)
.venv/bin/dy-fanpai approve <ws> cost
# generation.service.run 的 i2v_backend 参数在 CLI 接线后: --i2v-backend minimax
```

**验证**：`dy-fanpai doctor` 中 `MINIMAX_API_KEY` 不再 WARN。

## 第 4.6 步 · 自建 ComfyUI(自有 GPU 机器,替代即梦;experimental)

> 部署详见 `COMFYUI_DEPLOY.md`(AMD MI300X 走附录 A 官方镜像)。本步骤是接入 dy-fanpai。

```bash
# 1) 配置(指向自有 ComfyUI 机器)
export COMFYUI_BASE_URL="http://<机器IP>:8188"
# 模板路径(在机器上搭好工作流后导出 JSON 到本机)
export COMFYUI_WORKFLOW_I2V="/path/to/comfyui_i2v.json"   # Wan2.1 图生视频
export COMFYUI_WORKFLOW_MM="/path/to/comfyui_mm.json"      # LatentSync 口型

# 2) 验证
dy-fanpai doctor   # COMFYUI_BASE_URL 应显示就位

# 3) 生成时切后端(纯产品段)
# generation.service.run 的 i2v_backend 参数: --i2v-backend comfyui
```

> ⚠ mm 段默认仍走即梦;ComfyUI LatentSync 口型实测通过前不切换口播段。
> 模板占位符约定见 `../resources/workflows/README.md`。
