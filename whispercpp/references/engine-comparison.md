# 引擎对比：whisper.cpp vs FunASR SenseVoice（2026-08 实测）

> 同一段 263s 千川口播视频（阿泽·全域推商品），两引擎 A/B 实测数据。
> 结论：**术语密集场景首选 whisper.cpp**；SenseVoice 仅用于情感/说话人/粤语场景。

## 实测数据

| 维度 | whisper.cpp large-v3-turbo | FunASR SenseVoice (small) |
|---|---|---|
| 推理引擎 | Metal GPU（Apple Silicon） | 纯 CPU |
| 耗时（263s 音频）| 26.6s（~9.9x 实时） | 30.4s（~8.6x 实时） |
| **千川** | ✅ 正确 | ❌ 「千仓」 |
| **智能优位圈** | ✅ 正确 | ❌ 「智能优惠券」 |
| **AIGC / 混剪** | ✅ 正确 | ❌ 「a r g c」/「混检」 |
| 追投/一键起量/商品卡/保本 | ✅ | ✅（热词生效后）|
| 分段标点 | ✅ 自带 | ❌ 需另配 ct-punc 模型 |
| 口语流畅度 | 稍机械 | 更自然（"实操走一遍"）|
| 附加能力 | — | 情感/事件标签、说话人分离、粤语 |

## 关键结论

1. **术语识别 whisper.cpp 更优**：large-v3-turbo 是 500 万小时多语种训练 + `--prompt` initial prompt 生效；
   SenseVoice 中文口语强但领域术语偏弱（热词 hotword 需按"词 权重"格式传，如 `千川 30`，且仍可能错）
2. **速度几乎打平**：8.6x vs 9.9x，印证"小模型 GPU 收益≈0"（SenseVoice 234M 非自回归，CPU 足够）
3. **SenseVoice 独有优势**：口语自然度、情感/说话人/音频事件标签、粤语/方言、热词硬约束（仅部分生效）

## 选型建议

| 场景 | 引擎 |
|---|---|
| 千川/投流/电商术语密集转写 | **whisper.cpp large-v3-turbo**（默认）|
| 情感分析、说话人分离、粤语 | FunASR SenseVoice（CPU，device="cpu"）|
| 通用长文转写、多语种 | whisper.cpp（99 语言）|

## FunASR 快速备忘（备用）

```bash
# 安装
pip install torch torchaudio funasr

# Python 用法（macOS 无 CUDA → device="cpu"）
python -c "
from funasr import AutoModel
from funasr.utils.postprocess_utils import rich_transcription_postprocess
m = AutoModel(model='iic/SenseVoiceSmall', vad_model='fsmn-vad', device='cpu')
r = m.generate(input='audio.wav', hotword='千川 30 追投 20')
print(rich_transcription_postprocess(r[0]['text']))"
```

### FunASR 模型下载坑（实测）

- ModelScope 正确模型 ID：
  - ASR：`iic/SenseVoiceSmall`（model.pt 897MB）
  - VAD：`iic/speech_fsmn_vad_zh-cn-16k-common-pytorch`（**不是** `iic/fsmn-vad`，那个文件为空）
- 下载走 **modelscope CLI 或 curl 直连**（国内站，示例环境中走代理反而失败，建议直连）
- 文件 URL 格式：`https://modelscope.cn/models/<id>/resolve/master/<file>`
- 热词格式必须是「词 + 空格 + 权重」：`"千川 30 追投 20 ..."`
