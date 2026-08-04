# AMD MI300X 上运行 ComfyUI：6 篇最新社区方案对比分析

> 版本:1.0  日期:2026-08-04
> 数据来源:ModelScope Learn 六篇实战文章(2026-05-22 ~ 2026-08-03)
> 分析对象环境:AMD 8 核 + 200GB RAM + **MI300X(192GB, gfx942)** + Ubuntu + ROCm 7.2
> 应用目标:Wan2.1 i2v + LatentSync 口型,对接 dy-fanpai 管线(HTTP API)

---

## 1. 六篇文章速览

| # | 文章 | 发布时间 | 环境 | 核心主题 | 最值得抄的要点 |
|---|---|---|---|---|---|
| 1 | [MiniMax-H3 开源:MI308X 跑 ComfyUI 全流程实战(INT8 ConvRot + FlashAttention + Triton)](https://modelscope.cn/learn/435354) | 2026-08-03 | MI308X(≈MI300X) 192GB / ROCm 7.2 / ComfyUI 0.30.0 | INT8 量化 + 注意力 + Triton 提速 ~30% | **triton 必须 ≥3.7.1**(3.6.0 在 ROCm 下 int8 内核崩);`--use-flash-attention --enable-triton-backend`;SageAttention 官方不支持 ROCm;aria2 并发下载 |
| 2 | [SCAIL-2 + ComfyUI 在 AMD MI300X 上的运行踩坑与适配记录](https://modelscope.cn/learn/435230) | ~2026-07 | MI300X 192GB / ModelScope Notebook | 动作迁移工作流大显存适配 | **大显存 ≠ 直接跑原工作流**:BlockSwap=0、关 offload、关 non-blocking、VAE tiling 开启、主模型常驻 GPU、`--highvram`;SageAttention 在 ROCm 没有可用实现 |
| 3 | [创空间部署应用笔记:AMD ROCm 环境模型加速](https://modelscope.cn/learn/435197) | 2026-07-30 | 创空间(魔搭) / AMD ROCm | 文生图/图生视频注意力与参数 | `flash_attention_2` ROCm 完美支持(首选)、`sdpa` 备选、`flash_attention_3` 不可选;xformers 可试失败回退;模型缓存到持久卷 `/mnt/workspace/.cache/modelscope` |
| 4 | [Wan2.2 ROCm 图生视频实战](https://modelscope.cn/learn/435068) | ~2026-07 | MI300X 192GB / gfx942 | Wan2.2-I2V-A14B 稳定生成 | 权重 126GB 先校验完整性;17 帧冒烟测试再批量;`offload_model=False` 常驻 GPU(峰值 78GB);批量只初始化一次 `WanI2V`,预热后 178s/段 |
| 5 | [安装运行 ComfyUI 基于 Ubuntu+ROCm(Ryzen AI Max+ 395)](https://modelscope.cn/learn/434027) | 2026-05-22 | 消费级 AMD(Ryzen AI Max+ 395) | 基础安装流程 | conda + Python 3.12;`pip install torch torchvision torchaudio triton --index-url`(官方 ROCm whl) |
| 6 | [N 卡到 A 卡 100% 无损迁移 + MI300X 榨汁指南](https://modelscope.cn/learn/434324) | 2026-06-08 | MI300X 192GB | 迁移避坑 + 极限性能 | **别直接 `pip install -r requirements.txt`**(会覆盖 ROCm torch);用 `venv --system-site-packages` 继承全局;卸 xformers/flash-attn/bitsandbytes;`HSA_OVERRIDE_GFX_VERSION=9.4.2`;TunableOp 算子自整定 |

---

## 2. 关键决策点对比

### 2.1 环境搭建方式(分歧最大)

| 方式 | 出处 | 优点 | 风险 |
|---|---|---|---|
| A. 全新 venv + `pip install -r requirements.txt` | 文1(435354) | 简单标准 | **文6 警告**:会覆盖预装/全局的 ROCm torch,MI300X 变"亮机卡" |
| B. conda + Python 3.12 + 官方 ROCm whl 手动装 torch | 文5(434027) | 版本可控,消费级可行 | 手动步骤多 |
| C. `venv --system-site-packages` 继承全局 ROCm torch + **sed 删 requirements.txt 里 torch 行** | 文6(434324) | **防弹**,保住平台定制 ROCm 环境 | 依赖全局环境干净 |
| D. 官方 Docker 镜像 `rocm/comfyui`(0.18.2) | 项目附录A | 开箱即用,最快起服务 | 镜像版本旧(0.18.2 vs 社区最新 0.30.0),装自定义节点/新特性需进容器再装 |

> **结论**:如果机器是魔搭/云厂商预装 ROCm 的环境 → 走 **C(继承全局)** 最安全;如果是裸机 Ubuntu → 走 **B(官方 ROCm whl)**;要快速验证 → **D(Docker)**。项目现有的 install_comfyui.sh(全新 venv + rocm7.2 whl)本质是 B,本身没问题,但**不要**在已预装 ROCm 的机器上直接跑,先确认 `torch.version.hip` 是否非空。

### 2.2 注意力实现(核心分歧,务必读)

| 方案 | 文1(435354) 实测 | 文2(435230) 实测 | 文3(435197) 实测 | 文6(434324) | 结论 |
|---|---|---|---|---|---|
| **flash_attention_2 / `--use-flash-attention`** | ✅ flash_attn 2.8.3 ROCm 可用,但**必须加启动参数**才生效,默认是 pytorch attention | — | ✅ "ROCm 完美支持"(首选) | — | **首选**,确定可用 |
| **sdpa / `--use-pytorch-cross-attention`** | 兜底(AOTriton flash) | ✅ 用这个(SageAttention 缺失会报错) | ✅ 备选 | ✅ 启动参数里带 | **最稳兜底** |
| xformers | — | — | ✅ 可试,失败回退默认 | ❌ 卸载 | 消费级可试,Instinct 上非必需 |
| **SageAttention** | ❌ "官方不支持 ROCm,别碰" | ❌ "没有可用实现会直接报错" | — | ⚠️ 建议装来替代 xformers | **有矛盾**:文6 建议装,但文1(更新、同环境)实测反对。**以文1 为准,ROCm 上别装** |

> **结论**:启动参数用 `--use-flash-attention`(装了 ROCm 版 flash_attn)或 `--use-pytorch-cross-attention`(不想装 flash_attn 时)。**不要装 sageattention**。注意 434324 的 sageattention 建议已过时/有误。

### 2.3 启动参数与 AMD 环境变量(直接抄)

**文1(435354) 最终组合拳:**
```bash
export HF_ENDPOINT=https://hf-mirror.com
python main.py --listen 0.0.0.0 --port 8188 \
  --disable-auto-launch --use-flash-attention --enable-triton-backend
# 前置: pip install triton==3.7.1  (3.6.0 在 ROCm 下 int8 内核会崩,libdevice 缺 rint)
```

**文2(435230) 大显存关键参数:**
```bash
python main.py --highvram --disable-async-offload \
  --disable-pinned-memory --use-pytorch-cross-attention
```

**文6(434324) MI300X 榨汁脚本:**
```bash
export TORCH_ROCM_AOTRITON_ENABLE_EXPERIMENTAL=1      # 实验性高效注意力
export PYTORCH_TUNABLEOP_ENABLED=1                    # 算子自整定(第一次慢,之后起飞)
export PYTORCH_HIP_ALLOC_CONF=garbage_collection_threshold:0.2,max_split_size_mb:2048,expandable_segments:False
export HSA_OVERRIDE_GFX_VERSION=9.4.2                 # MI300X = gfx942
export HIP_FORCE_DEV_KERN_ARG=1
export MIOPEN_FIND_MODE=FAST
python main.py --highvram --disable-smart-memory --disable-xformers \
  --use-pytorch-cross-attention --listen 0.0.0.0 --port 8188
```

**项目现有 run_comfyui.sh(附录B)对照:**
```bash
export FLASH_ATTENTION_TRITON_AMD_ENABLE="TRUE"
export TORCH_ROCM_AOTRITON_ENABLE_EXPERIMENTAL=1
export HSA_OVERRIDE_GFX_VERSION=11.0.0    # ⚠ 见下方修正
export PYTORCH_HIP_ALLOC_CONF="garbage_collection_threshold:0.8,expandable_segments:True"
python main.py --listen 0.0.0.0 --port 8188 --disable-xformers --use-flash-attention --fp16-vae
```

> ⚠ **发现的问题**:
> 1. **`HSA_OVERRIDE_GFX_VERSION=11.0.0` 是 RX7900(gfx1100) 的值,MI300X(gfx942) 应该用 `9.4.2` 或留空**——文6 用的是 9.4.2;项目附录B 自己也注明"MI300X 通常不需要 override"。
> 2. 缺少 `--enable-triton-backend` 和 triton ≥3.7.1 的安装校验——文1 实测这是 INT8 提速 30% 的关键。
> 3. 缺少 `--highvram`——文2/文6 一致认为 192GB 大显存应常驻 GPU。

### 2.4 显存/offload 策略(192GB 大显存的"反直觉"适配)

文2(435230) 的核心理念:**小显存卡的优化项(BlockSwap、CPU offload、强制清显存、non-blocking)放到 MI300X 上会适得其反**——32.8GB 的主模型明明放得进显存,却被反复搬运,表现为"采样 0% + 内存波动",看着像卡死。

| 工作流设置 | MI300X 适配值 | 原因 |
|---|---|---|
| 主模型 `main_device` | GPU + sdpa | 常驻显存,不 offload |
| BlockSwap | `blocks_to_swap=0` | 低显存方案,大显存增加总线压力 |
| BlockSwap non-blocking | 关闭 | ROCm 下 pinned memory 异步搬运压内存 |
| PurgeVRAM 节点 | 旁路 | 采样前清主模型 = 白折腾 |
| VAE tiling | 全部开启 | 长视频编解码峰值更可控 |
| 彩色遮罩渲染 | CPU | 多帧遮罩不占生成显存 |
| TextEncode | 磁盘缓存 | 6.7GB 文本编码器不重复读 |
| 启动参数 | `--highvram --disable-async-offload --disable-pinned-memory` | 减少隐式 offload |

文4(435068) 印证:`offload_model=False` + 只初始化一次 pipeline,33 帧/12 步峰值显存仅 78GB,预热后稳定 178s/段。

### 2.5 模型下载与缓存(国内加速共识)

- **ModelScope 直连 + aria2 并发**:`aria2c -c -x16 -s16 "<resolve URL>"`——单线程 25~30MB/s → 200MB/s(文1)。resolve URL 的 auth_key 会过期,**断流用 `-c` 续传,别从头下**。
- **HF 镜像**:`export HF_ENDPOINT=https://hf-mirror.com`(文1/文2)。
- **GitHub 镜像**:`git config --global url."https://mirror.ghproxy.com/https://github.com".insteadOf "https://github.com"`(文6)。
- **持久缓存目录**:`MODELSCOPE_CACHE=/mnt/workspace/.cache/modelscope`(文3)——重新发布应用秒加载,别放应用目录。
- **磁盘注意**:`/tmp` 通常只有 30G,大文件放 `/var/tmp` 再软链进 models(文1);权重下载后先校验文件数+总字节数再跑(文4,126GB 权重 <110GiB 视为不完整)。

### 2.6 外网访问方式

| 方式 | 出处 | 评价 |
|---|---|---|
| DSW Jupyter 代理 `/dsw-xxx/proxy/8188/` | 文1 | **最稳**,无 24Mbps 限速、WebSocket 正常 |
| ModelScope Notebook 原生端口代理 | 文2 | 默认首选,免 Tunnel,但需登录态 |
| SSH 隧道 `ssh -N -L 8188:127.0.0.1:8188` | 文1 | 简单可靠 |
| SakuraFrp / Cloudflare tunnel | 文1/文2 | 国内慢(24Mbps),只当免登录分享的备用 |
| 防火墙放行 8188 | 项目附录 | 本机 dy-fanpai 调用最直接 |

---

## 3. 六篇共识(可以放心照做)

1. **ROCm 下 torch 报 `cuda:0` 是正常的**(兼容层命名),判断标准是 `torch.version.hip` 非空;
2. **注意力优先 flash attention 系**,ROCm 官方/社区实测可用;SageAttention 不碰(文1 最新实测);
3. **192GB 大显存 = 模型常驻 GPU + 关 offload + `--highvram`**,别照搬小显存优化;
4. **模型下载走 ModelScope 直连 + 并发**,HF 走 hf-mirror,网络盘慢时看磁盘吞吐别慌;
5. **版本坑**:triton ≥3.7.1(ROCm int8 内核);NumPy 固定 2.1.3(防与 amd-quark 冲突,文2);Python 3.12 配 `SQLAlchemy>=2.0`(文6);
6. **别直接 `pip install -r requirements.txt` 覆盖 torch**(文6 血泪教训)。

## 4. 分歧/矛盾点(需要你决策)

| 矛盾 | 各说各话 | 建议 |
|---|---|---|
| SageAttention | 文6 建议装;文1/文2 实测反对 | **不装**(文1 环境相同、时间最新) |
| `HSA_OVERRIDE_GFX_VERSION` | 项目脚本 11.0.0(RX7900);文6 用 9.4.2;附录B 说 MI300X 可留空 | **改 9.4.2 或留空**,11.0.0 是错的 |
| 全新 venv vs 继承全局 | 文1 全新 venv;文6 继承全局 | 取决于机器是否预装 ROCm torch:预装→继承,裸机→官方 whl |
| `--use-flash-attention` vs `--use-pytorch-cross-attention` | 文1/文3 前者;文2/文6 后者 | 装了 ROCm flash_attn 用前者,否则后者(可都试,看日志 `Using Flash Attention` 才生效) |

---

## 5. 针对本环境(MI300X + Wan2.1 + LatentSync)的推荐方案

### 推荐:venv 继承全局(若已预装 ROCm torch)或官方 whl(裸机)+ 社区最新启动组合

**安装(修改 install_comfyui.sh 的思路):**
```bash
# 1) 先确认全局 torch 是 ROCm 版(非空才是)
python3 -c "import torch; print(torch.version.hip)"   # 期望输出 7.x.x

# 2) 继承全局建 venv(防覆盖 torch),或裸机用官方 whl
python3 -m venv .venv --system-site-packages
source .venv/bin/activate
sed -i '/^torch/d' requirements.txt     # 阉割 torch 行(继承全局时)
pip install -r requirements.txt
pip install triton==3.7.1               # 关键!ROCm int8 内核需要
pip install flash-attn --index-url <ROCm 适配源>  # 可选,装了才能用 --use-flash-attention
```

**启动(融合文1+文2+文6,替换 run_comfyui.sh):**
```bash
#!/bin/bash
cd /mnt/workspace/ComfyUI
source /mnt/workspace/env/bin/activate   # 或 .venv

# ---- AMD 加速区 ----
export TORCH_ROCM_AOTRITON_ENABLE_EXPERIMENTAL=1
export FLASH_ATTENTION_TRITON_AMD_ENABLE="TRUE"
export PYTORCH_HIP_ALLOC_CONF="garbage_collection_threshold:0.8,expandable_segments:True"
export HSA_OVERRIDE_GFX_VERSION=9.4.2    # MI300X=gfx942(之前 11.0.0 是 RX7900 的,错的)
export HIP_FORCE_DEV_KERN_ARG=1
export MIOPEN_FIND_MODE=FAST
export PYTORCH_TUNABLEOP_ENABLED=1        # 可选:第一次慢,之后算子自整定加速

# ---- ComfyUI ----
python main.py --listen 0.0.0.0 --port 8188 \
  --highvram --disable-smart-memory --disable-async-offload --disable-pinned-memory \
  --disable-xformers --use-flash-attention --enable-triton-backend --fp16-vae
```

**工作流适配(Wan2.1 i2v + LatentSync,照文2 改):**
- 主模型 `main_device`=GPU、`sdpa`;BlockSwap=0、non-blocking 关;
- VAE tiling 三处全开(Encode/Decode/Embeds);遮罩渲染走 CPU;
- 口型模型 LatentSync-1.6 装好后按官方工作流参数,`lips_expression 1.5~2.5`;
- 批量生成只初始化一次,连续调 `generate()`(文4 实测预热后稳定 178s/段)。

**验证顺序(文4 的节奏):** 权重完整性校验 → 17 帧冒烟测试 → 单段 5s 视频 → 口型对嘴验证 → 再批量。

---

## 6. 项目现有文件需修正清单

| 文件 | 现状 | 建议 |
|---|---|---|
| `scripts/run_comfyui.sh` | `HSA_OVERRIDE_GFX_VERSION=11.0.0` | 改 `9.4.2` 或留空(MI300X) |
| `scripts/run_comfyui.sh` | 无 `--highvram`、无 `--enable-triton-backend` | 补上(文2/文1 实测) |
| `scripts/install_comfyui.sh` | 全新 venv + rocm7.2 whl(裸机 OK) | 若机器已预装 ROCm,先查 `torch.version.hip`,改用 `--system-site-packages` + 删 torch 行 |
| `scripts/install_comfyui.sh` | 未装 triton 指定版本 | 补 `pip install triton==3.7.1` |
| `COMPYUI_DEPLOY.md` 附录A | Docker 镜像 0.18.2 | 若走 Docker,记得容器内装最新节点/升级 ComfyUI,否则缺 int8 convrot 等新特性 |

---

## 7. 实机诊断结论(2026-08-04, diag_mi300x.sh 输出)

### 7.1 机器真实配置(与文档假设的差异)

| 项 | 文档假设 | 实机确认 | 影响 |
|---|---|---|---|
| GPU | MI300X 192GB | **MI308X**(SKU M3080202, 0x74b6, gfx942 / CDNA3), VRAM 205.8GB(191.7GiB 可用) | 无,MI308X=MI300X 中国特供版,与 435354 完全同款 |
| 系统 | Ubuntu | Ubuntu 22.04.5 LTS x86_64(阿里云 DSW 容器) | 435354 同款环境,优化直接适用 |
| CPU/内存 | AMD 8 核 | Intel Xeon 虚拟核,200Gi RAM(199Gi 可用) | 无 |
| ROCm | 7.2 | **7.2.3** | ✅ |
| PyTorch | 2.11.0(ROCm) | **2.11.0+gitd0c8b1f, hip=7.2.53211** ✅ | 系统已预装,勿覆盖 |
| Python | 3.12 | 3.12.13(/usr/bin/python3) | ✅ |
| flash_attn | — | **2.8.3 已装** | `--use-flash-attention` 可直接用 |
| triton | — | **3.6.0 ⚠️** | **必须升 3.7.1**(3.6.0 int8 内核崩) |
| numpy | — | 2.3.5 | 无 amd-quark 冲突,暂可不动 |
| ComfyUI 位置 | /mnt/workspace | **/workspace/ComfyUI**(git 无 tag,未完成安装) | 脚本 COMFY_WORK 默认值已改 /workspace |
| 模型 | — | **diffusion_models/vae 全空,0 模型** | 需先下载 Wan2.1 I2V 6 件套 |
| 磁盘 | — | 根分区 560G 可用;/mnt/workspace 为 1.0P NFS;/tmp 仅 28G | 模型放工作盘,大文件勿落 /tmp |
| 网络 | — | modelscope.cn 200 OK / hf-mirror 200 OK | 国内直连畅通,可走 ModelScope 下载 |
| 已知异常 | — | dmesg 2 条 `gfx_v9_4_3_bad_op_irq: Illegal opcode`;rocm-smi get_name 报 libdrm 错;torch device 名为空 | 与 triton 3.6.0 int8 内核崩溃同源,升 3.7.1 后观察;不影响启动 |

### 7.2 最终行动方案(按实机状态定制)

```bash
# 1) 装依赖(系统已预装 ROCm torch,只补 ComfyUI 依赖 + 升 triton)
cd /workspace/ComfyUI
python3 -m venv .venv --system-site-packages    # 继承系统 ROCm torch,防覆盖
source .venv/bin/activate
pip install -r requirements.txt
pip install "triton>=3.7.1"                      # ★ 关键:修 3.6.0 int8 崩溃
python -c "import torch; print(torch.version.hip)"  # 确认 hip 非空

# 2) 下载 Wan2.1 I2V 模型(59.7GB, 走 ModelScope 直连)
bash /workspace/scripts/download_wan22_models.sh --comfy-dir /workspace/ComfyUI --only i2v

# 3) 启动(修正版 run_comfyui.sh)
bash /workspace/scripts/run_comfyui.sh           # 已含 --highvram + flash-attn + triton 后端

# 4) 浏览器访问(DSW 实例,走 Jupyter 代理,无 24Mbps 限速)
#    https://<DSW实例域名>/dsw-2074693/proxy/8188/
```

> 与旧方案的 3 处修正:① COMFY_WORK 默认 /mnt/workspace → **/workspace**(实机位置);
> ② 删掉 HSA_OVERRIDE_GFX_VERSION=11.0.0(RX7900 值,MI308X 设了反而可能触发 Illegal opcode);
> ③ 补 `--highvram --enable-triton-backend` + triton≥3.7.1(435354 实测提速 ~30% 来源)。
