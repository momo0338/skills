#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""raw XML 读取器：openpyxl 读不了（空 rgb 等）或需要绕开 dimension 截断时，
直接解析 sheet XML 取全部行 / A 列行序。自动兼容 sharedStrings(t="s") 与 inlineStr(t="inlineStr")。
用法:
  python3 xlsx_rawxml.py rows  <file.xlsx> <sheet名> [最多列数]   # 打印全部行（\t 分隔）
  python3 xlsx_rawxml.py order <file.xlsx> <sheet名> [另一个.xlsx ...]  # 多文件 A 列行序比对
"""
import re
import sys
import zipfile
from xml.etree import ElementTree as ET

NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
RNS = "{http://schemas.openxmlformats.org/package/2006/relationships}"
DNS = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"
COL_RE = re.compile(r"([A-Z]+)")


def col_idx(col):
    n = 0
    for ch in col:
        n = n * 26 + (ord(ch) - 64)
    return n - 1


def sheet_path(z, sheetname):
    """用 ElementTree 解析 workbook.xml + rels——属性顺序不固定，禁正则。"""
    sst = []
    if "xl/sharedStrings.xml" in z.namelist():
        root = ET.fromstring(z.read("xl/sharedStrings.xml").decode("utf-8"))
        for si in root.iter(NS + "si"):
            sst.append("".join(t.text or "" for t in si.iter(NS + "t")))
    wb = ET.fromstring(z.read("xl/workbook.xml").decode("utf-8"))
    rels = ET.fromstring(z.read("xl/_rels/workbook.xml.rels").decode("utf-8"))
    relmap = {r.get("Id"): r.get("Target") for r in rels.iter(RNS + "Relationship")}
    target = None
    for sh in wb.iter(NS + "sheet"):
        if sh.get("name") == sheetname:
            t = relmap[sh.get(DNS + "id")].lstrip("/")
            target = t if t.startswith("xl/") else "xl/" + t   # Target 可能已含 xl/ 前缀
    if target is None:
        raise KeyError("sheet 不存在: %s（可用: %s）" % (
            sheetname, [s.get("name") for s in wb.iter(NS + "sheet")]))
    return sst, target


def read_rows(path, sheetname, maxc=None):
    z = zipfile.ZipFile(path)
    sst, target = sheet_path(z, sheetname)
    root = ET.fromstring(z.read(target).decode("utf-8"))
    z.close()
    rows = []
    for row in root.iter(NS + "row"):
        cells = {}
        for c in row.iter(NS + "c"):
            ref = c.get("r", "")
            m = COL_RE.match(ref)
            if not m:
                continue
            ci = col_idx(m.group(1))
            if maxc and ci >= maxc:
                continue
            t = c.get("t")
            v = c.find(NS + "v")
            if t == "s" and v is not None:
                val = sst[int(v.text)]
            elif t == "inlineStr":
                isv = c.find(NS + "is")
                val = "".join(x.text or "" for x in isv.iter(NS + "t")) if isv is not None else None
            elif v is not None:
                val = v.text
                if t is None:
                    try:
                        val = int(v.text)
                    except ValueError:
                        try:
                            val = float(v.text)
                        except ValueError:
                            pass
            else:
                val = None
            if val is not None and val != "":
                cells[ci] = val
        if cells:
            width = max(cells) + 1
            if maxc:
                width = min(width, maxc)
            rows.append([cells.get(i) for i in range(width)])
    return rows


def main():
    if len(sys.argv) < 4:
        print(__doc__); sys.exit(2)
    mode = sys.argv[1]
    if mode == "rows":
        path, sheet = sys.argv[2], sys.argv[3]
        maxc = int(sys.argv[4]) if len(sys.argv) > 4 else None
        for r in read_rows(path, sheet, maxc):
            print("\t".join("" if v is None else str(v) for v in r))
    elif mode == "order":
        sheet = sys.argv[2]
        paths = sys.argv[3:]
        orders = {}
        for p in paths:
            rows = read_rows(p, sheet, maxc=1)
            orders[p] = [r[0] for r in rows if r and r[0]]
            print("%-60s 行数=%d 前5=%s" % (p.split("/")[-1], len(orders[p]), orders[p][:5]))
        if len(orders) > 1:
            base = list(orders.values())[0]
            for p, o in orders.items():
                print("%-60s 与首个文件行序一致: %s" % (p.split("/")[-1], o == base))
    else:
        print("未知 mode:", mode); sys.exit(2)


if __name__ == "__main__":
    main()
