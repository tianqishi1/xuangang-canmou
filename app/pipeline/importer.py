# -*- coding: utf-8 -*-
"""导入编排：Excel → 规范化 → 条件结构化 → 入库（parse_status=auto，待人工审核）。"""
import os
from app.models import Position, MajorCatalog
from app.pipeline.excel_parser import load_template, parse_excel
from app.pipeline.cond_extract import extract_conditions


def _to_int(v, default=1):
    try:
        return int(float(str(v).strip()))
    except (TypeError, ValueError):
        return default


def _to_float(v):
    try:
        return float(str(v).strip())
    except (TypeError, ValueError):
        return None


def import_excel(db, excel_path, template_path, exam_id, source_file=None):
    tpl = load_template(template_path)
    catalog = db.query(MajorCatalog).filter_by(
        province=tpl["province"], year=tpl["year"]).all()
    rows = parse_excel(excel_path, tpl)
    created, need_review = 0, 0
    for row in rows:
        tree, risks, service = extract_conditions(row, catalog)
        has_review = _has_manual_review(tree)
        p = Position(
            exam_id=exam_id,
            org_name=row.get("org_name", ""),
            org_level=row.get("org_level") or None,
            region=row.get("region") or None,
            quota=_to_int(row.get("quota"), 1),
            service_years=service,
            major_req_raw=row.get("major_req"),
            edu_req_raw=row.get("edu_req"),
            degree_req_raw=row.get("degree_req"),
            other_req_raw=row.get("other_req"),
            remark_raw=row.get("remark"),
            cond_json=tree,
            risk_flags=risks,
            parse_status="auto",
            source_row=row.get("_source_row"),
            region_code=row.get("region_code") or None,
            unit_code=row.get("unit_code") or None,
            position_code=row.get("position_code") or None,
            full_code="".join(row.get(k, "") for k in ("region_code", "unit_code", "position_code")) or None,
            position_name=row.get("position_name") or None,
            position_desc=row.get("position_desc") or None,
            exam_kind=row.get("exam_kind") or None,
            open_ratio=_to_float(row.get("open_ratio")),
            source_file=source_file or os.path.basename(str(excel_path)),
        )
        db.add(p)
        created += 1
        need_review += int(has_review)
    db.commit()
    return {"rows": len(rows), "created": created, "need_manual_review": need_review}


def _has_manual_review(node):
    if not node:
        return False
    if node.get("op") == "manual_review":
        return True
    return any(_has_manual_review(c) for c in node.get("children", []))
