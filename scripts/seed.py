# -*- coding: utf-8 -*-
"""种子数据：专业目录（教育部本科目录真实代码）+ 审核口径案例 + 考试场次。"""
import datetime as dt
from app.db import engine, SessionLocal, Base
from app import models  # noqa: F401 确保建表
from app.models import MajorCatalog, AuditCase, Exam

CATALOG = [
    # (code, name, level, parent)
    ("02", "经济学", "门类", None),
    ("03", "法学", "门类", None),
    ("05", "文学", "门类", None),
    ("07", "理学", "门类", None),
    ("08", "工学", "门类", None),
    ("12", "管理学", "门类", None),
    ("0201", "经济学类", "专业类", "02"),
    ("0202", "财政学类", "专业类", "02"),
    ("0301", "法学类", "专业类", "03"),
    ("0501", "中国语言文学类", "专业类", "05"),
    ("0502", "外国语言文学类", "专业类", "05"),
    ("0712", "统计学类", "专业类", "07"),
    ("0809", "计算机类", "专业类", "08"),
    ("0829", "安全科学与工程类", "专业类", "08"),
    ("1201", "管理科学与工程类", "专业类", "12"),
    ("1202", "工商管理类", "专业类", "12"),
    ("1204", "公共管理类", "专业类", "12"),
    ("020101", "经济学", "专业", "0201"),
    ("020201K", "财政学", "专业", "0202"),
    ("030101K", "法学", "专业", "0301"),
    ("050101", "汉语言文学", "专业", "0501"),
    ("050201", "英语", "专业", "0502"),
    ("071201", "统计学", "专业", "0712"),
    ("080901", "计算机科学与技术", "专业", "0809"),
    ("080902", "软件工程", "专业", "0809"),
    ("082901", "安全工程", "专业", "0829"),
    ("120102", "信息管理与信息系统", "专业", "1201"),
    ("120203K", "会计学", "专业", "1202"),
    ("120402", "行政管理", "专业", "1204"),
]

CASES = [
    ("计算机及应用", "计算机类", "PASS",
     "旧专业名，对应现行目录0809计算机类（省报考指南专业对照表口径）"),
    ("信息管理与信息系统", "计算机类", "FAIL",
     "属1201管理科学与工程类，不属计算机类（2025年省考招录单位审核答复口径）"),
]


def seed():
    Base.metadata.create_all(engine)
    db = SessionLocal()
    try:
        if db.query(MajorCatalog).count() == 0:
            for code, name, level, parent in CATALOG:
                db.add(MajorCatalog(province="jiangsu", year=2026, code=code,
                                    name=name, level=level, parent_code=parent))
        if db.query(AuditCase).count() == 0:
            for mt, rt, v, ev in CASES:
                db.add(AuditCase(province="jiangsu", major_text=mt, req_text=rt,
                                 verdict=v, evidence=ev, year=2025))
        exam = db.query(Exam).filter_by(name="江苏省2026年度考试录用公务员（仿真）").first()
        if not exam:
            exam = Exam(name="江苏省2026年度考试录用公务员（仿真）", province="jiangsu",
                        year=2026, type="省考",
                        reg_start=dt.date(2025, 11, 4), reg_end=dt.date(2025, 11, 10),
                        exam_at=dt.date(2025, 12, 7))
            db.add(exam)
        db.commit()
        return exam.id
    finally:
        db.close()


if __name__ == "__main__":
    print("exam_id =", seed())
