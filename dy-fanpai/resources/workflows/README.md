# ComfyUI 工作流模板

在自有 ComfyUI 机器上搭好工作流后,导出 JSON 保存到本目录,并在 config 指定路径:

- `comfyui_i2v.json` — Wan2.1 图生视频(纯产品段)。config 键 `COMFYUI_WORKFLOW_I2V`。
- `comfyui_mm.json` — LatentSync 口型(口播段)。config 键 `COMFYUI_WORKFLOW_MM`。

## 占位符约定(模板内用这些字面量,提交时被替换)

| 占位符 | 含义 | 例 |
|---|---|---|
| `__PROMPT__` | 该段生成 prompt | 放在文本节点/prompt 字段 |
| `__IMAGE__` | 上传后的图片文件名(第一张) | LoadImage 的 image 字段 |
| `__IMAGE2__` | 第二张图(口播段参考图) | 第二个 LoadImage |
| `__AUDIO__` | 上传后的音频文件名 | LoadAudio 的 audio 字段 |
| `__DURATION__` | 段时长(秒) | 帧数/时长节点 |
| `__WIDTH__` / `__HEIGHT__` | 输出分辨率 | EmptyLatentImage 等 |
| `__RESOLUTION__` | `宽x高` 组合串 | 文本提示可引用 |

示例(LoadImage 节点):
```json
{"type": "LoadImage", "inputs": {"image": "__IMAGE__", "upload": "image"}}
```

> 占位符在模板 JSON 的**字符串值**中;模块提交前递归替换。
> 不出现的占位符保持原样,便于发现模板缺参。
