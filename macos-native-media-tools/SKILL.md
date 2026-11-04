---
name: macos-native-media-tools
description: 用 macOS 原生能力离线处理素材：把扫描版 PDF 渲染成图片、对图片做中文 OCR（Vision 框架）、用代码直接绘制图片（AppKit）、解码二维码/条码（Vision，可验微信带 logo 群码）。当需要"从无文字层的 PDF 里取文字"、"把图片名单/证书/表格转成可检索文本"、"生成配图/示意图/证书样式图"、"校验二维码是否真能扫/改图后复验扫码"而手边没有 API 或在线工具时使用。全程不联网、不装依赖，只需本机 /usr/bin/swiftc。
metadata:
  version: "1.1.0"
  date: "2026-09-16"
  agent_created: true
---

# macOS 原生素材处理四件套（PDF→图 / 图→文字 / 代码画图 / 码→内容）

四个高频场景，全部用 macOS 自带框架 + `swiftc`（Xcode Command Line Tools 提供，本机 `/usr/bin/swiftc`）解决，**不联网、不装 pip 包、不依赖在线 API**。

## 前置检查

```bash
which swiftc            # /usr/bin/swiftc
ls /Library/Developer/CommandLineTools/usr/bin/swiftc
```
若缺失，说明未装 Xcode CLT，本技能全部不适用（改走在线方案）。

---

## 一、PDF → PNG（含扫描版 PDF）

**为什么需要**：扫描件 PDF **没有文字层**（`pypdf` 只能提出几个字符），必须渲染成图再 OCR。
（先验证：`pypdf` 提取字符数 < 50 基本就是扫描件。）

```swift
// p2p.swift —— 用法: p2p in.pdf outdir
import Foundation
import PDFKit
import AppKit
let args = CommandLine.arguments
guard args.count >= 3 else { print("usage: p2p in.pdf outdir"); exit(1) }
guard let doc = PDFDocument(url: URL(fileURLWithPath: args[1])) else { exit(2) }
let outdir = args[2]
let scale: CGFloat = 3.0                       // 3x 足够 OCR，别低于 2x
for i in 0..<doc.pageCount {
    guard let page = doc.page(at: i) else { continue }
    let rect = page.bounds(for: .mediaBox)
    let w = Int(rect.width * scale), h = Int(rect.height * scale)
    guard let ctx = CGContext(data: nil, width: w, height: h, bitsPerComponent: 8,
        bytesPerRow: 0, space: CGColorSpaceCreateDeviceRGB(),
        bitmapInfo: CGImageAlphaInfo.premultipliedFirst.rawValue) else { continue }
    ctx.setFillColor(CGColor.white)             // 必须铺白底，否则透明变黑
    ctx.fill(CGRect(x: 0, y: 0, width: w, height: h))
    ctx.scaleBy(x: scale, y: scale)
    page.draw(with: .mediaBox, to: ctx)
    guard let cg = ctx.makeImage() else { continue }
    let rep = NSBitmapImageRep(cgImage: cg)
    if let d = rep.representation(using: .png, properties: [:]) {
        try? d.write(to: URL(fileURLWithPath: String(format: "%@/p%02d.png", outdir, i + 1)))
    }
}
```
```bash
swiftc -O -o p2p p2p.swift && mkdir -p out && ./p2p "扫描件.pdf" out
```

---

## 二、图片 → 中文文字（Vision OCR + 表格行重建）

```swift
// ocr.swift —— 用法: ocr 图1 图2 ...
import Foundation
import Vision
import AppKit
let paths = Array(CommandLine.arguments.dropFirst())
for path in paths {
    guard let img = NSImage(contentsOfFile: path),
          let cg = img.cgImage(forProposedRect: nil, context: nil, hints: nil) else { continue }
    let req = VNRecognizeTextRequest()
    req.recognitionLevel = .accurate
    req.recognitionLanguages = ["zh-Hans", "en-US"]   // 中文必需 zh-Hans
    req.usesLanguageCorrection = false                 // ⚠️ 名单/证书类必须关，否则会"纠正"人名
    try? VNImageRequestHandler(cgImage: cg, options: [:]).perform([req])
    guard let obs = req.results else { continue }
    var items: [(y: CGFloat, x: CGFloat, t: String)] = []
    for o in obs { if let c = o.topCandidates(1).first {
        items.append((o.boundingBox.midY, o.boundingBox.minX, c.string)) } }
    items.sort { a, b in abs(a.y - b.y) < 0.012 ? a.x < b.x : a.y > b.y }
    var rows: [[(x: CGFloat, t: String)]] = []; var curY: CGFloat = -1; var cur: [(x: CGFloat, t: String)] = []
    for it in items {
        if curY < 0 || abs(it.y - curY) < 0.012 { cur.append((it.x, it.t)); curY = curY < 0 ? it.y : (curY + it.y)/2 }
        else { rows.append(cur); cur = [(it.x, it.t)]; curY = it.y }
    }
    if !cur.isEmpty { rows.append(cur) }
    print("===FILE=== \(path)")
    for r in rows { print(r.sorted { $0.x < $1.x }.map { $0.t }.joined(separator: " | ")) }
}
```
```bash
swiftc -O -o ocr ocr.swift
./ocr 图*.png > /tmp/ocr_raw.txt      # 目录内批量
```

**要点**
- **表格行重建**：用 `boundingBox.midY` 把同一视觉行聚类，再按 `minX` 拼成 `列1 | 列2 | 列3`；阈值 `0.012` 是实测好用的值。
- **⚠️ shell glob 顺序坑**：`*.png *.jpg` 会把 jpg 全排到 png 之后，**输出顺序错乱**。解析文件名里的序号**重新排序**。
- **必须加免责声明**：OCR 是机器稿，人名/公司名生僻字会错；表格单元格内长文本在图上折行会被切成相邻两行 → **不能当结构化数据用**。产物命名 `xxxOCR识别稿_仅供参考.txt`，开头写明"引用一律以原图为准"。
- **可交叉验证**：各图行数之和 ↔ 原文声明的总数（例：指导教师图 1+22+22+5=50 ↔ 原文"50 位"），对得上才说明理解无误。

---

## 三、用代码画图（AppKit 绘图出 PNG）

**何时用**：需要配图/示意图/证书样式图，但**不能用真实照片**（隐私），或浏览器截图不可用（见下）。

```swift
import AppKit
let W: CGFloat = 1000, H: CGFloat = 940, SCALE: CGFloat = 2
func R(_ x: CGFloat, _ y: CGFloat, _ w: CGFloat, _ h: CGFloat) -> NSRect {
    NSRect(x: x, y: H - y - h, width: w, height: h)      // 以「左上角为原点」的坐标助手
}
func draw(_ s: String, _ rect: NSRect, font: NSFont, color: NSColor,
          align: NSTextAlignment = .left, kern: CGFloat = 0,
          lineHeight: CGFloat = 0, firstIndent: CGFloat = 0) {
    let p = NSMutableParagraphStyle()
    p.alignment = align
    if lineHeight > 0 { p.minimumLineHeight = lineHeight; p.maximumLineHeight = lineHeight }
    p.firstLineHeadIndent = firstIndent
    NSAttributedString(string: s, attributes: [.font: font, .foregroundColor: color,
        .paragraphStyle: p, .kern: kern]).draw(in: rect)
}
guard let rep = NSBitmapImageRep(bitmapDataPlanes: nil, pixelsWide: Int(W*SCALE),
    pixelsHigh: Int(H*SCALE), bitsPerSample: 8, samplesPerPixel: 4, hasAlpha: true,
    isPlanar: false, colorSpaceName: .deviceRGB, bytesPerRow: 0, bitsPerPixel: 0) else { exit(1) }
let ctx = NSGraphicsContext(bitmapImageRep: rep)!
NSGraphicsContext.saveGraphicsState(); NSGraphicsContext.current = ctx
ctx.cgContext.scaleBy(x: SCALE, y: SCALE)                 // 2x 出图，防止发虚
NSColor.white.setFill(); NSRect(x: 0, y: 0, width: W, height: H).fill()
// …在此按逻辑坐标绘制：NSBezierPath 画边框/圆，draw() 画文字…
NSGraphicsContext.restoreGraphicsState()
try! rep.representation(using: .png, properties: [:])!.write(to: URL(fileURLWithPath: "/tmp/out.png"))
```

**要点与坑**
- **坐标系**：AppKit 原点在左下。统一写个 `R(x,y,w,h)` 助手把"左上角坐标"翻过来，**千万别手算每个 y**。
- **中文字体**：`NSFont(name: "Songti SC", size:)`（宋体，适合证书/公文感）、`"PingFang SC"`（黑体，适合说明/图例）；都要 `?? 系统字体` 兜底。
- **字号/字距/行距**：`kern` 控字距（标题拉开好看）；行距用 `minimumLineHeight = maximumLineHeight`。
- **⚠️ 踩过的坑**：`minimumLineHeight` **大于容器 rect 高度会裁掉首行**——容器高度必须 ≥ 行高。绘图后**一定要 Read 出来肉眼验一次**（尤其首行、边缘）。
- 绘制顺序即图层顺序；半透明红圆 + 细字可模拟"盖章"。

---

## 四、二维码/条码 → 内容（Vision 解码，含微信带 logo 码）

**何时用**：
1. 要发布出去的二维码（公众号文章内嵌图、海报、封面）**最终验收"真的能扫"**——图看不清、被压在深色底、缩得太小、量化过头都可能在编辑器和预览里"看着正常"却扫不出来；
2. **改图后复验**：缩放/压缩/调色板量化/合成白底之后，解码载荷必须与原图**逐字符一致**；
3. 记录码的指向（微信入群链形如 `https://weixin.qq.com/g/xxxx`）。

脚本：`scripts/decode_barcode.swift`

```bash
swiftc -O -o decode_barcode scripts/decode_barcode.swift   # 编译一次反复用
./decode_barcode 待检图.png
# 输出：[路径] VNBarcodeSymbologyQR len=88
#        https://weixin.qq.com/g/AQYAAC...
```

**要点与坑（都是实测踩过的）**
- **⚠️ 不要用 OpenCV/pyzbar 验微信码**：`cv2.QRCodeDetector` 对**带中心 logo 的微信二维码**只能"检出"（`detect` 有结果），`detectAndDecode` **恒返回空串**；二值化、裁边再试同样失败。本机未装 opencv-contrib，也就没有 `cv2.wechat_qrcode_WeChatQRCode`。**Vision 能稳定解出**（与 iPhone 相机同源）。
- **⚠️ RGBA 图转 RGB 会黑底**：微信二维码截图常是 RGBA 且**四角透明**（圆角卡片的透明区 0.2% 左右）。`PIL` 的 `im.convert("RGB")` 会把透明像素变成**纯黑**，嵌进文章里就是一块黑边。正确做法是先合成白底：
  ```python
  bg = Image.new("RGB", im.size, (255,255,255)); bg.paste(im, mask=im.split()[3])
  ```
  这个坑**只靠文字检查发现不了**（标签配平、空壳检查全绿），必须**截图目检**或查四角灰度是否 =255。
- **验证口径**：改图后跑一次解码，与原图**载荷字符串完全相同**才算通过；只比"长度相同"不够。
- **灰度唯一值数**（mp-publish 里的旧口径）只能辅助判断"像不像二维码"，**不能替代解码**。
- 位置与尺度：码在图上再小也能解，但**发布前必须按最终展示尺寸复验**（展示 ≈280px 时，源图 ≥600px 宽足够）。

### 4.1 把「带标题/有效期文字的微信码截图」做成可用的纯码方图（实测配方）

微信导出的群码/客服码截图**自带标题与说明文字**（「群聊: xxx」「该二维码7天内(…前)有效」「扫二维码，添加我为朋友。」）。直接内嵌有两个问题：并排/缩小后小字糊成一团；**有效期日期一旦进正文，文章过期后即成为错误信息**。正确做法：

1. **紧贴码边裁掉全部原图留白**（标题、有效期、页脚一并消失）；
2. **静区自己合成**——白边是可以造出来的！把紧裁的码贴到纯白画布上补 **15% 宽度的白边**（≈6 个模块，规范红线 4 个模块），比依赖原图留白可靠得多；
3. 导出 600×600、16 色量化（典型 40–60KB），再解码复验。

**两个必踩的坑**：

- **⚠️ 判"静区有没有混入内容"必须用亮阈值（`luminance < 240`），不能用 `< 128`**：有效期/说明文字是**灰色**（实测灰度 ≈150–170），用暗阈值会判定"静区干净"，实际却把灰字裁进了图里。**这个缺陷所有文字级检查（标签配平、空壳扫描）都不会报**，只有像素目检才抓得到。
- **⚠️ `cv2.QRCodeDetector().detect()` 的四角可能内缩**（实测群码内缩约 70px），不能直接当二维码边界 → 从四角框**向外逐圈扩张**（下一圈环带内无深色像素即停）才是真实码边界。
- **⚠️ 截图常带一条贯穿全图的卡片边缘暗线**（实测 x≈36 处 2px 暗线），会让"逐行是否有深色"的统计完全失效 → 统计前先把边缘 x<50 / x>w-50 的列屏蔽。
- 合成静区后仍会剩**一圈 1px 灰度 246 的抗锯齿边**（缩放产生），属正常，不是文字混入。

---

## 关键坑位（跨场景）

- **浏览器截图不可靠**：ego-browser 的 `Page.captureScreenshot` 在本机反复 `CdpRequestTimeoutError`（页面重、视频组件多时必现）。**要么跳过截图，要么直接用本技能第三节用代码画图**。
- **扫描件判定**：`pypdf` 提取字符 < 50 → 扫描件 → 先走第一节渲染。
- **`pypdf` 不在托管 Python 里**：先建 venv 再装
  `~/.workbuddy/binaries/python/versions/<ver>/bin/python3 -m venv ~/.workbuddy/binaries/python/envs/default && ~/.workbuddy/binaries/python/envs/default/bin/pip install pypdf`
- 四个工具都建议 `swiftc -O` 编译一次反复用，别每次 `swift` 直跑（慢 2–3s）。
- **PIL 在托管解释器里没有**：图像处理用带 PIL 的隔离解释器 `~/.workbuddy/binaries/python/envs/default/bin/python3`（托管 `.../versions/<ver>/bin/python3` 只有标准库）。
