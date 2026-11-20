# -*- coding: utf-8 -*-
"""专业匹配子引擎：精确命中 → 目录树祖先匹配 → 审核口径案例 → UNCERTAIN。"""
from app.engine.conditions import Result, PASS, FAIL, UNCERTAIN


def _find_major(catalog, major_text, stage=None, ctx=None):
    t = (major_text or "").strip()
    by_name = (ctx or {}).get("_major_by_name")
    if by_name is not None:
        hits = [r for r in by_name.get(t, []) if r.level == "专业"]
    else:
        hits = [r for r in catalog if r.name == t and r.level == "专业"]
    if not hits:
        return None
    if stage:
        pref = [r for r in hits if len(r.code) == 6 and r.code[0] == stage]
        if pref:
            return pref[0]
    return hits[0]


def _stage_from_edu(edu):
    from app.engine.conditions import normalize_edu
    n = normalize_edu(edu)
    if n in ("硕士研究生", "博士研究生", "研究生"):
        return "1"
    if n == "本科":
        return "2"
    if n in ("大专", "专科"):
        return "3"
    return None


STAGE_LABEL = {"1": "研究生", "2": "本科", "3": "专科"}


def _class_name(catalog, code, ctx=None):
    by_code = (ctx or {}).get("_class_by_code")
    if by_code is not None:
        row = by_code.get(code)
        return row.name if row else code
    for row in catalog:
        if row.code == code:
            return row.name
    return code


def match_major(major_text, req, ctx):
    if not req or req.get("type") == "any":
        return Result(PASS, "专业不限")
    if not major_text or not str(major_text).strip():
        return Result(UNCERTAIN, "画像缺少「专业」，请补充毕业证专业原文")

    text = str(major_text).strip()
    # 双学位/第二专业/括号方向：口径各省不一，保守转人工
    if any(sep in text for sep in ("/", "、", "（", "(")):
        return Result(UNCERTAIN, f"专业「{text}」含双学位/方向表述，审核口径需人工确认")

    catalog = ctx.get("catalog", [])
    cases = ctx.get("audit_cases", [])
    stage = _stage_from_edu(ctx.get("profile_edu"))

    if req.get("type") == "exact":
        names = req.get("names", [])
        if text in names:
            return Result(PASS, f"专业「{text}」精确命中要求")
        row = _find_major(catalog, text, stage, ctx)
        if row is None:
            hit = _search_case(cases, text, "、".join(names))
            if hit:
                return hit
            return Result(UNCERTAIN, f"专业「{text}」未收录于本省专业目录，需人工确认")
        return Result(FAIL, f"专业「{text}」不在要求名单（{'、'.join(names)}）内")

    if req.get("type") == "catalog_class":
        codes = req.get("codes", [])
        row = _find_major(catalog, text, stage, ctx)
        if row is None:
            hit = _search_case(cases, text, "/".join(_class_name(catalog, c, ctx) for c in codes))
            if hit:
                return hit
            return Result(UNCERTAIN, f"专业「{text}」未收录于本省专业目录，需人工确认所属类别")
        # 代码前缀即祖先关系：080901 属于 0809(计算机类) 属于 08(工学)
        for c in codes:
            if row.code.startswith(c):
                return Result(PASS, f"专业「{text}」({row.code}) 属于要求的「{_class_name(catalog, c, ctx)}」({c})")
        belong = _class_name(catalog, row.code[:4], ctx)
        req_names = [_class_name(catalog, c, ctx) for c in codes]
        # 同名大类但学历层次不符（江苏目录分研究生/本科/专科三栏）
        if (belong in req_names and len(row.code) == 6 and row.code[0] in STAGE_LABEL
                and all(len(c) == 4 and c[0] in STAGE_LABEL for c in codes)):
            return Result(FAIL, f"专业「{text}」属{STAGE_LABEL[row.code[0]]}层次「{belong}」，"
                                f"该职位要求{STAGE_LABEL[codes[0][0]]}层次对应专业")
        return Result(FAIL, f"专业「{text}」属「{belong}」，不属要求的「{'/'.join(req_names)}」")

    return Result(UNCERTAIN, f"未知专业要求类型 {req.get('type')}")


def _search_case(cases, major_text, req_text):
    for c in cases:
        if c.major_text == major_text and c.req_text == req_text:
            return Result(c.verdict, f"按历史审核口径判定：{c.evidence}")
    return None
