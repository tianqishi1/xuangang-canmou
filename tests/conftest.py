# -*- coding: utf-8 -*-
import os, sys
from types import SimpleNamespace
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

CATALOG = [
    ("08", "工学", "门类"), ("12", "管理学", "门类"), ("03", "法学", "门类"),
    ("0809", "计算机类", "专业类"), ("1201", "管理科学与工程类", "专业类"),
    ("1202", "工商管理类", "专业类"), ("0301", "法学类", "专业类"),
    ("080901", "计算机科学与技术", "专业"), ("080902", "软件工程", "专业"),
    ("120102", "信息管理与信息系统", "专业"), ("120203K", "会计学", "专业"),
    ("030101K", "法学", "专业"),
]


@pytest.fixture
def ctx():
    return {
        "province": "jiangsu",
        "catalog": [SimpleNamespace(code=c, name=n, level=l) for c, n, l in CATALOG],
        "audit_cases": [
            SimpleNamespace(major_text="计算机及应用", req_text="计算机类",
                            verdict="PASS", evidence="旧专业名对照口径"),
            SimpleNamespace(major_text="信息管理与信息系统", req_text="计算机类",
                            verdict="FAIL", evidence="属管理科学与工程类"),
        ],
    }


@pytest.fixture
def base_profile():
    return {"edu": "本科", "degree": "学士", "major_text": "计算机科学与技术",
            "is_fresh": True, "political": "共青团员", "hukou": "南京",
            "grassroots_years": 0, "certs": [], "est_score": 130}
