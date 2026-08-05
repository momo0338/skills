// ============================================================
// MiniMax H3 图生视频 —— 无限画布自定义脚本（能力：视频）
// 用法：渠道配置 → 添加模型(能力=视频) → 「调用脚本」→ 粘贴本文件内容
//       画布上把一张图片连接到本模型节点作为输入（images[0] = 首帧）
// 前置：ComfyUI 以 --enable-cors-header=* 启动；模型依赖 download_minimax_h3.sh
// 注意：API Key 填任意占位值（ComfyUI 无鉴权，但无限画布校验非空）
// 输入：prompt、images[0]（首帧图 dataURL）、params.seconds / params.size
// 输出：{ blob, mimeType: "video/mp4" }（H3 自带音频音轨）
// ============================================================

if (!images || !images.length) throw new Error("图生视频需要先连接一张图片到本模型节点");

// ---- H3 训练区间约束：帧数 = 秒×24 对齐 17 的倍数，最少 5 秒 ----
const seconds = Math.max(1, Number((params && params.seconds) || 5));
const frames = Math.round(seconds * 24);
const length = Math.max(5, frames + (17 - (frames % 17)) % 17);

// ---- 尺寸：跟随画布参数 WxH 映射到 ResolutionSelector 比例 ----
const ASPECT_OPTIONS = [
  ["1:1 (Square)", 1],
  ["2:3 (Portrait Photo)", 2 / 3],
  ["3:2 (Photo)", 3 / 2],
  ["3:4 (Portrait Standard)", 3 / 4],
  ["4:3 (Standard)", 4 / 3],
  ["9:16 (Portrait Widescreen)", 9 / 16],
  ["16:9 (Widescreen)", 16 / 9],
  ["21:9 (Ultrawide)", 21 / 9],
];
function pickAspectRatio(w, h) {
  const ratio = (w || 16) / (h || 9);
  return ASPECT_OPTIONS.reduce(
    (best, [label, r]) => (Math.abs(r - ratio) < Math.abs(best[1] - ratio) ? [label, r] : best),
    ASPECT_OPTIONS[0],
  )[0];
}
const sizeMatch = String((params && params.size) || "1280x720").match(/^(\d+)x(\d+)$/);
const aspectRatio = sizeMatch ? pickAspectRatio(Number(sizeMatch[1]), Number(sizeMatch[2])) : "16:9 (Widescreen)";

// ---- 上传参考图到 ComfyUI input 目录，返回文件名 ----
async function uploadImage(dataUrl) {
  const blob = await (await fetch(dataUrl)).blob();
  const form = new FormData();
  form.append("image", blob, "h3_ref.png");
  form.append("overwrite", "true");
  const res = await request({
    method: "post",
    url: `${baseUrl}/api/upload/image`,
    data: form, // 不要手动设 Content-Type，交给浏览器带 boundary
  });
  if (!res || !res.name) throw new Error("图片上传失败: " + JSON.stringify(res));
  return res.name;
}
const firstFrameName = await uploadImage(images[0]);

const workflow = {
  "92": {
    "inputs": { "filename_prefix": "video/MiniMax_H3", "format": "auto", "codec": "auto", "video": ["105:91", 0] },
    "class_type": "SaveVideo", "_meta": { "title": "保存视频" }
  },
  "114": {
    "inputs": { "image": "h3_ref.png" },
    "class_type": "LoadImage", "_meta": { "title": "加载图像" }
  },
  "115": {
    "inputs": { "aspect_ratio": "1:1 (Square)", "megapixels": 0.4, "multiple": 32 },
    "class_type": "ResolutionSelector", "_meta": { "title": "分辨率选择器" }
  },
  "119": {
    "inputs": { "upscale_method": "nearest-exact", "megapixels": 1, "resolution_steps": 32 },
    "class_type": "ImageScaleToTotalPixels", "_meta": { "title": "缩放图像（像素）" }
  },
  "120": {
    "inputs": { "image": ["119", 0] },
    "class_type": "GetImageSize", "_meta": { "title": "获取图像尺寸" }
  },
  "105:11": {
    "inputs": { "vae_name": "minimax_h3_video_vae_fp16.safetensors" },
    "class_type": "VAELoader", "_meta": { "title": "加载VAE" }
  },
  "105:24": {
    "inputs": { "vae_name": "minimax_h3_audio_vae_fp32.safetensors" },
    "class_type": "VAELoader", "_meta": { "title": "加载VAE" }
  },
  "105:23": {
    "inputs": { "samples": ["105:14", 0], "vae": ["105:24", 0] },
    "class_type": "VAEDecodeAudio", "_meta": { "title": "VAE解码（音频）" }
  },
  "105:10": {
    "inputs": { "samples": ["105:14", 0], "vae": ["105:11", 0] },
    "class_type": "VAEDecode", "_meta": { "title": "VAE解码" }
  },
  "105:17": {
    "inputs": { "sampler_name": "res_multistep" },
    "class_type": "KSamplerSelect", "_meta": { "title": "K采样器选择" }
  },
  "105:9": {
    "inputs": { "scheduler": "simple", "steps": 20, "denoise": 1, "model": ["105:6", 0] },
    "class_type": "BasicScheduler", "_meta": { "title": "基本调度器" }
  },
  "105:14": {
    "inputs": {
      "noise": ["105:15", 0], "guider": ["105:16", 0], "sampler": ["105:17", 0],
      "sigmas": ["105:9", 0], "latent_image": ["105:104", 1]
    },
    "class_type": "SamplerCustomAdvanced", "_meta": { "title": "自定义采样器（高级）" }
  },
  "105:16": {
    "inputs": { "model": ["105:6", 0], "conditioning": ["105:104", 0] },
    "class_type": "BasicGuider", "_meta": { "title": "基本引导器" }
  },
  "105:6": {
    "inputs": { "unet_name": "minimax_h3_fl2va_pruned_int8_convrot.safetensors", "weight_dtype": "default" },
    "class_type": "UNETLoader", "_meta": { "title": "UNet加载器" }
  },
  "105:13": {
    "inputs": { "clip_name": "qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors", "type": "minimax", "device": "default" },
    "class_type": "CLIPLoader", "_meta": { "title": "加载CLIP" }
  },
  "105:15": {
    "inputs": { "noise_seed": 168866841893410 },
    "class_type": "RandomNoise", "_meta": { "title": "随机噪波" }
  },
  "105:91": {
    "inputs": { "fps": 24, "bit_depth": 8, "images": ["105:10", 0], "audio": ["105:23", 0] },
    "class_type": "CreateVideo", "_meta": { "title": "创建视频" }
  },
  "105:104": {
    "inputs": {
      "prompt": "", "width": ["115", 0], "height": ["115", 1], "length": ["105:107", 1],
      "clip": ["105:13", 0], "vae": ["105:11", 0], "first_frame": ["114", 0]
    },
    "class_type": "MiniMaxH3ImageToVideo", "_meta": { "title": "MiniMax H3 Image to Video" }
  },
  "105:107": {
    "inputs": { "expression": "a", "values.a": ["105:111", 0] },
    "class_type": "ComfyMathExpression", "_meta": { "title": "数学表达式" }
  },
  "105:111": {
    "inputs": { "value": 5 },
    "class_type": "PrimitiveFloat", "_meta": { "title": "Float (duration)" }
  }
};

// ---- 注入本次生成参数 ----
workflow["114"].inputs.image = firstFrameName;                    // 首帧图
workflow["105:104"].inputs.prompt = prompt;                       // 提示词
workflow["105:111"].inputs.value = seconds;                       // 时长（秒）
workflow["105:107"].inputs.expression = `max(5, round(a * 24)) + (5 - (max(5, round(a * 24)) % 17)) % 17`;
workflow["115"].inputs.aspect_ratio = aspectRatio;                // 比例
workflow["115"].inputs.megapixels = 0.4;
workflow["105:15"].inputs.noise_seed = Math.floor(Math.random() * 2 ** 31); // 随机种子

// ---- 1. 提交任务 ----
const task = await request({
  method: "post",
  url: `${baseUrl}/api/prompt`,
  headers: { "Content-Type": "application/json" },
  data: { prompt: workflow, client_id: "infinite-canvas" },
});
if (!task.prompt_id) throw new Error("ComfyUI 未返回任务 ID: " + JSON.stringify(task));

// ---- 2. 轮询直到完成（超时 15 分钟）----
await poll(
  () => request({ method: "get", url: `${baseUrl}/api/history/${task.prompt_id}` }),
  (h) => {
    if (!h) return false;
    const node = h[task.prompt_id];
    if (!node) return false;
    const st = node.status && node.status.status_str;
    if (st === "error" || st === "failed") return true;
    return st === "success" || Object.values(node.outputs || {}).some((o) =>
      o.videos?.length || o.gif?.length || (o.images || []).some((i) => /\.(mp4|webm|mov|mkv)$/i.test(i.filename || ""))
    );
  },
  { intervalMs: 4000, timeoutMs: 900000 },
);

// ---- 3. 取结果并下载 ----
const history = await request({ method: "get", url: `${baseUrl}/api/history/${task.prompt_id}` });
const node = history[task.prompt_id];
if (node.status && (node.status.status_str === "error" || node.status.status_str === "failed")) {
  throw new Error("ComfyUI 执行失败: " + JSON.stringify(node.status.messages || {}));
}
// 注意：SaveVideo 的输出在 history 里挂在 "images" 键下，filename 才是 .mp4
const isVideo = (i) => /\.(mp4|webm|mov|mkv)$/i.test((i.filename || ""));
const vid = Object.values(node.outputs || {})
  .flatMap((o) => (o.videos || []).concat(o.gif || []).concat((o.images || []).filter(isVideo)))[0];
if (!vid) throw new Error("没有找到视频输出，实际输出: " + JSON.stringify(Object.keys(node.outputs || {})));

const blob = await (await fetch(
  `${baseUrl}/view?filename=${encodeURIComponent(vid.filename)}&subfolder=${encodeURIComponent(vid.subfolder || "")}&type=${vid.type || "output"}`
)).blob();
return { blob, mimeType: "video/mp4" };
