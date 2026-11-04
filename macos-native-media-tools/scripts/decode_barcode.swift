// decode_barcode.swift —— 用 Apple Vision 解码二维码/条码（本机原生，不联网）
//
// 用法（推荐先编译，反复调用快）：
//   swiftc -O -o decode_barcode decode_barcode.swift
//   ./decode_barcode 图1.png [图2.png ...]
// 或直接解释执行（慢约 2-3s，适合一次性）：
//   swift decode_barcode.swift 图.png
//
// 为什么不用 OpenCV / pyzbar：
//   cv2.QRCodeDetector 只能"检出"带 logo 的微信二维码，detectAndDecode 返回空；
//   本机无 opencv-contrib，故无 cv2.wechat_qrcode_WeChatQRCode 可用。
//   Vision 的 VNDetectBarcodesRequest 与 iPhone 相机同源，微信带 logo 群码可稳定解出。
//
// 典型用途：
//   1) 校验要嵌进公众号文章/海报的二维码"真的能扫"（成品的最终验收）；
//   2) 改图（缩放/量化/合成白底）后复验载荷与原图逐字符一致；
//   3) 记录二维码指向（微信入群链形如 https://weixin.qq.com/g/xxxx）。

import Foundation
import Vision
import AppKit

let paths = Array(CommandLine.arguments.dropFirst())
guard !paths.isEmpty else {
    print("usage: decode_barcode <image> [image...]"); exit(1)
}

var anyFail = false
for path in paths {
    guard let img = NSImage(contentsOfFile: path),
          let cg = img.cgImage(forProposedRect: nil, context: nil, hints: nil) else {
        print("[\(path)] LOAD_FAILED"); anyFail = true; continue
    }
    let req = VNDetectBarcodesRequest()
    // 默认已覆盖 QR/EAN/Code128 等；只想要二维码就解开下一行
    // req.symbologies = [.qr]
    let handler = VNImageRequestHandler(cgImage: cg, options: [:])
    do { try handler.perform([req]) } catch {
        print("[\(path)] PERFORM_ERROR \(error)"); anyFail = true; continue
    }
    let results = req.results ?? []
    if results.isEmpty { print("[\(path)] 未检出条码"); anyFail = true; continue }
    for r in results {
        let p = r.payloadStringValue ?? "(nil)"
        print("[\(path)] \(r.symbology.rawValue) len=\(p.count)")
        print("   \(p)")
    }
}
exit(anyFail ? 3 : 0)
