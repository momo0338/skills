# ComfyUI 工作流模板

在自有 ComfyUI 机器上搭好工作流后,导出 JSON 保存到本目录,并在 config 指定路径:

- `comfyui_i2v.json` — Wan2.1 图生视频(纯产品段)。config 键 `COMFYUI_WORKFLOW_I2V`。graph 格式。
- `comfyui_h3_i2v.json` — MiniMax H3(FL2VA) 图生视频。config 键 `COMFYUI_WORKFLOW_H3_I2V`。graph 格式。
- `comfyui_h3_t2v.json` — MiniMax H3 文生视频。config 键 `COMFYUI_WORKFLOW_H3_T2V`。扁平格式。
- `comfyui_h3_r2v.json` — MiniMax H3(ref2va) 参考生视频(1~2 张参考图驱动)。config 键
  `COMFYUI_WORKFLOW_H3_R2V`。扁平格式。
- `comfyui_mm.json` — LatentSync 口型(口播段)。config 键 `COMFYUI_WORKFLOW_MM`。

两种模板格式都支持,`submit()` 自动识别:
- **graph 格式**(顶层有 `nodes`/`links`):ComfyUI 网页导出的画布格式,提交前转扁平。
- **扁平格式**(顶层即 `{node_id: {class_type, inputs}}`):与 `/prompt` API 一致,
  直接提交。H3 t2v/r2v 模板采用此格式(从 `scripts/h3_video_t2v.js` /
  `h3_video_r2v.js` 抽取,实测工作流)。

## 占位符约定(模板内用这些字面量,提交时被替换)

| 占位符 | 含义 | 例 |
|---|---|---|
| `__PROMPT__` | 该段生成 prompt | 放在文本节点/prompt 字段 |
| `__IMAGE__` | 上传后的图片文件名(第一张) | LoadImage 的 image 字段 |
| `__IMAGE2__` | 第二张图(r2v 参考图 2) | 第二个 LoadImage |
| `__AUDIO__` | 上传后的音频文件名 | LoadAudio 的 audio 字段 |
| `__DURATION__` | 段时长(秒) | 帧数/时长节点 |
| `__WIDTH__` / `__HEIGHT__` | 输出分辨率 | EmptyLatentImage 等 |
| `__RESOLUTION__` | `宽x高` 组合串 | 文本提示可引用 |
| `__FRAMES__` | 按后端帧率计算的帧数(Wan 16fps / H3 24fps+17k 网格) | 帧数节点 |
| `__ASPECT__` | H3 ResolutionSelector 的 aspect_ratio 枚举串(按宽高自动映射 8 档) | ResolutionSelector |
| `__SEED__` | H3 随机种子(0..2^31,未显式指定时自动生成) | RandomNoise 的 noise_seed |

示例(LoadImage 节点):
```json
{"type": "LoadImage", "inputs": {"image": "__IMAGE__", "upload": "image"}}
```

> 占位符在模板 JSON 的**字符串值**中;模块提交前递归替换。
> 不出现的占位符保持原样,便于发现模板缺参。
> r2v 单参考图时自动移除第二个 LoadImage 与 `ref_images.ref_image_1` 引用。
