import Foundation
import Vision
import AppKit

// 用法: swift vision_barcode.swift <图片路径> [--count]
// 输出: 每个码一行 "VAL=<payload> CONF=<置信度>"；无码输出 NO_BARCODE
// 适用: cv2.QRCodeDetector 解不出的彩色/艺术/低对比度二维码（macOS Vision 识别率更高）
// 2026-11-10 收编自 r36 内蒙古能源集团篇实测脚本（cv2 四通道×四尺度全空，Vision 一次 1.0）

let args = CommandLine.arguments
guard args.count > 1 else {
    print("usage: swift vision_barcode.swift <img>")
    exit(1)
}
let path = args[1]
let url = URL(fileURLWithPath: path)
guard let img = NSImage(contentsOf: url),
      let cg = img.cgImage(forProposedRect: nil, context: nil, hints: nil) else {
    print("ERR load \(path)")
    exit(1)
}

let req = VNDetectBarcodesRequest()
req.symbologies = [.qr]
let handler = VNImageRequestHandler(cgImage: cg, options: [:])

do {
    try handler.perform([req])
    let results = req.results ?? []
    if results.isEmpty {
        print("NO_BARCODE")
        exit(0)
    }
    for p in results {
        let val = p.payloadStringValue ?? "nil"
        print("VAL=\(val) CONF=\(String(format: "%.3f", p.confidence))")
    }
} catch {
    print("ERR \(error.localizedDescription)")
    exit(1)
}
