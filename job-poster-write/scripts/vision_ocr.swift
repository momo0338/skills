import Foundation
import Vision
import AppKit

// 用法: swift ocr.swift <image> [--json]
// 输出: 每行文本 + 归一化 bbox(左,上,右,下) + 置信度

let args = CommandLine.arguments
guard args.count >= 2 else {
    FileHandle.standardError.write("usage: ocr.swift <image> [--json]\n".data(using: .utf8)!)
    exit(2)
}
let path = args[1]
let asJSON = args.contains("--json")

guard let img = NSImage(contentsOfFile: path),
      let tiff = img.tiffRepresentation,
      let rep = NSBitmapImageRep(data: tiff),
      let cg = rep.cgImage else {
    FileHandle.standardError.write("cannot load image: \(path)\n".data(using: .utf8)!)
    exit(1)
}

let req = VNRecognizeTextRequest()
req.recognitionLevel = .accurate
req.recognitionLanguages = ["zh-Hans", "en-US"]
req.usesLanguageCorrection = true

let handler = VNImageRequestHandler(cgImage: cg, options: [:])
let t0 = Date()
do {
    try handler.perform([req])
} catch {
    FileHandle.standardError.write("ocr failed: \(error)\n".data(using: .utf8)!)
    exit(1)
}
let cost = Date().timeIntervalSince(t0)

var rows: [[String: Any]] = []
for obs in (req.results ?? []) {
    guard let cand = obs.topCandidates(1).first else { continue }
    let bb = obs.boundingBox   // 归一化，原点左下
    rows.append([
        "text": cand.string,
        "conf": Double(round(cand.confidence * 1000) / 1000),
        "x0": Double(round(bb.minX * 10000) / 10000),
        "y0": Double(round(bb.minY * 10000) / 10000),
        "x1": Double(round(bb.maxX * 10000) / 10000),
        "y1": Double(round(bb.maxY * 10000) / 10000),
    ])
}

// 按阅读顺序排序：上→下（y1 降序），左→右
rows.sort { a, b in
    let ay = a["y1"] as! Double, by = b["y1"] as! Double
    if abs(ay - by) > 0.004 { return ay > by }
    return (a["x0"] as! Double) < (b["x0"] as! Double)
}

let out: [String: Any] = ["file": path, "cost_sec": Double(round(cost * 100) / 100), "count": rows.count, "lines": rows]
if asJSON {
    let d = try! JSONSerialization.data(withJSONObject: out, options: [.prettyPrinted, .sortedKeys])
    print(String(data: d, encoding: .utf8)!)
} else {
    print("OCR \(rows.count) 行 / \(String(format: "%.2f", cost))s ← \(path)")
    for r in rows {
        print(String(format: "[y%.3f] %@", r["y0"] as! Double, r["text"] as! String))
    }
}
