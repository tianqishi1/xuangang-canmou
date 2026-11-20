# -*- coding: utf-8 -*-
"""端到端回归：职位行 → 条件抽取 → 规则引擎匹配（不经数据库）。"""
from types import SimpleNamespace
from app.pipeline.cond_extract import extract_conditions
from app.engine.matcher import match_profile
from tests.conftest import CATALOG


def make_position(pid, **kw):
    row = {"org_name": f"单位{pid}", "major_req": "不限", "edu_req": "本科及以上",
           "degree_req": "学士及以上", "other_req": "", "remark": ""}
    row.update(kw)
    catalog = [SimpleNamespace(code=c, name=n, level=l) for c, n, l in CATALOG]
    tree, risks, service = extract_conditions(row, catalog)
    return SimpleNamespace(id=pid, org_name=row["org_name"], region="南京",
                           org_level="市级", quota=1, service_years=service,
                           cond_json=tree, risk_flags=risks, parse_status="auto")


class TestEndToEnd:
    def test_computer_fresh_grad(self, base_profile, ctx):
        positions = [
            make_position(1, org_name="大数据局", major_req="计算机类", other_req="限应届毕业生"),
            make_position(2, org_name="司法局", major_req="法学类"),
            make_position(3, org_name="乡镇街道", other_req="限苏州户籍", remark="最低服务期5年"),
        ]
        results = {r["position_id"]: r for r in match_profile(base_profile, positions, ctx)}
        assert results[1]["status"] == "PASS"
        assert results[2]["status"] == "FAIL"
        assert results[3]["status"] == "FAIL"
        assert results[3]["service_years"] == 5

    def test_xinguan_major_trap(self, base_profile, ctx):
        """信管专业报计算机类岗必须 FAIL，报管理科学与工程类岗必须 PASS。"""
        p = dict(base_profile, major_text="信息管理与信息系统")
        positions = [
            make_position(1, org_name="大数据局", major_req="计算机类"),
            make_position(2, org_name="发改委", major_req="管理科学与工程类"),
        ]
        results = {r["position_id"]: r for r in match_profile(p, positions, ctx)}
        assert results[1]["status"] == "FAIL"
        assert results[2]["status"] == "PASS"

    def test_unknown_major_is_uncertain_not_fail(self, base_profile, ctx):
        p = dict(base_profile, major_text="临床医学")
        positions = [make_position(1, major_req="计算机类")]
        assert match_profile(p, positions, ctx)[0]["status"] == "UNCERTAIN"

    def test_social_person_fresh_only_fail(self, base_profile, ctx):
        p = dict(base_profile, is_fresh=False)
        positions = [make_position(1, other_req="限应届毕业生")]
        assert match_profile(p, positions, ctx)[0]["status"] == "FAIL"

    def test_results_sorted_pass_first(self, base_profile, ctx):
        positions = [
            make_position(1, major_req="法学类"),
            make_position(2, major_req="计算机类"),
        ]
        results = match_profile(base_profile, positions, ctx)
        assert results[0]["status"] == "PASS"
