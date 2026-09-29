#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""xlsx 动表前 30 秒机检：zip 完整性 / openpyxl 可读性 / dimension 一致性 / 空 rgb / 行列快照。
用法: python3 xlsx_preflight.py <file.xlsx> [more.xlsx ...]
退出码: 0=全过, 1=有问题(见输出)。"""
import sys
import zipfile


def preflight(path):
    print("=" * 72)
    print("文件:", path)
    ok = True

    # ① zip 完整性
    try:
        z = zipfile.ZipFile(path)
        bad = z.testzip()
        names = z.namelist()
        if bad:
            print("  [FAIL] zip 损坏条目:", bad); ok = False
        else:
            print("  [ok] zip 完整, %d 个条目" % len(names))
        # ④ 空 rgb 扫描（腾讯文档保存的高发缺陷）
        empty_rgb = []
        for n in names:
            if n.endswith(".xml"):
                data = z.read(n)
                if b'rgb=""' in data:
                    empty_rgb.append(n)
        if empty_rgb:
            print("  [FAIL] 空颜色 rgb=\"\" 出现在: %s -> openpyxl 会崩, 先修补再干活" % empty_rgb); ok = False
        else:
            print("  [ok] 无空颜色 rgb")
        # 应用身份
        if "docProps/app.xml" in names:
            app = z.read("docProps/app.xml").decode("utf-8", "ignore")
            if "Tencent" in app or "tencent" in app:
                print("  [info] 保存器: Tencent office（空 rgb / flush 高发，提高警惕）")
        z.close()
    except Exception as e:
        print("  [FAIL] zip 读取异常: %r" % e); return False

    # ② openpyxl 可读性 + ③ dimension + ⑤ 行数快照
    try:
        import openpyxl
        wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
        print("  [ok] openpyxl 可读, sheets: %s" % wb.sheetnames)
        for name in wb.sheetnames:
            ws = wb[name]
            rows = 0
            maxc = 0
            for r in ws.iter_rows(values_only=True):
                rows += 1
                maxc = max(maxc, len(r))
            dim = ws.calculate_dimension() if hasattr(ws, "calculate_dimension") else "?"
            print("    %-22s 非空行=%-5d 实际最大列=%-3d dimension=%s" % (name, rows, maxc, dim))
        wb.close()
    except Exception as e:
        print("  [FAIL] openpyxl 打不开: %r" % e)
        print("         -> 转 raw XML 读取（xlsx_rawxml.py），或先修补空 rgb")
        ok = False
    print("  结论:", "PASS" if ok else "FAIL")
    return ok


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__); sys.exit(2)
    allok = all(preflight(p) for p in sys.argv[1:])
    sys.exit(0 if allok else 1)
