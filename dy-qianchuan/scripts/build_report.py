#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
千川 HTML 看板生成器
读取 analyze.py 输出的 report_YYYY-MM-DD.json，生成可视化看板。
"""
import argparse
import json
import os
import datetime

SYS_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(SYS_DIR, "data", "daily")
TEMPLATE_PATH = os.path.join(SYS_DIR, "templates", "dashboard_template.html")


def build_html(result):
    """根据分析结果渲染看板HTML"""
    date_str = result["date"]
    account = result["account"]
    p = result["profit"]
    stage = result["stage"]
    strategy = result["strategy"]
    materials = result["materials"]

    profit_color = {"盈利": "#0F6E56", "亏损": "#A32D2D", "持平": "#854F0B"}.get(p["profit_status"], "#5F5E5A")

    def money(v):
        if abs(v) >= 10000:
            return f"{v/10000:.1f}万"
        return f"{v:,.0f}"

    def status_color(s):
        return {"健康": "#0F6E56", "关注": "#854F0B", "衰退": "#A32D2D"}.get(s, "#5F5E5A")

    def action_color(a):
        return {"关停": "#A32D2D", "加量": "#0F6E56", "观察2天": "#854F0B",
                "密切观察": "#BA7517", "维持": "#5F5E5A"}.get(a, "#5F5E5A")

    # 指标卡
    cards = f"""
    <div class="cards">
      <div class="card">
        <div class="label">表面 ROI</div>
        <div class="value">{p['surface_roi']}</div>
        <div class="sub">GMV {money(account['pay_order_amount'])} ÷ 消耗 {money(account['stat_cost'])}</div>
      </div>
      <div class="card">
        <div class="label">真实 ROI <span class="badge">扣全部成本</span></div>
        <div class="value" style="color:{profit_color}">{p['real_roi']}</div>
        <div class="sub">净利润 {money(p['net_profit'])} ÷ 消耗 {money(account['stat_cost'])}</div>
      </div>
      <div class="card">
        <div class="label">保本 ROI</div>
        <div class="value" style="color:#BA7517">{p['breakeven_roi']}</div>
        <div class="sub">低于此值投放即亏损</div>
      </div>
      <div class="card">
        <div class="label">净利润</div>
        <div class="value" style="color:{profit_color}">{money(p['net_profit'])}</div>
        <div class="sub">{p['profit_status']} · 目标ROI {p['target_roi']}</div>
      </div>
    </div>
    """

    # 成本构成
    cost_rows = [
        ("退款", p["refund"], "#E24B4A"),
        ("货品成本", p["goods_cost"], "#D85A30"),
        ("达人佣金", p["commission"], "#7F77DD"),
        ("人工(日摊)", p["fixed_daily"], "#888780"),
        ("平台扣点", p["platform_fee"], "#B4B2A9"),
        ("千川消耗", p["ad_cost"], "#378ADD"),
        ("运费", p["freight"], "#B4B2A9"),
        ("技术服务费", p["tech_fee"], "#B4B2A9"),
    ]
    max_cost = max(v for _, v, _ in cost_rows) or 1
    cost_bars = ""
    for name, v, color in cost_rows:
        w = max(v / max_cost * 100, 2)
        cost_bars += f"""
        <div class="cost-row">
          <span class="cost-name">{name}</span>
          <div class="cost-bar"><div style="width:{w:.1f}%;background:{color}"></div></div>
          <span class="cost-val">{money(v)}</span>
        </div>"""

    # 素材表
    cat_color = {"爆款跑量": "#0F6E56", "高ROI低量": "#185FA5", "潜力素材": "#854F0B", "低效素材": "#A32D2D"}
    material_rows = ""
    for m in materials:
        sc = status_color(m["status"])
        ac = action_color(m["action"])
        cc = cat_color.get(m.get("category", ""), "#5F5E5A")
        material_rows += f"""
        <tr>
          <td>{m['name']}</td>
          <td>{m['days_on']}天</td>
          <td>{money(m['stat_cost'])}</td>
          <td>{m['ctr']}%</td>
          <td>{m['cvr']}%</td>
          <td>{m['roi']}</td>
          <td><span style="color:{sc};font-weight:500">{m['score']}分 · {m['status']}</span></td>
          <td><span style="color:{cc};font-weight:500">{m.get('category', '—')}</span></td>
          <td>{m['test_result'] or '—'}</td>
          <td><span class="tag" style="color:{ac};border-color:{ac}">{m['action']}</span></td>
        </tr>"""

    # 操作清单
    def action_section(title, items, icon, color):
        if not items:
            return ""
        rows = "".join(f'<li><b>{m["name"]}</b> — {m["action_reason"]}</li>' for m in items)
        return f'<div class="op-block"><h3 style="color:{color}">{icon} {title} ({len(items)})</h3><ul>{rows}</ul></div>'

    ops = ""
    ops += action_section("关停清单", strategy["close_list"], "■", "#A32D2D")
    ops += action_section("加量清单", strategy["boost_list"], "▲", "#0F6E56")
    ops += action_section("观察清单", strategy["watch_list"], "●", "#BA7517")
    if strategy["test_passed"]:
        ops += action_section("测试通过", strategy["test_passed"], "✓", "#0F6E56")
    if strategy["test_failed"]:
        ops += action_section("测试未通过", strategy["test_failed"], "✕", "#A32D2D")
    if strategy["replace_plan"]:
        repl = "".join(f'<li><b>{r["name"]}</b> → {r["plan"]}</li>' for r in strategy["replace_plan"])
        ops += f'<div class="op-block"><h3 style="color:#7F77DD">↻ 替换建议 ({len(strategy["replace_plan"])})</h3><ul>{repl}</ul></div>'

    # 库存预警
    inv = ""
    if strategy["inventory_warning"]:
        wl = "".join(f"<li>{w}</li>" for w in strategy["inventory_warning"])
        inv = f'<div class="op-block"><h3 style="color:#A32D2D">⚠ 库存预警</h3><ul>{wl}</ul></div>'

    # 掉量排查（周期化运营）
    decline_html = ""
    decline_checks = result.get("decline_checks", [])
    if decline_checks:
        d_rows = ""
        for c in decline_checks:
            color = "#A32D2D" if "⚠" in c["status"] else "#0F6E56"
            icon = "⚠" if "⚠" in c["status"] else "✓"
            d_rows += f'<tr><td>{icon} {c["item"]}</td><td style="color:{color};font-weight:500">{c["status"]}</td>' \
                      f'<td>{c.get("detail", "")}</td><td>{c["action"]}</td></tr>'
        decline_html = f"""
    <div class="section">
      <h2>掉量排查清单（先排查病因，再控本止损 + 新量承接）</h2>
      <table>
        <thead><tr><th>排查项</th><th>状态</th><th>依据</th><th>处理动作</th></tr></thead>
        <tbody>{d_rows}</tbody>
      </table>
      <div class="note" style="margin-top:12px;margin-bottom:0">原则：掉量后先观察30分钟排除大盘波动；未恢复则定位根因（低效素材/出价竞争力/体验分&lt;4.6/直播转化）；收缩衰退素材守住底线，补新素材+建新计划破局，盘活历史潜力素材（50-100元小额复测）</div>
    </div>"""

    # 风险预警（看板设计方法论：带病增长判断）
    risk_html = ""
    risk_checks = result.get("risk_checks", [])
    if risk_checks:
        r_rows = ""
        for r in risk_checks:
            lvl_color = {"高": "#A32D2D", "中": "#BA7517", "低": "#0F6E56"}.get(r["level"], "#5F5E5A")
            r_rows += f'<tr><td>{r["item"]}</td><td style="color:{lvl_color};font-weight:500">{r["level"]}</td>' \
                      f'<td>{r.get("detail", "")}</td><td>{r["action"]}</td></tr>'
        risk_html = f"""
    <div class="section">
      <h2>风险预警（带病增长判断：GMV↑但转化↓ / 退款↑ / 推广费↑但ROI↓）</h2>
      <table>
        <thead><tr><th>风险项</th><th>级别</th><th>依据</th><th>处理动作</th></tr></thead>
        <tbody>{r_rows}</tbody>
      </table>
      <div class="note" style="margin-top:12px;margin-bottom:0">看板逻辑：先看整体经营 → 再看平台/商品 → 最后看风险。退款、库存、毛利风险提前暴露，才是运营的作战地图</div>
    </div>"""

    # ROI四层漏斗归因（小伍：先看流量→再看承接→最后才看素材）
    rf = result.get("roi_funnel", {})
    if rf:
        layer_color = {"第一层·吸引": "#185FA5", "第二层·匹配": "#0F6E56",
                       "第三层·承接": "#854F0B", "第四层·放大": "#A32D2D",
                       "漏斗正常": "#0F6E56", "综合排查": "#A32D2D"}.get(rf["layer"], "#5F5E5A")
        roi_funnel_html = f"""
    <div class="section">
      <h2>ROI 四层漏斗归因（先看流量 → 再看承接 → 最后才看素材）</h2>
      <div class="cards">
        <div class="card"><div class="label">漏斗定位</div>
          <div class="value" style="font-size:18px;color:{layer_color}">{rf['layer']}</div></div>
        <div class="card"><div class="label">判断依据</div>
          <div class="value" style="font-size:16px">{rf['issue']}</div>
          <div class="sub">CTR {rf['ctr']}% · CVR {rf['cvr']}% · ROI {rf['roi']} / 保本 {rf['breakeven']}</div></div>
      </div>
      <div class="note" style="margin-top:12px;margin-bottom:0">处理建议：{rf['action']}</div>
    </div>"""
    else:
        roi_funnel_html = ""

    # 测试预算
    budget_note = (f'<div class="note">阶段：<b>{stage["stage"]}</b>（{stage["desc"]}）· '
                   f'测试预算占比 {strategy["stage_budget_ratio"]*100:.0f}% → '
                   f'今日测试预算约 <b>{money(strategy["test_budget"])}</b> 元（新素材消耗≥150元、ROI≥12为通过标准）'
                   f'<br>预算分配：<b>{strategy["budget_alloc"]["rule"]}</b>（主力 {money(strategy["budget_alloc"]["main_budget"])} 元 / '
                   f'测试 {money(strategy["budget_alloc"]["test_budget"])} 元）· 调整建议：{strategy["budget_adj"]}</div>')

    # 账号类型诊断（全域投放）
    at = result.get("account_type", {})
    if at:
        at_type_color = {"付费主导型": "#A32D2D", "高自然流型": "#0F6E56",
                         "均衡型": "#185FA5", "探索期账号": "#854F0B"}.get(at["type"], "#5F5E5A")
        account_type_note = f"""
    <div class="section">
      <h2>账号类型诊断（全域投放）</h2>
      <div class="cards">
        <div class="card"><div class="label">账号类型</div>
          <div class="value" style="font-size:20px;color:{at_type_color}">{at['type']}</div></div>
        <div class="card"><div class="label">自然流占比（估）</div>
          <div class="value">{at['natural_share']*100:.0f}%</div></div>
        <div class="card"><div class="label">ROI 稳定性</div>
          <div class="value" style="font-size:20px">{'稳定' if at['roi_stable'] else '波动大'}</div></div>
        <div class="card"><div class="label">客单价</div>
          <div class="value" style="font-size:20px">¥{at['unit_price']:.0f}</div></div>
      </div>
      <div class="note" style="margin-bottom:0;margin-top:12px">策略：{at['strategy']}</div>
    </div>"""
    else:
        account_type_note = ""

    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>千川投流日报 {date_str}</title>
<style>
* {{ margin:0; padding:0; box-sizing:border-box; }}
body {{ font-family:-apple-system,BlinkMacSystemFont,'PingFang SC','Microsoft YaHei',sans-serif;
  background:#f7f7f5; color:#2C2C2A; padding:24px; }}
.wrap {{ max-width:960px; margin:0 auto; }}
h1 {{ font-size:20px; font-weight:500; margin-bottom:4px; }}
.sub {{ color:#5F5E5A; font-size:13px; margin-bottom:20px; }}
.cards {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(200px,1fr)); gap:12px; margin-bottom:20px; }}
.card {{ background:#fff; border:0.5px solid #e2e0d8; border-radius:12px; padding:16px; }}
.card .label {{ font-size:12px; color:#5F5E5A; margin-bottom:6px; }}
.card .value {{ font-size:26px; font-weight:500; }}
.card .sub {{ font-size:12px; color:#888780; margin-top:4px; }}
.badge {{ background:#FAEEDA; color:#854F0B; font-size:11px; padding:2px 6px; border-radius:6px; margin-left:4px; }}
.section {{ background:#fff; border:0.5px solid #e2e0d8; border-radius:12px; padding:20px; margin-bottom:16px; }}
.section h2 {{ font-size:15px; font-weight:500; margin-bottom:14px; }}
.cost-row {{ display:flex; align-items:center; gap:10px; margin-bottom:8px; font-size:12px; }}
.cost-name {{ width:80px; color:#5F5E5A; flex-shrink:0; }}
.cost-bar {{ flex:1; background:#f1efe8; border-radius:4px; height:14px; overflow:hidden; }}
.cost-bar div {{ height:14px; border-radius:4px; }}
.cost-val {{ width:50px; text-align:right; font-weight:500; }}
table {{ width:100%; border-collapse:collapse; font-size:12px; }}
th {{ text-align:left; color:#5F5E5A; font-weight:400; padding:8px 6px; border-bottom:1px solid #e2e0d8; }}
td {{ padding:8px 6px; border-bottom:0.5px solid #f1efe8; }}
.tag {{ border:0.5px solid; border-radius:6px; padding:2px 8px; font-size:11px; }}
.op-block {{ margin-bottom:14px; padding:12px 14px; background:#fafaf8; border-radius:8px; }}
.op-block h3 {{ font-size:13px; font-weight:500; margin-bottom:8px; }}
.op-block ul {{ list-style:none; }}
.op-block li {{ font-size:13px; color:#444441; padding:3px 0; }}
.op-block li b {{ font-weight:500; }}
.note {{ background:#E6F1FB; color:#0C447C; border-radius:8px; padding:10px 14px; font-size:13px; margin-bottom:16px; }}
.footer {{ text-align:center; color:#888780; font-size:12px; margin-top:24px; }}
</style>
</head>
<body>
<div class="wrap">
  <h1>千川投流日报 · {date_str}</h1>
  <div class="sub">数据源：千川开放平台 · 双引擎：利润引擎 + 素材引擎</div>
  {cards}
  {budget_note}
  {account_type_note}
  {roi_funnel_html}
  <div class="section">
    <h2>成本构成拆解（真实 ROI 核算）</h2>
    {cost_bars}
  </div>
  <div class="section">
    <h2>素材健康度明细（12维评分）</h2>
    <table>
      <thead><tr><th>素材</th><th>上线</th><th>消耗</th><th>CTR</th><th>CVR</th><th>ROI</th><th>评分/状态</th><th>分类</th><th>测试</th><th>操作</th></tr></thead>
      <tbody>{material_rows}</tbody>
    </table>
  </div>
  <div class="section">
    <h2>今日操作清单</h2>
    {ops}
    {inv}
  </div>
  {decline_html}
  {risk_html}
  <div class="footer">千川投流决策技能 · 建议每日打烊后运行 · 操作清单需结合人工判断</div>
</div>
</body>
</html>"""


def main():
    parser = argparse.ArgumentParser(description="千川看板生成")
    parser.add_argument("--date", default=None, help="指定日期报告（默认取最新）")
    args = parser.parse_args()

    if args.date:
        report_path = os.path.join(DATA_DIR, f"report_{args.date}.json")
    else:
        files = sorted([f for f in os.listdir(DATA_DIR) if f.startswith("report_")])
        if not files:
            print("未找到分析报告，请先运行 analyze.py", file=sys.stderr)
            sys.exit(1)
        report_path = os.path.join(DATA_DIR, files[-1])
        args.date = files[-1].replace("report_", "").replace(".json", "")

    with open(report_path, encoding="utf-8") as f:
        result = json.load(f)

    html = build_html(result)
    out_path = os.path.join(DATA_DIR, f"dashboard_{args.date}.html")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"看板已生成: {out_path}")


if __name__ == "__main__":
    main()
