# -*- coding: utf-8 -*-
"""专业匹配子引擎回归集：精确 / 目录祖先 / 门类 / 未收录 / 审核案例 / 双学位。"""
from app.engine.major import match_major
from app.engine.conditions import PASS, FAIL, UNCERTAIN


def cls(*codes):
    return {"type": "catalog_class", "codes": list(codes)}


def exact(*names):
    return {"type": "exact", "names": list(names)}


class TestMajor:
    def test_any_pass(self, ctx):
        assert match_major("任何专业", {"type": "any"}, ctx).status == PASS

    def test_exact_hit(self, ctx):
        assert match_major("会计学", exact("会计学", "审计学"), ctx).status == PASS

    def test_exact_miss_known_major_fails(self, ctx):
        assert match_major("计算机科学与技术", exact("会计学"), ctx).status == FAIL

    def test_class_prefix_match(self, ctx):
        assert match_major("软件工程", cls("0809"), ctx).status == PASS

    def test_class_mismatch_fails(self, ctx):
        r = match_major("信息管理与信息系统", cls("0809"), ctx)
        assert r.status == FAIL
        assert "管理科学与工程" in r.reason

    def test_gate_level_match(self, ctx):
        assert match_major("计算机科学与技术", cls("08"), ctx).status == PASS

    def test_multi_class_or(self, ctx):
        assert match_major("会计学", cls("0809", "1202"), ctx).status == PASS

    def test_unknown_major_uncertain(self, ctx):
        assert match_major("临床医学", cls("0809"), ctx).status == UNCERTAIN

    def test_unknown_major_exact_uncertain(self, ctx):
        assert match_major("临床医学", exact("会计学"), ctx).status == UNCERTAIN

    def test_audit_case_pass_old_name(self, ctx):
        r = match_major("计算机及应用", cls("0809"), ctx)
        assert r.status == PASS
        assert "口径" in r.reason

    def test_audit_case_fail(self, ctx):
        r = match_major("信息管理与信息系统", exact("计算机科学与技术"), ctx)
        # 精确名单未命中且目录可查 → 直接 FAIL（不走案例）
        assert r.status == FAIL

    def test_dual_degree_uncertain(self, ctx):
        assert match_major("法学/计算机科学与技术", cls("0809"), ctx).status == UNCERTAIN

    def test_empty_major_uncertain(self, ctx):
        assert match_major("", cls("0809"), ctx).status == UNCERTAIN
        assert match_major(None, {"type": "any"}, ctx).status == PASS
