#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Counter 全行多重集 diff 归因：两个（或多个）时点的 xlsx 逐行比对，按名称分四类：
  计划清单内 / 同名改写（改行）/ 纯删 / 纯增。必须全部可解释，终验才算过。
用法:
  python3 xlsx_counterdiff.py <sheet名> <基准.xlsx> <当前.xlsx> [--list 计划清单.txt] [--cols 17] [--raw]
  --raw: 基准文件 openpyxl 读不了时，用 raw XML 读取（空 rgb 等）。
清单文件：每行一个名称（如迁移名单），用于把 removed 分成"计划内/计划外"。
"""
import sys
from collections import Counter

W_DEFAULT = 17


def norm(v):
    if v is None:
        return None
    if isinstance(v, str):
        s = v.strip()
        return s if s else None
    return v


def load_openpyxl(path, sheet, width):
    import openpyxl
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    ws = wb[sheet]
    rows = []
    for r in ws.iter_rows(values_only=True):
        vals = [norm(x) for x in r]
        vals += [None] * (width - len(vals))
        if any(v is not None for v in vals):
            rows.append(tuple(vals[:width]))
    wb.close()
    return rows


def load_raw(path, sheet, width):
    sys.path.insert(0, __file__.rsplit("/", 1)[0])
    from xlsx_rawxml import read_rows
    rows = []
    for r in read_rows(path, sheet):
        vals = [norm(x) for x in r]
        vals += [None] * (width - len(vals))
        if any(v is not None for v in vals):
            rows.append(tuple(vals[:width]))
    return rows


def main():
    argv = sys.argv[1:]
    args, opts, raw = [], {}, "--raw" in argv
    i = 0
    while i < len(argv):
        a = argv[i]
        if a == "--raw":
            i += 1
        elif a in ("--list", "--cols") and i + 1 < len(argv):
            opts[a] = argv[i + 1]
            i += 2
        else:
            args.append(a)
            i += 1
    if len(args) < 3:
        print(__doc__); sys.exit(2)
    sheet, base_p, cur_p = args[0], args[1], args[2]
    width = int(opts.get("--cols", W_DEFAULT))
    listfile = opts.get("--list")

    loader = load_raw if raw else load_openpyxl
    base = loader(base_p, sheet, width)
    cur = loader(cur_p, sheet, width)
    hdr = base[0] if base and base[0][0] == "名称" else None
    b = base[1:] if hdr else base
    c = cur[1:] if (cur and cur[0][0] == "名称") else cur
    print("基准 %s：数据行=%d" % (base_p.split("/")[-1], len(b)))
    print("当前 %s：数据行=%d" % (cur_p.split("/")[-1], len(c)))

    b_cnt, c_cnt = Counter(b), Counter(c)
    removed = list((b_cnt - c_cnt).elements())
    added = list((c_cnt - b_cnt).elements())
    rn = Counter(r[0] for r in removed)
    an = Counter(r[0] for r in added)
    nset = set()
    if listfile:
        with open(listfile, encoding="utf-8") as f:
            nset = set(l.strip() for l in f if l.strip())

    in_plan = sorted(k for k in rn if k in nset)
    replaced = sorted(k for k in rn if k in an and k not in nset)
    pure_rem = sorted(k for k in rn if k not in an and k not in nset)
    pure_add = sorted(k for k in an if k not in rn)

    print("\n== 四分类归因 ==")
    print("计划清单内迁出/删除: %d 行" % sum(rn[k] for k in in_plan))
    print("同名改写(改行): %d 行" % len(replaced))
    print("纯删(计划外): %d 行 -> %s" % (len(pure_rem), pure_rem[:20]))
    print("纯增(计划外): %d 行 -> %s" % (len(pure_add), pure_add[:20]))
    if replaced:
        b_by, c_by = {}, {}
        for r in b:
            b_by.setdefault(r[0], []).append(r)
        for r in c:
            c_by.setdefault(r[0], []).append(r)
        print("\n== 同名改写列级明细 ==")
        for name in replaced:
            old, new = b_by[name][0], c_by[name][0]
            ch = [(i, old[i], new[i]) for i in range(len(old)) if old[i] != new[i]]
            desc = "; ".join("col%d: %s -> %s" % (i, o, n) for i, o, n in ch)
            print("  %s: %s" % (name, desc[:300]))


if __name__ == "__main__":
    main()
