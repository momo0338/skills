# 即梦页面手动执行操作单(无 API/CLI 权限路径)

> 版本:1.0  日期:2026-08-03
> 工作区:`/tmp/fp_flow/ws`(146.7s 男童内裤带货视频,30 段规划,原音已切)
> 目的:你无即梦 API/CLI 权限 → 改为**在即梦官网(jimeng.jianying.com)页面手动生成**,
> 产物放回工作区 → 我自动跑后续 assemble/deliver 并对比效果。
> 纪律:一次一段、按清单核对、产物命名严格一致(否则后续脚本找不到)。

---

## 第 0 步 · 准备真实素材(必须先做)

当前 `assets.json` 里的图片路径是**占位符**(文件不存在),必须先替换成真实素材:

| 素材 | 目标路径(工作区内) | 说明 |
|---|---|---|
| 主播锚图(可选) | `inputs/assets/host.jpg` | 若视频有真人主播则放同人截图;纯产品视频可留空 |
| 产品 hero 图 | `inputs/assets/内裤正面.jpg` | 内裤正面照(白/浅绿/深蓝其中一色即可) |
| 产品特写图 | `inputs/assets/内裤特写.jpg` | 内裤细节/底裆特写 |
| 包装袋图 | `inputs/assets/包装袋.jpg` | 视频里的包装袋截图 |
| 网纱袋图 | `inputs/assets/网纱袋.jpg` | 视频里的透明袋截图 |

```bash
# 把真实图片复制到工作区(命名与上表一致)
mkdir -p /tmp/fp_flow/ws/inputs/assets
cp /你的/真实/图片.jpg /tmp/fp_flow/ws/inputs/assets/内裤正面.jpg
# …其余同理
```

> 无主播出镜(本视频全为手部特写)→ host.jpg 可跳过,但 mm 段会缺少主播图,
> 即梦页面生成时**只用产品图即可**(提示词里的 @图片1 主播部分可忽略/删减)。

---

## 第 1 步 · 在即梦页面生成(逐段操作)

打开 https://jimeng.jianying.com →「视频生成」(seedance/2.0 或当前可用模型)。

### A. 纯产品段(i2v,12 段:S1 S2 S4 S7 S10 S13 S16 S19 S22 S25 S28 S30)

每段操作:
1. **上传锚图**:把该段对应的产品图拖进「参考图/首帧」;
2. **粘贴 prompt**:从下面清单复制该段的 `prompt`;
3. **时长**:该段的 `duration` 秒;
4. **比例**:9:16;
5. 生成 → 下载视频 → 存为 `generation/clips/S<xx>.mp4`。

### B. 口播段(mm,18 段:其余全部)

每段操作:
1. **上传参考图**:该段 `images` 列出的产品图(1~2 张);
2. **上传音频**:该段 `audio/segments/S<xx>.wav`(已切好);
3. **粘贴 prompt**;
4. **时长**/比例同上;
5. 生成 → 下载 → 存为 `generation/clips/S<xx>.mp4`。

---

## 第 2 步 · 逐段参数清单(复制用)

> 完整 prompt 很长,这里给出每段的**关键信息**;完整 prompt 见
> `/tmp/fp_flow/ws/planning/segments.md`(人审稿,逐段代码块)。

| 段 | 类型 | 时长 | 参考图(assets/) | 音频(有则传) |
|---|---|---|---|---|
| S1 | i2v | 4s | 包装袋.jpg | — |
| S2 | i2v | 4s | 包装袋.jpg | — |
| S3 | mm | 4s | 内裤正面.jpg | S3.wav |
| S4 | i2v | 4s | 内裤特写.jpg | — |
| S5 | mm | 7s | 内裤正面.jpg | S5.wav |
| S6 | mm | 6s | 内裤正面.jpg | S6.wav |
| S7 | i2v | 6s | 内裤正面.jpg | — |
| S8 | mm | 5s | 内裤正面.jpg | S8.wav |
| S9 | mm | 6s | 内裤正面.jpg | S9.wav |
| S10 | i2v | 5s | 内裤特写.jpg | — |
| S11 | mm | 6s | 内裤正面.jpg | S11.wav |
| S12 | mm | 7s | 内裤正面.jpg | S12.wav |
| S13 | i2v | 5s | 包装袋.jpg | — |
| S14 | mm | 5s | 内裤正面.jpg | S14.wav |
| S15 | mm | 5s | 内裤正面.jpg | S15.wav |
| S16 | i2v | 5s | 内裤特写.jpg | — |
| S17 | mm | 5s | 内裤正面.jpg | S17.wav |
| S18 | mm | 5s | 内裤正面.jpg | S18.wav |
| S19 | i2v | 5s | 包装袋.jpg | — |
| S20 | mm | 5s | 内裤正面.jpg | S20.wav |
| S21 | mm | 5s | 内裤正面.jpg | S21.wav |
| S22 | i2v | 5s | 内裤特写.jpg | — |
| S23 | mm | 5s | 内裤正面.jpg | S23.wav |
| S24 | mm | 5s | 内裤正面.jpg | S24.wav |
| S25 | i2v | 5s | 包装袋.jpg | — |
| S26 | mm | 5s | 内裤正面.jpg | S26.wav |
| S27 | mm | 5s | 内裤正面.jpg | S27.wav |
| S28 | i2v | 5s | 内裤特写.jpg | — |
| S29 | mm | 5s | 内裤正面.jpg | S29.wav |
| S30 | i2v | 5s | 内裤特写.jpg | — |

> 注:实际以 `segments.md` 的 images 字段为准(上表为常见映射;个别段图可能不同)。

---

## 第 3 步 · 产物放回(完成后告诉我)

```bash
# 全部 clip 放好后检查
ls /tmp/fp_flow/ws/generation/clips/*.mp4 | wc -l    # 期望 30
```

放好后**跟我说一声**,我自动跑:
1. **assemble**:归一化 → concat → 配音轨 → mux 成 `output/FULL.mp4`;
2. **qc**:解码/分辨率/时长比 结构评委;
3. **deliver**:SRT 字幕 + 无烧字幕 FINAL(本机缺 libass 时)+ 剪映草稿规格;
4. **对比**:与源视频做时长/结构比对,给验收结论。

---

## 快捷做法(嫌 30 段太多)

**先做 2~3 段试水**(比如 S1 i2v + S3 mm + S4 i2v),我先把 pipeline 跑通验证效果,
满意后再批量生成剩余段。每段约 1~2 分钟页面操作。

## 若即梦页面也缺权限

同思路可切 **MiniMax**(`--i2v-backend minimax`,已实现,配 key 即可)或 **Ark Seedance**
(控制台开通模型)。告诉我你实际能用的平台,我对应调整。
