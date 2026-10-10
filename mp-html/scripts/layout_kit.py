#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""mp-html · 排版组装公共库（layout_kit）——各 write 线共用的排版 HTML 生成骨架。

定位（2026-10-09 架构约定）：
  mp-html   = 方言规范（SKILL.md）+ 校验器（wx_dialect_check/wx_overflow_check）+ **组装库（本文件）**
  job-write / school-write / 后续各 write = 各自的线内生成器实例（gen_*.py），from layout_kit import Layout

用法（每篇稿的 gen_*.py 只写三块）：
    import sys, os
    sys.path.insert(0, os.path.expanduser('~/src/skills/mp-html/scripts'))
    from layout_kit import Layout

    L = Layout(brand='#920303', brand_dark='#5E0606', bg_light='#fdf3f3',
               border_light='#eedcdc', faq_bg='#faf6f6')
    h = L.doc_open('页面<title>标题</title>')
    h += L.highlight_card(sub, intro, items, numbers=['1.','2.','3.','4.'])   # 划重点卡
    h += L.quad_grid([('大字','小字'),...])                                    # 速览四格
    h += L.sec_title('招聘速览') ; h += L.p(...) ; h += L.ul([...], numbers=...)
    h += L.table(headers, rows, widths)                                        # 通用表格
    ... 各段 ...
    h += L.cta() ; L.write(h, out, must_have=[...], forbidden=[...])

内建断言：section 配平 / CTA 唯一 / 别家主题色残留 / th=0 / 外链图=0 / 段组件齐全 / 相邻标签插换行。
"""
import re
import os

DEFAULT_CTA = '/Users/zhugx/codeup/obsidian/03-工作记录/码上职业/素材/组件/cta-客服码单码.html'
FONT_STACK = ("-apple-system,BlinkMacSystemFont,'Helvetica Neue','PingFang SC',"
              "'Hiragino Sans GB','Microsoft YaHei UI','Microsoft YaHei',Arial,sans-serif")


class Layout:
    def __init__(self, brand, brand_dark, bg_light, border_light, faq_bg, faq_border, cta_path=DEFAULT_CTA):
        self.brand, self.dark = brand, brand_dark
        self.bg, self.border, self.faq_bg, self.faq_border = bg_light, border_light, faq_bg, faq_border
        self.cta_path = cta_path

    # ── 文档骨架
    def doc_open(self, title):
        return (f'<!DOCTYPE html><html><head><meta charset="utf-8"/>{title}</head>'
                '<body style="margin:0;padding:0;background:#ffffff;">'
                f'<section style="max-width:677px;margin:0 auto;box-sizing:border-box;font-family:{FONT_STACK};'
                'font-size:16px;line-height:1.75;color:#333333;word-wrap:break-word;padding:12px 10px;">')

    @staticmethod
    def doc_close():
        # 2026-10-09 CTA 模板已改为 4/4 自平衡（原 5/4 半开），此处只关 677px 根容器
        return ['</section>', '</body></html>']

    # ── 段组件
    def pill(self, sub, text='码上君划重点'):
        return (f'<section style="margin-bottom:10px;">'
                f'<span style="background:{self.brand};color:#fff;font-size:12px;font-weight:700;'
                f'padding:2px 8px;border-radius:4px;margin-right:8px;">{text}</span>'
                f'<span style="color:{self.brand};font-size:15px;font-weight:800;">{sub}</span></section>')

    def sec_title(self, t):
        # 竖线加重符挂在文字 span 的 border-left 上（2026-10-09）：空 span 微信客户端会剥掉不渲染
        return (f'<section style="margin:24px 0 12px;padding:0 14px;">'
                f'<span style="border-left:4px solid {self.brand};padding-left:9px;'
                f'font-size:18px;font-weight:800;color:{self.brand};">{t}</span></section>')

    def p(self, txt, style=''):
        return f'<p style="margin:0 0 10px;font-size:15px;line-height:1.75;color:#334155;{style}">{txt}</p>'

    def note(self, txt):
        """小字注释行（与历史稿结构一致：外层 p 15px + 内层 span 12.5px）"""
        return (f'<p style="margin:0 0 10px;font-size:15px;line-height:1.75;color:#334155;">'
                f'<span style="font-size:12.5px;color:#64748b;">{txt}</span></p>')

    def ul(self, items, numbers=None):
        """列表纪律（朱总 2026-10-08 定）：编号类传 numbers=['1.','2.']，无序类不传——正文永不出现「•」"""
        out = '<section style="margin:0 0 10px;">'
        for i, it in enumerate(items):
            pre = f'{numbers[i]} ' if numbers else ''
            out += f'<p style="margin:0 0 6px;font-size:15px;line-height:1.7;color:#334155;">{pre}{it}</p>'
        return out + '</section>'

    def faq(self, q, a):
        return (f'<section style="background:{self.faq_bg};border:1px solid {self.faq_border};'
                f'border-radius:8px;padding:12px 14px;margin:0 0 10px;">'
                f'<p style="margin:0 0 6px;font-size:15px;font-weight:800;color:{self.dark};line-height:1.6;">{q}</p>'
                f'<p style="margin:0;font-size:14.5px;line-height:1.75;color:#334155;">{a}</p></section>')

    def highlight_card(self, sub, intro, items, numbers=None, pill_text='码上君划重点'):
        """划重点卡：pill + 导语 + 要点列表，外层浅底卡。
        pill_text=None/'' 时不渲染卡内 pill（段标题已有同名文字时用，避免重复——2026-10-09 大丰稿实测）"""
        out = (f'<section style="background:{self.bg};border:1px solid {self.border};'
               f'border-radius:8px;padding:14px 16px;margin:0 0 16px;">')
        # 左侧 4px 加粗框线已去（朱总 2026-10-09 口味：正常 1px 四边框线）
        if pill_text:
            out += self.pill(sub, pill_text)
        out += self.p(intro) + self.ul(items, numbers) + '</section>'
        return out

    def quad_grid(self, cells):
        """速览四格：cells = [(大字, 小字), ×4]
        ⚠️ 布局表格的 td 必须显式 border:0 —— 微信对表格单元格有默认描边，
        不写会渲染出矩形框线套住圆角卡片（2026-10-10 体育局稿实测）"""
        def cell(v1, v2):
            return (f'<td style="padding:0 4px;border:0;">'
                    f'<section style="background:{self.bg};border:1px solid {self.border};border-radius:10px;'
                    f'padding:10px 4px;text-align:center;">'
                    f'<section style="font-size:14.5px;font-weight:800;color:{self.brand};line-height:1.4;">{v1}</section>'
                    f'<section style="font-size:11px;color:#475569;line-height:1.5;margin-top:3px;">{v2}</section>'
                    f'</section></td>')
        return ('<table style="width:100%;border-collapse:collapse;table-layout:fixed;'
                'margin:0 0 6px;"><tr>' + ''.join(cell(a, b) for a, b in cells) + '</tr></table>')

    def th(self, t, w):
        return (f'<td style="width:{w};background:{self.brand};background-color:{self.brand};color:#fff;'
                f'font-size:12.5px;font-weight:700;padding:7px 3px;text-align:center;">{t}</td>')

    def td(self, t, w, bg, st=''):
        return (f'<td style="width:{w};background:{bg};background-color:{bg};padding:5px 4px;'
                f'font-size:12.5px;color:#334155;{st}">{t}</td>')

    def table(self, headers, rows, widths, zebra='#f0f7f5', style=''):
        """通用表格：headers=[(文本,宽%)], rows=[[...]], widths=[..%]；zebra 斑马底色"""
        h = '<section style="margin:0 0 10px;"><table style="width:100%;border-collapse:collapse;table-layout:fixed;">'
        h += '<tr>' + ''.join(self.th(t, w) for t, w in zip(headers, widths)) + '</tr>'
        for i, r in enumerate(rows):
            bg = '#ffffff' if i % 2 else zebra
            h += '<tr>' + ''.join(self.td(c, w, bg) for c, w in zip(r, widths)) + '</tr>'
        return h + '</table></section>'

    # ── CTA（组件复用，色板替换）
    def cta(self):
        cta = open(self.cta_path, encoding='utf-8').read()
        return cta.replace('#0085d0', self.brand).replace('#003876', self.dark)

    # ── 收尾：断言 + 换行规整 + 写盘
    def write(self, body_parts, out, must_have, forbidden_colors, job_sections=True):
        html = '\n'.join(body_parts)
        o, c = html.count('<section'), html.count('</section>')
        assert o == c, f'section 配平失败: {o}/{c}'
        assert html.count('招聘信息不漏接') == 1, 'CTA 重复'
        assert not re.findall(forbidden_colors, html, re.I), '残留别家主题色'
        assert html.count('<th ') == 0, '表头用了 th（微信方言禁）'
        assert 'src="http' not in html, '外部图片链接（须 base64 内嵌）'
        for k in must_have:
            assert k in html, f'段组件丢失: {k}'
        html = re.sub(r'(?<=>)(?=<)', chr(10), html)   # 相邻标签插换行：修加粗密度分母假象
        open(out, 'w', encoding='utf-8').write(html)
        print(f'OK {out}\nsection {o}/{c} ｜ <strong> {html.count("<strong>")}')
        return html
