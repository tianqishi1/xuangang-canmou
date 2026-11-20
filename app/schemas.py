# -*- coding: utf-8 -*-
from typing import Optional, List
from pydantic import BaseModel


class ProfileIn(BaseModel):
    name: Optional[str] = None
    edu: Optional[str] = None
    degree: Optional[str] = None
    major_text: Optional[str] = None
    grad_year: Optional[int] = None
    is_fresh: Optional[bool] = None
    hukou: Optional[str] = None
    gender: Optional[str] = None
    political: Optional[str] = None
    grassroots_years: Optional[float] = None
    certs: List[str] = []
    est_score: Optional[float] = None
    region_pref: List[str] = []


class MatchIn(BaseModel):
    exam_id: int
    profile: ProfileIn


class ProfileOut(ProfileIn):
    id: int

    class Config:
        from_attributes = True
