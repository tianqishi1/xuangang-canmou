# -*- coding: utf-8 -*-
"""M0 最小闭环演示：建库 → 种子 → 生成仿真职位表 → 导入 → 三个画像匹配。"""
import os
import sys
import random

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)

from app.db import SessionLocal
from app.models import Position, ScoreLine, MajorCatalog, AuditCase
from app.engine.matcher import match_profile
from scripts.seed import seed
from scripts.make_sample_excel import make
from app.pipeline.importer import import_excel


def attach_score_lines(db):
    """给前6个岗位挂仿真历史进面线（真实项目来自官方公示名单）。"""
    if db.query(ScoreLine).count() > 0:
        return
    random.seed(42)
    for p in db.query(Position).limit(6).all():
        base = random.uniform(122, 140)
        for y in (2023, 2024, 2025):
            db.add(ScoreLine(position_id=p.id, year=y, kind="进面线",
                             score=round(base + random.uniform(-3, 3), 1),
                             ratio=round(random.uniform(20, 300), 1),
                             approved=int(random.uniform(30, 900)),
                             source_url="https://example.gov.cn/公示（仿真）"))
    db.commit()


PROFILES = {
    "A 应届计算机本科生（南京）": {
        "edu": "本科", "degree": "学士", "major_text": "计算机科学与技术",
        "is_fresh": True, "political": "共青团员", "hukou": "南京",
        "grassroots_years": 0, "certs": [], "est_score": 132},
    "B 往届信管专业（常州户籍，基层3年）": {
        "edu": "本科", "degree": "学士", "major_text": "信息管理与信息系统",
        "is_fresh": False, "political": "群众", "hukou": "常州",
        "grassroots_years": 3, "certs": [], "est_score": 128},
    "C 财政学硕士党员（无锡）": {
        "edu": "硕士研究生", "degree": "硕士", "major_text": "财政学",
        "is_fresh": False, "political": "中共党员", "hukou": "无锡",
        "grassroots_years": 0, "certs": [], "est_score": 138},
}


def main():
    exam_id = seed()
    db = SessionLocal()
    try:
        if db.query(Position).count() == 0:
            xlsx = make(os.path.join(HERE, "data", "sample_positions.xlsx"))
            tpl = os.path.join(HERE, "config", "provinces", "jiangsu_2026.yaml")
            summary = import_excel(db, xlsx, tpl, exam_id)
            print("导入结果:", summary)
        attach_score_lines(db)
        ctx = {"province": "jiangsu",
               "catalog": db.query(MajorCatalog).filter_by(province="jiangsu", year=2026).all(),
               "audit_cases": db.query(AuditCase).filter_by(province="jiangsu").all()}
        positions = db.query(Position).filter_by(exam_id=exam_id).all()
        for label, profile in PROFILES.items():
            print("\n" + "=" * 70)
            print("画像:", label)
            results = match_profile(profile, positions, ctx)
            for r in results:
                mark = {"PASS": "[可报]", "UNCERTAIN": "[存疑]", "FAIL": "[不可]"}[r["status"]]
                risks = ("  风险:" + "/".join(r["risk_flags"])) if r["risk_flags"] else ""
                print(f"  {mark} {r['org_name']} ({r['region']}) — {r['reason']}{risks}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
