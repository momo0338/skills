# 明日验证清单(2026-08-04)

> 生成日期:2026-08-03 晚。今日已完成管线全链路打通,明日起重新验证。
> 工作区已从临时目录迁移到稳定路径:**`~/dy_fp/ws`**(勿再用 /tmp/fp_flow)。

---

## 当前已完成(今天 2026-08-03 的成果)

### 代码与后端(已提交,git 全绿)
| 项 | 状态 |
|---|---|
| Qwen 反推腿(`reverse/qwen.py`) | ✅ 实测通过(真实视频 88 镜) |
| Seed 反推腿(`reverse/seed.py`) | ✅ 实测通过(88 镜) |
| Kimi 反推腿(`reverse/kimi.py`) | 🟡 缺 K3 权限(账号只有 k2.6,不支持视频) |
| reverse 阶段接入 CLI | ✅ `run --stage reverse --leg qwen/seed` |
| audio 阶段接入 CLI(原音切段) | ✅ `run --stage audio` |
| MiniMax H3 后端(`generation/minimax.py`) | ✅ 代码就绪,待 key 实测 |
| ComfyUI 后端(`generation/comfyui.py`) | ✅ 代码就绪,待自有机器部署 |
| 烧字幕(libass) | ✅ brew ffmpeg-full 已装,验证通过 |
| planner 修复(audio 路径+无主播编号) | ✅ 已提交 |
| 测试基线 | ✅ 239 passed / ruff / pyright 全绿 |

### 管线端到端(真实内裤视频 146.7s)
```
reverse(88镜) → plan(30段) → audio(30 wav) → generate(S1+S3 手动) → assemble → deliver ✅
```
- 预览片 8.2s(仅 S1+S3,28 段缺失)已生成,烧字幕成功;
- 四道闸门 rights→plan→cost→qc 全部验证。

---

## 明日验证步骤(按序)

### 1. 确认环境
```bash
cd /Users/zhugx/src/skills/dy-fanpai
.venv/bin/dy-fanpai doctor   # 期望:ARK/KIMI/XYQ WARN(缺),DASHSCOPE OK,MINIMAX WARN,COMfyUI WARN
```

### 2. 继续生成剩余 28 段(即梦页面手动)
- 素材在 `~/dy_fp_manual/`(30 段音频 + 3 张产品图)
- 每段:上传对应图+音频(口播段)→ 贴 `~/dy_fp/ws/planning/segments.md` 的 prompt → 9:16 → 下载
- **产物命名**:`~/dy_fp/ws/generation/clips/S<段号>.mp4`(如 S2.mp4)
- 建议顺序:口播段优先(难度高),i2v 后做

### 3. 每凑齐一批就装配
```bash
# 批 cost + qc 闸(已批过一次,新工作区需重批)
.venv/bin/dy-fanpai approve ~/dy_fp/ws cost
.venv/bin/dy-fanpai approve ~/dy_fp/ws qc
# 装配(deliver 含烧字幕+SRT+剪映草稿)
# 注意:assemble 阶段 CLI 尚未接线,用模块直接调:
.venv/bin/python -c "
import sys; sys.path.insert(0, 'src')
from dy_fanpai.media.ffmpeg import assemble
assemble('~/dy_fp/ws/planning/segments.json', '~/dy_fp/ws/generation/clips', '~/dy_fp/ws/audio/segments', '~/dy_fp/ws/output/FULL.mp4')
"
.venv/bin/dy-fanpai run ~/dy_fp/ws --stage deliver   # 若草稿已存在报错,删 output/草稿 或手动调
```

### 4. 备选:ComfyUI 自动链路(自有 MI300X 机器)
- 部署:`COMPYUI_DEPLOY.md` 附录 A(AMD 官方镜像,5 条命令)
- 搭好工作流导出模板 → 配 `COMfyUI_BASE_URL`/`COMfyUI_WORKFLOW_I2V`/`COMfyUI_WORKFLOW_MM`
- `--i2v-backend comfyui` 切后端,口播段需 LatentSync 实测后放开

### 5. 备选:MiniMax(若拿到 key)
- 配 `MINIMAX_API_KEY` → `--i2v-backend minimax`(纯产品段确定支持)

---

## 关键路径速查

| 项 | 路径 |
|---|---|
| 工作区 | `~/dy_fp/ws` |
| 素材(页面操作用) | `~/dy_fp_manual/`(33 文件) |
| 规划/人审稿 | `~/dy_fp/ws/planning/segments.json` / `segments.md` |
| 段音频 | `~/dy_fp/ws/audio/segments/*.wav` |
| 生成产物放这 | `~/dy_fp/ws/generation/clips/S<段号>.mp4` |
| 成片 | `~/dy_fp/ws/output/`(FULL/FINAL/SRT/草稿) |
| 部署操作单 | `COMPYUI_DEPLOY.md` |
| 即梦手动操作单 | `JIMENG_MANUAL.md` |

---

## 明日验证目标(验收标准)

1. **完整成片**:30 段全部生成 → assemble → 146s FULL.mp4 无缺片警告;
2. **字幕正确**:SRT 时间轴与成片对齐,无重叠/错位;
3. **四闸门**:全流程按 rights→plan→cost→qc 顺序推进;
4. **(可选)双后端对比**:Qwen 反推 + 即梦生成 vs ComfyUI 生成的成片质量对比。
