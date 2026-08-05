// ============================================================
// MiniMax H3 参考生视频 —— 无限画布自定义脚本（能力：视频）
// 用法：渠道配置 → 添加模型(能力=视频) → 「调用脚本」→ 粘贴本文件内容
//       画布上连接 1~2 张参考图到本模型节点（images[0]/images[1]）
// 前置：ComfyUI 以 --enable-cors-header=* 启动；ref2va 模型已下载
//       （download_minimax_h3.sh --only r2v 或 both）
// 注意：API Key 填任意占位值（ComfyUI 无鉴权，但无限画布校验非空）
// 输入：prompt、images（参考图，最多取前 2 张）、params.seconds / params.size
// 输出：{ blob, mimeType: "video/mp4" }（H3 自带音频音轨）
// 说明：ref_image_size=match 输出尺寸跟随参考图比例；视频脚本无音频参考输入
//       （无限画布自定义脚本不传 audioReferences，Seedance 协议才有）
// ============================================================

if (!images || !images.length) throw new Error("参考生视频需要至少连接一张参考图到本模型节点");

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
const refNames = [await uploadImage(images[0])];
if (images[1]) refNames.push(await uploadImage(images[1]));

const workflow = {
  "92": {
    "inputs": { "filename_prefix": "video/MiniMax_H3", "format": "auto", "codec": "auto", "video": ["130", 0] },
    "class_type": "SaveVideo", "_meta": { "title": "保存视频" }
  },
  "115": {
    "inputs": { "aspect_ratio": "16:9 (Widescreen)", "megapixels": 0.4, "multiple": 32 },
    "class_type": "ResolutionSelector", "_meta": { "title": "Resolution Selector (Size)" }
  },
  "119": {
    "inputs": { "vae_name": "minimax_h3_video_vae_fp16.safetensors" },
    "class_type": "VAELoader", "_meta": { "title": "加载VAE" }
  },
  "120": {
    "inputs": { "vae_name": "minimax_h3_audio_vae_fp32.safetensors" },
    "class_type": "VAELoader", "_meta": { "title": "加载VAE" }
  },
  "121": {
    "inputs": { "samples": ["125", 0], "vae": ["120", 0] },
    "class_type": "VAEDecodeAudio", "_meta": { "title": "VAE解码（音频）" }
  },
  "122": {
    "inputs": { "samples": ["125", 0], "vae": ["119", 0] },
    "class_type": "VAEDecode", "_meta": { "title": "VAE解码" }
  },
  "123": {
    "inputs": { "sampler_name": "res_multistep" },
    "class_type": "KSamplerSelect", "_meta": { "title": "K采样器选择" }
  },
  "124": {
    "inputs": { "scheduler": "simple", "steps": 20, "denoise": 1, "model": ["127", 0] },
    "class_type": "BasicScheduler", "_meta": { "title": "基本调度器" }
  },
  "125": {
    "inputs": {
      "noise": ["129", 0], "guider": ["126", 0], "sampler": ["123", 0],
      "sigmas": ["124", 0], "latent_image": ["136", 1]
    },
    "class_type": "SamplerCustomAdvanced", "_meta": { "title": "自定义采样器（高级）" }
  },
  "126": {
    "inputs": { "model": ["127", 0], "conditioning": ["136", 0] },
    "class_type": "BasicGuider", "_meta": { "title": "基本引导器" }
  },
  "127": {
    "inputs": { "unet_name": "minimax_h3_ref2va_pruned_int8_convrot.safetensors", "weight_dtype": "default" },
    "class_type": "UNETLoader", "_meta": { "title": "UNet加载器" }
  },
  "128": {
    "inputs": { "clip_name": "qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors", "type": "minimax", "device": "default" },
    "class_type": "CLIPLoader", "_meta": { "title": "加载CLIP" }
  },
  "129": {
    "inputs": { "noise_seed": 157368968253448 },
    "class_type": "RandomNoise", "_meta": { "title": "随机噪波" }
  },
  "130": {
    "inputs": { "fps": 24, "bit_depth": 8, "images": ["122", 0], "audio": ["121", 0] },
    "class_type": "CreateVideo", "_meta": { "title": "创建视频" }
  },
  "131": {
    "inputs": { "expression": "a", "values.a": ["132", 0] },
    "class_type": "ComfyMathExpression", "_meta": { "title": "数学表达式" }
  },
  "132": {
    "inputs": { "value": 5 },
    "class_type": "PrimitiveFloat", "_meta": { "title": "Float (Duration)" }
  },
  "136": {
    "inputs": {
      "prompt": "", "width": ["115", 0], "height": ["115", 1], "length": ["131", 1],
      "ref_image_size": "match", "clip": ["128", 0], "vae": ["119", 0], "audio_vae": ["120", 0],
      "ref_images.ref_image_0": ["137", 0], "ref_images.ref_image_1": ["139", 0]
    },
    "class_type": "MiniMaxH3ReferenceToVideo", "_meta": { "title": "MiniMax H3 Reference to Video" }
  },
  "137": {
    "inputs": { "image": "h3_ref.png" },
    "class_type": "LoadImage", "_meta": { "title": "加载图像" }
  },
  "139": {
    "inputs": { "image": "h3_ref.png" },
    "class_type": "LoadImage", "_meta": { "title": "加载图像" }
  }
};

// ---- 注入本次生成参数 ----
workflow["137"].inputs.image = refNames[0];                       // 参考图 1
if (refNames[1]) {
  workflow["139"].inputs.image = refNames[1];                     // 参考图 2
} else {
  delete workflow["139"];                                         // 单图时移除第二个 LoadImage
  delete workflow["136"].inputs["ref_images.ref_image_1"];
}
workflow["136"].inputs.prompt = prompt;                           // 提示词
workflow["132"].inputs.value = seconds;                           // 时长（秒）
workflow["131"].inputs.expression = `max(5, round(a * 24)) + (5 - (max(5, round(a * 24)) % 17)) % 17`;
workflow["115"].inputs.aspect_ratio = aspectRatio;                // 比例
workflow["115"].inputs.megapixels = 0.4;
workflow["129"].inputs.noise_seed = Math.floor(Math.random() * 2 ** 31); // 随机种子

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
