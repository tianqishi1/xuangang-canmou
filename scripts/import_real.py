# -*- coding: utf-8 -*-
"""真实数据导入：江苏省2027年度考试录用公务员。

数据源（data/real/）：
- 省级机关/13设区市/监狱戒毒系统职位简介表（官方原件，南京为市委组织部xlsx，其余为官方xls镜像）
- 江苏省2027年度考试录用公务员专业参考目录（省委组织部官方doc，已转docx）
- 2024-2026历史进面分/报名人数（华图汇总，原始数据为官方公示）

用法：python scripts/import_real.py
幂等：已导入的场次/目录/分数线自动跳过。
"""
import datetime as dt
import difflib
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)

from app.db import SessionLocal, ensure_schema
from app.models import Exam, Position, MajorCatalog, AuditCase, ScoreLine
from app.pipeline.cond_extract import split_items
from app.pipeline.importer import import_excel

REAL = os.path.join(HERE, "data", "real")
TPL = os.path.join(HERE, "config", "provinces", "jiangsu_2027.yaml")
EXAM_NAME = "江苏省2027年度考试录用公务员"
HISTORY_URL = "https://ah.huatu.com/zt/jsgwyzwb/（华图汇总2024-2026官方公示数据，仅供参考）"

POSITION_FILES = [
    "shengji_2027.xls", "nanjing_2027.xlsx", "suzhou_2027.xls", "wuxi_2027.xls",
    "xuzhou_2027.xls", "changzhou_2027.xls", "zhenjiang_2027.xls", "nantong_2027.xls",
    "lianyungang_2027.xls", "huaian_2027.xls", "yancheng_2027.xls", "yangzhou_2027.xls",
    "taizhou_2027.xls", "suqian_2027.xls", "sifaxingzheng_2027.xls",
]


def _clean(s):
    return re.sub(r"\s+", "", str(s or ""))


def _code(v, width):
    t = _clean(v)
    if t.endswith(".0"):
        t = t[:-2]
    return t.zfill(width) if t else ""


def parse_catalog_docx(path):
    """官方专业参考目录 → [(序号, 大类名, {层次: [(规范名, 原文名)]})]"""
    import docx
    doc = docx.Document(path)
    table = next(t for t in doc.tables if len(t.columns) == 5)
    entries = []
    for row in table.rows[1:]:
        cells = [c.text.strip() for c in row.cells]
        if not cells[0].strip().isdigit():
            continue
        idx = int(cells[0])
        cat = _clean(cells[1])
        stages = {}
        for stage, ci in ((1, 2), (2, 3), (3, 4)):
            names = []
            for n in split_items(cells[ci]):
                n = _clean(n)
                if not n:
                    continue
                base = re.sub(r"（[^）]*）|\([^)]*\)", "", n)
                names.append((base, n))
            stages[stage] = names
        entries.append((idx, cat, stages))
    return entries


def seed_catalog(db, entries):
    n_cls = n_major = 0
    for idx, cat, stages in entries:
        for stage, names in stages.items():
            if not names:
                continue
            cls_code = f"{stage}{idx:03d}"
            db.add(MajorCatalog(province="jiangsu", year=2027, code=cls_code,
                                name=cat, level="专业类", parent_code=None))
            n_cls += 1
            for j, (base, raw) in enumerate(names, start=1):
                code = f"{cls_code}{j:02d}"
                db.add(MajorCatalog(province="jiangsu", year=2027, code=code,
                                    name=base, level="专业", parent_code=cls_code))
                n_major += 1
                if raw != base:
                    db.add(MajorCatalog(province="jiangsu", year=2027, code=code,
                                        name=raw, level="专业", parent_code=cls_code))
                    n_major += 1
    db.commit()
    return n_cls, n_major


def _num(v):
    try:
        return float(str(v).strip())
    except (TypeError, ValueError):
        return None


def _dept_match(hist_dept, org_name, region):
    a, b = _clean(hist_dept), _clean(org_name)
    if not a or not b:
        return False
    for prefix in (_clean(region), _clean(region).rstrip("市")):
        if prefix and a.startswith(prefix):
            a = a[len(prefix):]
            break
    if a == b or a.endswith(b) or b.endswith(a):
        return True
    return difflib.SequenceMatcher(None, a, b).ratio() >= 0.8


def attach_history(db, exam_id):
    import openpyxl
    path = os.path.join(REAL, "huatu_history_2024_2026.xlsx")
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    positions = db.query(Position).filter_by(exam_id=exam_id).all()
    by_code = {}
    for p in positions:
        if p.full_code:
            by_code.setdefault(p.full_code, []).append(p)
    attached = skipped_dept = skipped_name = 0
    for sheet in ("2026", "2025", "2024"):
        ws = wb[sheet]
        rows = list(ws.iter_rows(values_only=True))
        year = int(sheet)
        for r in rows[1:]:
            if not r or not r[0]:
                continue
            code = _clean(r[0])
            cands = by_code.get(code)
            if not cands:
                continue
            dept, hist_name = str(r[3] or ""), str(r[4] or "")
            p = next((x for x in cands if _dept_match(dept, x.org_name, str(r[2] or ""))), None)
            if p is None:
                skipped_dept += 1
                continue
            if difflib.SequenceMatcher(None, _clean(hist_name), _clean(p.position_name)).ratio() < 0.4:
                skipped_name += 1
                continue
            quota = _num(r[9]) or 1
            applicants = _num(r[10])
            lo, hi = _num(r[12]), _num(r[13])
            ratio = round(applicants / quota, 1) if applicants else None
            for kind, score in (("进面线", lo), ("进面最高分", hi)):
                if score is None:
                    continue
                db.add(ScoreLine(position_id=p.id, year=year, kind=kind, score=score,
                                 ratio=ratio, applicants=int(applicants) if applicants else None,
                                 source_url=HISTORY_URL))
                attached += 1
    db.commit()
    return {"lines": attached, "skipped_dept": skipped_dept, "skipped_name": skipped_name}


def main():
    ensure_schema()
    db = SessionLocal()
    report = {}
    try:
        exam = db.query(Exam).filter_by(name=EXAM_NAME).first()
        if not exam:
            exam = Exam(name=EXAM_NAME, province="jiangsu", year=2027, type="省考",
                        reg_start=dt.date(2026, 11, 3), reg_end=dt.date(2026, 11, 9),
                        exam_at=dt.date(2026, 12, 6))
            db.add(exam)
            db.commit()
        report["exam_id"] = exam.id

        # 专业目录（官方2027版）
        if db.query(MajorCatalog).filter_by(province="jiangsu", year=2027).count() == 0:
            entries = parse_catalog_docx(os.path.join(REAL, "catalog_2027.docx"))
            n_cls, n_major = seed_catalog(db, entries)
            report["catalog"] = {"categories": len(entries), "class_rows": n_cls, "major_rows": n_major}
            # 移除仿真演示口径案例，真实判定以官方目录为准
            removed = db.query(AuditCase).filter(
                AuditCase.major_text.in_(["计算机及应用", "信息管理与信息系统"])).delete()
            db.commit()
            report["demo_audit_cases_removed"] = removed
        else:
            report["catalog"] = "already imported"

        # 职位表
        if db.query(Position).filter_by(exam_id=exam.id).count() == 0:
            per_file = {}
            for fn in POSITION_FILES:
                summary = import_excel(db, os.path.join(REAL, fn), TPL, exam.id, source_file=fn)
                per_file[fn] = summary
            report["positions"] = per_file
        else:
            report["positions"] = "already imported"

        # 历史进面线
        has_lines = db.query(ScoreLine).join(Position, ScoreLine.position_id == Position.id)\
            .filter(Position.exam_id == exam.id).count()
        if has_lines == 0:
            report["history"] = attach_history(db, exam.id)
        else:
            report["history"] = "already attached"

        total = db.query(Position).filter_by(exam_id=exam.id).count()
        review = db.query(Position).filter_by(exam_id=exam.id, parse_status="auto").count()
        report["total_positions"] = total
        report["parse_status_auto"] = review
        out = os.path.join(REAL, "import_report.json")
        with open(out, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        print("report saved:", out)
    finally:
        db.close()


if __name__ == "__main__":
    main()
