# -*- coding: utf-8 -*-
"""真实数据管线回归：表头归一化 / 学位派生 / 逗号分句 / 层次感知专业匹配。"""
import os
import sys
from types import SimpleNamespace

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.pipeline.cond_extract import (extract_conditions, parse_major, parse_other, split_items)
from app.engine.major import match_major
from app.engine.conditions import PASS, FAIL, UNCERTAIN

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def ns(code, name, level):
    return SimpleNamespace(code=code, name=name, level=level)


# 江苏目录仿真片段：法律类=序号3，财务财会类=序号9
JS_CATALOG = [
    ns("1003", "法律类", "专业类"), ns("2003", "法律类", "专业类"), ns("3003", "法律类", "专业类"),
    ns("100301", "刑法学", "专业"), ns("200301", "法学", "专业"), ns("300301", "法律事务", "专业"),
    ns("1009", "财务财会类", "专业类"), ns("2009", "财务财会类", "专业类"),
    ns("100901", "会计学", "专业"), ns("200901", "会计学", "专业"),
]


def test_split_items_paren_aware():
    items = split_items("企业管理（含：财务管理，市场营销），会计学")
    assert items == ["企业管理（含：财务管理，市场营销）", "会计学"]


def test_parse_other_comma_and_degree_consumed():
    leaves, risks, _ = parse_other("取得相应学位，中共党员（含预备），面向2027年普通高校应届毕业生")
    fields = [l.get("field") for l in leaves]
    assert "political" in fields and "is_fresh" in fields
    assert not any(l.get("op") == "manual_review" for l in leaves)


def test_parse_other_gender_hard_condition():
    leaves, _, _ = parse_other("取得相应学位，男性")
    assert {"field": "gender", "op": "==", "value": "男"} in leaves


def test_gender_eval():
    from app.engine.conditions import eval_node
    node = {"field": "gender", "op": "==", "value": "男"}
    assert eval_node(node, {"gender": "男"}, {}).status == PASS
    assert eval_node(node, {"gender": "女"}, {}).status == FAIL
    assert eval_node(node, {}, {}).status == UNCERTAIN


def test_info_clauses_not_manual_review():
    leaves, risks, _ = parse_other("录用后由公务员主管部门统筹分配，按照考试总成绩由高到低组织选岗")
    assert not any(l.get("op") == "manual_review" for l in leaves)
    assert len(risks) == 2


def test_degree_derived_from_edu():
    row = {"edu_req": "本科及以上", "major_req": "法律类", "other_req": "取得相应学位，中共党员"}
    tree, risks, _ = extract_conditions(row, JS_CATALOG)
    degree = [c for c in tree["children"] if c.get("field") == "degree"]
    assert degree == [{"field": "degree", "op": ">=", "value": "学士"}]


def test_degree_derived_graduate():
    row = {"edu_req": "研究生", "major_req": "刑法学", "other_req": "取得相应学位"}
    tree, _, _ = extract_conditions(row, JS_CATALOG)
    degree = [c for c in tree["children"] if c.get("field") == "degree"]
    assert degree[0]["value"] == "硕士"


def test_parse_major_stage_undergrad_plus():
    node = parse_major("法律类", JS_CATALOG, "本科及以上")
    assert node["value"]["type"] == "catalog_class"
    assert set(node["value"]["codes"]) == {"1003", "2003"}


def test_parse_major_stage_graduate_only():
    node = parse_major("法律类", JS_CATALOG, "研究生")
    assert node["value"]["codes"] == ["1003"]


def test_parse_major_unknown_class_manual_review():
    node = parse_major("外星语类", JS_CATALOG, "本科")
    assert node["op"] == "manual_review"


def test_match_major_cross_stage_pass():
    # 硕士会计学 报 本科及以上·财务财会类 → 研究生栏会计学命中1009
    ctx = {"catalog": JS_CATALOG, "audit_cases": [], "profile_edu": "硕士研究生"}
    req = {"type": "catalog_class", "codes": ["1009", "2009"]}
    assert match_major("会计学", req, ctx).status == PASS


def test_match_major_stage_mismatch_fail():
    # 本科法学 报 研究生-only 法律类 → FAIL（层次不符）
    ctx = {"catalog": JS_CATALOG, "audit_cases": [], "profile_edu": "本科"}
    req = {"type": "catalog_class", "codes": ["1003"]}
    res = match_major("法学", req, ctx)
    assert res.status == FAIL and "层次" in res.reason


def test_match_major_undergrad_pass():
    ctx = {"catalog": JS_CATALOG, "audit_cases": [], "profile_edu": "本科"}
    req = {"type": "catalog_class", "codes": ["1003", "2003"]}
    assert match_major("法学", req, ctx).status == PASS


def test_real_nanjing_file_parses():
    path = os.path.join(HERE, "data", "real", "nanjing_2027.xlsx")
    if not os.path.exists(path):
        pytest.skip("真实数据文件未下载")
    from app.pipeline.excel_parser import parse_excel, load_template
    tpl = load_template(os.path.join(HERE, "config", "provinces", "jiangsu_2027.yaml"))
    rows = parse_excel(path, tpl)
    assert len(rows) > 500
    r = rows[0]
    assert r["org_name"] and r["region_code"] == "010000"
    assert r["edu_req"] and r["major_req"]
    tree, risks, _ = extract_conditions(r, JS_CATALOG)
    assert tree is not None
