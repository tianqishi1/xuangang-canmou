# -*- coding: utf-8 -*-
"""条件抽取器回归集：常见职位表表述 → 条件树/风险标签/服务期。"""
from types import SimpleNamespace
from app.pipeline.cond_extract import extract_conditions, parse_other

CATALOG = [SimpleNamespace(code="0809", name="计算机类", level="专业类"),
           SimpleNamespace(code="08", name="工学", level="门类")]


def row(**kw):
    base = {"org_name": "测试单位", "major_req": "不限", "edu_req": "本科及以上",
            "degree_req": "学士及以上", "other_req": "", "remark": ""}
    base.update(kw)
    return base


class TestExtract:
    def test_edu_above(self):
        tree, _, _ = extract_conditions(row(), CATALOG)
        assert {"field": "edu", "op": ">=", "value": "本科"} in tree["children"]

    def test_only_benke(self):
        tree, _, _ = extract_conditions(row(edu_req="仅限本科"), CATALOG)
        assert {"field": "edu", "op": "==", "value": "本科"} in tree["children"]

    def test_major_class(self):
        tree, _, _ = extract_conditions(row(major_req="计算机类"), CATALOG)
        m = [c for c in tree["children"] if c.get("field") == "major"][0]
        assert m["value"] == {"type": "catalog_class", "codes": ["0809"]}

    def test_major_exact(self):
        tree, _, _ = extract_conditions(row(major_req="会计学、审计学"), CATALOG)
        m = [c for c in tree["children"] if c.get("field") == "major"][0]
        assert m["value"]["type"] == "exact"

    def test_fresh_party_grassroots(self):
        leaves, _, _ = parse_other("限应届毕业生；中共党员；两年以上基层工作经历")
        assert {"field": "is_fresh", "op": "==", "value": True} in leaves
        assert {"field": "political", "op": "in", "value": ["中共党员"]} in leaves
        assert {"field": "grassroots_years", "op": ">=", "value": 2} in leaves

    def test_hukou_and_service(self):
        leaves, risks, service = parse_other("限常州户籍；最低服务期5年")
        assert {"field": "hukou", "op": "in", "value": ["常州"]} in leaves
        assert service == 5
        assert "最低服务期5年" in risks

    def test_risk_not_hard_condition(self):
        leaves, risks, _ = parse_other("适合男性，经常夜班值班")
        assert leaves == []  # 风险提示不得变成硬性 FAIL 条件
        assert len(risks) >= 1

    def test_unknown_clause_manual_review(self):
        leaves, _, _ = parse_other("需常驻境外工作")
        assert leaves[0]["op"] == "manual_review"

    def test_sanbuxian_flag(self):
        _, risks, _ = extract_conditions(row(degree_req="不限"), CATALOG)
        assert any("三不限" in r for r in risks)

    def test_cert(self):
        leaves, _, _ = parse_other("取得法律职业资格证书")
        assert {"field": "cert", "op": "has", "value": "法律职业资格证书"} in leaves
