#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
build_editor.py — 把 geomap 的模板 + GeoJSON + d3 打包成一个"可视化编辑器"单文件 HTML。

用法:
  python3 build_editor.py --config examples/jiangsu_metro_onmap.json \
                          --output /path/to/图说-编辑器.html

产物是一个自包含 HTML：左侧表单改配置（标题/副标题/各市指标/颜色/偏移/排行卡/Logo），
右侧 iframe 实时预览；支持导出 PNG（foreignObject 栅格化）、下载 standalone HTML、
下载/复制 JSON、localStorage 自动保存、一键恢复默认。
"""
import argparse
import json
import os
import sys

SKILL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEMPLATE_DIR = os.path.join(SKILL_DIR, "templates")
SCRIPTS_DIR = os.path.join(SKILL_DIR, "scripts")
sys.path.insert(0, SCRIPTS_DIR)
from fetch_geojson import get_geojson  # noqa: E402

EDITOR_SHELL = r"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>图说编辑器 — __EDITOR_TITLE__</title>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  html, body { height: 100%; }
  body {
    font-family: -apple-system, BlinkMacSystemFont, "PingFang SC", "Microsoft YaHei", sans-serif;
    background: #EEF2F6; color: #1B2A38; font-size: 14px;
    display: flex; flex-direction: column; overflow: hidden;
  }
  header {
    background: #0C447C; color: #fff; padding: 10px 16px;
    display: flex; align-items: center; gap: 10px; flex: none; flex-wrap: wrap;
  }
  header h1 { font-size: 15px; font-weight: 600; margin-right: auto; }
  header h1 small { font-weight: 400; opacity: .75; margin-left: 8px; }
  header button {
    background: rgba(255,255,255,.14); color: #fff; border: 1px solid rgba(255,255,255,.35);
    border-radius: 6px; padding: 6px 12px; font-size: 13px; cursor: pointer;
  }
  header button:hover { background: rgba(255,255,255,.26); }
  header button.primary { background: #DDF32E; color: #0859A1; border-color: #DDF32E; font-weight: 600; }
  main { flex: 1; display: flex; min-height: 0; }
  aside {
    width: 400px; flex: none; background: #fff; border-right: 1px solid #D8E0E8;
    overflow-y: auto; padding: 14px 14px 40px;
  }
  #stageWrap { flex: 1; overflow: auto; background: #DDE4EB; position: relative; }
  #pvBox { transform-origin: top left; margin: 0 auto; }
  #pv { width: 1080px; height: 2160px; border: 0; display: block; background: #0972D3; }
  .sec { margin-bottom: 18px; }
  .sec > h2 {
    font-size: 13px; font-weight: 600; color: #0C447C; margin-bottom: 8px;
    padding-bottom: 6px; border-bottom: 1px solid #E3EAF0;
    display: flex; align-items: center; justify-content: space-between;
  }
  .sec > h2 button {
    font-size: 12px; padding: 2px 8px; border-radius: 5px; cursor: pointer;
    border: 1px solid #B9C7D4; background: #F3F7FA; color: #0C447C;
  }
  .fld { display: flex; align-items: center; gap: 8px; margin-bottom: 8px; }
  .fld label { width: 96px; flex: none; color: #5A6B7B; font-size: 12.5px; }
  .fld input[type=text], .fld input[type=number], .fld select {
    flex: 1; min-width: 0; border: 1px solid #C6D2DC; border-radius: 6px;
    padding: 5px 8px; font-size: 13px; font-family: inherit; background: #FBFDFE;
  }
  .fld input:focus, .fld select:focus { outline: 2px solid #B5D4F4; border-color: #378ADD; }
  .fld input[type=color] { width: 34px; height: 28px; padding: 0; border: 1px solid #C6D2DC; border-radius: 5px; background: #fff; }
  .rowcard {
    border: 1px solid #DCE4EC; border-radius: 8px; padding: 8px 8px 4px; margin-bottom: 8px; background: #FCFDFE;
  }
  .rowcard .top { display: flex; align-items: center; gap: 6px; margin-bottom: 6px; }
  .rowcard .top input[name=name] { flex: 1; font-weight: 600; }
  .rowcard .del {
    border: 0; background: #FCEBEB; color: #A32D2D; border-radius: 5px;
    width: 22px; height: 22px; cursor: pointer; font-size: 13px; line-height: 1;
  }
  .mini { display: flex; gap: 6px; margin-bottom: 6px; }
  .mini label { flex: none; width: 52px; color: #5A6B7B; font-size: 12px; align-self: center; }
  .mini input, .mini select { flex: 1; min-width: 0; border: 1px solid #C6D2DC; border-radius: 5px; padding: 4px 6px; font-size: 12.5px; background: #fff; }
  .hint { font-size: 12px; color: #7A8B9B; line-height: 1.6; margin: 4px 0 10px; }
  .ok { color: #0F6E56; }
</style>
</head>
<body>
<header>
  <h1>图说编辑器 <small id="cfgName"></small></h1>
  <button class="primary" id="btnPng">导出 PNG</button>
  <button id="btnHtml">下载 HTML</button>
  <button id="btnJson">下载 JSON</button>
  <button id="btnCopy">复制 JSON</button>
  <button id="btnReset">恢复默认</button>
  <span id="status" class="ok"></span>
</header>
<main>
  <aside id="form"></aside>
  <div id="stageWrap"><div id="pvBox"><iframe id="pv"></iframe></div></div>
</main>

<script id="tpl-src" type="text/template">__TPL__</script>
<script id="geo-src" type="application/json">__GEO__</script>
<script id="d3-src" type="text/plain">__D3__</script>
<script>
(function () {
  "use strict";
  var END = "%%ENDSCRIPT%%";
  var CLOSE = "<" + "/script>";

  var tplRaw = document.getElementById("tpl-src").textContent;
  var tpl = tplRaw.split(END).join(CLOSE);
  var d3src = document.getElementById("d3-src").textContent;
  var geoText = document.getElementById("geo-src").textContent;
  var DEFAULT = __CONFIG__;
  var LS_KEY = "geomap-editor:v2:" + (DEFAULT.__name || "config");

  var PALETTE = { red: "#E5251E", orange: "#F37021", green: "#6DB935",
                  yellow: "#FDB827", blue: "#0859A1", gray: "#FFFFFF" };
  function toHex(c) {
    if (!c) return "#E5251E";
    if (PALETTE[c]) return PALETTE[c];
    return c;
  }

  var cfg = load();
  function load() {
    try {
      var s = localStorage.getItem(LS_KEY);
      if (s) return JSON.parse(s);
    } catch (e) {}
    return JSON.parse(JSON.stringify(DEFAULT));
  }
  function persist() {
    try { localStorage.setItem(LS_KEY, JSON.stringify(cfg)); } catch (e) {}
  }

  var form = document.getElementById("form");
  var pv = document.getElementById("pv");
  var pvBox = document.getElementById("pvBox");
  var stageWrap = document.getElementById("stageWrap");
  var statusEl = document.getElementById("status");
  var timer = null;

  function el(tag, cls, text) {
    var e = document.createElement(tag);
    if (cls) e.className = cls;
    if (text != null) e.textContent = text;
    return e;
  }
  function fld(labelText, input) {
    var d = el("div", "fld");
    var l = el("label", null, labelText);
    d.appendChild(l); d.appendChild(input);
    return d;
  }
  function tInput(value, oninput) {
    var i = document.createElement("input");
    i.type = "text"; i.value = value == null ? "" : value;
    i.addEventListener("input", function () { oninput(i.value); });
    return i;
  }
  function nInput(value, oninput) {
    var i = document.createElement("input");
    i.type = "number"; i.value = value == null ? 0 : value;
    i.addEventListener("input", function () { oninput(i.value); });
    return i;
  }
  function cInput(value, oninput) {
    var wrap = el("div");
    wrap.style.cssText = "display:flex;gap:6px;flex:1;align-items:center;";
    var c = document.createElement("input");
    c.type = "color"; c.value = toHex(value);
    var t = tInput(value, oninput);
    t.style.flex = "1";
    c.addEventListener("input", function () { t.value = c.value; oninput(c.value); });
    t.addEventListener("input", function () {
      if (/^#[0-9a-fA-F]{6}$/.test(t.value)) { c.value = t.value; oninput(t.value); }
    });
    wrap.appendChild(c); wrap.appendChild(t);
    return wrap;
  }
  function selInput(value, opts, oninput) {
    var s = document.createElement("select");
    opts.forEach(function (o) {
      var op = document.createElement("option");
      op.value = o; op.textContent = o;
      if (o === value) op.selected = true;
      s.appendChild(op);
    });
    s.addEventListener("change", function () { oninput(s.value); });
    return s;
  }
  function touch() {
    clearTimeout(timer);
    timer = setTimeout(function () { persist(); updatePreview(); }, 250);
    statusEl.textContent = "已修改";
    setTimeout(function () { statusEl.textContent = ""; }, 1200);
  }

  /* ---------------- 表单 ---------------- */
  function renderForm() {
    form.innerHTML = "";

    var sec = el("div", "sec");
    sec.appendChild(el("h2", null, "基础文字"));
    [["pill_text", "顶部胶囊"], ["title", "主标题"], ["subtitle", "副标题"],
     ["source_note", "来源注脚"], ["rank_title", "排行卡标题"], ["rank_sub", "排行卡说明"],
     ["watermark_text", "防盗水印"], ["brand_stamp", "品牌印章"]].forEach(function (p) {
      var i = tInput(cfg[p[0]] || "", function (v) { cfg[p[0]] = v; touch(); });
      i.dataset.k = p[0];
      sec.appendChild(fld(p[1], i));
    });
    var lab = el("label", null, "标记模式");
    var s = selInput(cfg.label_mode || "onmap", ["onmap", "chip", "badge"], function (v) {
      cfg.label_mode = v; touch(); renderForm();
    });
    var d = el("div", "fld"); d.appendChild(lab); d.appendChild(s);
    sec.appendChild(d);
    sec.appendChild(el("p", "hint", "onmap＝文字标在色块内（信息最全）；chip＝编号圆点+排行卡对照；badge＝徽章+引线。"));
    form.appendChild(sec);

    form.appendChild(listSec("highlights", "地图高亮城市", [
      { k: "name", label: "城市", type: "text" },
      { k: "metric", label: "指标", type: "text" },
      { k: "color", label: "颜色", type: "color" },
      { k: "offset0", label: "偏移X", type: "number" },
      { k: "offset1", label: "偏移Y", type: "number" }
    ], function () {
      return { name: "", metric: "", color: "green", offset: [0, 0] };
    }, "城市名必须与省界 GeoJSON 一致（如「南京市」）。offset 是标注中心相对城市中心的像素偏移。"));

    form.appendChild(listSec("ranking", "排行卡", [
      { k: "name", label: "城市", type: "text" },
      { k: "value", label: "数值", type: "number" },
      { k: "value_text", label: "显示", type: "text" },
      { k: "color", label: "颜色", type: "color" },
      { k: "tag", label: "标签", type: "text" }
    ], function () {
      return { name: "", value: 0, value_text: "0 km", color: "green", tag: "" };
    }, "排序就是显示顺序；tag 用于标注口径（如「有轨电车」）。"));

    form.appendChild(listSec("logos", "底部 Logo 墙", [
      { k: "name", label: "名称", type: "text" },
      { k: "sub", label: "英文小标", type: "text" }
    ], function () { return { name: "", sub: "" }; }, ""));
  }

  function listSec(key, title, fields, blank, hint) {
    var sec = el("div", "sec");
    var h = el("h2", null, title);
    var add = el("button", null, "+ 添加");
    add.addEventListener("click", function () {
      cfg[key].push(blank()); touch(); renderForm();
    });
    h.appendChild(add);
    sec.appendChild(h);
    if (hint) sec.appendChild(el("p", "hint", hint));

    (cfg[key] || []).forEach(function (item, idx) {
      var card = el("div", "rowcard");
      var top = el("div", "top");
      fields.forEach(function (f) {
        if (f.k !== "name") return;
        var i = tInput(item[f.k] || "", function (v) { item[f.k] = v; touch(); });
        i.name = "name";
        top.appendChild(i);
      });
      var del = el("button", "del", "×");
      del.title = "删除";
      del.addEventListener("click", function () {
        cfg[key].splice(idx, 1); touch(); renderForm();
      });
      top.appendChild(del);
      card.appendChild(top);

      fields.forEach(function (f) {
        if (f.k === "name") return;
        var mini = el("div", "mini");
        mini.appendChild(el("label", null, f.label));
        if (f.type === "color") {
          mini.appendChild(cInput(item[f.k], function (v) { item[f.k] = v; touch(); }));
        } else if (f.k === "offset0") {
          var i0 = nInput((item.offset || [])[0], function (v) {
            item.offset = item.offset || [0, 0]; item.offset[0] = Number(v) || 0; touch();
          });
          mini.appendChild(i0);
        } else if (f.k === "offset1") {
          var i1 = nInput((item.offset || [])[1], function (v) {
            item.offset = item.offset || [0, 0]; item.offset[1] = Number(v) || 0; touch();
          });
          mini.appendChild(i1);
        } else if (f.type === "number") {
          mini.appendChild(nInput(item[f.k], function (v) { item[f.k] = Number(v) || 0; touch(); }));
        } else {
          mini.appendChild(tInput(item[f.k] || "", function (v) { item[f.k] = v; touch(); }));
        }
        card.appendChild(mini);
      });
      sec.appendChild(card);
    });
    return sec;
  }

  /* ---------------- 渲染 ---------------- */
  function esc(s) {
    return String(s == null ? "" : s)
      .split("&").join("&amp;").split("<").join("&lt;").split(">").join("&gt;");
  }
  function logosHtml(list) {
    return (list || []).map(function (l) {
      return '<div class="logo-item"><div class="logo-name">' + esc(l.name) + "</div>" +
             (l.sub ? '<div class="logo-sub">' + esc(l.sub) + "</div>" : "") + "</div>";
    }).join("");
  }
  function buildPoster(c) {
    var h = tpl;
    var rep = {
      "__TITLE__": (c.pill_text || c.province) + " - " + (c.title || ""),
      "__BG_GRADIENT__": c.bg_gradient || "linear-gradient(180deg, #0972D3 0%, #0866C2 40%, #0653A0 100%)",
      "__PILL_BG__": c.pill_bg || "#DDF32E",
      "__PILL_COLOR__": c.pill_color || "#0859A1",
      "__PILL_TEXT__": c.pill_text || c.province,
      "__MAIN_TITLE__": c.title || "地图图说",
      "__SUB_TITLE__": c.subtitle || "",
      "__WM_COLOR__": c.watermark_color || "rgba(8, 89, 161, 0.22)",
      "__BRAND_STAMP__": c.brand_stamp || "满爸爱生活",
      "__LOGOS_HTML__": logosHtml(c.logos),
      "__CONFIG_JSON__": JSON.stringify({
        province: c.province, pill_text: c.pill_text, pill_bg: c.pill_bg, pill_color: c.pill_color,
        title: c.title, subtitle: c.subtitle, label_mode: c.label_mode,
        source_note: c.source_note, rank_title: c.rank_title, rank_sub: c.rank_sub,
        watermark_text: c.watermark_text, brand_stamp: c.brand_stamp,
        highlights: c.highlights, ranking: c.ranking, logos: c.logos
      }),
      "__GEO_JSON__": geoText
    };
    Object.keys(rep).forEach(function (k) { h = h.split(k).join(rep[k]); });
    var d3tag = "<scr" + "ipt src=\"d3.v7.min.js\">" + CLOSE;
    if (h.indexOf(d3tag) < 0) throw new Error("模板中未找到 d3 引用标签");
    // 必须用 split/join：String.replace 会把替换串里的 $& / $` / $' 当特殊模式展开，
    // 而 d3 源码里恰好含 "$&"，会把被替换的标签原文插进代码中间，截断整个库。
    h = h.split(d3tag).join("<scr" + "ipt>" + d3src + CLOSE);
    return h;
  }
  function updatePreview() { pv.srcdoc = buildPoster(cfg); }

  /* ---------------- 导出 ---------------- */
  function saveBlob(blob, name) {
    var a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = name;
    a.click();
    setTimeout(function () { URL.revokeObjectURL(a.href); }, 4000);
  }
  function baseName() {
    var t = (cfg.province || "poster") + "-" + (cfg.title || "图说");
    return t.replace(/\s+/g, "");
  }
  function exportPNG() {
    var doc = pv.contentDocument;
    if (!doc || !doc.documentElement) { alert("预览尚未就绪"); return; }
    var xml = new XMLSerializer().serializeToString(doc.documentElement);
    var svgStr = '<svg xmlns="http://www.w3.org/2000/svg" width="1080" height="2160">' +
      '<foreignObject x="0" y="0" width="1080" height="2160">' + xml + "</foreignObject></svg>";
    var img = new Image();
    img.onload = function () {
      var c = document.createElement("canvas");
      c.width = 2160; c.height = 4320;
      var ctx = c.getContext("2d");
      ctx.scale(2, 2);
      ctx.fillStyle = "#0972D3"; ctx.fillRect(0, 0, 1080, 2160);
      ctx.drawImage(img, 0, 0, 1080, 2160);
      c.toBlob(function (b) {
        if (!b) { alert("导出失败，请改用技能命令渲染正式版"); return; }
        saveBlob(b, baseName() + "-2x.png");
      }, "image/png");
    };
    img.onerror = function () { alert("导出失败：可改用「下载 HTML」后自行截图，或用技能命令渲染"); };
    img.src = "data:image/svg+xml;charset=utf-8," + encodeURIComponent(svgStr);
  }

  document.getElementById("btnPng").addEventListener("click", exportPNG);
  document.getElementById("btnHtml").addEventListener("click", function () {
    saveBlob(new Blob([buildPoster(cfg)], { type: "text/html;charset=utf-8" }), baseName() + "-源文件.html");
  });
  document.getElementById("btnJson").addEventListener("click", function () {
    var c = JSON.parse(JSON.stringify(cfg)); delete c.__name;
    saveBlob(new Blob([JSON.stringify(c, null, 2)], { type: "application/json" }), baseName() + "-配置.json");
  });
  document.getElementById("btnCopy").addEventListener("click", function () {
    var c = JSON.parse(JSON.stringify(cfg)); delete c.__name;
    navigator.clipboard.writeText(JSON.stringify(c, null, 2)).then(function () {
      statusEl.textContent = "JSON 已复制";
      setTimeout(function () { statusEl.textContent = ""; }, 1500);
    });
  });
  document.getElementById("btnReset").addEventListener("click", function () {
    if (!confirm("放弃当前修改，恢复为默认配置？")) return;
    localStorage.removeItem(LS_KEY);
    cfg = JSON.parse(JSON.stringify(DEFAULT));
    renderForm(); updatePreview();
  });

  function fit() {
    var w = stageWrap.clientWidth - 24;
    var s = Math.min(w / 1080, 1);
    pvBox.style.transform = "scale(" + s + ")";
    pvBox.style.width = 1080 * s + "px";
    pvBox.style.height = 2160 * s + "px";
    pvBox.style.margin = "12px";
  }
  window.addEventListener("resize", fit);

  document.getElementById("cfgName").textContent = DEFAULT.__name || "";
  renderForm();
  updatePreview();
  fit();
})();
</script>
</body>
</html>
"""


def build_editor(config_path: str, output_path: str) -> str:
    with open(config_path, "r", encoding="utf-8") as f:
        config = json.load(f)
    config["__name"] = os.path.splitext(os.path.basename(config_path))[0]

    with open(os.path.join(TEMPLATE_DIR, "poster_template.html"), "r", encoding="utf-8") as f:
        tpl = f.read()
    # 模板内含 </script>，塞进 text/template 容器前先替换成安全标记，运行时再还原
    tpl = tpl.replace("</script", "%%ENDSCRIPT%%")
    assert "%%ENDSCRIPT%%" in tpl

    with open(os.path.join(TEMPLATE_DIR, "d3.v7.min.js"), "r", encoding="utf-8") as f:
        d3 = f.read()
    assert "</script" not in d3 and "</scr" not in d3.lower().replace(" ", "")

    geo_path = get_geojson(config["province"])
    with open(geo_path, "r", encoding="utf-8") as f:
        geo = f.read()
    assert "</script" not in geo

    html = EDITOR_SHELL
    html = html.replace("__EDITOR_TITLE__", f'{config.get("province","")}·{config.get("title","")}')
    html = html.replace("__TPL__", tpl)
    html = html.replace("__GEO__", geo)
    html = html.replace("__D3__", d3)
    html = html.replace("__CONFIG__", json.dumps(config, ensure_ascii=False))

    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)
    return output_path


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="把 geomap 配置打包成可视化编辑器单文件 HTML")
    ap.add_argument("--config", "-c", required=True, help="配置文件路径 (JSON)")
    ap.add_argument("--output", "-o", required=True, help="输出编辑器 HTML 路径")
    a = ap.parse_args()
    out = build_editor(a.config, a.output)
    print(f"编辑器已生成: {out} ({os.path.getsize(out)/1024:.0f} KB)")
