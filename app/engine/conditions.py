# -*- coding: utf-8 -*-
"""确定性资格规则引擎：三态逻辑（PASS/FAIL/UNCERTAIN），LLM 零参与。

条件树 DSL:
  {"op": "AND"|"OR", "children": [...]}
  叶子: {"field": ..., "op": ..., "value": ...}
红线：任何字段缺失/无法判定 → UNCERTAIN，绝不假阳性 PASS。
"""
from dataclasses import dataclass, field as dc_field

PASS, FAIL, UNCERTAIN = "PASS", "FAIL", "UNCERTAIN"

EDU_ORDER = {"高中": 1, "中专": 1, "大专": 2, "专科": 2, "本科": 3,
             "硕士研究生": 4, "研究生": 4, "博士研究生": 5}
EDU_ALIAS = {"大学本科": "本科", "大学专科": "大专", "硕士": "硕士研究生",
             "博士": "博士研究生", "硕士研究生及以上": "硕士研究生"}
DEGREE_ORDER = {"无": 0, "学士": 1, "硕士": 2, "博士": 3}
PARTY_FULL = {"中共党员", "中共预备党员"}


@dataclass
class Result:
    status: str
    reason: str = ""
    children: list = dc_field(default_factory=list)

    @property
    def ok(self):
        return self.status == PASS


def _and(results):
    if any(r.status == FAIL for r in results):
        fails = [r.reason for r in results if r.status == FAIL]
        return Result(FAIL, "；".join(fails), results)
    if any(r.status == UNCERTAIN for r in results):
        uncs = [r.reason for r in results if r.status == UNCERTAIN]
        return Result(UNCERTAIN, "；".join(uncs), results)
    return Result(PASS, "全部条件符合", results)


def _or(results):
    if any(r.status == PASS for r in results):
        return Result(PASS, "满足可选条件之一", results)
    if any(r.status == UNCERTAIN for r in results):
        return Result(UNCERTAIN, "；".join(r.reason for r in results if r.status == UNCERTAIN), results)
    return Result(FAIL, "；".join(r.reason for r in results if r.status == FAIL), results)


def normalize_edu(text):
    if not text:
        return None
    t = str(text).strip()
    return EDU_ALIAS.get(t, t)


def eval_node(node, profile, ctx):
    """ctx: {'catalog': [MajorCatalog...], 'audit_cases': [AuditCase...], 'province': str}"""
    if node is None:
        return Result(PASS, "无限制条件")
    op = node.get("op")
    if op == "AND":
        return _and([eval_node(c, profile, ctx) for c in node.get("children", [])])
    if op == "OR":
        return _or([eval_node(c, profile, ctx) for c in node.get("children", [])])
    return eval_leaf(node, profile, ctx)


def eval_leaf(node, profile, ctx):
    fld, op, val = node.get("field"), node.get("op"), node.get("value")

    if op == "manual_review":
        return Result(UNCERTAIN, f"条件需人工确认：{val}")

    if fld == "major":
        from app.engine.major import match_major
        return match_major(profile.get("major_text"), val, ctx)

    raw = profile.get("certs") if fld == "cert" else profile.get(fld)
    if raw is None or raw == "":
        return Result(UNCERTAIN, f"画像缺少「{FIELD_LABELS.get(fld, fld)}」，请补充后重新匹配")

    if fld == "edu":
        u, r = normalize_edu(raw), normalize_edu(val)
        if u not in EDU_ORDER or r not in EDU_ORDER:
            return Result(UNCERTAIN, f"学历表述无法识别：{raw} / 要求 {val}")
        if op == ">=":
            ok = EDU_ORDER[u] >= EDU_ORDER[r]
            return Result(PASS if ok else FAIL,
                          f"学历{u}{'≥' if ok else '<'}要求{r}")
        if op == "==":
            ok = EDU_ORDER[u] == EDU_ORDER[r]
            return Result(PASS if ok else FAIL, f"学历{u}，仅限{r}")
        return Result(UNCERTAIN, f"未知学历运算符 {op}")

    if fld == "degree":
        u = str(raw).replace("学位", "")
        r = str(val).replace("学位", "")
        if u not in DEGREE_ORDER or r not in DEGREE_ORDER:
            return Result(UNCERTAIN, f"学位表述无法识别：{raw} / 要求 {val}")
        ok = DEGREE_ORDER[u] >= DEGREE_ORDER[r] if op == ">=" else DEGREE_ORDER[u] == DEGREE_ORDER[r]
        return Result(PASS if ok else FAIL, f"学位{u}，要求{val}")

    if fld == "is_fresh":
        if not isinstance(raw, bool):
            return Result(UNCERTAIN, "应届身份未确认，请补充毕业年份/社保情况")
        ok = raw == val
        return Result(PASS if ok else FAIL,
                      "应届身份符合" if ok else ("该岗仅限应届毕业生" if val else "该岗仅限非应届（社会人员）"))

    if fld == "political":
        allowed = set(val) if isinstance(val, list) else {val}
        expanded = set()
        for a in allowed:
            if a == "中共党员":
                expanded |= PARTY_FULL
            else:
                expanded.add(a)
        ok = str(raw).strip() in expanded
        return Result(PASS if ok else FAIL, f"政治面貌{raw}，要求{'/'.join(sorted(allowed))}")

    if fld == "hukou":
        allowed = val if isinstance(val, list) else [val]
        ok = any(str(raw).strip().startswith(a) or a in str(raw) for a in allowed)
        return Result(PASS if ok else FAIL, f"户籍{raw}，要求{'/'.join(allowed)}")

    if fld == "grassroots_years":
        try:
            ok = float(raw) >= float(val)
        except (TypeError, ValueError):
            return Result(UNCERTAIN, "基层工作年限无法解析")
        return Result(PASS if ok else FAIL, f"基层经历{raw}年，要求≥{val}年")

    if fld == "cert":
        certs = profile.get("certs") or []
        ok = val in certs
        return Result(PASS if ok else FAIL, f"要求证书「{val}」{'已有' if ok else '未提供'}")

    if fld == "gender":
        if not raw or str(raw).strip() not in ("男", "女"):
            return Result(UNCERTAIN, "性别未确认，请补充（人民警察等职位有性别硬性要求）")
        ok = str(raw).strip() == val
        return Result(PASS if ok else FAIL, f"性别{raw}，要求{val}")

    if fld == "age":
        try:
            ok = float(raw) <= float(val)
        except (TypeError, ValueError):
            return Result(UNCERTAIN, "年龄无法解析")
        return Result(PASS if ok else FAIL, f"年龄{raw}，要求≤{val}")

    return Result(UNCERTAIN, f"未知条件字段 {fld}，需人工确认")


FIELD_LABELS = {"edu": "学历", "degree": "学位", "major_text": "专业", "gender": "性别",
                "is_fresh": "应届身份", "hukou": "户籍", "political": "政治面貌",
                "grassroots_years": "基层工作年限", "certs": "证书", "age": "年龄"}

