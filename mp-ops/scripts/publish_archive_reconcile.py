#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""发表记录勾稽：把本地 vault 稿件与线上「发表记录」对齐，输出待归档 / 待确认 / 待补档清单。

用法：
    python3 publish_archive_reconcile.py                     # 只出报告（dry-run，不动任何文件）
    python3 publish_archive_reconcile.py --apply             # 对「高置信已发」的待发布稿执行 git mv 归档
    python3 publish_archive_reconcile.py --records <json>    # 指定发表记录 JSON（默认取缓存目录最新一份）
    python3 publish_archive_reconcile.py --report <path>     # 指定报告输出路径

为什么不能用标题精确匹配：
    公众号为了打开率，会把同一篇稿件的标题**彻底改写**（本地工作标题 ≠ 发布标题），
    所以匹配采用「最长公共子串 + 泛词剥离」，并对每篇待发布稿输出**最相似的 3 篇线上稿**，
    让人肉眼判，而不是替人下结论。只有达到阈值的才标记为「高置信」，可自动归档。
"""
import argparse
import glob
import json
import os
import re
import shutil
import subprocess
import sys
from difflib import SequenceMatcher

# 迁移到 skill 后不再写死某个账号目录，由环境变量注入（兼容原默认值）
VAULT = os.environ.get('GZH_VAULT') or os.path.expanduser('~/codeup/obsidian')
WORK = os.environ.get('GZH_WORK_DIR') or os.path.join(VAULT, '03-工作记录/满爸爱生活')
CACHE = os.path.expanduser('~/.cache/weixin/publish_records')
PUBLISHED_DIRS = os.environ.get('GZH_PUBLISHED_DIRS', '0南京遛娃,1行走中国,3本地生活,4散装江苏,5教育').split(',')
# 注：'6招聘' 已于 2026-09-16 随「码上职业」独立成号迁出本账号
# （目录迁至 03-工作记录/码上职业/，发布出口＝码上职业，不再计入满爸爱生活的分区勾稽）。
PENDING = '待发布'

CLEAN = re.compile(r'[\-—–_｜|/,，、（）()【】《》\s・·：:；;"“”\'’]+')
MIN_LCS = 6        # 高置信：公共子串长度下限（汉字）
MIN_CORE = 4       # 高置信：剥离泛词后仍需保留的特征字数
TOPN = 3           # 每篇待发布稿展示的最近邻篇数

GENERIC = ['南京', '遛娃', '博物馆', '攻略', '指南', '大学', '公园', '校区', '全国', '免费',
           '打卡', '带娃', '亲子', '景区', '盘点', '名单', '汇总', '推荐', '系列', '周末',
           '全', '遛', '娃', '怎么', '如何', '什么', '这些', '那些', '一篇', '一次']
# 含泛词子串（"大学生"含"大学"），必须在剥泛词前保护，否则会被打碎
PROTECT = ('大学生', '中学生', '小学生', '幼儿园', '动物园', '植物园', '科技馆')


def norm(s):
    return CLEAN.sub('', s or '')


def lcs(a, b):
    m = SequenceMatcher(None, a, b, autojunk=False).find_longest_match(0, len(a), 0, len(b))
    return m.size, a[m.a:m.a + m.size]


DIGITS = re.compile(r'[0-9０-９]+')


def core_len(frag):
    c = DIGITS.sub('', frag)          # 数字片段（日期/开放时间/票价）无区分力，先剔
    for w in PROTECT:
        c = c.replace(w, '\u2605' * 3)
    for w in GENERIC:
        c = c.replace(w, '')
    return len(c)


# ---------------- 数据加载 ----------------
def load_records(path=None):
    if not path:
        cands = sorted(glob.glob(os.path.join(CACHE, '*发表记录*.json')))
        if not cands:
            sys.exit(f'找不到发表记录 JSON，请用 --records 指定（缓存目录：{CACHE}）')
        path = cands[-1]
    d = json.load(open(path, encoding='utf-8'))
    rows = []
    for it in d['publish_list']:
        info = json.loads(it['publish_info'])
        arts = info.get('appmsg_info') or []
        ts = (info.get('sent_info') or {}).get('time')
        if not ts and arts:
            ts = (arts[0].get('line_info') or {}).get('send_time') or 0
        for a in arts:
            rows.append({
                'title': (a.get('title') or '').strip(),
                'digest': (a.get('digest') or '').strip(),
                'url': a.get('content_url') or '',
                'read': a.get('read_num', 0),
                'share': a.get('share_num', 0),
                'haokan': a.get('old_like_num', 0),
                'comment': a.get('comment_num', 0),
                'ts': ts or 0,
                'notified': '已通知' if it['publish_type'] == 101 else '未通知',
                'deleted': bool(a.get('is_deleted')),
            })
    seen, uniq = set(), []
    for r in rows:
        k = (r['title'], r['url'])
        if k in seen:
            continue
        seen.add(k)
        uniq.append(r)
    uniq.sort(key=lambda r: -r['ts'])
    return uniq, path


def list_md(d):
    """列出待归档候选稿。

    ⚠️ **已知盲区（2026-09-22 实测）**：本函数**只扫 `.md`**，看不到"md 已被归档、
    只在 `待发布/` 剩一份 `-排版.html`"的稿 —— 这类稿勾稽**永远不报**。
    实测因此漏掉两篇已发稿：《五小比赛》与《学平险》（md 早已在 `5教育/`，
    只剩排版稿没归）。**存量核对别只信勾稽，要单独扫一遍孤儿 `-排版.html`。**

    ⚠️ 同理 `main()` 的 `--apply` 分支**只搬单个文件**，不会带走
    `-排版.html` / `-封面.jpg` / `__assets/`，搬完会造成图片断链。
    完整搬法见 SKILL.md §⑧「归档是三件套：稿 + 排版稿 + 专属图」。
    """
    if not os.path.isdir(d):
        return []
    return [f[:-3] for f in sorted(os.listdir(d))
            if f.endswith('.md') and not f.startswith('00-')]


# ---------------- 人工核对白名单 ----------------
# 那些"确实是同一篇、但本地工作标题与发布标题毫无字面关系"的稿件，算法抓不到（见报告第二节）。
# 每条都经人工比对线上 digest 确认，key = 待发布稿件名，value = (线上标题特征词, 归档去向目录)。
# ⚠️ 只往这里加**已经人工核实过 digest** 的条目，不要凭标题像不像就加。
CONFIRMED = {
    '东南大学四牌楼校区-六朝宫苑里的千年名校':
        ('东南大学藏着1500岁六朝松', '0南京遛娃'),
    '南京遛娃-中国科举博物馆，带娃体验古代高考不收费':
        ('中国科举博物馆沾沾文气', '0南京遛娃'),
    '南京遛娃-雨花台方孝孺墓-一部剧带出的免费忠义课-发布版':
        ('被灭十族', '0南京遛娃'),
    '南京遛娃-坐着S3号线看长江追高铁':
        ('坐着S3地铁巧遇高铁', '0南京遛娃'),
    '南京中小学学生卡办理全攻略-2026开学季':
        ('南京中小学学生卡办理全指南', '3本地生活'),
    '南京大学生免费景区全攻略-2026开学季':
        ('南京大学生免费游玩全攻略', '3本地生活'),
    '南京娃连休5天！2026江苏秋假与中秋国庆放假全汇总':
        ('连休5天！江苏12市秋假', '3本地生活'),
    '镇江遛娃-博物馆+科技馆一日两馆全免费-发布版':
        ('镇江一天刷两馆', '1行走中国'),
    '南京遛娃-本周末4个去处-镇江免票桨板赛免费大展教师福利':
        ('镇江26家景区南京人凭身份证免票', '1行走中国'),
    '南京五小比赛全指南-5大赛道与申报攻略':
        ('同班孩子悄悄拿了科创奖', '5教育'),
    '为什么即便不买任何商业保险，也该给孩子上一份学平险':
        ('学平险', '5教育'),
}


def local_text(name, folder):
    """本地可比对文本 = 文件名（仅此）。

    ⚠️ 实测否决过「文件名 + 正文前 900 字」的做法：本地稿正文与线上 digest 共享大量
    样板文本（开放时间 `9:00-17:00,16:30停止入馆`、`门票30元`、`闭馆法定节假日除外`、
    `2026年`），最长公共子串会优先命中这些噪声片段，把 36 篇里的 28 篇误判为"已发"。
    文件名才是真正带场所特征的短文本，宁可召回低也要精度。
    """
    return norm(name)


def nearest(name, folder, pub, topn=TOPN):
    """返回 (score, frag, item) 降序的前 topn 个候选。"""
    nm = local_text(name, folder)
    out = []
    for p in pub:
        size, frag = lcs(nm, norm(p['title']) + '|' + norm(p['digest']))
        if size < 4 or core_len(frag) < 3:
            continue
        out.append((size, core_len(frag), frag, p))
    out.sort(key=lambda c: (-c[0], -c[1], -c[3]['read']))
    return out[:topn]


def local_match(p, local_files):
    """某一篇线上文章是否能在本地找到对应稿件。local_files: {稿件名: 所在分区}。
    算法（文件名相似度）与人工白名单 CONFIRMED 都算命中——两者必须同时生效，
    否则「索引说 21 篇已归档 / 勾稽说 137 篇未归档」这种口径打架会重现。
    """
    for nm, folder in local_files.items():
        kw = CONFIRMED.get(nm, (None, None))[0]
        if kw and kw in p['title']:
            return nm
        if classify(nearest(nm, folder, [p], topn=1)):
            return nm
    return None


ARCHIVE = '已发布存档'   # 线上抓回的正文存档（YYYY-MM/DD-标题.md，两层结构）


def list_md_deep(sub):
    """递归列出 md（存档是两层目录）。返回文件名（去 .md），排除 README。"""
    root = os.path.join(WORK, sub)
    out = []
    if not os.path.isdir(root):
        return out
    for r, _, fs in os.walk(root):
        for f in fs:
            if f.endswith('.md') and f != 'README.md':
                out.append(f[:-3])
    return sorted(out)


def all_local_files():
    d = {}
    for sub in [PENDING] + PUBLISHED_DIRS:
        for nm in list_md(os.path.join(WORK, sub)):
            d[nm] = sub
    # 存档也算"本地已有"，否则线上已发的稿永远显示未归档
    for nm in list_md_deep(ARCHIVE):
        d.setdefault(nm, ARCHIVE)
    return d


def classify(cand):
    """高置信判定：片段够长且剥离泛词后仍有特征。"""
    if not cand:
        return False
    size, core, frag, p = cand[0]
    return size >= MIN_LCS and core >= MIN_CORE


# 内容线定义（口径固定，改这里等于改口径，需在复盘里声明）
CONTENT_LINES = {
    '家长刚需·补贴福利': ['补贴', '医保', '保险', '学平险', '报销', '免费领', '福利', '优惠'],
    '家长刚需·健康疫苗': ['疫苗', '流感', '停课', '就诊', '挂号', '防疫'],
    '事件热点·赛事热梗': ['苏超', '夺冠', '队徽', '刷屏', '网友', '爆', '热'],
    '官方时效·免票开放日': ['免票', '免费开放', '开放日', '免费日', '免门票', '预约'],
    '官方时效·假期安排': ['放假', '假期', '秋假', '寒假', '暑假', '调休', '连休', '节假'],
    '官方时效·开学招生': ['开学', '招生', '入学', '校历', '录取', '赋分', '学区', '施教',
                          '学生卡', '新生', '在校生', '赛事', '比赛', '科创', '白名单'],
    '场馆场景·攻略': ['遛娃', '博物馆', '攻略', '场馆', '纪念馆', '图书馆', '校区', '公园',
                      '馆', '墓', '陵', '遗址', '旧址', '景区', '森林', '园', '街', '山'],
}


def content_line(title):
    for name, kws in CONTENT_LINES.items():
        if any(k in title for k in kws):
            return name
    return '其他'


def build_review(pub, ym):
    """生成某月的数据复盘（数据段自动填，人工段留 TODO）。"""
    import datetime
    TZ = datetime.timezone(datetime.timedelta(hours=8))

    def dstr(p):
        return datetime.datetime.fromtimestamp(p['ts'], TZ).strftime('%Y-%m-%d') if p['ts'] else ''

    # 同标题去重，留阅读最高；剔除已删
    uniq = {}
    for p in pub:
        if p['deleted'] or not p['ts']:
            continue
        if p['title'] not in uniq or p['read'] > uniq[p['title']]['read']:
            uniq[p['title']] = p
    # 近似标题再合一次：前 15 字相同视为同一篇（重发/标题截断），留阅读最高
    dedup = {}
    for p in uniq.values():
        key = norm(p['title'])[:15]
        if key not in dedup or p['read'] > dedup[key]['read']:
            dedup[key] = p
    A = list(dedup.values())

    cur = sorted([p for p in A if dstr(p).startswith(ym)], key=lambda x: -x['ts'])
    ly = f'{int(ym[:4]) - 1}{ym[4:]}'
    prev = [p for p in A if dstr(p).startswith(ly)]

    def agg(rs):
        n = len(rs)
        tr = sum(r['read'] for r in rs)
        return n, tr, (tr // n if n else 0)

    n_all, tr_all, mean_all = agg(A)
    n_c, tr_c, mean_c = agg(cur)
    n_p, tr_p, mean_p = agg(prev)

    top = max(cur, key=lambda x: x['read']) if cur else None
    top_share = (top['read'] / tr_c * 100) if (top and tr_c) else 0

    lines = {}
    for r in cur:
        ln = content_line(r['title'])
        lines.setdefault(ln, []).append(r)

    L = ['---', f'title: 满爸爱生活 · {ym} 数据复盘', f'date: {ym}-??',
         'category: 满爸爱生活', 'tags: [运营, 复盘]', '---', '',
         f'# 满爸爱生活 · {ym} 数据复盘', '',
         '> 数据源：公众号后台「发表记录」缓存 JSON；口径见《运营总览》。',
         '> 本文件**数据段自动生成**，`TODO` 段落需人工填写（归因与下月排期）。', '',
         '## 1. 本月总览', '',
         '| 指标 | 本月 | 去年同月 | 账号基线（全历史） |', '|---|---|---|---|',
         f'| 篇数 | {n_c} | {n_p} | {n_all} |',
         f'| 阅读合计 | {tr_c:,} | {tr_p:,} | {tr_all:,} |',
         f'| 篇均阅读 | {mean_c:,} | {mean_p:,} | {mean_all:,} |', '']

    if top:
        L += [f'**头部集中度**：最高单篇《{top["title"]}》**{top["read"]:,}**，'
              f'占本月总阅读 **{top_share:.1f}%**；剔除后本月篇均 '
              f'{(tr_c - top["read"]) // max(n_c - 1, 1):,}。', '',
              ('> ⚠️ 单篇占比超 60% 说明"一篇文章撑一个月"，其余稿件实际表现需单独看，'
               '不要被月度合计掩盖。' if top_share > 60 else ''), '']

    L += ['## 2. 内容线配比与效率', '',
          '| 内容线 | 篇数 | 阅读合计 | 篇均 | 占篇数比 |', '|---|---|---|---|---|']
    for ln, rs in sorted(lines.items(), key=lambda kv: -sum(r['read'] for r in kv[1])):
        n, tr, mn = agg(rs)
        L.append(f'| {ln} | {n} | {tr:,} | {mn:,} | {n / n_c * 100:.0f}% |')
    L += ['', 'TODO：与账号历史基线对比，判断哪条线在变好/变坏。', '',
          '## 3. 逐篇台账', '',
          '| 日期 | 标题 | 内容线 | 阅读 | 分享 | 在看 | 留言 | 分享率 |', '|---|---|---|---|---|---|---|---|']
    for r in cur:
        sr = (r['share'] / r['read'] * 100) if r['read'] else 0
        L.append(f"| {dstr(r)} | {r['title'].replace('|','｜')} | {content_line(r['title'])} | "
                 f"{r['read']:,} | {r['share']} | {r['haokan']} | {r['comment']} | {sr:.1f}% |")
    L += ['', 'TODO：阅读 ≥10,000 或 ≤100 的稿子，各写一句归因。', '',
          '## 4. 窗口命中情况（对照《运营日历》）', '',
          'TODO：本月有哪些节点？踩了几个？漏了哪个？', '',
          '## 5. 下月排期调整', '', 'TODO：篇数、各线配比、要绑的节点（必须落地）。', '',
          '## 6. 需要决策的问题', '', 'TODO', '',
          '---', f'*数据段由 `publish_archive_reconcile.py --review {ym}` 生成；'
          f'按《00-复盘SOP.md》填写 TODO 后归档。*']

    out_dir = os.path.join(WORK, '运营', '复盘')
    os.makedirs(out_dir, exist_ok=True)
    out = os.path.join(out_dir, f'{ym}-复盘.md')
    if os.path.exists(out):
        print(f'⚠️ {out} 已存在，跳过（避免覆盖人工填写内容）。加 --force 未实现，请手动改名。')
        return
    open(out, 'w', encoding='utf-8').write('\n'.join(L))
    print(f'复盘：{out}（本月 {n_c} 篇 / {tr_c:,} 阅读 / 篇均 {mean_c:,}；'
          f'头部占比 {top_share:.1f}%）')


def build_index(pub):
    """生成《已发文章索引》：线上全量发表记录 + 本地归档状态，供选题去重与检索。"""
    import datetime

    # 反向映射：本地文件（含待发布）→ 命中的线上文章（与勾稽共用同一匹配器）
    local_files = all_local_files()
    archived = {}          # id(pub item) -> (本地目录, 本地文件名)
    for p in pub:
        nm = local_match(p, local_files)
        if nm:
            archived[id(p)] = (local_files[nm], nm)

    TZ = datetime.timezone(datetime.timedelta(hours=8))
    def dstr(p):
        return datetime.datetime.fromtimestamp(p['ts'], TZ).strftime('%Y-%m-%d') if p['ts'] else '—'

    n_arch = len(archived)
    L = ['---', 'title: 满爸爱生活 · 已发文章索引', f'date: {datetime.date.today().isoformat()}',
         'category: 满爸爱生活', 'source: 公众号后台', 'tags: [索引, 发表记录, 选题去重]', '---', '',
         f'# 满爸爱生活 · 已发文章索引（截至 {datetime.date.today().isoformat()}）', '',
         '> **用途**：① 选题前查重——避免把一个已经发过的点位再写一遍；② 快速回看历史表现',
         '（什么题材/什么城市/什么写法容易起量）；③ 核对本地 vault 的归档缺口。', '',
         f'> **口径**：线上发表记录 **{len(pub)}** 篇（含未通知、已删除）；其中能在本地 vault'
         f'找到对应稿件的 **{n_arch}** 篇，**{len(pub) - n_arch}** 篇本地无留档。'
         '「本地归档」列显示所在分区目录，「—」= vault 里没有。', '',
         '## 一、按月清单', '']

    # 按月分组
    buckets = {}
    for p in pub:
        key = dstr(p)[:7] if p['ts'] else '未知'
        buckets.setdefault(key, []).append(p)
    for key in sorted(buckets, reverse=True):
        items = sorted(buckets[key], key=lambda x: -x['ts'])
        tot = sum(i['read'] for i in items)
        L += [f'### {key}（{len(items)} 篇，阅读合计 {tot:,}）', '',
              '| 日期 | 标题 | 阅读 | 分享 | 在看 | 留言 | 本地归档 | 原文 |',
              '|---|---|---|---|---|---|---|---|']
        for p in items:
            loc = archived.get(id(p))
            ltag = loc[0] if loc else '—'
            flag = '~~已删除~~ ' if p['deleted'] else ''
            L.append(f"| {dstr(p)} | {flag}{p['title'].replace('|','｜')} | {p['read']:,} | "
                     f"{p['share']} | {p['haokan']} | {p['comment']} | {loc_template(ltag)} | "
                     f"[↗]({p['url']}) |")
        L.append('')

    # 爆款榜（选题参考）
    def uniq_by_title(rs):
        seen, out = set(), []
        for r in rs:
            if r['title'] in seen:
                continue
            seen.add(r['title'])
            out.append(r)
        return out

    top = sorted(uniq_by_title([p for p in pub if not p['deleted']]), key=lambda x: -x['read'])
    L += ['## 二、阅读 30 强（选题参考）', '',
          '同一个标题只留表现最好的一条。**通读这一列可以反推账号的流量密码**：'
          '冲突感标题（"被灭十族""醒醒""玩坏了"）与"家长刚需+官方时效"（疫苗、学生卡、补贴）两条线最稳。', '',
          '| # | 日期 | 标题 | 阅读 | 分享 | 在看 |', '|---|---|---|---|---|---|']
    for i, p in enumerate(top[:30], 1):
        L.append(f"| {i} | {dstr(p)} | {p['title'].replace('|','｜')} | {p['read']:,} | "
                 f"{p['share']} | {p['haokan']} |")
    L += ['', '## 三、本地 vault 未归档的已发文章', '',
          f'共 **{len(pub) - n_arch}** 篇。这批没有本地留档，容易被当成"没写过"而重复选题。', '']
    miss = [p for p in top if id(p) not in archived]
    L += ['| 日期 | 标题 | 阅读 |', '|---|---|---|']
    for p in miss:
        L.append(f"| {dstr(p)} | {p['title'].replace('|','｜')} | {p['read']:,} |")
    L += ['', '---', '',
          '*生成：`python3 ~/.workbuddy/skills/mp-ops/scripts/publish_archive_reconcile.py --index`*']

    out = os.path.join(WORK, '已发文章索引-满爸爱生活.md')
    open(out, 'w', encoding='utf-8').write('\n'.join(L))
    print(f'索引：{out}（{len(pub)} 篇线上 / {n_arch} 篇有本地归档）')


def loc_template(tag):
    return tag if tag != '—' else '—'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--records')
    ap.add_argument('--report')
    ap.add_argument('--apply', action='store_true', help='对高置信已发稿执行 git mv 归档')
    ap.add_argument('--index', action='store_true', help='额外生成《已发文章索引》')
    ap.add_argument('--review', metavar='YYYY-MM',
                    help='生成该月数据复盘（写入 运营/复盘/YYYY-MM-复盘.md）')
    args = ap.parse_args()

    pub, src = load_records(args.records)
    pending_dir = os.path.join(WORK, PENDING)
    pending = list_md(pending_dir)

    rows = []
    for nm in pending:
        cands = nearest(nm, pending_dir, pub)
        rows.append({
            'name': nm,
            'cands': cands,
            'hi': classify(cands),
        })
    # 并入人工核对白名单（算法抓不到的那批）
    for r in rows:
        if r['name'] in CONFIRMED:
            kw, dest = CONFIRMED[r['name']]
            hit = next((p for p in pub if kw in p['title']), None)
            r['hi'] = True
            r['manual'] = True
            r['dest'] = dest
            r['cands'] = [(len(kw), len(kw), kw, hit)] if hit else r['cands']
    hi = [r for r in rows if r['hi']]
    lo = [r for r in rows if not r['hi']]
    print(f'发表记录源：{src}')
    print(f'线上图文 {len(pub)} 篇｜待发布 {len(pending)} 篇')
    print(f'  ✅ 高置信已发（可归档）: {len(hi)}')
    print(f'  ❓ 需人工判断           : {len(lo)}')

    # 线上已发、本地未归档（与索引共用同一匹配器）
    local_files = all_local_files()
    orphan = [p for p in pub if not local_match(p, local_files)]
    print(f'  ⬜ 线上已发、本地未归档: {len(orphan)}')

    # ---------------- 报告 ----------------
    import datetime
    today = datetime.date.today().isoformat()
    rp = args.report or os.path.join(WORK, '工具', f'勾稽报告-{today}.md')
    L = []
    L += ['---', 'title: 满爸爱生活 · 待发布稿件 ↔ 线上发表记录 勾稽报告',
          f'date: {today}', 'category: 满爸爱生活', 'source: 公众号后台', 'tags: [勾稽, 运营台账]', '---', '',
          f'# 待发布稿件 ↔ 线上发表记录 勾稽报告（{today}）', '',
          f'- 线上图文 **{len(pub)}** 篇（源：`{os.path.basename(src)}`）',
          f'- `待发布/` **{len(pending)}** 篇',
          f'- ✅ 高置信已发、建议归档：**{len(hi)}** 篇',
          f'- ⬜ 线上已发、本地 vault 未归档：**{len(orphan)}** 篇', '',
          '> **为什么每篇都要人看**：公众号为打开率会把标题彻底改写，本地工作标题与发布标题常常毫无字面关系。'
          '本报告不替你下结论，而是给出**最相似的 3 篇线上稿**，让你 10 秒判一篇。', '',
          '> 匹配口径：只用**文件名**（不含正文）与线上「标题 + digest」求最长公共子串，'
          '片段需 ≥6 汉字、且剔除数字与泛词后仍剩 ≥4 字。'
          '（曾试过并入本地正文，因开放时间/票价等样板文本会产生大量假阳性而否决。）', '',
          '## 一、高置信已发（达到阈值，可 `--apply` 一键归档）', '',
          '| 待发布稿件 | 线上已发标题 | 阅读 | 命中片段 | 判定来源 |', '|---|---|---|---|---|']
    for r in hi:
        s, c, frag, p = r['cands'][0]
        src_tag = '人工核实 digest' if r.get('manual') else '算法（文件名相似度）'
        L.append(f"| {r['name']} | {p['title'].replace('|','｜')} | {p['read']:,} | {frag} | {src_tag} |")

    L += ['', '## 二、需人工判断（列出最近邻 3 篇，自行比对）', '',
          '| 待发布稿件 | 最近邻线上稿（相似度） | 阅读 |', '|---|---|---|']
    for r in lo:
        cells = []
        for s, c, frag, p in r['cands']:
            cells.append(f"`{s}` {p['title'][:38]}（「{frag}」）")
        rd = r['cands'][0][3]['read'] if r['cands'] else 0
        L.append(f"| {r['name']} | {'<br>'.join(cells) if cells else '—'} | {rd:,} |")

    L += ['', f'## 三、线上已发、本地 vault 未归档（{len(orphan)} 篇，按阅读降序）', '',
          '按 vault 现有约定，这批没有本地留档，容易被重复选题。', '',
          '| # | 日期 | 标题 | 阅读 | 分享 | 在看 | 留言 |', '|---|---|---|---|---|---|---|']
    for i, p in enumerate(sorted(orphan, key=lambda x: -x['read']), 1):
        d = datetime.datetime.fromtimestamp(p['ts'], datetime.timezone(datetime.timedelta(hours=8))
                                            ).strftime('%Y-%m-%d') if p['ts'] else '—'
        L.append(f"| {i} | {d} | {p['title'].replace('|','｜')} | {p['read']:,} | {p['share']} | "
                 f"{p['haokan']} | {p['comment']} |")
    L += ['', '---', '',
          '*重新生成：`python3 ~/.workbuddy/skills/mp-ops/scripts/publish_archive_reconcile.py`*']
    os.makedirs(os.path.dirname(rp), exist_ok=True)
    open(rp, 'w', encoding='utf-8').write('\n'.join(L))
    print(f'\n报告：{rp}')

    if args.index:
        build_index(pub)

    if args.review:
        build_review(pub, args.review)

    if args.apply:
        moved = 0
        for r in hi:
            p = r['cands'][0][3]
            t = p['title']
            if r.get('dest'):
                dest = r['dest']          # 人工核对条目用指定去向
            elif any(k in t for k in ('徐州', '沛县', '苏北', '淮安', '泰州', '扬州', '镇江', '马鞍山')):
                dest = '1行走中国'
            else:
                dest = '0南京遛娃'
            for suffix in ('.md', '__assets'):
                src = os.path.join(pending_dir, r['name'] + suffix)
                if not os.path.exists(src):
                    continue
                dst = os.path.join(WORK, dest, os.path.basename(src))
                rel_s = os.path.relpath(src, VAULT)
                rel_d = os.path.relpath(dst, VAULT)
                res = subprocess.run(['git', 'mv', rel_s, rel_d], cwd=VAULT,
                                     capture_output=True, text=True)
                if res.returncode == 0:
                    how = 'git mv'
                else:
                    # 未纳入版本控制的文件 git mv 会直接拒绝 → 退回普通 mv + git add
                    try:
                        shutil.move(src, dst)
                    except OSError as e:
                        print(f'  !! 失败 {rel_s}: {e}')
                        continue
                    subprocess.run(['git', 'add', rel_d], cwd=VAULT,
                                   capture_output=True, text=True)
                    how = 'mv+add（原文件未入库）'
                moved += 1
                print(f'  [{how}] {rel_s} -> {rel_d}')
        print(f'已归档 {moved} 项（git 可回滚）。')


if __name__ == '__main__':
    main()
