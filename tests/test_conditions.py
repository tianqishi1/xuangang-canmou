# -*- coding: utf-8 -*-
"""资格规则引擎回归集：三态逻辑 / 学历学位 / 政治面貌 / 应届 / 户籍 / 基层 / 缺失字段。"""
from app.engine.conditions import eval_node, PASS, FAIL, UNCERTAIN


def leaf(field, op, value):
    return {"field": field, "op": op, "value": value}


def AND(*children):
    return {"op": "AND", "children": list(children)}


def OR(*children):
    return {"op": "OR", "children": list(children)}


class TestLogic:
    def test_and_fail_dominates(self, base_profile, ctx):
        r = eval_node(AND(leaf("edu", ">=", "本科"), leaf("hukou", "in", ["苏州"])), base_profile, ctx)
        assert r.status == FAIL

    def test_and_uncertain_when_no_fail(self, base_profile, ctx):
        p = dict(base_profile, is_fresh=None)
        r = eval_node(AND(leaf("edu", ">=", "本科"), leaf("is_fresh", "==", True)), p, ctx)
        assert r.status == UNCERTAIN

    def test_or_pass_dominates(self, base_profile, ctx):
        r = eval_node(OR(leaf("hukou", "in", ["苏州"]), leaf("edu", ">=", "本科")), base_profile, ctx)
        assert r.status == PASS

    def test_or_all_fail(self, base_profile, ctx):
        r = eval_node(OR(leaf("hukou", "in", ["苏州"]), leaf("edu", ">=", "博士研究生")), base_profile, ctx)
        assert r.status == FAIL

    def test_empty_tree_pass(self, base_profile, ctx):
        assert eval_node(None, base_profile, ctx).status == PASS


class TestEdu:
    def test_benke_meets_benke_above(self, base_profile, ctx):
        assert eval_node(leaf("edu", ">=", "本科"), base_profile, ctx).status == PASS

    def test_dazhuan_fails_benke(self, base_profile, ctx):
        p = dict(base_profile, edu="大专")
        assert eval_node(leaf("edu", ">=", "本科"), p, ctx).status == FAIL

    def test_master_meets_benke_above(self, base_profile, ctx):
        p = dict(base_profile, edu="硕士研究生")
        assert eval_node(leaf("edu", ">=", "本科"), p, ctx).status == PASS

    def test_only_benke_rejects_master(self, base_profile, ctx):
        p = dict(base_profile, edu="硕士研究生")
        assert eval_node(leaf("edu", "==", "本科"), p, ctx).status == FAIL

    def test_alias_normalization(self, base_profile, ctx):
        p = dict(base_profile, edu="大学本科")
        assert eval_node(leaf("edu", ">=", "本科"), p, ctx).status == PASS

    def test_degree(self, base_profile, ctx):
        assert eval_node(leaf("degree", ">=", "学士"), base_profile, ctx).status == PASS
        p = dict(base_profile, degree="无")
        assert eval_node(leaf("degree", ">=", "学士"), p, ctx).status == FAIL


class TestIdentity:
    def test_fresh_required_unknown_is_uncertain(self, base_profile, ctx):
        p = dict(base_profile, is_fresh=None)
        assert eval_node(leaf("is_fresh", "==", True), p, ctx).status == UNCERTAIN

    def test_fresh_required_social_fails(self, base_profile, ctx):
        p = dict(base_profile, is_fresh=False)
        assert eval_node(leaf("is_fresh", "==", True), p, ctx).status == FAIL

    def test_party_full_includes_probationary(self, base_profile, ctx):
        p = dict(base_profile, political="中共预备党员")
        assert eval_node(leaf("political", "in", ["中共党员"]), p, ctx).status == PASS

    def test_party_rejects_league(self, base_profile, ctx):
        assert eval_node(leaf("political", "in", ["中共党员"]), base_profile, ctx).status == FAIL

    def test_party_or_league(self, base_profile, ctx):
        assert eval_node(leaf("political", "in", ["中共党员", "共青团员"]), base_profile, ctx).status == PASS

    def test_hukou_prefix(self, base_profile, ctx):
        p = dict(base_profile, hukou="南京市鼓楼区")
        assert eval_node(leaf("hukou", "in", ["南京"]), p, ctx).status == PASS
        assert eval_node(leaf("hukou", "in", ["苏州"]), p, ctx).status == FAIL

    def test_grassroots(self, base_profile, ctx):
        p = dict(base_profile, grassroots_years=3)
        assert eval_node(leaf("grassroots_years", ">=", 2), p, ctx).status == PASS
        assert eval_node(leaf("grassroots_years", ">=", 5), p, ctx).status == FAIL

    def test_cert(self, base_profile, ctx):
        p = dict(base_profile, certs=["法律职业资格证书"])
        assert eval_node(leaf("cert", "has", "法律职业资格证书"), p, ctx).status == PASS
        assert eval_node(leaf("cert", "has", "法律职业资格证书"), base_profile, ctx).status == FAIL


class TestSafety:
    def test_missing_field_never_pass(self, base_profile, ctx):
        for fld in ("edu", "degree", "hukou", "political", "grassroots_years"):
            p = dict(base_profile)
            p[fld] = None
            r = eval_node(leaf(fld, ">=", "本科" if fld == "edu" else "x"), p, ctx)
            assert r.status == UNCERTAIN, fld

    def test_manual_review_is_uncertain(self, base_profile, ctx):
        r = eval_node(leaf("other", "manual_review", "需常驻境外"), base_profile, ctx)
        assert r.status == UNCERTAIN

    def test_unknown_field_is_uncertain(self, base_profile, ctx):
        r = eval_node(leaf("mystery", "==", 1), base_profile, ctx)
        assert r.status == UNCERTAIN
