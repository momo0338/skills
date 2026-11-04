#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""上海城投集团2027届校园招聘 · 8 段骨架排版生成器

硬信息来源（全部可核）：
1) 岗位数据 = 上海城投招聘官网北森网关 https://chengtou.zhiye.com/api/Jobad/GetJobAdPageList
   CategoryId=2（校招）共 90 条，逐条 Require 均含「招聘对象：应届毕业生」
2) 校招流程 = https://chengtou.zhiye.com/campus 页面官方原文
3) 企业简介 = https://www.chengtou.com/n610/ 集团官网原文（数据截至 2023 年底）
"""
import re

BRAND = '#D00810'          # 城投红（logo 有彩度像素众数色实测 #D00810）
BRAND_DARK = '#8E0509'     # CTA 渐变深端
BG_LIGHT = '#fdf2f2'
BORDER_LIGHT = '#f3c9c9'
GRAY_BG = '#f5f6f7'
FAQ_BG = '#fffafa'

OUT = '/Users/zhugx/codeup/obsidian/03-工作记录/码上职业/事业单位/待发布/2026-11-04-上海城投2027校招-排版.html'
MD = '/Users/zhugx/codeup/obsidian/03-工作记录/码上职业/事业单位/待发布/2026-11-04-上海城投2027校招-源稿.md'
TITLE = '上海城投2027校招90岗：14个专业不限，大专可报，11月30日前网申'
DIGEST = ('上海市国资委全资国企90个校招岗全部面向应届生：本科64岗、大专20岗、硕士5岗，14岗专业不限，'
          '年龄多按28周岁以下。网申与在线测评均需11月30日前在chengtou.zhiye.com完成。')


def pill(sub):
    return ('<section style="margin-bottom:10px;">'
            f'<span style="background:{BRAND};color:#fff;font-size:12px;font-weight:700;padding:2px 8px;border-radius:4px;margin-right:8px;">码上君划重点</span>'
            f'<span style="color:{BRAND};font-size:15px;font-weight:800;">{sub}</span></section>')


def sec_title(t):
    return ('<section style="margin:24px 0 12px;padding:0 14px;">'
            f'<span style="display:inline-block;width:4px;height:18px;background:{BRAND};margin-right:8px;border-radius:2px;vertical-align:-2px;"></span>'
            f'<span style="font-size:18px;font-weight:800;color:{BRAND};">{t}</span></section>')


def p(txt, style=''):
    return f'<p style="margin:0 0 10px;font-size:15px;line-height:1.75;color:#334155;{style}">{txt}</p>'


def ul(items, numbers=None):
    out = '<section style="margin:0 0 10px;">'
    for i, it in enumerate(items):
        pre = f'{numbers[i]} ' if numbers else ''
        out += f'<p style="margin:0 0 6px;font-size:15px;line-height:1.7;color:#334155;">{pre}{it}</p>'
    return out + '</section>'


def th(txt, w):
    return (f'<td style="width:{w};background:{BRAND};background-color:{BRAND};color:#fff;'
            f'font-size:12.5px;font-weight:700;text-align:center;padding:7px 4px;">{txt}</td>')


# ── 学历层次汇总（数据来自网关 90 条逐条统计）
EDU_ROWS = [
    ('大专及以上', '20', '25–28 周岁以下',
     '运行操作岗（金华/南平/宁波/老港等）、资源化维护岗（污水公司）、船舶清扫工、集卡驾驶、桥吊司机、车间操作工'),
    ('本科及以上', '64', '26–30 周岁以下',
     '生产运维岗、供水服务代表、管网作业岗、项目管理岗（水务项目公司）、数据管理岗（制水公司）、财务管理（2027）'),
    ('硕士研究生及以上', '5', '28–30 周岁以下',
     '研发岗（水中心）、机器人系统工程师（水中心）、党群干事、监管工程师、检测工程师'),
    ('博士研究生', '1', '35 周岁以下', '博士后（水中心）'),
]

# ── 14 个专业不限岗位（逐条取自 Require「专业：不限」）
NO_MAJOR = [
    ('管网作业岗（管网公司）', '本科及以上', '26周岁以下'),
    ('生产运维统计员（天马）', '本科及以上', '28周岁以下'),
    ('生产运维统计员（东石塘）', '本科及以上', '28周岁以下'),
    ('仓库管理员（环慧）', '本科及以上', '28周岁以下'),
    ('船舶轮机操作员', '本科及以上', '28周岁以下'),
    ('中控', '本科及以上', '28周岁以下'),
    ('物业运营', '本科及以上', '28周岁以下'),
    ('租赁运营', '本科及以上', '28周岁及以下'),
    ('桥吊司机', '本科及以上', '28周岁以下'),
    ('集卡驾驶', '本科及以上', '28周岁以下'),
    ('船舶清扫工', '大专及以上', '25周岁以下'),
    ('船舶轮机', '大专及以上', '25周岁以下'),
    ('集卡驾驶', '大专及以上', '25周岁以下'),
    ('车间操作工', '大专及以上', '25周岁以下'),
]

# ── 官方校招流程（chengtou.zhiye.com/campus 原文）
FLOW = [
    ('网申', '2026年11月30日前'),
    ('在线测评', '2026年11月30日前'),
    ('统一线上面试', '2026年12月'),
    ('线下面试', '2026年12月至2027年1月'),
    ('发放Offer', '2027年春节前后'),
]


def edu_table():
    rows = ''
    for i, (edu, cnt, age, rep) in enumerate(EDU_ROWS):
        bg = '#ffffff' if i % 2 else BG_LIGHT
        rows += ('<tr>'
                 f'<td style="background:{bg};background-color:{bg};padding:7px 5px;font-size:13px;font-weight:700;color:{BRAND_DARK};vertical-align:top;">{edu}</td>'
                 f'<td style="background:{bg};background-color:{bg};padding:7px 5px;font-size:13px;color:#334155;text-align:center;vertical-align:top;">{cnt}</td>'
                 f'<td style="background:{bg};background-color:{bg};padding:7px 5px;font-size:13px;color:#334155;vertical-align:top;">{age}</td>'
                 f'<td style="background:{bg};background-color:{bg};padding:7px 5px;font-size:12.5px;color:#475569;vertical-align:top;word-break:break-word;line-break:anywhere;">{rep}</td>'
                 '</tr>')
    return ('<section style="margin:0 0 8px;">'
            '<table style="width:100%;border-collapse:collapse;table-layout:fixed;">'
            '<tr>' + th('学历要求', '17%') + th('岗位数', '10%') + th('年龄上限', '19%') + th('代表性岗位（原文岗位名）', '54%') + '</tr>'
            f'{rows}</table>'
            '<p style="margin:6px 0 0;font-size:12.5px;color:#64748b;">按招聘官网 90 条校招岗位逐条统计；四个层次合计 20＋64＋5＋1＝90 个岗位。'
            '公告未披露各岗位招聘人数，需在官网岗位详情页查看具体要求。</p></section>')


def nomajor_table():
    rows = ''
    for i, (name, edu, age) in enumerate(NO_MAJOR):
        bg = '#ffffff' if i % 2 else BG_LIGHT
        rows += ('<tr>'
                 f'<td style="background:{bg};background-color:{bg};padding:6px 5px;font-size:13px;color:#1e293b;word-break:break-word;line-break:anywhere;">{name}</td>'
                 f'<td style="background:{bg};background-color:{bg};padding:6px 5px;font-size:12.5px;color:#334155;text-align:center;">{edu}</td>'
                 f'<td style="background:{bg};background-color:{bg};padding:6px 5px;font-size:12.5px;color:#334155;text-align:center;">{age}</td>'
                 '</tr>')
    return ('<section style="margin:0 0 8px;">'
            '<table style="width:100%;border-collapse:collapse;table-layout:fixed;">'
            '<tr>' + th('岗位名称', '52%') + th('学历要求', '22%') + th('年龄', '26%') + '</tr>'
            f'{rows}</table>'
            '<p style="margin:6px 0 0;font-size:12.5px;color:#64748b;">14 条岗位的「专业」一栏均写「不限」；其中「集卡驾驶」在本科与大专两个层次各设一岗，要求不同，报名时按学历对应投递。</p></section>')


def flow_table():
    rows = ''
    for i, (step, when) in enumerate(FLOW):
        bg = '#ffffff' if i % 2 else BG_LIGHT
        rows += ('<tr>'
                 f'<td style="background:{bg};background-color:{bg};padding:7px 6px;font-size:13.5px;color:#1e293b;font-weight:700;text-align:center;">{step}</td>'
                 f'<td style="background:{bg};background-color:{bg};padding:7px 6px;font-size:13.5px;color:{BRAND_DARK};text-align:center;font-weight:700;">{when}</td>'
                 '</tr>')
    return ('<section style="margin:0 0 10px;">'
            '<table style="width:100%;border-collapse:collapse;table-layout:fixed;">'
            '<tr>' + th('环节', '40%') + th('时间（官网校招流程原文）', '60%') + '</tr>'
            f'{rows}</table></section>')


def tri_grid():
    def cell(v1, v2):
        return ('<td style="padding:0;">'
                f'<section style="background:{BG_LIGHT};border:1px solid {BORDER_LIGHT};border-radius:10px;padding:10px 6px;text-align:center;">'
                f'<section style="font-size:15px;font-weight:800;color:{BRAND};line-height:1.4;">{v1}</section>'
                f'<section style="font-size:11.5px;color:#334155;line-height:1.5;margin-top:3px;">{v2}</section>'
                '</section></td>')
    return ('<table style="width:100%;border-collapse:separate;border-spacing:8px 0;table-layout:fixed;margin:0 0 6px;"><tr>'
            + cell('11月30日前', '网申＋在线测评截止')
            + cell('国有独资', '上海市国资委全资持有')
            + cell('90个岗位', '本科64·大专20·硕士5')
            + '</tr></table>')


def faq(q, a):
    return (f'<section style="background:{FAQ_BG};border:1px solid #f0dede;border-radius:8px;padding:12px 14px;margin:0 0 10px;">'
            f'<p style="margin:0 0 6px;font-size:15px;font-weight:800;color:{BRAND_DARK};line-height:1.6;">{q}</p>'
            f'<p style="margin:0;font-size:14.5px;line-height:1.75;color:#334155;">{a}</p></section>')


h = []
h.append('<!DOCTYPE html><html><head><meta charset="utf-8"/><title>' + TITLE + '</title></head><body style="margin:0;padding:0;background:#ffffff;">')
h.append('<section style="max-width:677px;margin:0 auto;box-sizing:border-box;font-family:-apple-system,BlinkMacSystemFont,\'Helvetica Neue\',\'PingFang SC\',\'Hiragino Sans GB\',\'Microsoft YaHei UI\',\'Microsoft YaHei\',Arial,sans-serif;font-size:16px;line-height:1.75;color:#333333;word-wrap:break-word;padding:12px 10px;">')

# ── 划重点卡
h.append(f'<section style="background:{BG_LIGHT};border:1px solid {BORDER_LIGHT};border-left:4px solid {BRAND};border-radius:8px;padding:14px 16px;margin:0 0 16px;">')
h.append(pill('上海城投2027校招：90个岗位、11月30日前关闸'))
h.append(p('上海城投（集团）有限公司2027届校园招聘已启动，招聘官网 <span style="color:' + BRAND_DARK + ';font-weight:700;">chengtou.zhiye.com</span> 在挂 <strong>90 个校招岗位</strong>，每一条的岗位要求都写明「招聘对象：应届毕业生」。这条对江苏、上海两地毕业生都适用——岗位上还有金华、南平、宁波、湖州等外地项目岗。'))
h.append(ul([
 f'<span style="color:{BRAND_DARK};font-weight:800;">90 个岗位按学历分四档，大专能报的有 20 个。</span>本科及以上 <strong>64 个</strong>、大专及以上 <strong>20 个</strong>、硕士研究生及以上 5 个、博士研究生 1 个。对专科同学来说，20 个岗位集中在运行操作、船舶、集卡驾驶、车间操作这类一线技术岗。',
 f'<span style="color:{BRAND_DARK};font-weight:800;">14 个岗位「专业不限」，是不卡专业的主要入口。</span>管网作业岗、中控、物业运营、租赁运营、桥吊司机、集卡驾驶、车间操作工等 14 条岗位的专业栏写的是「不限」；其余岗位按工程类、电气类、自动化类、机械类、环境类、电子信息类、经济学类、管理学类等方向设限。',
 f'<span style="color:{BRAND_DARK};font-weight:800;">年龄是逐岗写的，主流是 28 周岁以下。</span>90 条里 59 个岗位要求 28 周岁以下，13 个要求 25 周岁以下，11 个 26 周岁以下，6 个 30 周岁以下，博士岗 35 周岁以下——<strong>没有统一的年龄线</strong>，投之前必须点开目标岗位看那一条。',
 f'<span style="color:{BRAND_DARK};font-weight:800;">流程没有笔试，是网申＋测评＋两轮面试。</span>官网校招流程：网申 2026年11月30日前、在线测评 2026年11月30日前、统一线上面试 2026年12月、线下面试 2026年12月至2027年1月、Offer 2027年春节前后。',
], numbers=['1.', '2.', '3.', '4.']))
h.append('</section>')

# ── 三宫格
h.append(tri_grid())

# ── 一、单位来头
h.append(sec_title('一、单位来头：上海市国资委全资的基础设施主力军'))
h.append(p('上海城投（集团）有限公司成立于 1992 年，前身是上海市城市建设投资开发总公司，2014 年改制为有限责任公司，由<strong>上海市国资委全资持有</strong>，是一家专业从事城市基础设施投资、建设、运营管理的国有特大型企业集团。集团官网披露的家底：'))
h.append(ul([
 '旗下 6 家子集团（城投公路、城投水务、城投资产、上海中心、城投环境、城投兴港）、2 家上市公司（城投控股、上海环境）、1 家科研机构（城投研究院），以及城投老港、长兴开发公司、长兴前卫公司、城投财务公司、城投环保金服公司等单位；',
 '聚焦<strong>路桥、水务、环境、置业</strong>四大业务板块，完成长江隧桥、青草沙水源地、老港再生能源利用中心、上海中心大厦等 300 余项市重大工程的投资建设任务；',
 '运营收费高速公路占全市 73%；原水供应能力占全市 98%，自来水生产、污水处理能力占全市 75%，防汛排水能力占浦东以外中心城区近 100%；承担全市 80% 生活垃圾转运和 100% 医废转运处置；',
 '截至 2023 年底，集团总资产近八千亿元，资产负债率 53%，现有员工 17000 多人（以上为集团官网简介口径）。',
]))
h.append(p('⚠️ 这份稿子的岗位数据取自招聘官网在挂的校招岗位，企业规模数据取自集团官网简介——两处口径与招聘海报上的宣传数字可能不一致，以官网原文为准。', 'font-size:13.5px;color:#64748b;'))

# ── 二、招什么人
h.append(sec_title('二、招什么人：90 个校招岗按学历拆开'))
h.append(p('招聘官网「校园招聘」频道在挂 <strong>90 个岗位</strong>，覆盖上海本部与金华、南平、宁波、湖州等外地项目。按学历要求分布如下：'))
h.append(edu_table())

h.append(p('<strong>14 个岗位专业不限（逐条取自官网岗位要求）</strong>：', 'margin-top:12px;'))
h.append(nomajor_table())

h.append(p('除上述专业不限岗外，其余岗位按专业方向设限，主要涵盖：工程类（土木、给排水、道路桥梁、水利）、电气类、自动化类、机械类、环境类、电子信息类、计算机类、经济学类、管理学类、人文社科类。'))

# ── 三、条件与禁入
h.append(sec_title('三、资格条件与硬门槛'))
h.append(f'<section style="background:{GRAY_BG};border-radius:8px;padding:12px 14px;margin:0 0 10px;">')
h.append(ul([
 '<strong>招聘对象</strong>：90 条岗位的岗位要求均写明「招聘对象：应届毕业生」，<strong>不要求工作经验</strong>；这与同站 105 个社招岗位（普遍要求 2–5 年相关经验）分属两个频道，别投错入口。',
 '<strong>学历</strong>：大专及以上 20 个、本科及以上 64 个、硕士研究生及以上 5 个、博士研究生 1 个，逐岗写明，没有跨档放宽的表述。',
 '<strong>年龄</strong>：按岗位分别写明「×× 周岁以下」，主流为 28 周岁以下（59 个岗位）；大专岗多为 25 周岁以下（13 个）；博士岗 35 周岁以下。',
 '<strong>专业</strong>：14 个岗位不限专业；其余按岗位对应专业方向审核，具体以官网岗位详情页为准。',
 '<strong>其他要求</strong>：多数岗位写明「人品正直，身心健康；遵纪守法；无犯罪记录」，部分写明「在本科及以上学历阶段取得奖学金者优先」；管网作业岗另注明需能适应值班与户外作业、有 C1 及以上驾照者优先。',
 '<strong>公告未披露项</strong>：各岗位<strong>招聘人数</strong>、统一笔面试合格线、体检具体指标，官网岗位页均未列出，需在投递后以招录单位通知为准。',
]))
h.append('</section>')

# ── 四、怎么报名
h.append(sec_title('四、怎么报名：一个入口、五个环节'))
h.append(p(f'网申入口只有招聘官网：<span style="color:{BRAND_DARK};font-weight:700;word-break:break-all;">https://chengtou.zhiye.com/</span>，进入「校园招聘」频道注册账号、按岗位投递简历。官网提示可在「个人中心」实时查询招聘进展。'))
h.append(flow_table())
h.append(p('⚠️ 两个容易踩的点：① <strong>在线测评与网申同为 11月30日前</strong>，不是网申完再等通知测评，两者都要在这个时点前完成；② 线上面试安排在 2026年12月、线下面试跨到 2027年1月，<strong>Offer 要到 2027年春节前后</strong>，秋招后期才出结果，别把它当成唯一备选。'))
h.append(p('官网披露的福利与培养口径（原文）：五险一金、企业年金、疗休养、年度体检、交通补贴、通讯补贴；「城聚英才」租房补贴、人才落户办理；入职集训到专业进阶的全周期课程、资深导师一对一带教、跨部门轮岗与行业沙龙、管理/专技/技能多路径晋升。'))

# ── FAQ
h.append(sec_title('五、校招常见问答（FAQ）'))
h.append(faq('Q1　上海城投2027校招什么时候截止网申？',
 '官网校招流程写明：网申与在线测评均需在 <strong>2026年11月30日前</strong>完成。之后统一线上面试在 2026年12月，线下面试在 2026年12月至2027年1月，Offer 于 2027年春节前后发放。'))
h.append(faq('Q2　上海城投2027校招大专生能报吗？',
 '能。90 个校招岗位里有 <strong>20 个学历要求为「大专及以上」</strong>，集中在运行操作岗（金华、南平、宁波、老港、天马、环慧、湖州阳晨等）、资源化维护岗（污水公司）、船舶清扫工、集卡驾驶、桥吊司机、车间操作工等一线技术岗，年龄多为 25 周岁以下。'))
h.append(faq('Q3　上海城投校招哪些岗位不限专业？',
 '共 <strong>14 个</strong>：管网作业岗（管网公司）、生产运维统计员（天马）、生产运维统计员（东石塘）、仓库管理员（环慧）、船舶轮机操作员、中控、物业运营、租赁运营、桥吊司机、集卡驾驶（本科）、船舶清扫工、船舶轮机、集卡驾驶（大专）、车间操作工。这些岗位的「专业」一栏写的是「不限」。'))
h.append(faq('Q4　往届生可以报上海城投2027校招吗？',
 '官网 90 条校招岗位的岗位要求均写明「招聘对象：应届毕业生」，且不要求工作经验。同站另有 105 个社会招聘岗位，普遍要求 2–5 年相关工作经验——往届生应走「社会招聘」频道，不要投校招入口。'))
h.append(faq('Q5　上海城投2027校招一共招多少人？',
 '官网校招频道在挂 <strong>90 个岗位</strong>，但<strong>各岗位的招聘人数未披露</strong>（岗位页只列岗位职责、学历、专业、年龄要求）。以岗位数计是 90 个，实际录用总量需以招录单位通知为准，不要按岗位数推算人数。'))
h.append(faq('Q6　上海城投校招有笔试吗？在线测评考什么？',
 '官网校招流程列的是「网申 → 在线测评 → 统一线上面试 → 线下面试 → 发放 Offer」，<strong>没有笔试环节</strong>。在线测评的具体内容与要求，官网未在流程页展开，投递后以系统通知为准。'))
h.append(faq('Q7　上海城投校招可以投几个岗位？',
 '招聘海报标注「每人最多可以投递 2 个岗位」。该口径来自集团招聘宣传材料，官网流程页未重复说明，实际以报名系统内的投递上限提示为准——投递前先在系统里确认一次。'))
h.append(faq('Q8　上海市外高校的应届生能报上海城投吗？',
 '可以。岗位分布在城投公路、城投水务、城投环境、城投资产等板块，除上海本部外还有金华、南平、宁波、湖州等外地项目岗。岗位要求中未见户籍限制表述；具体到某个岗位是否限定工作地，以官网岗位详情页为准。'))

# ── CTA
CTA_PATH = '/Users/zhugx/codeup/obsidian/03-工作记录/码上职业/素材/组件/cta-客服码单码.html'
cta = open(CTA_PATH, encoding='utf-8').read()
cta = cta.replace('#0085d0', BRAND).replace('#003876', BRAND_DARK)
h.append(cta)
h.append('</section>')   # 闭合根容器（CTA 片段自身已 4/4 配平，不再额外补）
h.append('</body></html>')

html = '\n'.join(h)

# ── 断言
open_sect, close_sect = html.count('<section'), html.count('</section>')
assert open_sect == close_sect, f'⛔ section 配平失败: {open_sect}/{close_sect}'
assert html.count('招聘信息不漏接') == 1, '⛔ CTA 重复'
assert not re.findall(r"#(?:c8102e|800000|991b1b|E2211C|0085d0|003876|007068|00483F)", html, re.I), '⛔ 残留别家主题色'
assert '<div' not in html and 'position:' not in html, '⛔ div/position'
assert html.count('<th ') == 0, '⛔ 表头用了 th'
assert 'src="http' not in html, '⛔ 外部图片链接'
assert '<title>' in html, '⛔ 缺 title'
for k in ['码上君划重点', '一、单位来头', '二、招什么人', '三、资格条件', '四、怎么报名', '五、校招常见问答']:
    assert k in html, f'⛔ 段组件丢失: {k}'
# 守恒：90 个岗位
_edu = sum(int(r[1]) for r in EDU_ROWS)
assert _edu == 90, f'⛔ 学历分层合计 {_edu} ≠ 90'
assert len(NO_MAJOR) == 14, f'⛔ 专业不限岗位 {len(NO_MAJOR)} ≠ 14'

html = re.sub(r'(?<=>)(?=<)', chr(10), html)
open(OUT, 'w', encoding='utf-8').write(html)
print(f'OK 已写出 {OUT}')
print(f'section 配平: {open_sect}/{close_sect} ｜ <strong>: {html.count("<strong>")} ｜ 字节: {len(html)}')
print(f'TITLE {len(TITLE)} 字 ｜ DIGEST {len(DIGEST)} 字')
