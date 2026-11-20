# -*- coding: utf-8 -*-
"""确定性条件抽取器：把职位表各列与「其他条件」栏人话转成条件树。

M0 用规则+词典；LLM 辅助抽取作为可插拔扩展点（extract_with_llm），
其输出同样必须走人工审核后才置 parse_status=reviewed。
"""
import re
from app.engine.conditions import normalize_edu

CN_NUM = {"一": 1, "两": 2, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9, "十": 10}
RISK_PATTERNS = [
    (r"适合男性|适宜男性", "性别倾向提示（非硬性条件，注意实际工作强度）"),
    (r"常年下乡|经常下乡|驻村", "需常年下乡/驻村"),
    (r"经常加班|加班较多|夜班|值班", "加班/值班较多"),
    (r"野外|高空|井下|一线执法", "野外/一线作业"),
    (r"经常出差|长期出差|长期驻点|封闭驻点|需长期驻点", "需长期驻点/经常出差"),
    (r"统筹分配|统一分配|统筹使用", "录用后统筹分配（具体单位待定）"),
    (r"组织选岗|依次选岗|按.*成绩.*选岗", "按考试总成绩选岗"),
    (r"课程试讲|试讲|专业能力测试", "面试含专业能力测试/试讲"),
    (r"三不限", "三不限岗位（竞争通常极高）"),
]
KNOWN_CERTS = ["法律职业资格证书", "注册会计师", "英语六级", "英语四级", "计算机二级",
               "医师执业证书", "护士执业证书", "教师资格"]


def split_items(text):
    # 按 、，,;； 切分，但忽略括号内部的分隔符（如「企业管理（含：财务管理，市场营销）」）
    items, buf, depth = [], [], 0
    for ch in str(text or ""):
        if ch in "（(":
            depth += 1
        elif ch in "）)":
            depth = max(0, depth - 1)
        if depth == 0 and ch in "、，,;；":
            if "".join(buf).strip():
                items.append("".join(buf).strip())
            buf = []
        else:
            buf.append(ch)
    if "".join(buf).strip():
        items.append("".join(buf).strip())
    return items


def _num(text):
    if text.isdigit():
        return int(text)
    return CN_NUM.get(text)


def parse_edu(raw):
    if not raw or str(raw).strip() in ("不限", "无限制", ""):
        return None
    t = str(raw).strip()
    m = re.search(r"(博士研究生|硕士研究生|研究生|本科|大专|专科|高中|中专)", t)
    if not m:
        return {"field": "edu", "op": "manual_review", "value": f"学历要求：{t}"}
    base = normalize_edu(m.group(1))
    if "仅限" in t or re.search(r"^限", t):
        return {"field": "edu", "op": "==", "value": base}
    return {"field": "edu", "op": ">=", "value": base}


def parse_degree(raw):
    if not raw or str(raw).strip() in ("不限", "无限制", ""):
        return None
    t = str(raw).strip()
    m = re.search(r"(博士|硕士|学士)", t)
    if not m:
        return {"field": "edu", "op": "manual_review", "value": f"学位要求：{t}"}
    return {"field": "degree", "op": ">=", "value": m.group(1)}


def _stages_for_edu(edu_raw):
    # 职位学历栏 → 允许的专业目录层次（1研究生/2本科/3专科）
    t = str(edu_raw or "").strip()
    if not t or t in ("不限", "无限制"):
        return {1, 2, 3}
    if "博士" in t or "研究生" in t or "硕士" in t:
        return {1}
    if "本科" in t:
        return {1, 2} if "以上" in t else {2}
    if "大专" in t or "专科" in t:
        return {1, 2, 3} if "以上" in t else {3}
    return {1, 2, 3}


def parse_major(raw, catalog, edu_req=None):
    if not raw or str(raw).strip() in ("不限", "无限制", ""):
        return {"field": "major", "op": "match", "value": {"type": "any"}}
    items = split_items(raw)
    stages = _stages_for_edu(edu_req)
    codes, names, reviews = [], [], []
    for it in items:
        hits = [r for r in catalog if r.name == it and r.level in ("专业类", "门类")]
        # 江苏仿真目录代码：层次(1位)+大类序号(3位)；教育部旧代码不受层次过滤影响
        syn = [r for r in hits if re.fullmatch(r"[123][0-9]{3}", r.code)]
        if syn:
            sel = [r.code for r in syn if int(r.code[0]) in stages]
            if sel:
                codes.extend(sel)
            else:
                reviews.append(f"专业大类「{it}」与职位学历层次不对应，需人工确认")
        elif hits:
            codes.append(hits[0].code)
        elif it.endswith("类"):
            reviews.append(f"专业大类「{it}」未收录于本省专业参考目录，需人工确认")
        else:
            names.append(it)
    leaves = []
    if codes:
        leaves.append({"field": "major", "op": "match", "value": {"type": "catalog_class", "codes": codes}})
    if names:
        leaves.append({"field": "major", "op": "match", "value": {"type": "exact", "names": names}})
    for rv in reviews:
        leaves.append({"field": "major", "op": "manual_review", "value": rv})
    if len(leaves) == 1:
        return leaves[0]
    return {"op": "OR", "children": leaves}


def parse_other(raw):
    """返回 (条件叶子列表, 风险标签列表, 服务期年数或None)"""
    leaves, risks, service = [], [], None
    if not raw or str(raw).strip() in ("不限", "无", ""):
        return leaves, risks, service
    clauses = [c.strip() for c in re.split(r"[；;。\n，,]", str(raw)) if c.strip()]
    for c in clauses:
        consumed = False
        if re.search(r"应届", c):
            val = False if re.search(r"非应届|社会人员", c) else True
            leaves.append({"field": "is_fresh", "op": "==", "value": val})
            consumed = True
        if "中共党员" in c or "党员" in c:
            allowed = ["中共党员"]
            if "共青团员" in c:
                allowed.append("共青团员")
            leaves.append({"field": "political", "op": "in", "value": allowed})
            consumed = True
        m = re.search(r"([0-9一两二三四五六七八九十]+)年(?:以上)?(?:的)?基层工作经历", c)
        if m:
            n = _num(m.group(1))
            if n is not None:
                leaves.append({"field": "grassroots_years", "op": ">=", "value": n})
                consumed = True
        m = re.search(r"限([^，,；;。]{2,12}?)户籍", c)
        if m:
            leaves.append({"field": "hukou", "op": "in", "value": [m.group(1)]})
            consumed = True
        m = re.search(r"(?:最低服务期|最低服务年限|服务期)(?:为|不少于)?([0-9一两二三四五六七八九十]+)年", c)
        if m:
            n = _num(m.group(1))
            if n is not None:
                service = n
                risks.append(f"最低服务期{n}年")
                consumed = True
        for cert in KNOWN_CERTS:
            if cert in c:
                leaves.append({"field": "cert", "op": "has", "value": cert})
                consumed = True
        for pat, label in RISK_PATTERNS:
            if re.search(pat, c):
                risks.append(label)
                consumed = True  # 风险提示不是硬性条件，但整句已被理解
        if re.search(r"取得相应学位|取得对应学位", c):
            consumed = True  # 学位条件由 extract_conditions 按学历栏统一派生
        if re.search(r"(?:本科|研究生)阶段须为", c):
            leaves.append({"field": "other", "op": "manual_review", "value": c})
            consumed = True  # 阶段专业限制，引擎暂不支持自动判定
        if c in ("男性", "女性"):
            leaves.append({"field": "gender", "op": "==", "value": c[0]})
            consumed = True
        if re.search(r"户籍（生源）|户籍\(生源\)", c):
            leaves.append({"field": "other", "op": "manual_review",
                           "value": f"户籍/生源口径需人工确认：{c}"})
            consumed = True
        if re.search(r"年龄可放宽|另行通知|生活能够自理|能正常履行岗位职责|独立开展工作", c):
            consumed = True  # 程序性说明/放宽条款，不构成可自动判定的硬条件
        if not consumed:
            leaves.append({"field": "other", "op": "manual_review", "value": c})
    return leaves, risks, service


def extract_conditions(row, catalog):
    """row: 规范化后的职位行 dict。返回 (cond_tree, risk_flags, service_years)"""
    children = []
    for fn, key in ((parse_edu, "edu_req"), (parse_degree, "degree_req")):
        node = fn(row.get(key))
        if node:
            children.append(node)
    children.append(parse_major(row.get("major_req"), catalog, row.get("edu_req")))
    other_leaves, risks, service = parse_other(row.get("other_req"))
    children.extend(other_leaves)
    remark_leaves, remark_risks, remark_service = parse_other(row.get("remark"))
    children.extend(remark_leaves)
    risks.extend(remark_risks)
    service = service or remark_service
    # 真实省考表无独立学位栏：「取得相应学位」出现在其它栏，按学历栏派生
    other_text = str(row.get("other_req") or "")
    has_degree = any(isinstance(c, dict) and c.get("field") == "degree" for c in children)
    if not has_degree and re.search(r"取得相应学位|取得对应学位", other_text):
        edu = str(row.get("edu_req") or "")
        val = ("博士" if "博士" in edu else
               "硕士" if ("研究生" in edu or "硕士" in edu) else
               "学士" if "本科" in edu else None)
        if val:
            children.append({"field": "degree", "op": ">=", "value": val})
    # 职位简介只提取风险提示，不产生硬条件
    desc = str(row.get("position_desc") or "")
    if desc:
        for pat, label in RISK_PATTERNS:
            if re.search(pat, desc) and label not in risks:
                risks.append(label)
    # 三不限识别：专业不限 + 无其他硬条件
    major_any = any(c.get("field") == "major" and c.get("value", {}).get("type") == "any"
                    for c in children if isinstance(c, dict))
    hard = [c for c in children if c.get("field") not in ("major", "other", "edu", "degree")]
    if major_any and not hard:
        risks.append("三不限岗位（竞争通常极高）")
    tree = {"op": "AND", "children": children} if children else None
    return tree, risks, service


def extract_with_llm(row, llm_client):
    """扩展点：LLM 辅助抽取（qwen-plus + JSON schema 约束）。
    M0 未启用；启用后输出必须经人工审核队列，禁止直接 reviewed。"""
    raise NotImplementedError("M1 接入百炼 API 后启用，输出须人工审核")

