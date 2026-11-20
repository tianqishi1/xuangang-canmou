# -*- coding: utf-8 -*-
import os
import tempfile
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.orm import Session
from app.db import get_db
from app import models
from app.schemas import ProfileIn, ProfileOut, MatchIn
from app.engine.matcher import match_profile
from app.pipeline.importer import import_excel

router = APIRouter(prefix="/api")
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _ctx(db, province="jiangsu", year=2026):
    return {"province": province,
            "catalog": db.query(models.MajorCatalog).filter_by(province=province, year=year).all(),
            "audit_cases": db.query(models.AuditCase).filter_by(province=province).all()}


@router.get("/health")
def health():
    return {"ok": True}


@router.get("/exams")
def list_exams(db: Session = Depends(get_db)):
    return [{"id": e.id, "name": e.name, "province": e.province, "year": e.year,
             "type": e.type, "reg_start": e.reg_start, "reg_end": e.reg_end}
            for e in db.query(models.Exam).all()]


@router.get("/positions")
def list_positions(exam_id: int, db: Session = Depends(get_db)):
    ps = db.query(models.Position).filter_by(exam_id=exam_id).all()
    return [_pos_brief(p) for p in ps]


def _pos_brief(p):
    return {"id": p.id, "org_name": p.org_name, "region": p.region,
            "org_level": p.org_level, "quota": p.quota,
            "position_name": p.position_name, "full_code": p.full_code,
            "exam_kind": p.exam_kind,
            "service_years": p.service_years, "risk_flags": p.risk_flags or [],
            "major_req_raw": p.major_req_raw, "edu_req_raw": p.edu_req_raw,
            "other_req_raw": p.other_req_raw, "remark_raw": p.remark_raw,
            "parse_status": p.parse_status}


@router.get("/positions/{pid}/card")
def position_card(pid: int, db: Session = Depends(get_db)):
    p = db.get(models.Position, pid)
    if not p:
        raise HTTPException(404, "岗位不存在")
    lines = db.query(models.ScoreLine).filter_by(position_id=pid).order_by(models.ScoreLine.year).all()
    card = _pos_brief(p)
    card["degree_req_raw"] = p.degree_req_raw
    card["score_lines"] = [{"year": l.year, "kind": l.kind, "score": l.score,
                            "ratio": l.ratio, "approved": l.approved,
                            "applicants": l.applicants,
                            "source_url": l.source_url} for l in lines]
    card["disclaimer"] = "历史数据仅供参考，不构成进面保证；资格条件以招录单位审核为准。"
    return card


@router.post("/match")
def match(body: MatchIn, db: Session = Depends(get_db)):
    exam = db.get(models.Exam, body.exam_id)
    if not exam:
        raise HTTPException(404, "考试不存在")
    positions = db.query(models.Position).filter_by(exam_id=body.exam_id).all()
    profile = body.profile.model_dump()
    results = match_profile(profile, positions, _ctx(db, exam.province, exam.year))
    summary = {s: sum(1 for r in results if r["status"] == s) for s in ("PASS", "UNCERTAIN", "FAIL")}
    return {"summary": summary, "results": results,
            "disclaimer": "存疑项请务必致电招录单位确认；本结果不构成报考资格保证。"}


@router.post("/profiles", response_model=ProfileOut)
def create_profile(body: ProfileIn, db: Session = Depends(get_db)):
    p = models.UserProfile(**body.model_dump())
    db.add(p)
    db.commit()
    db.refresh(p)
    return p


@router.get("/profiles/{pid}", response_model=ProfileOut)
def get_profile(pid: int, db: Session = Depends(get_db)):
    p = db.get(models.UserProfile, pid)
    if not p:
        raise HTTPException(404, "画像不存在")
    return p


@router.post("/import")
def import_positions(exam_id: int = Form(...), template: str = Form("jiangsu_2026"),
                     file: UploadFile = File(...), db: Session = Depends(get_db)):
    tpl_path = os.path.join(HERE, "config", "provinces", f"{template}.yaml")
    if not os.path.exists(tpl_path):
        raise HTTPException(400, f"省份模板不存在: {template}")
    suffix = os.path.splitext(file.filename or "upload.xlsx")[1] or ".xlsx"
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(file.file.read())
        tmp_path = tmp.name
    try:
        return import_excel(db, tmp_path, tpl_path, exam_id)
    finally:
        os.unlink(tmp_path)
