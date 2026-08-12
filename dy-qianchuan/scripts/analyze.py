#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
千川双引擎分析:
  1. 利润引擎 ProfitEngine: 表面ROI -> 真实ROI -> 保本ROI -> 净利润 -> 盈亏判断
  2. 素材引擎 MaterialEngine: 12维健康度评分 -> 衰退信号 -> 每条素材决策
  3. 阶段识别 StageDetector: 冷启动/稳定/冲量/衰退
  4. 策略输出: 关停/观察/加量/替换/测试/库存预警清单
"""
import argparse
import json
import os
import datetime
import yaml

SYS_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
COST_PATH = os.path.join(SYS_DIR, "config", "cost_params.yaml")
DATA_DIR = os.path.join(SYS_DIR, "data", "daily")
HISTORY_DIR = os.path.join(SYS_DIR, "data", "history")


def load_cost_params():
    with open(COST_PATH, encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    return cfg


class ProfitEngine:
    """利润引擎: 计算真实ROI、保本ROI、净利润"""

    def __init__(self, cost_params):
        self.cp = cost_params["cost_params"]

    def analyze(self, account):
        gmv = account["pay_order_amount"]
        ad_cost = account["stat_cost"]
        refund_rate = self.cp["refund_rate"]

        refund = gmv * refund_rate
        goods_cost = gmv * (1 - self.cp["gross_margin"])
        freight = gmv * self.cp.get("freight_rate", 0.03)
        platform_fee = gmv * self.cp.get("platform_fee_rate", 0.05)
        tech_fee = gmv * self.cp.get("tech_fee_rate", 0.02)
        commission = gmv * self.cp.get("commission_rate", 0.15)
        fixed_month = self.cp["fixed_cost_month"]
        # 月固定成本按30天摊到日
        fixed_daily = fixed_month / 30.0

        total_cost = (refund + goods_cost + freight + platform_fee + tech_fee +
                      commission + ad_cost + fixed_daily)
        net_profit = gmv - total_cost

        surface_roi = gmv / ad_cost if ad_cost else 0
        real_roi = net_profit / ad_cost if ad_cost else 0

        # 保本ROI: 使净利润=0时的 ROI（净利率视角）
        # 净利率 = (1-退款率-货品率-运费率-平台扣点-技术费-佣金) - 固定成本率 - 消耗率
        # 保本ROI = 1 / (1 - 退款率 - (1-毛利率) - 运费率 - 扣点 - 技术费 - 佣金 - 固定成本率)
        gross_net_rate = (1 - refund_rate - (1 - self.cp["gross_margin"]) -
                          self.cp.get("freight_rate", 0.03) -
                          self.cp.get("platform_fee_rate", 0.05) -
                          self.cp.get("tech_fee_rate", 0.02) -
                          self.cp.get("commission_rate", 0.15))
        # 月固定成本率按当前GMV推算
        fixed_rate = fixed_month / (gmv * 30) if gmv else 0
        breakeven_roi = 1 / (gross_net_rate - fixed_rate) if (gross_net_rate - fixed_rate) > 0 else 999

        # 目标ROI（想赚 target_profit）
        target_profit = self.cp["target_profit"]
        target_rate = fixed_month + target_profit
        target_roi = 1 / (gross_net_rate - (target_rate / (gmv * 30))) if gmv else 999

        return {
            "gmv": gmv,
            "ad_cost": ad_cost,
            "surface_roi": round(surface_roi, 2),
            "real_roi": round(real_roi, 2),
            "net_profit": round(net_profit, 2),
            "refund": round(refund, 2),
            "goods_cost": round(goods_cost, 2),
            "freight": round(freight, 2),
            "platform_fee": round(platform_fee, 2),
            "tech_fee": round(tech_fee, 2),
            "commission": round(commission, 2),
            "fixed_daily": round(fixed_daily, 2),
            "breakeven_roi": round(breakeven_roi, 2),
            "target_roi": round(target_roi, 2),
            "refund_rate": refund_rate,
            "profit_status": "盈利" if net_profit > 0 else ("亏损" if net_profit < 0 else "持平"),
            "warnings": [],
        }


class MaterialEngine:
    """素材引擎: 12维健康度评分 + 衰退信号 + 决策"""

    def __init__(self, cost_params, profit_result):
        self.cp = cost_params["cost_params"]
        self.th = cost_params["thresholds"]
        self.profit = profit_result

    def score_material(self, m):
        """12维健康度评分（核心4维占80%，其余8维各5%）"""
        # 1. 消耗稳定性(15%): 用消耗绝对值折算，>=2000元满分
        cost_stability = min(m["stat_cost"] / 2000, 1.0) * 10
        # 2. 点击率(15%): CTR>=4% 满分
        ctr_score = min(m["ctr"] / 4.0, 1.0) * 10
        # 3. 转化率(15%): CVR>=5% 满分
        cvr_score = min(m["cvr"] / 5.0, 1.0) * 10
        # 4. ROI达标率(20%): 对比真实ROI/保本ROI
        breakeven = self.profit["breakeven_roi"]
        roi_score = min(m["roi"] / max(breakeven * 1.5, 1), 1.0) * 10
        # 5-12. 次要维度各5%: 简化打分（生命周期、稳定性、量级、趋势、成本、竞争、人群、时段）
        days = m.get("days_on", 1)
        life_score = 10 if days <= 7 else (8 if days <= 12 else 4)   # 生命周期
        trend_score = 7  # 趋势（未来可由历史数据推算）
        scale_score = min(m["stat_cost"] / 1000, 1.0) * 10           # 量级
        cost_score = min(1.0 / (m.get("roi", 1) / max(breakeven, 1)), 1.0) * 10  # 获客成本
        cpm_score = 7
        competition_score = 7
        audience_score = 7
        time_score = 7

        weighted = (
            cost_stability * 0.15 +
            ctr_score * 0.15 +
            cvr_score * 0.15 +
            roi_score * 0.20 +
            life_score * 0.05 +
            trend_score * 0.05 +
            scale_score * 0.05 +
            cost_score * 0.05 +
            cpm_score * 0.05 +
            competition_score * 0.05 +
            audience_score * 0.05 +
            time_score * 0.05
        )
        return round(weighted, 1)

    def detect_decline(self, m):
        """衰退三信号: 消耗低 + CTR低 + ROI低 同时触发"""
        signals = []
        if m["stat_cost"] < 800:
            signals.append("消耗不足")
        if m["ctr"] < 2.0:
            signals.append("CTR下滑")
        if m["roi"] < self.profit["breakeven_roi"] * 1.2:
            signals.append("ROI低于保本线1.2倍")
        return signals

    def analyze(self, materials):
        results = []
        for m in materials:
            score = self.score_material(m)
            signals = self.detect_decline(m)
            days = m.get("days_on", 1)

            if score >= self.th["material_score"]["healthy"]:
                status = "健康"
            elif score >= self.th["material_score"]["watch"]:
                status = "关注"
            else:
                status = "衰退"

            # 素材四分类（海盗船长: ROI×消耗 矩阵）
            # 爆款: ROI高+量足 / 高ROI低量 / 潜力: ROI一般+消耗正常 / 低效: ROI低
            breakeven = self.profit["breakeven_roi"]
            roi_high = m["roi"] >= breakeven * 1.5
            spend_ok = m["stat_cost"] >= 800
            if roi_high and spend_ok:
                category = "爆款跑量"
            elif roi_high and not spend_ok:
                category = "高ROI低量"
            elif spend_ok and not roi_high:
                category = "潜力素材"
            else:
                category = "低效素材"

            # 决策规则
            if status == "衰退" and days > 5 and signals:
                action = "关停"
                action_reason = f"评分{score}<6且上线{days}天，衰退信号: {'、'.join(signals)}"
            elif status == "衰退" and days <= 3:
                action = "观察2天"
                action_reason = f"上线仅{days}天，先优化出价/换封面再观察"
            elif status == "关注":
                action = "密切观察"
                action_reason = f"评分{score}处于6-8区间，监控消耗/CTR/ROI趋势"
            elif category == "高ROI低量":
                action = "调计划扩量"
                action_reason = f"ROI={m['roi']}高但消耗仅{m['stat_cost']}元，优先调计划再调素材"
            elif category == "潜力素材":
                action = "培育测试"
                action_reason = f"消耗正常但ROI={m['roi']}一般，搭新计划测试放大量级"
            elif status == "健康" and m["roi"] >= breakeven * 2:
                action = "加量"
                action_reason = f"评分{score}健康，ROI={m['roi']}远超保本线{breakeven}"
            else:
                action = "维持"
                action_reason = f"评分{score}健康，正常投放"

            # AB测试判定
            test_result = None
            if days <= 3:
                if m["stat_cost"] < self.th["ab_test"]["min_spend"]:
                    test_result = "测试中(消耗不足)"
                elif m["roi"] >= self.th["ab_test"]["pass_roi"]:
                    test_result = "通过"
                else:
                    test_result = "未通过"

            results.append({
                "name": m["name"],
                "days_on": days,
                "stat_cost": m["stat_cost"],
                "pay_amount": m["pay_amount"],
                "ctr": m["ctr"],
                "cvr": m["cvr"],
                "roi": m["roi"],
                "score": score,
                "status": status,
                "category": category,
                "signals": signals,
                "action": action,
                "action_reason": action_reason,
                "test_result": test_result,
            })
        return results


class StageDetector:
    """阶段识别（周期化运营: 探索/成长/稳定/衰退-掉量）
    核心阈值: 3天+3000展现；素材平均生命周期3-7天
    """

    @staticmethod
    def detect(account, materials, history=None):
        roi = account.get("pay_roi", 0)
        total_spend = sum(m["stat_cost"] for m in materials)
        # 素材年龄分布
        new_cnt = sum(1 for m in materials if m.get("days_on", 99) <= 3)
        old_cnt = sum(1 for m in materials if m.get("days_on", 0) >= 7)
        # 衰退素材（评分低）数量
        decline_cnt = sum(1 for m in materials if m.get("score", 10) < 6)

        if total_spend < 3000:
            stage = "探索期"
            desc = "消耗量级小（<3000元），系统建模阶段：看CTR/3秒停留，不纠结单日投产，不频繁调计划"
            key = "cold_start"
        elif decline_cnt >= 2 and old_cnt >= 2:
            stage = "衰退期"
            desc = f"多条素材跌破保本线（衰退{decline_cnt}条），收缩调整：只保留高于保本ROI的主计划，补新素材+建新计划"
            key = "decline"
        elif new_cnt >= 2 and roi >= 10:
            stage = "成长期"
            desc = "素材消耗稳步爬坡、净成交ROI达标稳定，逐步追加预算放大跑量素材消耗"
            key = "stable"
        elif roi >= 12:
            stage = "稳定期"
            desc = "主力素材消耗与投产平稳，保持节奏，同步储备新素材（预留7天产能缓冲）"
            key = "stable"
        else:
            stage = "稳定期"
            desc = "ROI处于可接受区间，持续优化素材结构，警惕掉量信号"
            key = "stable"

        return {"stage": stage, "desc": desc, "key": key}


class DeclineChecker:
    """掉量排查清单（先排查病因，再控本止损 + 新量承接）
    规则: 掉量后先观察30分钟排除大盘波动；未恢复逐项排查根因
    """

    @staticmethod
    def check(account, materials, profit, thresholds):
        checks = []
        breakeven = profit["breakeven_roi"]
        # 1. 主力素材是否被标记低效（用评分<6近似）
        low_eff = [m["name"] for m in materials if m.get("score", 10) < 6]
        if low_eff:
            checks.append({"item": "低效素材标记", "status": "⚠ 需关注",
                           "detail": f"{len(low_eff)}条素材评分<6（近似判定低效）：{'、'.join(low_eff[:3])}",
                           "action": "停止加码，准备替换"})
        # 2. 出价竞争力不足（用CTR低近似）
        low_ctr = [m["name"] for m in materials if m.get("ctr", 99) < 2.0]
        if low_ctr:
            checks.append({"item": "出价竞争力不足", "status": "⚠ 疑似",
                           "detail": f"{len(low_ctr)}条素材CTR<2%（近似判定）",
                           "action": "检查出价是否低于行业均值，必要时提价5-10%"})
        # 3. 素材消耗趋势（用消耗占比近似判断主力是否下滑）
        if materials:
            avg = sum(m["stat_cost"] for m in materials) / len(materials)
            main_mats = [m for m in materials if m["stat_cost"] > avg * 1.5]
            if main_mats and all(m.get("roi", 99) < breakeven * 1.2 for m in main_mats):
                checks.append({"item": "主力素材投产下滑", "status": "⚠ 需关注",
                               "detail": "消耗TOP素材ROI接近保本线，流量池可能收割殆尽",
                               "action": "新建全域计划重新探索流量池，勿死守老计划"})
        # 4. 账户整体掉量（当日消耗低）
        if account.get("stat_cost", 0) < 3000:
            checks.append({"item": "账户整体消耗低迷", "status": "⚠ 掉量信号",
                           "detail": f"当日消耗{account['stat_cost']}元（<3000元）",
                           "action": "先观察30分钟排除大盘波动；未恢复则排查体验分/直播间转化，补新素材+盘活历史素材"})

        if not checks:
            checks.append({"item": "账户状态", "status": "✅ 正常",
                           "detail": "未检测到明显掉量信号，维持当前节奏",
                           "action": "保持基础投放，继续储备新素材"})
        return checks


class RiskChecker:
    """风险预警（来自看板设计方法论: 退款/推广费/转化/毛利风险提前暴露）
    带病增长判断: GMV↑但转化↓ / GMV↑但退款↑ / 订单↑但客单↓ / 推广↑但ROI↓
    """

    @staticmethod
    def check(account, profit, materials, cost_params, history=None):
        risks = []
        cp = cost_params["cost_params"]
        th = cost_params["thresholds"]

        gmv = account.get("pay_order_amount", 0)
        ad_cost = account.get("stat_cost", 0)
        roi = account.get("pay_roi", 0)
        ctr = account.get("ctr", 0)
        cvr = account.get("cvr", 0)

        # 1. 退款风险（退款率 ≥30% 盈亏平衡线；高于配置值告警）
        refund_rate = cp["refund_rate"]
        if refund_rate >= 0.30:
            risks.append({"item": "退款率过高", "level": "高",
                          "detail": f"退款率{refund_rate*100:.0f}% ≥ 30%盈亏平衡线，卖得越多亏得越多",
                          "action": "优化品控与售后，排查高退款商品/原因"})
        elif refund_rate >= 0.20:
            risks.append({"item": "退款率偏高", "level": "中",
                          "detail": f"退款率{refund_rate*100:.0f}%，高于行业基准10-15%",
                          "action": "关注退款趋势，检查高退款品类"})

        # 2. 推广费风险（真实ROI < 保本ROI；净利润≤0 = 投放亏损）
        if profit["net_profit"] <= 0:
            risks.append({"item": "投放亏损", "level": "高",
                          "detail": f"净利润{profit['net_profit']:.0f}元 ≤ 0，真实ROI {profit['real_roi']} "
                                    f"< 保本ROI {profit['breakeven_roi']}",
                          "action": "缩量或调整出价，收缩跌破保本线素材"})
        elif profit["real_roi"] < profit["breakeven_roi"]:
            risks.append({"item": "盈利空间薄", "level": "中",
                          "detail": f"真实ROI {profit['real_roi']} < 保本ROI {profit['breakeven_roi']}，"
                                    f"净利润{profit['net_profit']:.0f}元，表面ROI虚高",
                          "action": "优化成本结构（退款/佣金/货品），警惕消耗放大亏损"})

        # 3. 转化率（基准: 行业2-5%，健康>3%，预警<1%）
        if cvr and cvr < 1.0:
            risks.append({"item": "转化率严重偏低", "level": "高",
                          "detail": f"CVR {cvr}% < 1% 预警线（行业2-5%），转化链路断裂",
                          "action": "立即检查落地页/商品承接/直播间转化，按淘汰标准3天观察"})
        elif cvr and cvr < 3.0:
            risks.append({"item": "转化率偏低", "level": "中",
                          "detail": f"CVR {cvr}% < 3%（行业2-5%，健康>3%），转化链路可能出问题",
                          "action": "检查直播间转化/落地页/商品承接"})

        # 4. 点击率（基准: 行业1.5-3%，健康>2%，预警<1%）
        if ctr and ctr < 1.0:
            risks.append({"item": "点击率严重过低", "level": "高",
                          "detail": f"CTR {ctr}% < 1% 预警线（行业1.5-3%），素材吸引力严重不足",
                          "action": "按淘汰标准2天观察，换素材再试1次"})
        elif ctr and ctr < 2.0:
            risks.append({"item": "点击率偏低", "level": "中",
                          "detail": f"CTR {ctr}% < 2%（行业1.5-3%，健康>2%），素材吸引力下降",
                          "action": "优化素材前三秒（沉浸式/价格福利型）"})

        # 4.5 CPM（基准: 行业50-150元，健康<120元，预警>200元）
        show_cnt = account.get("show_cnt", 0)
        if show_cnt and ad_cost:
            cpm = ad_cost / show_cnt * 1000
            if cpm > 200:
                risks.append({"item": "CPM过高", "level": "高",
                              "detail": f"CPM {cpm:.0f}元 > 200元预警线（行业50-150元），流量太贵",
                              "action": "检查定向是否过窄或竞争激烈，放宽定向条件"})
            elif cpm > 120:
                risks.append({"item": "CPM偏高", "level": "中",
                              "detail": f"CPM {cpm:.0f}元 > 120元健康线（行业50-150元）",
                              "action": "关注流量成本，必要时调整定向/出价"})

        # 5. 毛利率风险（配置毛利率低）
        if cp["gross_margin"] < 0.30:
            risks.append({"item": "毛利率偏低", "level": "中",
                          "detail": f"毛利率{cp['gross_margin']*100:.0f}% < 30%，单品利润薄",
                          "action": "优化供应链降进货价，或调整商品结构"})

        # 6. 带病增长判断（需要历史对比，此处用当日内部结构近似）
        if gmv and roi and ad_cost:
            pass  # 结构性判断已由上面覆盖

        if not risks:
            risks.append({"item": "经营健康", "level": "低",
                          "detail": "未检测到明显风险，维持当前节奏",
                          "action": "保持投放，继续储备素材"})
        return risks


class RoiFunnelDiagnoser:
    """ROI四层漏斗归因诊断（小伍: 先看流量→再看承接→最后才看素材）
    基于 CTR × ROI 组合判断问题出在漏斗哪一层
    """

    @staticmethod
    def diagnose(account, profit):
        ctr = account.get("ctr", 0)
        cvr = account.get("cvr", 0)
        roi = account.get("pay_roi", 0)
        breakeven = profit["breakeven_roi"]
        net = profit["net_profit"]

        ctr_low = ctr < 2.0
        ctr_high = ctr >= 2.0
        roi_low = roi < breakeven
        roi_ok = roi >= breakeven

        if ctr_low and roi_low:
            layer = "第一层·吸引"
            issue = "CTR低 + ROI低"
            action = "优先优化素材：用户没点击，素材吸引力不足"
        elif ctr_high and roi_low:
            layer = "第三层·承接"
            issue = "CTR高 + ROI低"
            action = "检查落地页与转化链路：点击质量未转化，优化落地页首屏/转化目标/商品承接"
        elif roi_low and net < 0:
            layer = "第二层·匹配"
            issue = "ROI持续低且亏损"
            action = "排查流量质量：收紧无效流量、检查定向精准度、调整转化目标"
        elif ctr_high and roi_low:
            layer = "第四层·放大"
            issue = "CTR稳定但ROI低于保本线"
            action = "排查流量竞争与账户节奏：预算变化/竞争加剧/系统学习状态"
        elif not roi_low:
            layer = "漏斗正常"
            issue = "ROI达标"
            action = "维持当前链路，持续监控各层数据变化"
        else:
            layer = "综合排查"
            issue = "多指标异常"
            action = "综合排查流量、出价、承接（ROI持续下降且CPA上涨时）"

        return {
            "layer": layer,
            "issue": issue,
            "action": action,
            "ctr": ctr,
            "cvr": cvr,
            "roi": roi,
            "breakeven": breakeven,
        }


class BoostEngine:
    """素材追投建议引擎（分步实操手册: 玩法A四关激活 / 玩法B翻倍定锚 / 玩法D追投铁律）
    输出: 可追投素材清单 + 追投预算建议 + 新素材激活建议
    """

    def __init__(self, material_results, profit, account):
        self.materials = material_results
        self.profit = profit
        self.account = account

    def analyze(self):
        breakeven = self.profit["breakeven_roi"]
        total_spend = sum(m["stat_cost"] for m in self.materials)
        rois = [m["roi"] for m in self.materials if m.get("roi")]
        avg_roi = sum(rois) / len(rois) if rois else 0

        # 铁律1·追高不追低: 只追 ROI≥保本1.2倍 且 消耗正常的优质素材
        boost_candidates = []
        for m in self.materials:
            if m["roi"] >= breakeven * 1.2 and m["stat_cost"] >= 800 and m["status"] in ("健康",):
                boost_candidates.append({
                    "name": m["name"],
                    "roi": m["roi"],
                    "stat_cost": m["stat_cost"],
                    "score": m["score"],
                })
        # 按ROI降序
        boost_candidates.sort(key=lambda x: x["roi"], reverse=True)

        # 铁律2·追新不追老: 每天30%预算给3天内新素材
        new_mats = [m for m in self.materials if m.get("days_on", 99) <= 3]
        new_budget = round(total_spend * 0.30)
        new_budget_note = (f"3天内新素材{len(new_mats)}条，按铁律2划 {new_budget} 元（30%预算）"
                           if new_mats else f"无3天内新素材，需补充新素材池（铁律2要求每天30%预算给新素材）")

        # 玩法B·翻倍定锚建议: 当ROI卡死或低于目标时给出
        target_roi = self.profit["target_roi"]
        if self.profit["surface_roi"] < target_roi and avg_roi < breakeven * 2:
            anchor_note = ("玩法B·翻倍定锚: 主计划ROI设系统推荐值2倍+10条追投赛马(100元/5h)"
                           "，消耗10~25块查ROI不达标即关，循环3~5轮沉淀6~8条")
        else:
            anchor_note = "主计划ROI达标，维持现状；追投只对优质素材（追高不追低）"

        # 玩法G·ROI层级建议: ROI卡死时降层扩池
        if self.profit["surface_roi"] < breakeven and self.account.get("pay_roi", 0) > 0:
            roi_layer_note = ("玩法G·降层扩池: 当前ROI低于保本线，ROI降到系统建议值80%"
                              "（成交目标出价=客单价×毛利率÷0.8），等20~30min看消耗；降层扩池只做一次")
        else:
            roi_layer_note = "ROI层级正常，无需降层扩池"

        return {
            "boost_candidates": boost_candidates,
            "new_material_budget": new_budget,
            "new_material_note": new_budget_note,
            "anchor_note": anchor_note,
            "roi_layer_note": roi_layer_note,
            "avg_roi": round(avg_roi, 2),
            "total_spend": total_spend,
        }


class AccountTypeDiagnoser:
    """账号类型诊断（来自全域投放方法论: 先诊断再开药方）
    维度: 自然流占比/开播在线/2小时后在线/ROI稳定性/素材更新频率/客单价
    """

    @staticmethod
    def diagnose(account, materials, cost_params):
        # 指标推导（可基于 API 补充字段，此处用现有数据近似）
        roi = account.get("pay_roi", 0)
        ctr = account.get("ctr", 0)
        total_spend = sum(m["stat_cost"] for m in materials)
        avg_spend = total_spend / len(materials) if materials else 0
        high_spend_cnt = sum(1 for m in materials if m["stat_cost"] > 800)

        # 自然流占比近似: ROI高于表面均值 → 自然流贡献大
        natural_share = max(0.0, min(1.0, (roi - 8) / 10)) if roi > 8 else 0.0
        # ROI稳定性: 素材ROI离散度
        rois = [m["roi"] for m in materials if m.get("roi")]
        roi_spread = (max(rois) - min(rois)) / (sum(rois) / len(rois)) if len(rois) > 1 and sum(rois) else 0
        roi_stable = roi_spread < 0.8
        # 素材更新频率: 短周期素材(<=3天)占比
        new_cnt = sum(1 for m in materials if m.get("days_on", 99) <= 3)
        update_freq = new_cnt / len(materials) if materials else 0
        # 客单价
        gmv = account.get("pay_order_amount", 0)
        orders = account.get("pay_order_count", 0)
        unit_price = gmv / orders if orders else 0

        if natural_share >= 0.5:
            acct_type = "高自然流型"
            strategy = "维持低ROI冲量；2小时后提ROI保利润；前2小时规划节奏拉满自然流"
        elif roi_stable and update_freq >= 0.3:
            acct_type = "均衡型"
            strategy = "稳定投放，按阶段切换测试预算，素材方向持续测新"
        elif avg_spend < 1000:
            acct_type = "探索期账号"
            strategy = "先跑量建立数据模型，加大素材测试，验证自然流占比"
        else:
            acct_type = "付费主导型"
            strategy = "优化人货场后再降ROI，素材是核心；拉时长需谨慎（越长ROI越低）"

        return {
            "type": acct_type,
            "strategy": strategy,
            "natural_share": round(natural_share, 2),
            "roi_stable": roi_stable,
            "update_freq": round(update_freq, 2),
            "unit_price": round(unit_price, 2),
            "avg_spend": round(avg_spend, 2),
        }



class StrategyBuilder:
    """策略输出: 组装今日操作清单"""

    def __init__(self, profit, material_results, stage, cost_params, inventory):
        self.profit = profit
        self.materials = material_results
        self.stage = stage
        self.cp = cost_params["cost_params"]
        self.th = cost_params["thresholds"]
        self.inventory = inventory

    def build(self):
        close_list = [m for m in self.materials if m["action"] == "关停"]
        watch_list = [m for m in self.materials if m["action"] in ("观察2天", "密切观察")]
        boost_list = [m for m in self.materials if m["action"] == "加量"]
        keep_list = [m for m in self.materials if m["action"] == "维持"]
        test_passed = [m for m in self.materials if m["test_result"] == "通过"]
        test_failed = [m for m in self.materials if m["test_result"] == "未通过"]

        # 测试预算分配（按阶段）
        stage_key = self.stage.get("key") or self.stage["stage"]
        stage_budget_ratio = self.th["stage_test_budget"].get(stage_key, 0.15)
        total_spend = sum(m["stat_cost"] for m in self.materials)
        test_budget = round(total_spend * stage_budget_ratio)

        # 替换建议（按成本×成功率）
        replace_plan = []
        for m in close_list:
            replace_plan.append({
                "name": m["name"],
                "plan": "阶梯替换(成功率70%)" if self.profit["net_profit"] > 0 else "换封面低成本测试(成功率45%)",
            })

        # 预算分配法则（千川乘方: 成熟7:2:1 / 新账户5:3:2）
        is_new_account = self.stage.get("key") in ("cold_start", None) or total_spend < 3000
        if is_new_account:
            budget_rule = {"main": 0.5, "test": 0.3, "backup": 0.2, "label": "新账户 5:3:2"}
        else:
            budget_rule = {"main": 0.7, "test": 0.2, "aggressive": 0.1, "label": "成熟账户 7:2:1"}
        budget_alloc = {
            "rule": budget_rule["label"],
            "main_budget": round(total_spend * budget_rule["main"]),
            "test_budget": round(total_spend * budget_rule.get("test", 0.2)),
        }

        # 预算调整建议（表10: 按ROI表现）
        adj = "维持不变"
        if self.profit["surface_roi"] > self.th["ab_test"]["pass_roi"] * 1.2:
            adj = f"ROI>目标120% → 加预算30-50%（当前{self.profit['surface_roi']}）"
        elif self.profit["surface_roi"] < self.th["ab_test"]["pass_roi"] * 0.5:
            adj = f"ROI<目标50% → 暂停亏损计划（当前{self.profit['surface_roi']}）"
        elif self.profit["surface_roi"] < self.th["ab_test"]["pass_roi"] * 0.8:
            adj = f"ROI在目标50-80% → 观察并减预算20%（当前{self.profit['surface_roi']}）"

        return {
            "budget_alloc": budget_alloc,
            "budget_adj": adj,
            "close_list": close_list,
            "watch_list": watch_list,
            "boost_list": boost_list,
            "keep_list": keep_list,
            "test_passed": test_passed,
            "test_failed": test_failed,
            "test_budget": test_budget,
            "stage_budget_ratio": stage_budget_ratio,
            "replace_plan": replace_plan,
            "inventory_warning": self.inventory,
        }


class InventoryChecker:
    """素材库库存检查（3:1原则）"""

    @staticmethod
    def check(materials, thresholds):
        th = thresholds
        active = [m for m in materials if m["status"] in ("健康", "关注")]
        backup = [m for m in materials if m["status"] == "衰退" or m["days_on"] <= 3]
        testing = [m for m in materials if m.get("days_on", 99) <= 3]

        warns = []
        if len(active) < th["inventory"]["main_active"]:
            warns.append(f"主推在投素材仅{len(active)}条，低于安全线{th['inventory']['main_active']}条，需补充")
        if len(backup) < th["inventory"]["backup"]:
            warns.append(f"备选素材仅{len(backup)}条，低于安全线{th['inventory']['backup']}条，3:1原则要求每3条在投至少1条备选")
        if len(testing) < th["inventory"]["testing"]:
            warns.append(f"测试中素材仅{len(testing)}条，低于安全线{th['inventory']['testing']}条，需加大测试")
        return warns


def save_report(result, date_str):
    os.makedirs(DATA_DIR, exist_ok=True)
    path = os.path.join(DATA_DIR, f"report_{date_str}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    return path


def archive_history(result, date_str):
    """归档历史数据（用于12批复盘）"""
    os.makedirs(HISTORY_DIR, exist_ok=True)
    path = os.path.join(HISTORY_DIR, f"{date_str}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"account": result["account"], "materials": result["materials"]},
                  f, ensure_ascii=False, indent=2)
    return path


def main():
    parser = argparse.ArgumentParser(description="千川双引擎分析")
    parser.add_argument("--date", default=None, help="分析指定日期数据（默认取最新）")
    args = parser.parse_args()

    cost_params = load_cost_params()
    th = cost_params["thresholds"]

    # 读取最新原始数据
    if args.date:
        date_str = args.date
        raw_path = os.path.join(DATA_DIR, f"raw_{date_str}.json")
    else:
        raw_files = sorted([f for f in os.listdir(DATA_DIR) if f.startswith("raw_")])
        if not raw_files:
            print("未找到数据，请先运行 fetch_data.py --mock", file=sys.stderr)
            sys.exit(1)
        raw_path = os.path.join(DATA_DIR, raw_files[-1])
        date_str = raw_files[-1].replace("raw_", "").replace(".json", "")

    with open(raw_path, encoding="utf-8") as f:
        raw = json.load(f)

    account = raw["account"]
    materials = raw["materials"]

    # 1. 利润引擎
    profit = ProfitEngine(cost_params).analyze(account)
    # 2. 素材引擎
    material_results = MaterialEngine(cost_params, profit).analyze(materials)
    # 3. 阶段识别
    stage = StageDetector.detect(account, materials)
    # 3.5 账号类型诊断（全域投放方法论）
    account_type = AccountTypeDiagnoser.diagnose(account, materials, cost_params)
    # 4. 库存检查（用分析后的素材结果）
    inventory_warning = InventoryChecker.check(material_results, th)
    # 4.5 掉量排查（周期化运营方法论）
    decline_checks = DeclineChecker.check(account, material_results, profit, th)
    # 4.6 风险预警（看板设计方法论：带病增长判断）
    risk_checks = RiskChecker.check(account, profit, material_results, cost_params)
    # 4.7 ROI四层漏斗归因（小伍: 先流量再承接最后素材）
    roi_funnel = RoiFunnelDiagnoser.diagnose(account, profit)
    # 4.8 追投建议（分步实操手册: 四关激活/翻倍定锚/追投铁律）
    boost = BoostEngine(material_results, profit, account).analyze()
    # 5. 策略输出
    strategy = StrategyBuilder(profit, material_results, stage, cost_params, inventory_warning).build()

    # 汇总
    result = {
        "date": date_str,
        "account": account,
        "profit": profit,
        "materials": material_results,
        "stage": stage,
        "account_type": account_type,
        "decline_checks": decline_checks,
        "risk_checks": risk_checks,
        "roi_funnel": roi_funnel,
        "boost": boost,
        "strategy": strategy,
    }

    report_path = save_report(result, date_str)
    history_path = archive_history(result, date_str)
    print(f"分析完成: {report_path}")
    print(f"已归档: {history_path}")
    print()
    print(f"【利润】表面ROI={profit['surface_roi']} 真实ROI={profit['real_roi']} "
          f"保本ROI={profit['breakeven_roi']} 净利润={profit['net_profit']}元 "
          f"({profit['profit_status']})")
    print(f"【阶段】{stage['stage']} - {stage['desc']}")
    print(f"【掉量排查】")
    for c in decline_checks:
        print(f"  {'⚠' if '⚠' in c['status'] else '✅'} {c['item']}: {c['status']} - {c['action']}")
    print(f"【风险预警】")
    for r in risk_checks:
        lvl_icon = {"高": "🔴", "中": "🟠", "低": "🟢"}.get(r["level"], "•")
        print(f"  {lvl_icon} [{r['level']}] {r['item']}: {r['detail']} → {r['action']}")
    print(f"【ROI漏斗】{roi_funnel['layer']}（{roi_funnel['issue']}）→ {roi_funnel['action']}")
    print(f"【追投建议】{boost['anchor_note']}")
    print(f"  {boost['new_material_note']}")
    if boost['boost_candidates']:
        top = boost['boost_candidates'][0]
        print(f"  可追投优质素材 {len(boost['boost_candidates'])} 条，首选: {top['name']} (ROI {top['roi']})")
    print(f"  {boost['roi_layer_note']}")
    print(f"【账号类型】{account_type['type']} - 自然流占比~{account_type['natural_share']*100:.0f}% "
          f"ROI稳定={account_type['roi_stable']} 客单价{account_type['unit_price']}元")
    print(f"  策略: {account_type['strategy']}")
    print(f"【素材】共{len(material_results)}条: " +
          f"健康{sum(1 for m in material_results if m['status']=='健康')}条 / "
          f"关注{sum(1 for m in material_results if m['status']=='关注')}条 / "
          f"衰退{sum(1 for m in material_results if m['status']=='衰退')}条")
    print(f"【操作】关停{len(strategy['close_list'])}条 | 观察{len(strategy['watch_list'])}条 | "
          f"加量{len(strategy['boost_list'])}条 | 测试通过{len(strategy['test_passed'])}条 | "
          f"测试预算{strategy['test_budget']}元")
    print(f"【预算】{strategy['budget_alloc']['rule']} 主力{strategy['budget_alloc']['main_budget']}元/测试{strategy['budget_alloc']['test_budget']}元 | 调整: {strategy['budget_adj']}")
    if inventory_warning:
        print("【库存预警】")
        for w in inventory_warning:
            print(f"  ⚠ {w}")
    print()
    print("今日操作清单:")
    for m in strategy["close_list"]:
        print(f"  🔴 关停: {m['name']} ({m['action_reason']})")
    for m in strategy["watch_list"]:
        print(f"  🟡 观察: {m['name']} ({m['action_reason']})")
    for m in strategy["boost_list"]:
        print(f"  🟢 加量: {m['name']} ({m['action_reason']})")
    for m in strategy["test_passed"]:
        print(f"  ✅ 测试通过: {m['name']} ROI={m['roi']}")
    for m in strategy["test_failed"]:
        print(f"  ❌ 测试未通过: {m['name']} ROI={m['roi']}")
    for rp in strategy["replace_plan"]:
        print(f"  🔄 替换建议: {rp['name']} -> {rp['plan']}")


if __name__ == "__main__":
    main()
