// ============================================================
// Z-Image Turbo 文生图 —— 无限画布自定义脚本（能力：图片）
// 用法：渠道配置 → 添加模型(能力=图片) → 「调用脚本」→ 粘贴本文件内容
// 前置：ComfyUI 以 --enable-cors-header=* 启动；z_image_turbo_bf16 /
//       qwen_3_4b / ae.safetensors 三个模型已就位（需重启 ComfyUI 扫描）
// ============================================================
const workflow = {
  "9": {
    "inputs": {
      "filename_prefix": "z-image-turbo",
      "images": [
        "57:8",
        0
      ]
    },
    "class_type": "SaveImage",
    "_meta": {
      "title": "保存图像"
    }
  },
  "57:30": {
    "inputs": {
      "clip_name": "qwen_3_4b.safetensors",
      "type": "lumina2",
      "device": "default"
    },
    "class_type": "CLIPLoader",
    "_meta": {
      "title": "加载CLIP"
    }
  },
  "57:29": {
    "inputs": {
      "vae_name": "ae.safetensors"
    },
    "class_type": "VAELoader",
    "_meta": {
      "title": "加载VAE"
    }
  },
  "57:33": {
    "inputs": {
      "conditioning": [
        "57:27",
        0
      ]
    },
    "class_type": "ConditioningZeroOut",
    "_meta": {
      "title": "条件零化"
    }
  },
  "57:8": {
    "inputs": {
      "samples": [
        "57:3",
        0
      ],
      "vae": [
        "57:29",
        0
      ]
    },
    "class_type": "VAEDecode",
    "_meta": {
      "title": "VAE解码"
    }
  },
  "57:28": {
    "inputs": {
      "unet_name": "z_image_turbo_bf16.safetensors",
      "weight_dtype": "default"
    },
    "class_type": "UNETLoader",
    "_meta": {
      "title": "UNet加载器"
    }
  },
  "57:27": {
    "inputs": {
      "text": "Latina female with thick wavy hair, harbor boats and pastel houses behind. Breezy seaside light, warm tones, cinematic close-up. ",
      "clip": [
        "57:30",
        0
      ]
    },
    "class_type": "CLIPTextEncode",
    "_meta": {
      "title": "CLIP文本编码"
    }
  },
  "57:13": {
    "inputs": {
      "width": 1024,
      "height": 1024,
      "batch_size": 1
    },
    "class_type": "EmptySD3LatentImage",
    "_meta": {
      "title": "空Latent图像（SD3）"
    }
  },
  "57:11": {
    "inputs": {
      "shift": 3,
      "model": [
        "57:28",
        0
      ]
    },
    "class_type": "ModelSamplingAuraFlow",
    "_meta": {
      "title": "采样算法（AuraFlow）"
    }
  },
  "57:3": {
    "inputs": {
      "seed": 0,
      "steps": 8,
      "cfg": 1,
      "sampler_name": "res_multistep",
      "scheduler": "simple",
      "denoise": 1,
      "model": [
        "57:11",
        0
      ],
      "positive": [
        "57:27",
        0
      ],
      "negative": [
        "57:33",
        0
      ],
      "latent_image": [
        "57:13",
        0
      ]
    },
    "class_type": "KSampler",
    "_meta": {
      "title": "K采样器"
    }
  }
};

// ---- 注入本次生成参数 ----
workflow["57:27"].inputs.text = prompt;                  // 提示词
const [w, h] = (params.size || "1024x1024").split("x").map(Number);
workflow["57:13"].inputs.width = w;                      // 宽
workflow["57:13"].inputs.height = h;                     // 高
workflow["57:3"].inputs.seed = Math.floor(Math.random() * 2 ** 31); // 随机种子

// ---- 1. 提交任务 ----
const task = await request({
  method: "post",
  url: `${baseUrl}/api/prompt`,
  headers: { "Content-Type": "application/json" },
  data: { prompt: workflow, client_id: "infinite-canvas" },
});
if (!task.prompt_id) throw new Error("ComfyUI 未返回任务 ID: " + JSON.stringify(task));

// ---- 2. 轮询直到完成（Z-Image 8 步，超时 10 分钟）----
await poll(
  () => request({ method: "get", url: `${baseUrl}/api/history/${task.prompt_id}` }),
  (h) => {
    if (!h) return false;
    const node = h[task.prompt_id];
    if (!node) return false;
    const st = node.status && node.status.status_str;
    if (st === "error" || st === "failed") return true;
    return st === "success" || Object.values(node.outputs || {}).some((o) => o.images?.length);
  },
  { intervalMs: 2000, timeoutMs: 600000 },
);

// ---- 3. 取结果并下载 ----
const history = await request({ method: "get", url: `${baseUrl}/api/history/${task.prompt_id}` });
const node = history[task.prompt_id];
if (node.status && (node.status.status_str === "error" || node.status.status_str === "failed")) {
  throw new Error("ComfyUI 执行失败: " + JSON.stringify(node.status.messages || {}));
}
const img = Object.values(node.outputs || {}).flatMap((o) => o.images || [])[0];
if (!img) throw new Error("没有找到图片输出");

const blob = await (await fetch(
  `${baseUrl}/view?filename=${encodeURIComponent(img.filename)}&subfolder=${encodeURIComponent(img.subfolder || "")}&type=${img.type || "output"}`
)).blob();
const dataUrl = await new Promise((resolve) => {
  const reader = new FileReader();
  reader.onloadend = () => resolve(reader.result);
  reader.readAsDataURL(blob);
});
return [dataUrl];
