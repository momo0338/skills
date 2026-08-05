# INFINITE_CANVAS_H3 · 无限画布接入 MiniMax H3 三能力配置手册

> 版本:1.0  日期:2026-08-05
> 目的:把本地 ComfyUI 上的 MiniMax H3 三个工作流(文生/图生/参考生视频)全部接入
> 无限画布(infinite-canvas),浏览器直连 ComfyUI 生成,无需再翻代码。
> 配套:`scripts/h3_video_t2v.js` / `scripts/h3_video_i2v.js` / `scripts/h3_video_r2v.js`。
> 实测:2026-08-05 三个脚本通过语法 + mock 端到端验证;用户环境 T2V 全链路已通。
> 纪律:改配置只动无限画布 UI,不碰脚本;隧道地址变了只改 Base URL。

---

## 0. 一句话总览

无限画布「渠道」里配一个 ComfyUI 渠道 → 手动加 3 个模型(能力=视频) →
每个模型粘贴对应脚本 → 画布上:文生直接出,图生/参考生把图片连线到模型节点。

---

## 1. 无限画布(项目信息)

| 项 | 值 |
|---|---|
| 项目 | basketikun/infinite-canvas(原版),AGPL-3.0 |
| 仓库 | https://github.com/basketikun/infinite-canvas |
| 技术栈 | Next.js/React + Go(旧版后端已移除,现纯前端) |
| 数据存储 | 浏览器本地(IndexedDB/localforage),配置不落服务器 |
| 用户实例 | https://tasks-threatening-synthetic-behavior.trycloudflare.com/canvas/O4XsMLRdl80fP1luhKaKT |
| 版本线索 | 2026-08-05 主分支 v0.13.0(频道 UI 为「渠道」抽屉) |

### 1.1 自定义脚本执行器规范(源码确认,web/src/services/api/model-plugin.ts)

脚本由 `new Function(...)` 包成 `async () => {}` 执行,可用全局变量:

| 变量 | 类型 | 说明 |
|---|---|---|
| `prompt` | string | 用户提示词(已拼系统提示词) |
| `images` | string[] | 参考图 **dataURL 数组**(图生图/图生视频/参考生时有值) |
| `params` | object | 视频:{seconds, size, resolution, ratio, generateAudio, watermark} |
| `model` / `baseUrl` / `apiKey` | string | 模型名 / 渠道地址(原样未拼 /v1) / API Key |
| `systemPrompt` / `reasoningEffort` | string | 系统提示词 / 推理强度(文本用) |
| `request` | fn | 裸 axios:request({method,url,headers,params,data,responseType}),**不加默认头**,url 相对时按 baseUrl 拼(不加 /v1) |
| `http` | obj | 便捷请求:http.post/get/url,自动带 `Authorization: Bearer apiKey`,path 相对按 baseUrl 拼 **/v1** |
| `poll` | fn | poll(request, extract, {intervalMs, timeoutMs}),extract 返回真值即结束 |
| `sleep` / `signal` / `onDelta` | fn/AbortSignal/fn | 延时 / 取消信号 / 流式文本(文本模型) |

返回约定(视频能力):`{ url }` 或 `{ blob }` 或视频 URL 字符串;
`videoPluginResult` 额外兼容 `{ video_url }` / `{ result_url }`。

关键细节:
- `params.size` 是 **WxH 像素**字符串(如 `1280x720`、`1024x1024`、`auto`),不是比例;
  `params.seconds` 是秒数(1-20,默认 6)。
- **视频脚本拿不到音频参考**:`audioReferences` 只在 Seedance(火山方舟)/OpenAI 协议里传,
  插件脚本只注入 `images`。H3 R2V 的音频驱动(口播段)在无限画布自定义脚本下不可用。
- **API Key 硬校验非空**:`createPluginVideoTask` 里 `if (!config.apiKey.trim()) throw`,
  ComfyUI 无鉴权也必须填占位值(如 `comfyui`)。
- 图片输入必须脚本自己处理:dataURL → fetch → blob → FormData 上传
  `POST {baseUrl}/api/upload/image`(不设 Content-Type,浏览器自动带 boundary)
  → 返回 `{name}` → 注入 LoadImage 节点 `inputs.image`。

---

## 2. ComfyUI 环境(H3 三工作流)

| 项 | 值 |
|---|---|
| ComfyUI 实例 | https://southwest-ways-grad-bowling.trycloudflare.com(cloudflared 隧道,**重启会换地址**) |
| 启动参数 | **必须 `--enable-cors-header=*`**(浏览器直连必需) |
| 工作流 json | ~/Downloads/video_minimax_h3_{t2v,i2v,r2v}.json(用户实测版,已核对) |
| 模型依赖 | `scripts/download_minimax_h3.sh`(fl2va 19.5GB + ref2va 19.5GB + qwen3vl clip + 双 VAE) |

三工作流差异(均 20 步 / res_multistep / simple / 24fps / 8bit / 自带音频音轨):

| | 核心节点 | unet | 图像输入 |
|---|---|---|---|
| T2V | MiniMaxH3ImageToVideo | fl2va | 无 |
| I2V | MiniMaxH3ImageToVideo | fl2va | `first_frame`(1 张) |
| R2V | MiniMaxH3ReferenceToVideo | ref2va | `ref_images.ref_image_0/1`(1~2 张),ref_image_size=match |

节点参数(ComfyUI object_info 确认):
- ResolutionSelector.aspect_ratio 共 8 档:`1:1 (Square)` / `2:3 (Portrait Photo)` /
  `3:2 (Photo)` / `3:4 (Portrait Standard)` / `4:3 (Standard)` /
  `9:16 (Portrait Widescreen)` / `16:9 (Widescreen)` / `21:9 (Ultrawide)`
- length:24fps 帧数,**训练区间 124-362,步长 17**(脚本按 秒×24 对齐 17 的倍数,最少 5 秒)
- R2V ref_images 为 autogrow(0-9 张),另有 ref_videos/ref_video_audios/ref_audios 可选输入

---

## 3. 无限画布配置步骤(渠道)

**入口**:无限画布左下角设置 → 「渠道」tab(默认页)。

1. **新增渠道**,编辑抽屉填:
   - 渠道名称:`ComfyUI-H3`
   - 接口格式:**OpenAI**(任选,模型挂了脚本走插件路径,协议不影响)
   - Base URL:`https://southwest-ways-grad-bowling.trycloudflare.com`(隧道地址变了就改这里)
   - API Key:`comfyui`(任意占位,非空即可)
2. **添加模型**:点「添加模型」→ 弹窗「输入模型名称」手动输入 `h3-t2v` → 增加模型;
   重复加 `h3-i2v`、`h3-r2v` → 确定。
   ⚠ **别点「拉取模型列表」**:ComfyUI 无 OpenAI /models 接口,必报错,手动加即可。
3. **逐个模型配置**(回到渠道抽屉):
   - 能力选 **「视频」**
   - 点 **「调用脚本」** → 粘贴对应 js 全文 → 保存(按钮变「脚本已设」)
     - h3-t2v ← `scripts/h3_video_t2v.js`
     - h3-i2v ← `scripts/h3_video_i2v.js`
     - h3-r2v ← `scripts/h3_video_r2v.js`
4. **保存渠道**。可选:设置页「默认视频模型」指到 `h3-t2v`。

---

## 4. 画布使用

| 模型 | 操作 |
|---|---|
| h3-t2v 文生 | 直接输入提示词生成,无需连图 |
| h3-i2v 图生 | 画布放一张图片节点,**连线到 h3-i2v 节点**(首帧) |
| h3-r2v 参考生 | 连线 **1~2 张** 参考图(脚本按需上传,单图自动移除第二个参考位) |

节点「视频设置」面板可调:清晰度(720p/480p)、尺寸(横屏/竖屏/方形等,
脚本自动映射 H3 8 档比例)、秒数(脚本对齐 17 倍数帧长)。

---

## 5. 三个脚本公共逻辑(scripts/h3_video_*.js)

1. 帧数 = `max(5, round(seconds*24) + (17 - round(seconds*24)%17) % 17)`(H3 latent 时间约束)
2. `params.size` WxH → 最近邻映射 ResolutionSelector.aspect_ratio 8 档;
   megapixels 固定 **0.4**(用户实测稳定档)
3. `images` dataURL → 上传 `/api/upload/image` → 文件名注入 LoadImage 节点
   (T2V 不传图;I2V 取 images[0];R2V 取前 2 张,单图删 139 节点+ref_image_1 引用)
4. 提交 `POST /api/prompt`(client_id=infinite-canvas)→ `poll` 4s/15min →
   取 history → **SaveVideo 的 .mp4 挂在 outputs 的 `images` 键下**(按 filename 后缀识别)
5. `GET /view?filename=...` 下载 blob → `return { blob, mimeType: "video/mp4" }`

---

## 6. 坑与排查

| 症状 | 原因 | 处理 |
|---|---|---|
| "请先配置 API Key" | 无限画布硬校验非空 | 填任意占位如 `comfyui` |
| "拉取模型列表失败" | ComfyUI 无 /models 接口 | 手动输入模型名添加 |
| 提交被 CORS 拦 | ComfyUI 未开 CORS | 以 `--enable-cors-header=*` 重启,隧道需带出该参数 |
| 报错"模型调用脚本执行失败" | 脚本运行时异常 | 看报错末尾真实原因,对照 §1.1 变量名 |
| 生成超时(15min) | H3 20 步较慢或显存不足 | 降低 megapixels(改脚本 0.4→0.3)/换小分辨率 |
| 想用 R2V 音频参考驱动 | 无限画布插件脚本拿不到音频 | 走本地 workflow 或改 H3 工作流手动跑 |

环境恢复顺序(隧道失效后):
1. 重启 ComfyUI(带 `--enable-cors-header=*`)→ cloudflared 起新隧道
2. 无限画布设置 → 渠道 → 改 Base URL 为新隧道地址 → 保存
3. 直接生成,无需改脚本/模型

---

## 7. 相关文件索引

| 文件 | 用途 |
|---|---|
| scripts/h3_video_t2v.js / i2v.js / r2v.js | 三个无限画布自定义脚本(本手册核心) |
| scripts/download_minimax_h3.sh | H3 模型下载(i2v/r2v/both,modelscope) |
| ~/Downloads/video_minimax_h3_{t2v,i2v,r2v}.json | 用户实测工作流原始 json(脚本的基底) |
| /tmp/infinite-canvas-src | 无限画布源码浅克隆(规范核实来源,可删可留) |
| scripts/image_z_image_turbo.js | Z-Image 文生图脚本(同类用法参考) |
