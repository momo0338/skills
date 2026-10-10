#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""江苏省体育局稿排版生成器（B线首篇走 layout_kit 2026-10-09 规范）"""
import sys, os
sys.path.insert(0, os.path.expanduser('~/src/skills/mp-html/scripts'))
from layout_kit import Layout

WS = '/Users/zhugx/codeup/obsidian/03-工作记录/码上职业/事业单位/待发布/'
OUT = WS + '2026-10-10-江苏省体育局直属事业单位5人-排版.html'

L = Layout(brand='#1A4E93', brand_dark='#123C6E', bg_light='#EAF1F9',
           border_light='#C5D5EA', faq_bg='#F7F8FA', faq_border='#E2E8F0')

parts = []
parts.append(L.doc_open('江苏省体育局直属事业单位招5人：全额拨款进编，足球教练不限专业，10月14日止'))

# 1. 划重点卡
parts.append(L.highlight_card(
    '江苏省体育局直属事业单位 2026 统一招聘',
    '这是一次省体育局系统三家直属全额拨款事业单位的统一招聘：4 个岗位 5 个人，全部进编，'
    '10 月 10 日上午 9 点刚开报，01-03 岗只给 5 天窗口。依据：10 月 9 日江苏省人力资源和社会保障厅'
    '《江苏省体育局直属事业单位2026年统一公开招聘人员公告》。',
    ['<strong>4 岗全部进编、全额拨款</strong>，均为专业技术岗位；',
     '足球教练员岗<strong>专业不限</strong>、本科可报（学位无要求），招 2 人；',
     '<strong>单科 60 分才合格</strong>，任一科目低于 60 分直接出局；',
     '01-03 岗 10 月 14 日 16:00 截止（开考比例 1:3）；04 博士岗 10 月 21 日截止、招满即止。'],
    numbers=['1.', '2.', '3.', '4.']))

# 2. 数据三宫格
parts.append(L.quad_grid([
    ('10月14日16:00', '01-03岗报名截止；04岗10月21日止'),
    ('进编', '全额拨款·省体育局直属事业单位'),
    ('5人', '4个岗位·足球教练不限专业'),
]))

# 3. 单位来头
parts.append(L.sec_title('单位来头：省体育局三家直属训练科研单位'))
parts.append(L.p('本次招聘的三家单位均为江苏省体育局直属全额拨款事业单位：江苏省体育局训练中心和江苏省体育科学研究所'
                 '位于南京市栖霞区仙林大道 169 号，江苏省足球运动管理中心（江苏省江宁足球训练基地）位于南京市江宁区'
                 '神凤路 1167 号。训练中心承担专业运动队训练保障，体科所承担竞技体育科技攻关与学术出版，'
                 '江宁基地是江苏省足球的专业训练大本营。'))

# 4. 码上君解读（黄底四问卡）
parts.append(
    '<section style="background:#FFF9E6;border:1px solid #F0E2B6;border-radius:8px;padding:14px 16px;margin:0 0 16px;">'
    '<p style="margin:0 0 8px;font-size:15px;font-weight:800;color:#8A6100;line-height:1.5;">码上君解读（求职者最关心的四个必答问题）</p>'
    '<p style="margin:0 0 7px;font-size:14.5px;line-height:1.75;color:#334155;"><strong>1. 是不是正式编？</strong> '
    '<strong style="color:#0F5132;">是。</strong>岗位表 4 个岗位「其他说明」栏全部标注「进编」，经费来源均为全额拨款。'
    '签订 3 年以上（含试用期）聘用合同的，应当在单位最低服务 3 年（含试用期）。薪酬待遇标准公告未披露。</p>'
    '<p style="margin:0 0 7px;font-size:14.5px;line-height:1.75;color:#334155;"><strong>2. 谁可以报考？</strong>'
    '01-03 岗招聘对象均为<strong>社会人员</strong>（应往届均可）；04 岗<strong>限 2026 年毕业生</strong>且要求博士学历。'
    '年龄一律 18—38 周岁（1987 年 10 月 10 日后出生），博士岗放宽到 40 周岁（1985 年 10 月 10 日后出生）。户籍不限。</p>'
    '<p style="margin:0 0 7px;font-size:14.5px;line-height:1.75;color:#334155;"><strong>3. 考试怎么考？</strong>'
    '01 岗＝笔试 50%＋专业技能测试 50%；02 岗＝笔试 30%＋技能测试 30%＋公开课试讲 40%；03 岗＝笔试 50%＋面试 50%；'
    '04 岗＝仅面试。<strong>各单科 60 分合格线，任一科目低于 60 分直接出局</strong>。技能测试/试讲/面试当场出分，'
    '笔试成绩考后在江苏体育网公布。</p>'
    '<p style="margin:0;font-size:14.5px;line-height:1.75;color:#334155;"><strong>4. 到哪儿报名、问谁？</strong>'
    '统一走「江苏省属事业单位公开招聘平台」：<strong>rs.jshrss.jiangsu.gov.cn/index/f/RCRS_0056</strong>；'
    '政策咨询 01 岗 025-85788036（冯老师）、02 岗 025-52709463（张老师）、03/04 岗 025-84431875（何老师）；'
    '监督 025-51889615（省体育局机关纪委）。</p></section>')

# 5. 招什么人（岗位表）
parts.append(L.sec_title('招什么人：官方岗位表 4 个岗位全解析'))
parts.append(L.note('数据源自江苏省人力资源和社会保障厅官网挂载附件《江苏省体育局2026年直属事业单位统一公开招聘人员公告岗位信息表》，经 100% 原文比对核准：'))
parts.append(L.table(
    [('序号','8%'),('岗位名称','22%'),('人数','7%'),('用人方式','9%'),('学历/学位','17%'),('需求专业','22%'),('考核方式','15%')],
    [
     ['1','队医（省体育局训练中心）','1','进编','本科及以上/相应学位','针灸推拿学、中医学、运动人体科学、运动康复、康复治疗学','笔试50%＋技能测试50%'],
     ['2','足球教练员（江宁足球训练基地）','2','进编','本科及以上/学位无要求','<strong>不限</strong>','笔试30%＋技能测试30%＋试讲40%'],
     ['3','编辑（省体育科学研究所）','1','进编','硕士研究生及以上/相应学位','新闻学、传播学、出版、语言学及应用语言学','笔试50%＋面试50%'],
     ['4','竞技体育科研人员（省体科所）','1','进编','博士研究生/相应学位','运动人体科学、康复医学与理疗学、中医骨伤科学、运动医学、体育教育训练学、运动康复学','面试100%'],
    ],
    [8,22,7,9,17,22,15]))
parts.append(L.p('<strong>招录合计：5 人</strong>（4 个岗位均为专业技术岗位，经费来源均为全额拨款；01-03 岗开考比例 1:3，'
                 '04 岗不设开考比例，体检、考察比例均为 1:1）。'))
parts.append(L.p('⚠️ 岗位表「其他说明」栏同时提示：01、02 岗<strong>单位地处偏远</strong>、需跟运动队出差服务较多；'
                 '03、04 岗<strong>出差加班较多</strong>——介意通勤与驻队节奏的读者投前想清楚。'))

# 6. 资格条件与红线禁入
parts.append(L.sec_title('资格条件与红线禁入'))
parts.append(
    '<section style="background:#F7F8FA;border:1px solid #E2E8F0;border-radius:8px;padding:12px 14px;margin:0 0 10px;">'
    '<p style="margin:0 0 6px;font-size:14.5px;line-height:1.75;color:#334155;">'
    '<span style="border-left:4px solid #1A4E93;padding-left:8px;color:#1A4E93;font-weight:800;">年龄红线</span><br/>'
    '18 周岁以上、38 周岁以下（<strong>1987 年 10 月 10 日之后出生</strong>）；应聘 04 博士岗位的放宽至 40 周岁以下'
    '（1985 年 10 月 10 日之后出生）。</p>'
    '<p style="margin:0;font-size:14.5px;line-height:1.75;color:#334155;">'
    '<span style="border-left:4px solid #1A4E93;padding-left:8px;color:#1A4E93;font-weight:800;">各岗硬门槛（缺一不可）</span><br/>'
    '01 队医：省级及以上专业运动队 2 年及以上队医工作经历＋医师资格证书或康复治疗师证书或运动防护师资格；'
    '02 足球教练员：中国足协 C 级及以上教练员执教资格证书或初级教练员职称及以上＋2 年以上专业运动队经历或 3 年以上足球执教经历；'
    '03 编辑：中级及以上出版专业技术人员职业资格＋期刊出版发行工作 2 年及以上；'
    '04 科研人员：以第一作者或通讯作者在核心期刊发表运动损伤与康复相关论文不少于 1 篇，且限 2026 年毕业生。</p></section>')
parts.append(
    '<section style="background:#F7F8FA;border:1px solid #E2E8F0;border-radius:8px;padding:12px 14px;margin:0 0 10px;">'
    '<p style="margin:0;font-size:14.5px;line-height:1.75;color:#334155;">'
    '<span style="border-left:4px solid #1A4E93;padding-left:8px;color:#1A4E93;font-weight:800;">专业认定</span><br/>'
    '参照《江苏省2026年度考试录用公务员专业参考目录》；专业名称已调整的，院校书面证明调整前后为同一专业或课程基本一致，视为符合。</p></section>')
parts.append(
    '<section style="background:#FEF2F2;border:1px solid #FCA5A5;border-radius:8px;padding:12px 14px;margin:0 0 16px;">'
    '<p style="margin:0 0 6px;font-size:14.5px;line-height:1.75;color:#991B1B;font-weight:800;">严禁报名情形（有其一即不要报名）</p>'
    '<p style="margin:0;font-size:14.5px;line-height:1.75;color:#991B1B;">现役军人或普通高校在读非 2026 届毕业生｜'
    '与事业单位负责人员有夫妻、直系血亲、三代以内旁系血亲或近姻亲等关系，以及《事业单位人事管理回避规定》明确应当回避的岗位｜'
    '5 年服务期未满的新录用公务员、经公开招聘被江苏省地方各类事业单位聘用且 3 年服务期未满的在编（在册）人员、'
    '有规定（含协议明确）不得解聘离开现工作单位（岗位）的人员｜国家、江苏省另有规定不得应聘到事业单位的人员。</p></section>')

# 7. 怎么报名
parts.append(L.sec_title('怎么报名：官方平台网申 + 关键时间轴'))
parts.append(
    '<section style="background:#E5EDF7;border:1px solid #C5D5EA;border-radius:8px;padding:12px 14px;margin:0 0 10px;">'
    '<p style="margin:0 0 6px;font-size:14.5px;color:#1A4E93;font-weight:800;">报名网址（请手动复制到浏览器打开）</p>'
    '<p style="margin:0;font-size:14.5px;font-weight:700;color:#333;word-break:break-all;line-height:1.7;">'
    'https://rs.jshrss.jiangsu.gov.cn/index/f/RCRS_0056</p></section>')
parts.append(
    '<section style="background:#F7F8FA;border:1px solid #E2E8F0;border-radius:8px;padding:12px 14px;margin:0 0 16px;">'
    '<p style="margin:0 0 6px;font-size:14.5px;line-height:1.75;color:#334155;"><span style="color:#1A4E93;">1. 01-03 岗：</span>'
    '报名、照片上传及修改补充信息 <strong>10 月 10 日 9:00 — 10 月 14 日 16:00</strong>；资格初审至 10 月 15 日 16:00；'
    '陈述申辩 10 月 10 日—16 日 9:00-16:00；对初审异议的处理至 10 月 16 日 17:00。</p>'
    '<p style="margin:0 0 6px;font-size:14.5px;line-height:1.75;color:#334155;"><span style="color:#1A4E93;">2. 04 岗：</span>'
    '报名 <strong>10 月 10 日 9:00 — 10 月 21 日 16:00</strong>；资格初审至 10 月 22 日 16:00；陈述申辩至 10 月 23 日；'
    '异议处理至 10 月 23 日 18:00。</p>'
    '<p style="margin:0 0 6px;font-size:14.5px;line-height:1.75;color:#334155;"><span style="color:#1A4E93;">3. 统一规则：</span>'
    '本次招聘<strong>不收报名费</strong>，通过初审即报名成功；提交 24 小时后（节假日顺延）可查初审结果；'
    '<strong>资格初审通过后不能再改报名信息</strong>；照片要求近期免冠正面二寸（35×45 毫米）证件照、jpg 格式、20KB 以下；'
    '「考生简历」从高中填起、经历时间勿中断，应届生须备注「未落实工作单位」。</p>'
    '<p style="margin:0 0 6px;font-size:14.5px;line-height:1.75;color:#334155;"><span style="color:#1A4E93;">4. 考试安排：</span>'
    '01/02/03 岗笔试 <strong>10 月 24 日</strong>；10 月 20 日 9:00 起登录报名平台打印准考证，不按规定打印不得参加考试。'
    '01 岗技能测试、03 岗面试时间地点邮件通知；04 岗不设开考比例，公告发布 7 个工作日后不定期启动考核、<strong>招满即止</strong>。</p>'
    '<p style="margin:0;font-size:14.5px;line-height:1.75;color:#334155;"><span style="color:#1A4E93;">官方电话：</span>'
    '政策咨询 025-85788036（01 岗）、025-52709463（02 岗）、025-84431875（03/04 岗）｜监督 025-51889615（省体育局机关纪委）｜'
    '举报 025-51889770（省体育局）、js_sydwgkzp@163.com、025-83338112（省人社厅）｜技术支持 025-83278731、025-52616712。</p></section>')

# 8. 常见问答
parts.append(L.sec_title('常见问答'))
faqs = [
    ('江苏省体育局直属事业单位招聘是事业编制吗？',
     '是。岗位表 4 个岗位「其他说明」栏均标注「进编」，经费来源均为全额拨款，属省体育局直属事业单位编制。'),
    ('江苏省体育局招聘报名截止时间是什么时候？',
     '01-03 岗 2026 年 10 月 14 日 16:00 截止；04 博士岗 10 月 21 日 16:00 截止且招满即止，公告发布 7 个工作日后即可不定期启动考核。'),
    ('足球教练员岗位真的不限专业吗？',
     '是。02 岗专业一栏为「不限」，本科学历即可、对学位无要求，但必须持中国足协 C 级及以上教练员证或初级教练员职称，并有 2 年专业运动队经历或 3 年足球执教经历。'),
    ('江苏省体育局招聘考什么？',
     '01 岗笔试＋技能测试各占 50%；02 岗笔试 30%＋技能测试 30%＋公开课试讲 40%；03 岗笔试＋面试各占 50%；04 岗仅面试。笔试考岗位相关专业知识，不指定大纲和教材，各单科 60 分合格。'),
    ('往届生能报江苏省体育局这批岗位吗？',
     '能。01-03 岗招聘对象均为社会人员；2024、2025 年毕业且报名时无工作单位的人员，可按 2026 年毕业生身份应聘面向 2026 年毕业生的岗位（04 岗即面向 2026 年毕业生）。'),
    ('江苏省体育局招聘年龄限制是多少？',
     '18—38 周岁（1987 年 10 月 10 日之后出生）；博士岗位放宽至 40 周岁以下（1985 年 10 月 10 日之后出生）。'),
    ('江苏省体育局招聘待遇怎么样？',
     '公告与岗位表均未披露薪酬待遇标准，可分别致电 025-85788036、025-52709463、025-84431875 按岗咨询。'),
    ('江苏省体育局招聘有服务期要求吗？',
     '有。聘用期限一般不低于 3 年并约定试用期；订立 3 年以上（含试用期）聘用合同的，应当在招聘单位最低服务 3 年（含试用期）。'),
]
for q, a in faqs:
    parts.append(L.faq(q, a))

# 9. 实操建议
parts.append(L.sec_title('实操建议：三条避坑'))
parts.append(
    '<section style="background:#F7F8FA;border:1px solid #E2E8F0;border-radius:8px;padding:12px 14px;margin:0 0 10px;">'
    '<p style="margin:0 0 7px;font-size:14.5px;line-height:1.75;color:#334155;">'
    '<span style="border-left:4px solid #1A4E93;padding-left:8px;color:#1A4E93;font-weight:800;">1. 01-03 岗只有 5 天窗口，今天就投。</span><br/>'
    '10 月 10 日 9:00 开报、10 月 14 日 16:00 关闸，中间还隔着周末；开考比例 1:3，报名人数不足岗位会被核减或取消——'
    '想投别等最后一晚，初审过了不能改信息，提交前逐项自查。</p>'
    '<p style="margin:0 0 7px;font-size:14.5px;line-height:1.75;color:#334155;">'
    '<span style="border-left:4px solid #1A4E93;padding-left:8px;color:#1A4E93;font-weight:800;">2. 证书和经历证明提前备好。</span><br/>'
    '队医岗要医师/康复治疗师/运动防护师证书＋运动队 2 年经历证明，教练岗要足协 C 级证＋执教经历证明，'
    '编辑岗要出版职业资格中级证书——资格复审要查原件，现在就翻出来。</p>'
    '<p style="margin:0;font-size:14.5px;line-height:1.75;color:#334155;">'
    '<span style="border-left:4px solid #1A4E93;padding-left:8px;color:#1A4E93;font-weight:800;">3. 算好单科合格账再报考。</span><br/>'
    '这批招聘任一科目低于 60 分直接淘汰，不是总分过线就行；02 岗要连闯笔试、技能测试、试讲三关，公开课试讲占 40% 权重最高，'
    '教学功底弱的教练岗考生提前练试讲。</p></section>')

# CTA + 收尾
parts.append(L.cta())
parts += L.doc_close()

L.write(parts, OUT,
        must_have=['招聘信息不漏接', '码上君划重点', 'rs.jshrss.jiangsu.gov.cn'],
        forbidden_colors=r'#0085d0|#003876|#920303')
