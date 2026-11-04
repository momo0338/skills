# job-poster-write · 微信招聘海报与长图流水线使用说明

> 本技能为通用全文海报/长图招聘公告流水线 **`job-poster-write`**。
> 目标：AI 人工介入压缩到唯一一步「读图 → 填 facts.json」，其余零 token 脚本跑。
> 运行：`python3 scripts/job_poster_pipeline.py <子命令>`

## AI 每篇标准序列（7 步，其中只有第 3 步花 token）

```bash
P="scripts/job_poster_pipeline.py"; PY=python3

# ① 抓文（零token）：meta+下图+切段+形态判断 → /tmp/wxwork_<缩写>/
$PY $P fetch "<微信URL>" --dir /tmp/wxwork_<缩写>

# ② 查重（零token）
$PY $P preflight "<单位专名>" [--db "<path.db>"]

# ③ 读图填 facts（唯一 token 开销）
#    读 seg*.png（长图切段）与 img*.png（多卡），硬信息逐条溯源，
#    填 facts.json —— 字段清单：$PY $P --facts-help
#    ⚠️ 截止时间原文没有＝"公告未披露"；敏感词（最高/最多/编制/直签/落户/食堂）
#       必须在 raw_evidence 里有图中原文出处，否则机检拦

# ④ 机检（零token）
$PY $P facts-check facts.json

# ⑤ 组版+封面（零token）
$PY $P gen facts.json
$PY $P cover facts.json          # 推荐：直传 facts.json 自动提取源图与落点目录防分裂
#    或手动指定：$PY $P cover <首图路径> --top 0 --bottom 460 --slug "<slug>" [--line-dir "待发布目录"]
#    cover 目检：Read 封面确认 logo/标题完整，不完整调 --top/--bottom 重裁

# ⑥ 推送（零token，内置 facts-check + --profile mashang 固化）
$PY $P push facts.json          # 推完看 draft/get 五项绿

# ⑦ 交付小结与日志（零token）：总结交付卡片 + 本地留存
$PY $P postprocess facts.json [--log "<path.log>"]
```

## 三类原文形态（fetch 自动判断 form）

| form | 特征 | AI 读法 |
|---|---|---|
| `long` | 单/多张 ≥900×3000 长图 | 读 `seg<idx>_<k>.png`（2000px+60 重叠切段） |
| `multi` | 3+ 张中等卡片图 | 按 idx 顺序直读 `img*.png`；>20 张时软卡竖拼（PIL vstack）base64 内嵌 |
| `text` | 正文是文字（少见） | 直接读 `text.txt`，走 bulletin-write 更合适 |

## 中介转载号三步核源（poster 判定"来源|XX"+免责声明+引流群即触发）

1. 图内 mmbiz URL 前缀与官方原文比对（同图未篡改）
2. 搜官方号原文（WebSearch"标题 + 公众号名"，中公/牛企等转载页常附官方原文链接）
3. 网申平台连通验证（curl 403 别急着判死，换正确域名/ego 渲染）
→ 三者齐才可写；`source_url` 永指官方，绝不用转载号链接。

## 坑位速查（全部实测踩过）

- layout_kit.table 的 headers 必须**纯文本列表**（嵌套元组＝整组文本塞进一个 th）
- `h` 为 str 时不能 `'\n'.join(h)`（会按字符拆串）
- 多图海报 >20 张：软内容卡竖拼 2 张 base64 内嵌（流水线自动换官方图床）
- 网申链接 i/l 易误读（zijgj2027 vs zjgj2027），必须放大核或平台连通验证
- 品牌色取长图众数色，禁沿用上一篇色板
- 封面裁窗要含 logo（目检 Read，必要时微调 --top）
- 流程顺序纪律：**preflight 查重通过后再制作**（勿先组版后查重）

## facts.json 字段清单

跑 `$PY $P --facts-help` 看权威清单。核心：source_url / publisher / company /
line_dir / brand / deadline / audience / positions / locations / apply /
title(≤64) / digest(≤120) / highlight_items(4-5条) / grid(3格) / sections(可选表/列表) /
body_imgs / raw_evidence(溯源) / source_note / work_dir / date_tag / slug。
