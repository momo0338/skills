#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""成稿事实核查【harness 模板】——新稿复用法：复制本文件，改 5 处：
  RAW_PATH   官方公告原文 txt（ego_fetch_text.py 的产出）
  MD_PATH    源稿 md
  POS        正向溯源清单：稿内每条硬信息（数字/日期/电话/域名/机构名），归一化后必须能在原文 find 到
  CROSS      反向断言清单：他省/他单位句型（体检三禁入、出生日期口径、六险二金…），不得作为事实陈述出现
             ⚠️ 稿内「与苏浙不同：无 425 门槛」这类**对照表述**会误触——人工判读，对照句合法
  FACTS      官方事实点覆盖率：官方公告逐节拆点（★最易漏非数字类：培养体系/福利/流程/留学生条款）
跑完五项全 ✅ 才准进 verify_draft.py；「公告未披露」计数>0 且无套话指纹。
"""
import re, sys

RAW_PATH = 'REPLACE_公告原文.txt'
MD_PATH  = 'REPLACE_源稿.md'

RAW = open(RAW_PATH, encoding='utf-8').read()
RAWN = re.sub(r'[\s\u3000]', '', RAW)
md = open(MD_PATH, encoding='utf-8').read()
body = md[md.index('## 码上君划重点'):]
bn = re.sub(r'[\s\u3000*]', '', body)

# ── 1) 摘要字符数（≤120，标注数须与实测一致）
m = re.search(r'\*\*SEO 摘要\*\*（(\d+)字，无 emoji）：(.+?)$', md, re.M)
if m:
    d = m.group(2)
    flag = '✅' if len(d) <= 120 and str(len(d)) == m.group(1) else '❌'
    print(f'{flag} 摘要实测 {len(d)} 字符（标注 {m.group(1)}，≤120）')

# ── 2) 正向溯源：每条硬信息必须能在官方原文 find 到
POS = [
    # '2026年10月10日', '不超过25周岁', '0451-53687913', ...
]
miss = [k for k in POS if re.sub(r'[\s\u3000]', '', k) not in RAWN]
print('❌ 正向溯源缺失:', miss or '✅ 无')

# ── 3) 反向断言（他省句型；对照句人工豁免）
CROSS = [
    # '恐高症', '辨色力', '425分', '六险二金', '特高压', ...
]
bad = [k for k in CROSS if k in body]
print('⚠️ 反向命中（人工判读：对照句=合法，事实陈述=打回）:', bad or '✅ 无')

# ── 4) 官方事实点覆盖率（★最易漏非数字类：培养体系/福利/流程/留学生条款）
FACTS = {
    # '体检标准': '公务员录用体检通用标准（试行）', '行程·清华会场': '西主楼3区103教室', ...
}
miss2 = [k for k, v in FACTS.items() if re.sub(r'[\s\u3000]', '', v) not in bn]
print('❌ 官方披露但稿内缺失:', miss2 or '✅ 无')

# ── 5) 套话指纹（命中且官方无出处=编造；「公告未披露」计数过低=缺口被脑补填满）
P = ['CET-4','CET-6','行测','色盲','色弱','A类编制','企业年金','六险二金','补充医疗','食堂','公寓','班车','落户','租房补贴','雏鹰','项目制','劳务外包','早投递']
hit = {k: body.count(k) for k in P if body.count(k)}
print('套话指纹:', hit or '✅ 无')
print('「公告未披露」出现:', body.count('公告未披露'), '次（同形套话块=该删，见 10-08 裁定）')
