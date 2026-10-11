"""Transparent advertising simulation for a fictional teaching scenario.

No platform traffic, randomness, network request or database write is involved.
Rates below are assumptions, not forecasts or industry benchmarks. Counts are
rounded down at each funnel stage, so reported ratios can differ from the model.
"""

from decimal import Decimal, InvalidOperation, ROUND_DOWN

from lab import metrics


MODEL_VERSION = "commuter-bag-v1"
DEFAULT_CONFIG = {
    "budget": 1000,
    "audience": "broad",
    "creative": "benefit",
    "landing": "clear",
    "bid": "balanced",
}
CENT = Decimal("0.01")
PRICE = 199
VARIABLE_COST = 99

# All multipliers deliberately describe one invented context: an unfamiliar
# commuter bag, purchase objective, and a clear product-information page.
AUDIENCE = {
    "broad": {"cpm": "1", "ctr": "1", "purchase": "1"},
    "focused": {"cpm": "1.3", "ctr": "1.1", "purchase": "1.25"},
}
CREATIVE = {
    "feature": {"ctr": "0.85", "purchase": "1.15"},
    "benefit": {"ctr": "1.1", "purchase": "1"},
    "story": {"ctr": "1.6", "purchase": "0.6"},
}
LANDING = {
    "basic": {"arrival": "0.72", "purchase": "0.65"},
    "clear": {"arrival": "0.92", "purchase": "1.15"},
}
BID = {
    "balanced": {"cpm": "1", "ctr": "1", "purchase": "1"},
    "reach": {"cpm": "0.8", "ctr": "0.9", "purchase": "0.8"},
}


def _normalize(config):
    if not isinstance(config, dict):
        raise ValueError("模拟配置必须为对象")
    unknown = set(config) - set(DEFAULT_CONFIG)
    if unknown:
        raise ValueError("未知模拟字段：" + "、".join(sorted(map(str, unknown))))
    result = {**DEFAULT_CONFIG, **config}
    raw_budget = result["budget"]
    if isinstance(raw_budget, bool) or not isinstance(raw_budget, (int, float, str, Decimal)):
        raise ValueError("预算须为100—50000元的有限金额，最多两位小数")
    try:
        budget = Decimal(str(raw_budget))
        if (not budget.is_finite() or not Decimal("100") <= budget <= Decimal("50000")
                or budget != budget.quantize(CENT)):
            raise ValueError("预算须为100—50000元的有限金额，最多两位小数")
    except (InvalidOperation, ValueError) as exc:
        raise ValueError("预算须为100—50000元的有限金额，最多两位小数") from exc
    for key, options in (("audience", AUDIENCE), ("creative", CREATIVE),
                         ("landing", LANDING), ("bid", BID)):
        if not isinstance(result[key], str) or result[key] not in options:
            raise ValueError(f"{key}须选择：{'、'.join(options)}")
    result["budget"] = float(budget)
    return result, budget


def _d(value):
    return Decimal(value)


def _whole(value):
    return int(value.to_integral_value(rounding=ROUND_DOWN))


def simulate(config: dict) -> dict:
    """Return one deterministic, JSON-serializable simulated plan.

    Missing supported fields use DEFAULT_CONFIG. Unknown fields, unsupported
    choices, non-finite amounts and budgets outside 100..50000 are rejected.
    Metrics use the same formulas and None-for-zero-denominator rule as lab.py.
    """
    normalized, budget = _normalize(config)
    audience = AUDIENCE[normalized["audience"]]
    creative = CREATIVE[normalized["creative"]]
    landing = LANDING[normalized["landing"]]
    bid = BID[normalized["bid"]]

    cpm = _d("24") * _d(audience["cpm"]) * _d(bid["cpm"])
    ctr = _d("0.012") * _d(audience["ctr"]) * _d(creative["ctr"]) * _d(bid["ctr"])
    arrival_rate = _d(landing["arrival"])
    purchase_rate = (_d("0.05") * _d(audience["purchase"])
                     * _d(creative["purchase"]) * _d(landing["purchase"])
                     * _d(bid["purchase"]))

    impressions = _whole(budget * 1000 / cpm)
    clicks = _whole(_d(impressions) * ctr)
    landing_views = _whole(_d(clicks) * arrival_rate)
    purchases = _whole(_d(landing_views) * purchase_rate)
    # Buy only whole simulated impressions; cent-rounding never exceeds budget.
    spend = (_d(impressions) * cpm / 1000).quantize(CENT, rounding=ROUND_DOWN)
    totals = {
        "impressions": impressions,
        "clicks": clicks,
        "landing_views": landing_views,
        "purchases": purchases,
        "spend": float(spend),
        "revenue": float(purchases * PRICE),
        "variable_cost": float(purchases * VARIABLE_COST),
    }
    calculated = metrics(totals)
    funnel = []
    previous = None
    for key, label in (("impressions", "曝光"), ("clicks", "点击"),
                       ("landing_views", "到达商品页"), ("purchases", "购买")):
        count = totals[key]
        funnel.append({"key": key, "label": label, "count": count,
                       "rate_from_previous": count / previous if previous else None})
        previous = count

    assumptions = [
        "全部数字来自固定教学公式，不使用真实平台、真实订单或随机抽样；相同配置可复现。",
        "虚构商品为通勤双肩包：每单收入199元，商品及履约变动成本99元；购买目标、CNY口径。",
        "基准CPM设定24元，点击率1.2%，到达后的购买率5%；这不是行业基准或投放预测。",
        "精准人群：CPM×1.3、点击率×1.1、购买率×1.25；是假设相关性更强但曝光更贵。",
        "功能/利益/故事素材：点击率分别×0.85/1.1/1.6，购买率分别×1.15/1/0.6；故事吸引更多好奇点击是本情境设定。",
        "基础/清晰商品页：到达率72%/92%，购买率×0.65/1.15；不推断任何真实页面表现。",
        "曝光优先出价：CPM×0.8、点击率×0.9、购买率×0.8；用于演示便宜曝光不必然带来更多购买。",
        "曝光、点击、到达、购买逐层向下取整，花费按曝光价格计算后向下保留两位小数；微小剩余预算不再购买曝光。",
        "显示的是观察完毕的整段虚拟投放汇总，无归因延迟、退款、竞价波动、预算饱和、重复用户或增量因果推断。",
        "ROI使用商品变动成本与广告费之和为分母，未含税费、固定成本等；应先核对真实业务成本口径。",
    ]
    insights = [
        f"预算¥{float(budget):,.2f}，模拟花费¥{float(spend):,.2f}；漏斗为{impressions:,}次曝光→{clicks:,}次点击→{landing_views:,}次到达→{purchases:,}笔购买。",
        "比较方案时保持预算和其他条件不变，每次只改变一个选项；本模型对比只能解释设定，不能证明市场规律。",
    ]
    if normalized["creative"] == "story":
        insights.append("本情境为故事素材设定更高点击率、更低购买意向；点击多不等于购买多，请同时比较CPA和贡献利润。")
    if normalized["audience"] == "focused":
        insights.append("本情境的精准人群曝光更贵、购买意向更高；是否值得要比较购买数量、CPA和利润，不能只看CPM。")
    if normalized["landing"] == "basic":
        insights.append("基础商品页在本情境中同时降低到达和购买；练习将问题定位到点击之后，但真实业务仍需检查加载、埋点和资料一致性。")
    if normalized["bid"] == "reach":
        insights.append("曝光优先在本情境中降低CPM但也降低后续转化；购买目标不能仅以曝光量评价。")
    if not purchases:
        insights.append("向下取整后购买为0，CPA不可计算（返回null），收入和商品变动成本为0；这不是CPA为0。")
    elif calculated["profit"] < 0:
        insights.append("当前成本口径下贡献利润为负；先核对成本和收入，再设计验证实验，不能只看ROAS大于1。")

    return {
        "config": normalized,
        "totals": totals,
        "metrics": calculated,
        "funnel": funnel,
        "label": "纯虚拟教学模拟｜固定公式｜不代表真实投放效果",
        "model": {
            "version": MODEL_VERSION,
            "cpm": float(cpm),
            "ctr": float(ctr),
            "arrival_rate": float(arrival_rate),
            "purchase_rate_after_arrival": float(purchase_rate),
            "rounding": "各层人数向下取整，花费向下保留两位小数",
        },
        "model_assumptions": assumptions,
        "insights": insights,
    }
