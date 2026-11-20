# -*- coding: utf-8 -*-
"""真实数据端到端演示：江苏省2027年度省考 × 三个画像。先运行 scripts/import_real.py。"""
import os
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)

from app.db import SessionLocal
from app.models import Exam, Position, MajorCatalog, AuditCase, ScoreLine
from app.engine.matcher import match_profile

PROFILES = {
    "A 法学本科应届（南京户籍，群众）": {
        "edu": "本科", "degree": "学士", "major_text": "法学",
        "is_fresh": True, "political": "群众", "hukou": "南京", "gender": "女",
        "grassroots_years": 0, "certs": [], "est_score": 135},
    "B 计算机本科往届（常州户籍）": {
        "edu": "本科", "degree": "学士", "major_text": "计算机科学与技术",
        "is_fresh": False, "political": "群众", "hukou": "常州", "gender": "男",
        "grassroots_years": 3, "certs": [], "est_score": 130},
    "C 会计学硕士党员（无锡户籍）": {
        "edu": "硕士研究生", "degree": "硕士", "major_text": "会计学",
        "is_fresh": False, "political": "中共党员", "hukou": "无锡", "gender": "男",
        "grassroots_years": 0, "certs": [], "est_score": 138},
}


def main():
    db = SessionLocal()
    try:
        exam = db.query(Exam).filter_by(name="江苏省2027年度考试录用公务员").first()
        if not exam:
            print("请先运行 python scripts/import_real.py")
            return
        ctx = {"province": "jiangsu",
               "catalog": db.query(MajorCatalog).filter_by(province="jiangsu", year=2027).all(),
               "audit_cases": db.query(AuditCase).filter_by(province="jiangsu").all()}
        positions = db.query(Position).filter_by(exam_id=exam.id).all()
        print(f"场次: {exam.name} | 岗位 {len(positions)} 个 | 目录 {len(ctx['catalog'])} 条")
        for label, profile in PROFILES.items():
            results = match_profile(profile, positions, ctx)
            n = {s: sum(1 for r in results if r["status"] == s) for s in ("PASS", "UNCERTAIN", "FAIL")}
            print("\n" + "=" * 70)
            print(f"画像: {label}  →  可报{n['PASS']} / 存疑{n['UNCERTAIN']} / 不可{n['FAIL']}")
            shown = 0
            for r in results:
                if r["status"] != "PASS" or shown >= 8:
                    continue
                p = db.get(Position, r["position_id"])
                lines = db.query(ScoreLine).filter_by(position_id=p.id, kind="进面线").all()
                hist = " ".join(f"{l.year}年{l.score}" for l in sorted(lines, key=lambda x: x.year))
                risks = ("  风险:" + "/".join(r["risk_flags"])) if r["risk_flags"] else ""
                print(f"  [可报] {p.org_name} · {p.position_name or ''} ({p.region}) "
                      f"招{p.quota}人 代码{p.full_code}{risks}")
                if hist:
                    print(f"         历史进面线: {hist}")
                shown += 1
    finally:
        db.close()


if __name__ == "__main__":
    main()
