# 推草稿 · 服务端验收 · 推送类坑位

> 本文件是 `job-write` 技能的**扩展参考**，不由 SKILL.md 常驻加载。
> **何时读**：要执行推送命令、核对服务端结果、排查微信报错时
> 读完回到 SKILL.md 继续；脚本路径均已写成绝对路径，与当前工作目录无关。
> 返回：`job-write/SKILL.md`

---

## 一、推草稿 + 服务端验收

> ⚠️ **招聘专栏的内容固定推送到「码上职业」公众号，必须显式带 `--profile mashang`。**
> 不带该参数会推到默认账号（满爸爱生活），属事故。账号机制见 `mp-publish` §一.B。
> `--author` 可省略（自动取该账号 `profiles.json` 的 `author` = 码上职业），写了就以显式值为准。

```bash
PY=/usr/local/bin/python3
$PY /Users/zhugx/src/skills/mp-publish/scripts/wx_pipeline.py \
  --html "<绝对路径>/xxx.html" \
  --profile mashang \
  --title "<含校招+单位+城市，≤64字符>" \
  --author "码上职业" \
  --digest "<手写，≤120字，含可搜长尾词>" \
  --cover "<绝对路径>/cover_xx.png" \
  --source-url "<官方报名站/官网招聘页/官方公众号链接>" \
  --update-auto
```

- **`--profile mashang` 是硬要求**（可省略的替代写法：先 `export WX_PROFILE=mashang`）。
  推送日志首行会打印 `目标账号: mashang  AppID=wxfc6d****7cd2`，**推错号时先看这行**。
- `--source-url`：写入草稿 `content_source_url`，**发文后文末「阅读原文」跳转官方源**（用户硬要求）。
- `--update-auto`：按**标题**匹配同名稿就地 update，改稿不留废稿；绝不用 delete+add（用户手改会丢）。
- ⚠️ **摘要来源＝同级源稿，且脚本 2026-09-16 前不认 `-源稿.md` 后缀**：`wx_pipeline.py` 原先只找 `NN-单位.md` / `-发布版.md`，与本专栏约定 `NN-单位-源稿.md` 不符 → **摘要静默回退成"正文开头兜底"**（实测踩过，服务端 digest 会是正文首段）。已修（加入 `-源稿.md` 两种匹配）。**推前必看日志那行**：`[0] 摘要(手动) N 字符` 才是手工摘要，`摘要(自动(正文开头兜底))` 就是没取到。
- ⚠️ **封面若为 RGBA PNG 会直接崩**：`crop_to_cover()` 存 JPEG 不支持 alpha，报 `OSError: cannot write mode RGBA as JPEG`。已修为自动合成白底。**本项目 05-03 荣耀终端封面即为 RGBA**，换封面优先用 JPEG 或存为 RGB PNG。
- ⚠️ **不传 `--cover` 时，prep 兜底会把「正文第一张 base64 图」当封面**——招聘稿件的首图正是**微信群二维码**，等于封面放二维码。流水线会用同级 `-封面.jpg/png` 覆盖它（`final_cover = args.cover or auto_cover`），但**同级封面缺失时必出事**，推前确认封面文件在。
- 验收看 `[VERIFY]`：**标题非空 + 正文 ≥200 字符 + 容器数>0 + 空样式=0**（四项硬校验，任一不达标流水线直接 exit 1）。
- 凭据：`wx_account.py check mashang` 一把过。报 **40164** = 出口 IP 变了，按报错里的 IP
  **到「码上职业」后台**加白名单（设置与开发 → 基本配置 → IP白名单）——**每个号各自维护白名单**。
- ⚠️ **改标题会生成重复草稿**：`--update-auto` 按标题匹配，标题一变就新建一篇、旧稿留箱。改标题后务必用 `draft/delete` 按旧 `media_id` 删旧稿（**精准按 id，别动其它稿**）；或保持标题稳定只调正文。
- ⚠️ **删稿红线不因换号而放松**：`draft/delete` 不可逆、无回收站，且被删 media_id 复用会报 `40007`。删前先 `draft/get` 存档。

---


---

## 二、推送类坑位速查

| 坑位现象 | 根本原因 | 标准解决方案 |
|---|---|---|
| **招聘稿推到了满爸爱生活** | 命令漏了 `--profile mashang` | 补上；推前确认日志首行 `目标账号: mashang`。可用 `export WX_PROFILE=mashang` 兜底 |
| **推草稿报 `40007 invalid media_id`** | 三种成因：没传封面素材 / media_id 属别的号 / 素材刚上传未同步 | 按 `mp-publish` §十四.1 的 40007 排查表逐项排除；脚本已打印可疑 thumb_media_id |
| **推草稿报 `40001 invalid credential`** | token 被顶掉（如手工调过 `cgi-bin/token`） | 脚本已自动刷新重试；勿手工调 `cgi-bin/token` 调试 |
| 改标题后草稿箱出现两篇同内容稿 | `--update-auto` 按标题匹配，标题变→新建 | 改标题后用 `draft/delete` 按旧 media_id 删旧稿 |
| ⚠️ **`--update-auto` 重推后草稿箱出现两篇同名稿**（2026-09-17 实测） | `find_existing_draft` 把 `draft/batchget` 的**瞬时失败**也当成"无同名草稿"返回 `(None,None)` → 静默新建 | **已修**：查询失败返回 `("__QUERY_FAILED__", 原因)`，pipeline 直接 `exit 1` 中止并要求重跑。若你用的还是旧版脚本，重推后**必须 `draft/list` 数一遍篇数** |
| ⚠️ **手写了 SEO 摘要却没用上**（日志显示 `摘要(自动(正文开头兜底))`） | 源稿摘要是**单行式**，旧正则只认两行式 | **已修**（两种写法均支持）。推前必看日志那行是否为 `[0] 摘要(手动) N 字符`；N 还必须 ≤120 |
| 推草稿报 40164 | 出口 IP 不在微信白名单 | 按报错 IP 加白名单（基本配置→IP白名单） |
