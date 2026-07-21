// Episteme.app icon generator (E179).
//
// The icns is a REPRODUCIBLE artifact: this script draws the mark with
// CoreGraphics (no design binary without a source), writes the full iconset,
// and runs iconutil. Regenerate with:
//
//   swift app/icon/make_icns.swift app/icon
//
// Mark: the Gate — two accent brackets facing each other with the operator
// (a filled dot) between them, on the console's dark panel color. Geometry
// is proportional to size, with stroke widths tuned so the gate survives
// 16 px.

import AppKit
import CoreGraphics
import Foundation

let bg = CGColor(red: 0x0B / 255.0, green: 0x0E / 255.0, blue: 0x14 / 255.0, alpha: 1)
let edge = CGColor(red: 0x1E / 255.0, green: 0x25 / 255.0, blue: 0x30 / 255.0, alpha: 1)
let accent = CGColor(red: 0x5E / 255.0, green: 0xC2 / 255.0, blue: 0xA6 / 255.0, alpha: 1)

func drawIcon(size: Int) -> CGImage {
    let s = CGFloat(size)
    let ctx = CGContext(
        data: nil, width: size, height: size, bitsPerComponent: 8, bytesPerRow: 0,
        space: CGColorSpace(name: CGColorSpace.sRGB)!,
        bitmapInfo: CGImageAlphaInfo.premultipliedLast.rawValue
    )!

    // Background: rounded square (macOS icon-grid inset), subtle edge.
    let inset = s * 0.06
    let rect = CGRect(x: inset, y: inset, width: s - 2 * inset, height: s - 2 * inset)
    let radius = rect.width * 0.225
    let path = CGPath(roundedRect: rect, cornerWidth: radius, cornerHeight: radius, transform: nil)
    ctx.addPath(path)
    ctx.setFillColor(bg)
    ctx.fillPath()
    if size >= 64 {
        ctx.addPath(path)
        ctx.setStrokeColor(edge)
        ctx.setLineWidth(max(1, s * 0.008))
        ctx.strokePath()
    }

    // The Gate: two brackets [ ] + the operator dot between them.
    let stroke = max(1.5, s * 0.075)
    let armLen = s * 0.14
    let bracketH = s * 0.46
    let leftX = s * 0.30
    let rightX = s * 0.70
    let midY = s * 0.5

    ctx.setStrokeColor(accent)
    ctx.setLineWidth(stroke)
    ctx.setLineCap(.round)
    ctx.setLineJoin(.round)

    // Left bracket [
    ctx.beginPath()
    ctx.move(to: CGPoint(x: leftX + armLen, y: midY + bracketH / 2))
    ctx.addLine(to: CGPoint(x: leftX, y: midY + bracketH / 2))
    ctx.addLine(to: CGPoint(x: leftX, y: midY - bracketH / 2))
    ctx.addLine(to: CGPoint(x: leftX + armLen, y: midY - bracketH / 2))
    ctx.strokePath()

    // Right bracket ]
    ctx.beginPath()
    ctx.move(to: CGPoint(x: rightX - armLen, y: midY + bracketH / 2))
    ctx.addLine(to: CGPoint(x: rightX, y: midY + bracketH / 2))
    ctx.addLine(to: CGPoint(x: rightX, y: midY - bracketH / 2))
    ctx.addLine(to: CGPoint(x: rightX - armLen, y: midY - bracketH / 2))
    ctx.strokePath()

    // The operator: a filled dot at the gate's center.
    let dotR = s * 0.065
    ctx.setFillColor(accent)
    ctx.fillEllipse(in: CGRect(x: s / 2 - dotR, y: midY - dotR, width: dotR * 2, height: dotR * 2))

    return ctx.makeImage()!
}

func writePNG(_ image: CGImage, to url: URL) {
    let rep = NSBitmapImageRep(cgImage: image)
    let data = rep.representation(using: .png, properties: [:])!
    try! data.write(to: url)
}

let outDir = CommandLine.arguments.count > 1 ? CommandLine.arguments[1] : "app/icon"
let iconset = URL(fileURLWithPath: outDir).appendingPathComponent("episteme.iconset")
try? FileManager.default.createDirectory(at: iconset, withIntermediateDirectories: true)

// (filename base size, pixel size) pairs iconutil expects.
let entries: [(String, Int)] = [
    ("icon_16x16", 16), ("icon_16x16@2x", 32),
    ("icon_32x32", 32), ("icon_32x32@2x", 64),
    ("icon_128x128", 128), ("icon_128x128@2x", 256),
    ("icon_256x256", 256), ("icon_256x256@2x", 512),
    ("icon_512x512", 512), ("icon_512x512@2x", 1024),
]
for (name, px) in entries {
    writePNG(drawIcon(size: px), to: iconset.appendingPathComponent("\(name).png"))
}

let task = Process()
task.executableURL = URL(fileURLWithPath: "/usr/bin/iconutil")
task.arguments = [
    "-c", "icns", iconset.path,
    "-o", URL(fileURLWithPath: outDir).appendingPathComponent("episteme.icns").path,
]
try! task.run()
task.waitUntilExit()
print("wrote \(outDir)/episteme.icns (exit \(task.terminationStatus))")
