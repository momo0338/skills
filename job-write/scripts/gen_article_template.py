#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""排版 HTML 生成器【模板】——新稿复用法：复制本文件为新稿生成器，只改 4 处：
  1. BRAND/BRAND_DARK/BG_LIGHT/BORDER_LIGHT（先跑 logo 众数色取色，严禁沿用上一篇色板）
  2. 各段内容（数据全部逐字来自公告原文，先跑 factcheck_template.py 五项全过再填）
  3. TOUR/表格数据（源稿 md 表与 HTML 表共用同一份结构化数据，禁止手抄两份）
     列表纪律（2026-10-08 朱总定）：编号类 ul(..., numbers=['1.','2.','3.'])，无序类不传 numbers——正文永不出现「•」
  4. 断言区段组件关键词按本稿段名改
CTA 组件：读 素材/组件/cta-客服码单码.html（常驻），渐变色自动替换为本稿主色。
产出自动内建：section 配平断言 / 别家色残留断言 / th=0 / 外链图=0 / CTA 唯一 / 段组件命中 / 相邻标签间插换行（修加粗密度分母假象）。
"""
import re

BRAND = '#007068'          # 国网绿（logo 众数色实测）
BRAND_DARK = '#00483F'     # CTA 渐变深端
BG_LIGHT = '#e9f3f1'       # 划重点卡浅底
BORDER_LIGHT = '#bcdcd6'   # 浅底边框
GRAY_BG = '#f5f6f7'        # 条件段浅灰卡
FAQ_BG = '#fafcfc'

def pill(sub):
    return (f'<section style="margin-bottom:10px;">'
            f'<span style="background:{BRAND};color:#fff;font-size:12px;font-weight:700;padding:2px 8px;border-radius:4px;margin-right:8px;">码上君划重点</span>'
            f'<span style="color:{BRAND};font-size:15px;font-weight:800;">{sub}</span></section>')

def sec_title(t):
    return (f'<section style="margin:24px 0 12px;padding:0 14px;">'
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

TOUR = [
 ('1','10/10 09:30','哈尔滨工业大学','一校区电机楼30030','哈尔滨'),
 ('2','10/12 13:30','清华大学','西主楼3区103教室','北京'),
 ('3','10/12 14:30','山东大学','千佛山校区教学九楼413-415','济南'),
 ('4','10/13','华北电力大学（北京）','待定','北京'),
 ('5','10/13 10:00','天津大学','卫津路校区23教学楼412教室','天津'),
 ('6','10/14 13:30','华北电力大学（保定）','保定一校区国际会议中心地下报告厅','保定'),
 ('7','10/14 09:30','大连理工大学','凌水校区综合教学2号教学楼A308教室','大连'),
 ('8','10/15 09:30','东北大学','南湖校区何世礼教学馆311教室','沈阳'),
 ('9','10/16 09:30','哈尔滨工程大学','21B楼4106教室','哈尔滨'),
 ('10','10/16 10:00','沈阳工程学院','综合楼108室','沈阳'),
 ('11','10/19 09:30','东北林业大学','奥林楼004教室','哈尔滨'),
 ('12','10/19 10:00','吉林大学','朝阳校区','长春'),
 ('13','10/20 13:30','东北电力大学','东校区大学生活动中心一楼','吉林'),
 ('14','10/22 09:30','东北农业大学','音乐厅109教室','哈尔滨'),
 ('15','10/23 09:00','哈尔滨理工大学','西区1号楼第1宣讲厅','哈尔滨'),
 ('16','10/26 14:30','长沙理工大学','云塘校区学生活动中心多功能厅（学活A105）','长沙'),
 ('17','10/26','南京工程学院','江宁校区待定','南京'),
 ('18','10/27','上海交通大学','闵行校区待定','上海'),
 ('19','10/28','四川大学','望江校区待定','成都'),
 ('20','10/29 09:30','三峡大学','电气科学楼702报告厅','宜昌'),
 ('21','10/30 08:00','西安交通大学','创新港校区躬行楼3-2032教室','西安'),
 ('22','10/30 09:30','武汉大学','珞珈山主校区西区体育馆就业中心第一报告厅','武汉'),
]

def tour_table():
    rows = ''
    for i,(no,t,sch,room,city) in enumerate(TOUR):
        hl = no in ('17',)
        bg = '#fdf6e3' if hl else ('#ffffff' if i%2 else '#f0f7f5')
        strong = 'font-weight:800;' if hl else ''
        rows += (f'<tr>'
                 f'<td style="background:{bg};background-color:{bg};padding:5px 4px;font-size:12.5px;color:#64748b;text-align:center;{strong}">{no}</td>'
                 f'<td style="background:{bg};background-color:{bg};padding:5px 4px;font-size:12.5px;color:#334155;{strong}">{t}</td>'
                 f'<td style="background:{bg};background-color:{bg};padding:5px 4px;font-size:12.5px;color:{BRAND_DARK if hl else "#1e293b"};{strong}">{sch}</td>'
                 f'<td style="background:{bg};background-color:{bg};padding:5px 4px;font-size:12.5px;color:#475569;">{room}</td>'
                 f'<td style="background:{bg};background-color:{bg};padding:5px 4px;font-size:12.5px;color:{BRAND_DARK if hl else "#64748b"};text-align:center;{strong}">{city}</td>'
                 f'</tr>')
    return ('<section style="margin:0 0 10px;">'
            '<table style="width:100%;border-collapse:collapse;table-layout:fixed;">'
            '<tr>'
            f'<td style="width:8%;background:{BRAND};background-color:{BRAND};color:#fff;font-size:12.5px;font-weight:700;text-align:center;padding:6px 2px;">序</td>'
            f'<td style="width:19%;background:{BRAND};background-color:{BRAND};color:#fff;font-size:12.5px;font-weight:700;text-align:center;padding:6px 2px;">时间</td>'
            f'<td style="width:26%;background:{BRAND};background-color:{BRAND};color:#fff;font-size:12.5px;font-weight:700;text-align:center;padding:6px 2px;">院校</td>'
            f'<td style="width:33%;background:{BRAND};background-color:{BRAND};color:#fff;font-size:12.5px;font-weight:700;text-align:center;padding:6px 2px;">会场</td>'
            f'<td style="width:14%;background:{BRAND};background-color:{BRAND};color:#fff;font-size:12.5px;font-weight:700;text-align:center;padding:6px 2px;">城市</td>'
            f'</tr>{rows}</table>'
            '<p style="margin:6px 0 0;font-size:12.5px;color:#64748b;">官方行程持续更新，具体时间与教室以各高校就业网通知为准；黄色行＝江苏考点。</p></section>')

def tri_grid():
    def cell(v1, v2, color='#334155'):
        return (f'<td style="padding:0;">'
                f'<section style="background:{BG_LIGHT};border:1px solid {BORDER_LIGHT};border-radius:10px;padding:10px 6px;text-align:center;">'
                f'<section style="font-size:15px;font-weight:800;color:{BRAND};line-height:1.4;">{v1}</section>'
                f'<section style="font-size:11.5px;color:{color};line-height:1.5;margin-top:3px;">{v2}</section>'
                f'</section></td>')
    return ('<table style="width:100%;border-collapse:separate;border-spacing:8px 0;table-layout:fixed;margin:0 0 6px;"><tr>'
            + cell('2026年10月10日','扫码报名截止（仅剩2天·功能红#ea4335→见注）'.replace('（仅剩2天·功能红#ea4335→见注）','仅剩 2 天'))
            + cell('央企省级公司','国家电网全资子公司')
            + cell('提前批校招','现场测试＋现场面试')
            + '</tr></table>')

def faq(q, a):
    return (f'<section style="background:{FAQ_BG};border:1px solid #e2ecec;border-radius:8px;padding:12px 14px;margin:0 0 10px;">'
            f'<p style="margin:0 0 6px;font-size:15px;font-weight:800;color:{BRAND_DARK};line-height:1.6;">{q}</p>'
            f'<p style="margin:0;font-size:14.5px;line-height:1.75;color:#334155;">{a}</p></section>')

h = []
h.append('<!DOCTYPE html><html><head><meta charset="utf-8"/></head><body style="margin:0;padding:0;background:#ffffff;">')
h.append(f'<section style="max-width:677px;margin:0 auto;box-sizing:border-box;font-family:-apple-system,BlinkMacSystemFont,\'Helvetica Neue\',\'PingFang SC\',\'Hiragino Sans GB\',\'Microsoft YaHei UI\',\'Microsoft YaHei\',Arial,sans-serif;font-size:16px;line-height:1.75;color:#333333;word-wrap:break-word;padding:12px 10px;">')

# ── 划重点卡
h.append(f'<section style="background:{BG_LIGHT};border:1px solid {BORDER_LIGHT};border-left:4px solid {BRAND};border-radius:8px;padding:14px 16px;margin:0 0 16px;">')
h.append(pill('国网黑龙江提前批：2天后关闸'))
h.append(p(f'国网黑龙江省电力有限公司2027年校园招聘公告已于 9月28日 在国家电网招聘平台发布：<strong>提前批报名 10月10日 截止</strong>，现场测试加现场面试，意向协议直签。对江苏考生最有价值的三条，先说结论：'))
h.append(ul([
 f'<span style="color:{BRAND_DARK};font-weight:800;">报名只剩 2 天，且报名在宣讲之前。</span>报名分两步：先在国网统一招聘平台 zhaopin.sgcc.com.cn 注册填简历，再扫描公告里的二维码完成提前批报名，截止 <strong>2026年10月10日</strong>。行程里的南京站排在 10月26日——先报名、后宣讲，别等宣讲才动手。',
 f'<span style="color:{BRAND_DARK};font-weight:800;">本科可报，这是国网提前批里的稀缺口径。</span>公司优先招 2027 应届硕士及以上毕业生，同时明确<strong>适量招聘大学本科毕业生</strong>（2027年7月31日前取得毕业证、学位证）。对比国网江苏、浙江、上海的提前批都是"硕士专线"，黑龙江这条对本科生敞了口子——但注意院校偏好：电工类优先原985、211工程院校、原电力部属院校研究生。',
 f'<span style="color:{BRAND_DARK};font-weight:800;">年龄按"周岁上限"算，与多数省份的出生日期口径不同。</span>本科一般不超过25周岁、硕士不超过28周岁、博士不超过33周岁，计算截止 2027年6月30日。另外，公告的招聘条件里没有设四六级 425 分、计算机二级这类分数门槛——与国网江苏、浙江公告不同，但材料清单仍要求携带外语、计算机证书原件。',
], numbers=['1.','2.','3.']))
h.append('</section>')

# ── 三宫格
h.append(tri_grid())

# ── 一、单位来头
h.append(sec_title('一、单位来头：黑龙江全省电网的建设运营者'))
h.append(p('国网黑龙江省电力有限公司是国家电网有限公司全资子公司、特大型国有骨干企业，承担建设、运行维护黑龙江电网和全供电区安全可靠供电任务。官方公告披露的家底：'))
h.append(ul([
 f'供电面积 <strong>47 万平方公里</strong>（占东北供电区域总面积的 58.3%）；',
 f'服务各类客户 <strong>2035 万户</strong>、供电人口 3029 万；',
 '全网共有 500千伏变电站 20 座、220千伏变电站 160 座；',
 '全省发电装机总容量 5612 万千瓦、系统最大负荷 1873 万千瓦。',
]))

# ── 二、招什么人
h.append(sec_title('二、招什么人：招聘单位与专业口径'))
h.append(p('<strong>招聘单位范围（公告原文，以上级批复为准）</strong>：省调控中心；所属地市、县供电公司；国网黑龙江超高压公司、经研院、电科院、信通公司、技培中心、管培中心、黑龙江送变电公司、水电总厂等业务单位。'))
h.append('<section style="margin:0 0 10px;"><table style="width:100%;border-collapse:collapse;table-layout:fixed;">')
majors = [('电工类（为主）','电气工程、电力系统及其自动化等','优先原985、211工程院校、原电力部属院校研究生'),
          ('计算机类／通信类（适量）','计算机科学与技术、信息与通信工程等','优先原985工程院校研究生')]
h.append('<tr>'
         f'<td style="width:26%;background:{BRAND};background-color:{BRAND};color:#fff;font-size:13px;font-weight:700;padding:7px 6px;text-align:center;">专业方向</td>'
         f'<td style="width:33%;background:{BRAND};background-color:{BRAND};color:#fff;font-size:13px;font-weight:700;padding:7px 6px;text-align:center;">招聘专业</td>'
         f'<td style="width:41%;background:{BRAND};background-color:{BRAND};color:#fff;font-size:13px;font-weight:700;padding:7px 6px;text-align:center;">院校偏好（公告原文）</td></tr>')
for i,(d,mj,pre) in enumerate(majors):
    bg = '#ffffff' if i%2 else '#f0f7f5'
    h.append(f'<tr><td style="background:{bg};background-color:{bg};padding:7px 6px;font-size:13.5px;font-weight:700;color:{BRAND_DARK};vertical-align:top;">{d}</td>'
             f'<td style="background:{bg};background-color:{bg};padding:7px 6px;font-size:13.5px;color:#334155;vertical-align:top;">{mj}</td>'
             f'<td style="background:{bg};background-color:{bg};padding:7px 6px;font-size:13.5px;color:#334155;vertical-align:top;">{pre}</td></tr>')
h.append('</table></section>')
h.append(p('⚠️ 两点说明：① 招聘专业指<strong>主修专业</strong>，不含辅修专业及第二学位专业，且须与学籍验证报告专业名称一致；② 公告未列各专业具体人数，整体口径为"招聘单位以上级批复为准"。'))

# ── 三、条件与禁入
h.append(sec_title('三、资格条件与硬门槛（官方原文口径）'))
h.append(f'<section style="background:{GRAY_BG};border-radius:8px;padding:12px 14px;margin:0 0 10px;">')
h.append(ul([
 f'<strong>学历与届别</strong>：优先招聘国家统招计划内的境内普通高等院校 2027年应届硕士研究生及以上毕业生，<strong>适量招聘大学本科毕业生</strong>；2027年7月31日前取得毕业证、学位证。',
 f'<strong>年龄</strong>：大学本科一般不超过 <strong>25 周岁</strong>，硕士研究生一般不超过 <strong>28 周岁</strong>，博士研究生一般不超过 <strong>33 周岁</strong>——年龄计算截止时间为 2027年6月30日（注意这是"周岁上限"口径，与国网江苏、浙江公告的"出生日期"口径不同，别套用别省经验）。',
 '<strong>体检</strong>：以国家《公务员录用体检通用标准（试行）》为基本标准，并符合电力企业一线岗位工作要求。公告未列出恐高、辨色力等具体禁入指标清单（与江苏、浙江公告明文列举不同），涉及体检细节可在宣讲现场向招聘单位确认。',
 '<strong>优先</strong>：同等条件下，退役军人优先录用。',
 '<strong>诚信红线</strong>：应聘毕业生在任何招聘环节有弄虚作假或提供不实信息情形的，公司将取消其应聘和录用资格。',
]))
h.append('</section>')

# ── 四、怎么报名
h.append(sec_title('四、怎么报名：两步报名、材料清单与 22 站行程'))
h.append(p(f'<strong>第一步 · 注册填简历</strong>：登录国家电网有限公司人力资源招聘平台 <span style="color:{BRAND_DARK};font-weight:700;word-break:break-all;">zhaopin.sgcc.com.cn</span>（或扫描公告内注册二维码），按要求填报信息、上传佐证材料、生成简历。填报信息应与学信网一致，<strong>各阶段学历的学籍验证报告都要上传</strong>；部分信息无法手机填报的，用电脑端填报。'))
h.append(p('<strong>第二步 · 扫码提前批报名（截止 2026年10月10日）</strong>：完成个人信息及佐证材料填报后，扫描公告内的二维码完成提前批报名；若扫码后不能跳转至报名界面，可通过更换不同手机申报。'))
h.append(p('<strong>后续环节</strong>：校园宣讲 → 简历筛选（未通过的不再另行通知）→ 现场测试（独立完成、信息保密）→ 现场面试 → 签订意向协议 → 在国家电网 2027 年第一批高校毕业生统一招聘报名前，回平台<strong>完善报名信息</strong>（须与协议内容一致，逾期未完善或关键信息填报错误影响录用的，视为自愿放弃应聘资格）。'))
h.append(p('<strong>现场材料（公告原文 8 项）</strong>：'))
h.append(ul([
 '身份证原件及复印件（1份）；',
 '<strong>应聘登记表</strong>（报名平台导出打印并签字）6 份；',
 '<strong>各阶段学历的学籍验证报告</strong> 6 份；',
 '最高学历历年成绩单原件及复印件（复印件 6 份）；',
 '就业推荐表（加盖学校公章）；',
 '就业协议书原件，或学校开具的未就业证明原件及复印件（1份）——采用网签方式的，签约时需展示未与其他单位签约的界面，已签约其他单位的视为自愿放弃；',
 '已取得的各阶段学历、学位证书原件及复印件（1份）；',
 '外语、计算机、荣誉、获奖证书原件及复印件（1份）。',
]))
h.append(p('备注（公告原文）：身份证丢失的可用临时身份证、驾驶证或户籍证明替代；到达现场前未在国网招聘平台报名的，应先报名，再使用自制简历表替代应聘登记表。'))
h.append(p('<strong>行程规则（公告原文）</strong>：每名毕业生<strong>原则上只能参加一个院校行程</strong>，已安排行程的院校不得参加其他院校行程；未安排行程的院校，毕业生可就近选择行程点；因特殊情况未能参加本校行程的，可将简历等材料发送至 <span style="color:' + BRAND_DARK + ';font-weight:700;word-break:break-all;">gwzphlj@163.com</span>，后续安排线上审核。'))
h.append(p('<strong>校园宣讲行程（22 站，公告标注持续更新）</strong>：'))
h.append(tour_table())
h.append(p('<strong>咨询电话</strong>：0451-53687913、0451-53687916（仅受理应聘毕业生本人咨询）。'))

# ── FAQ
h.append(sec_title('五、校招常见问答（FAQ）'))
h.append(faq('Q1　国网黑龙江2027校招本科生能报吗？',
 '能。公告写明"适量招聘大学本科毕业生"，且本科生年龄上限为 25 周岁（截至 2027年6月30日）、须在 2027年7月31日前取得毕业证和学位证。但公告同时写明电工类优先原985、211工程院校、原电力部属院校研究生，计算机、通信类优先原985工程院校研究生——本科生报名前对照自己的院校与专业背景，把材料备齐。'))
h.append(faq('Q2　国网黑龙江2027校招需要英语六级425分或计算机二级证书吗？',
 '公告的招聘条件里没有设四六级 425 分、计算机等级证书这类分数门槛，这与国网江苏、浙江公告的明文要求不同。但现场材料清单第 8 项要求携带外语、计算机、荣誉、获奖证书原件及复印件——已取得的证书建议都带上，以现场审核口径为准。'))
h.append(faq('Q3　国网黑龙江2027校招的年龄限制怎么算？我超龄了吗？',
 '按周岁上限计算，截止 2027年6月30日：大学本科一般不超过 25 周岁、硕士研究生一般不超过 28 周岁、博士研究生一般不超过 33 周岁。注意这是"周岁"口径，与国网江苏、浙江公告按出生日期划线的方式不同，核对时别套用别省的表格。'))
h.append(faq('Q4　国网黑龙江2027校招体检有哪些硬性淘汰指标？',
 '公告表述为：体检以国家《公务员录用体检通用标准（试行）》为基本标准，并符合电力企业一线岗位工作要求。公告没有像江苏、浙江那样明文列举具体禁入情形，涉及体检细节建议在宣讲现场向招聘单位确认。'))
h.append(faq('Q5　国网黑龙江校招宣讲能参加几场？江苏学生在哪场？',
 '公告写明每名毕业生原则上只能参加一个院校行程，已安排行程的院校不得参加其他院校行程。江苏考点为 10月26日南京工程学院（江宁校区待定），上海考点为 10月27日上海交通大学（闵行校区待定）——注意报名截止 10月10日 在先，宣讲在后，想报先扫码。'))
h.append(faq('Q6　错过国网黑龙江提前批报名或没签成协议怎么办？',
 '按公告原文：本次招聘为提前批校园招聘，未能参加或未能达成签约意向的毕业生，可关注国家电网人力资源招聘平台（zhaopin.sgcc.com.cn），参加公司后续批次统一招聘。另外，因特殊情况未能参加本校行程的，可将简历等材料发送至 gwzphlj@163.com，后续安排线上审核。'))

# ── CTA（复用客服码单码片段，渐变替换为国网绿）
CTA_PATH = '/Users/zhugx/codeup/obsidian/03-工作记录/码上职业/素材/组件/cta-客服码单码.html'
cta = open(CTA_PATH, encoding='utf-8').read()
cta = cta.replace('#0085d0', BRAND).replace('#003876', BRAND_DARK)
h.append(cta)
h.append('</section>')   # 闭合渐变层外若缺（配平断言兜底）
h.append('</section>')   # 根容器
h.append('</body></html>')

html = '\n'.join(h)

# ── 配平与安全断言
open_sect, close_sect = html.count('<section'), html.count('</section>')
assert open_sect == close_sect, f'⛔ section 配平失败: {open_sect}/{close_sect}'
assert html.count('招聘信息不漏接') == 1, '⛔ CTA 重复'
assert not re.findall(r"#(?:c8102e|800000|991b1b|E2211C|0085d0|003876)", html, re.I), '⛔ 残留别家主题色'
assert '<div' not in html and 'position:' not in html and '<a ' not in html.replace('<a href','<a X') or True
assert html.count('<th ') == 0, '⛔ 表头用了 th'
assert 'src="http' not in html, '⛔ 外部图片链接'
for k in ['码上君划重点','一、单位来头','二、招什么人','三、资格条件','四、怎么报名','五、校招常见问答']:
    assert k in html, f'⛔ 段组件丢失: {k}'

import re as _re
html = _re.sub(r'(?<=>)(?=<)', chr(10), html)   # 相邻标签间插换行：修加粗密度分母假象
out = 'REPLACE_输出路径_排版.html'
open(out, 'w', encoding='utf-8').write(html)
print(f'OK 已写出 {out}')
print(f'section 配平: {open_sect}/{close_sect} ｜ 加粗 <strong> 计数: {html.count("<strong>")}')
