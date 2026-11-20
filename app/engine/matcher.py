# -*- coding: utf-8 -*-
"""画像 × 岗位批量匹配。"""
from app.engine.conditions import eval_node


def match_profile(profile: dict, positions, ctx):
    ctx = dict(ctx)
    ctx["profile_edu"] = profile.get("edu")  # 专业目录层次定位（研究生/本科/专科）
    # 目录索引：避免每岗位 O(n) 线性扫描（真实目录约5000条）
    by_name, by_code = {}, {}
    for r in ctx.get("catalog", []):
        by_name.setdefault(r.name, []).append(r)
        by_code.setdefault(r.code, r)
    ctx["_major_by_name"] = by_name
    ctx["_class_by_code"] = by_code
    out = []
    for p in positions:
        res = eval_node(p.cond_json, profile, ctx)
        out.append({
            "position_id": p.id,
            "org_name": p.org_name,
            "region": p.region,
            "org_level": p.org_level,
            "quota": p.quota,
            "service_years": p.service_years,
            "status": res.status,
            "reason": res.reason,
            "risk_flags": p.risk_flags or [],
            "parse_status": p.parse_status,
        })
    order = {"PASS": 0, "UNCERTAIN": 1, "FAIL": 2}
    out.sort(key=lambda x: order[x["status"]])
    return out
