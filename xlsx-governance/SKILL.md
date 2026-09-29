---
name: xlsx-governance
description: >-
  本地 xlsx 数据治理与安全迁移 SOP（2026-09-29 实战沉淀）。适用于：总表/名册类 xlsx 的删行治理、sheet 拆分迁移、
  存档归档、变更归因 diff、以及腾讯文档/Tencent office 保存过的 xlsx 出现的各种疑难（openpyxl 崩溃、
  列被静默截断、编辑器并发 flush 覆盖）。核心纪律：动表前 /tmp 多时点备份、每个结论机检不采信口头报告、
  Counter 全行多重集 diff 四分类归因、zip 外科手术修复（不动无关字节）、用户并发编辑只披露不回滚、
  交付文档全部数字从 live 实拉生成（禁手抄）。
keywords:
  - xlsx
  - 表格治理
  - sheet 迁移
  - 数据归因
  - openpyxl
  - 空 rgb
  - dimension 截断
  - 编辑器 flush
  - 备份链
  - 总表
---

# xlsx-governance — 本地 xlsx 数据治理与安全迁移 SOP

> 一句话：**xlsx 治理的耗时大头不在写，在「读不动 → 归因不清 → 修复返工」。本 SOP 把三段全部前置排雷。**
> 唯一解释器：venv python（`/Users/zhugx/.workbuddy/binaries/python/envs/default/bin/python3`，系统 python 无 openpyxl）。

## 0. 触发场景

- 删行/合并/去重/拆分 sheet/迁入新 sheet/存档归档类治理
- 两个时点（或多个时点）的 xlsx 要 diff 归因
- openpyxl 打开 xlsx 报 `ValueError: Colors must be aRGB hex values` 或只能读到部分列
- 编辑器（腾讯文档/Tencent office）可能并发保存、需要区分「治理变更 vs 用户编辑」

## 1. 动表前（30 秒，跳过就是给自己挖坑）

```bash
# 多时点备份链，命名 = 时点 + 用途；这是 git 未跟踪文件唯一的回滚路径
cp <live> "/tmp/<名>.bak-$(date +%Y%m%d-%H%M)-<pre|postmig|fixed|postflush>.xlsx"
```

然后跑机检（见 scripts/xlsx_preflight.py）：

```bash
python3 scripts/xlsx_preflight.py <file.xlsx>
```

机检五连：① zip `testzip()` 完整性 ② openpyxl 能否打开（空 rgb 会在这崩）③ 各 sheet `dimension` 与实际最大列是否一致（不一致=会被静默截断）④ 空 `<fgColor rgb=""/>` 扫描 ⑤ 各 sheet 非空行数/列宽快照。**任何一项不过，先修再干活**，别做到一半才发现读不了。

## 2. 只读读取纪律

- 一律 `load_workbook(path, read_only=True, data_only=True)` + `iter_rows(values_only=True)`（否则拿到 ReadOnlyCell 对象，不是值）。
- **read_only 模式只读到 `<dimension ref>` 声明的列数**——表被误写过 dimension 时会静默丢列（曾把 17 列表误判成 7 列）。怀疑时用 raw XML 复核（§4）。
- 字符串统一 `strip()`，空串归一为 `None` 再比较。

## 3. 归因 diff：Counter 全行多重集（核心方法）

逐行转 tuple，`Counter` 多重集相减，按名称分四类——**必须全部可解释才算终验通过**：

```python
b_cnt, c_cnt = Counter(base_rows), Counter(cur_rows)
removed = (b_cnt - c_cnt).elements()   # 旧有新无
added   = (c_cnt - b_cnt).elements()   # 新有旧无
# 四分类：removed∩added=同名改写(改行)｜removed only=纯删｜added only=纯增｜清单内=计划迁出
```

注意：同名行在窗口内被改**两次**时，按名称只能归一次"改写"，别用行数硬凑——用多时点备份链把每个窗口分开算（§5）。

### 3b. 单元格级归因（改值场景）：⛔ 必须把 `''`/`None` 视为等价

§3 的 Counter 多重集管的是**删行/迁出**。改单元格（如回写某个 URL）要逐格比对，而
**openpyxl 保存会把空字符串 `''` 规范成 `None`** —— 实测一次只改 2 格，全表却报
**23009 处差异，其中 23007 处是 `'' → None`**，真变更被彻底淹没。

```python
real, benign = [], 0
for s in wa.sheetnames:                      # 两侧都用 data_only=True 读缓存值
    sa, sb = wa[s], wb[s]
    for r in range(1, max(sa.max_row, sb.max_row) + 1):
        for c in range(1, max(sa.max_column, sb.max_column) + 1):
            va, vb = sa.cell(r, c).value, sb.cell(r, c).value
            if va == vb: continue
            if (va in (None, "")) and (vb in (None, "")):
                benign += 1; continue        # 空表示差异，无信息损失
            real.append((s, r, c, va, vb))
assert not [d for d in real if d[1] not in EXPECT_ROWS]   # 反向断言：无越界改动
```

⛔ **只报 `real`（实质差异）**，`benign` 只作披露计数。看到万级差异先怀疑空表示，别急着以为文件被改坏。
📌 配套的**改前断言**同样重要：先断言命中行数 == 预期、性质/单位名匹配（防行号漂移），
**改后再做反向断言**（旧值全表零残留）——两头夹逼才敢认定零夹带。

## 4. openpyxl 读不了的备份：raw XML 读取法

腾讯文档保存过的文件常带 `<fgColor rgb=""/>`（违反 ST_UnsignedIntHex，openpyxl 全库崩，Excel/WPS 却能容忍）。读这类备份走 `zipfile + ElementTree`，三个坑全部踩过：

1. **rels 用 ElementTree 解析，别用正则**——`Target`/`Id` 属性顺序不固定，正则换个编辑器保存就失灵；
2. **sheet 路径拼接**：rels 的 Target 可能已含 `xl/` 前缀（`xl/worksheets/sheet3.xml`），再拼一次就是 `xl/xl/...`；
3. **两种字符串存储**：编辑器 flush 版可能没有 `sharedStrings.xml`，单元格用 `t="inlineStr"` + `<is><t>`；老文件用 `t="s"` + sharedStrings 索引。si 索引**跨文件不通用**。

现成读取器：`scripts/xlsx_rawxml.py`（读任意 sheet 的全部行 + A 列行序，自动兼容两种存储）。

## 5. 编辑器并发 flush：多时点备份链 + 窗口归因

编辑器（或 sheet-agent 会话）保存时会把**用户未保存的并发编辑**一并 flush 到磁盘。应对：

1. 每个关键动作前后都 `cp` 备份（pre / postmig / fixed / postflush…），形成备份链；
2. 对备份链逐对 diff，把每行变更归因到**具体时点 + 主体**（治理执行方 vs 用户）；
3. **用户编辑只披露、不回滚**——汇报时逐行列明，让用户裁定；可疑项（颜色代码误粘进数据列、性质误标、标题碎片命名）单独标记；
4. 修复写入用**原子替换**（`cp` 到 `.tmp` + `mv` 覆盖 + md5 核对），降低半写风险。

## 6. 修复：zip 外科手术（不到万不得已不整文件重写）

openpyxl 整文件 save 会丢编辑器特有的部件/样式（子代理就这么丢过 6 个真实值 + 21 行整列）。正确做法：**逐条目重写 zip，只替换目标部件，其余字节级不动**：

```python
zin = zipfile.ZipFile(src)
with zipfile.ZipFile(dst, "w") as zout:
    for item in zin.infolist():                     # 保留 ZipInfo 元数据
        data = zin.read(item.filename)
        if item.filename == target_part:
            data = rebuild(data)                    # 只重写目标 sheet 的 XML
        zout.writestr(item, data)                   # 传 item 不用 filename，保住 date_time/compress_type/external_attr
```

已跑通的修复原语：

- **空 rgb fill**：`<fgColor rgb=""/>` → `<fill><patternFill patternType="none"/></fill>`（语义等价的无填充）；
- **dimension**：误写 `G182` → 按实际重建 `A1:Q182`；
- **数据回填**：丢失单元格从 `/tmp` 备份按行按列补，样式索引对齐参照兄弟 sheet（表头/数据行各自的 `s=` 值）；
- **sharedStrings 追加**：新 si 追加后同步更新 `count/uniqueCount`。

## 7. 交付文档：全部数字从 live 实拉重生

治理类交付文档（清单/快照/披露）**禁止手抄数字**——写生成器脚本，从 live 文件 + 备份链实拉，一次生成。文档必备章节：终验结果表 / 执行缺陷披露 / 全量清单 / 非治理范围变更（窗口归因）/ 需用户裁定项 / 备份链 MD5 表。文档叙述与文件状态必须同时点；状态一变（如编辑器 flush）就重生。

## 8. 子代理（sheet-agent）产出必须过机检

实测五大缺陷模式（报告与实物不符，均为主代理终验才发现）：① 数据行只写前 N 列丢后半真实值；② 整列单元格抄漏；③ 表头套新样式/独有样式行；④ `dimension` 误写致工具静默截断；⑤ 保存写入空 rgb fill 致 openpyxl 崩溃。**验收 = 主代理跑 §3 归因 diff + §1 机检，全绿才算完成**，口头报告一律不采信。

## 9. 本机环境备忘

- venv python：`/Users/zhugx/.workbuddy/binaries/python/envs/default/bin/python3`（唯一有 openpyxl）；
- 微信/腾讯系导出的 xlsx 多为 Tencent office 保存（`docProps/app.xml` 可验），空 rgb 高发；
- macOS 无 `--time-style=full-iso` 的 `ls` 时用 `stat -f "%N mtime=%Sm size=%z" -t "%Y-%m-%d %H:%M:%S"`。

## 10. 多 sheet 拆分迁移（2026-09-29 实战：金融六 sheet）

把主表某类主体按类别拆进多个新 sheet（银行/基金/证券/期货/保险/信托/其他），沉淀九条：

1. **分类只认「名称｜全称」文本，表内标签列不可信**——实测标签系统性错标 30 行（保险主体贴"持牌公募基金"），按标签分桶会把方正证券、大家人寿混进基金桶。标签只作补充路由元数据。
2. **类别顺序即陷阱**：互斥关键词必须排序后单轮匹配，「担保」必须先于「基金」——否则国家融资担保基金（政策性担保基金）被「基金」抢先抓走。同性质还有「交易所」优先于「证券」。
3. **标签路由兜底 + 显式映射最小化**：名称无关键词时按表内自带分类元数据路由（如"私募股权与创投机构"→PE 桶、"资产管理公司"→AMC 桶、中央金融企业→其他）；显式实体映射全项目只允许 2 处且必须文档化。
4. **dry-run 断言先行，两连拦是常态不是事故**：迁移脚本默认 dry-run，先算每桶行数 + 断言（总数/守恒/无遗漏）全过才 `--apply`。实战两连拦分别抓住类别顺序错与标签路由比预估多抓 3 家——第二类"超预期"要逐桶诊断，确认是表内元数据可审计就更新 EXPECT 采纳，别硬掰。
5. **/tmp 中转 + 独立终验脚本，全绿才覆盖 live**：脚本输出写 `/tmp/migrated-*.xlsx` → 另写**独立**终验脚本（不复用迁移函数）→ 全绿后才 `cp` 覆盖 live。终验五连：未受影响 sheet 逐格零 diff；新 sheet 每行回原表按行内容原样匹配（`c_pre[r] > 0`）；`Counter(迁移集合) == Counter(移除集合)`；守恒断言（1872 + 552 = 2424）；子类分布核对。
6. **删除必须降序**：`sorted(idx, reverse=True)` 逐行 `delete_rows(idx, 1)`，升序会错位。
7. **新 sheet 样式从源 sheet 拷贝**：表头 `new_cell._style = copy(src._style)`、列宽照抄、冻结 A2；混合类别 sheet（如"其他"）加一列子类标签保审计，单类 sheet 列结构与先例 sheet 保持一致。
8. **写前 lsof 占检**：live 文件常年被编辑器开着，写前 `lsof <file>` 确认无占用，写后 preflight 复跑。
9. **存量业务记录不随单位行迁移**：「招聘信息」等跨 sheet 引用记录按先例不改不删；迁移只动主表公司行。
