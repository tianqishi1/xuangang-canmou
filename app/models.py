from sqlalchemy import Column, Integer, String, Boolean, Float, Date, JSON, ForeignKey, Text
from app.db import Base


class Exam(Base):
    __tablename__ = "exam"
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    province = Column(String, nullable=False)
    year = Column(Integer, nullable=False)
    type = Column(String, default="省考")  # 国考/省考/事业/选调
    reg_start = Column(Date)
    reg_end = Column(Date)
    exam_at = Column(Date)


class Position(Base):
    __tablename__ = "position"
    id = Column(Integer, primary_key=True)
    exam_id = Column(Integer, ForeignKey("exam.id"), nullable=False)
    org_name = Column(String, nullable=False)
    org_level = Column(String)          # 省级/市级/县级/乡镇
    region = Column(String)             # 地区名
    quota = Column(Integer, default=1)
    service_years = Column(Integer)     # 最低服务期（年），坑位标签来源
    major_req_raw = Column(Text)
    edu_req_raw = Column(String)
    degree_req_raw = Column(String)
    other_req_raw = Column(Text)
    remark_raw = Column(Text)
    cond_json = Column(JSON)            # 结构化条件树（引擎唯一依据）
    risk_flags = Column(JSON, default=list)
    parse_status = Column(String, default="auto")  # auto=待人工审核 / reviewed=已审核
    source_row = Column(Integer)
    parsed_version = Column(String, default="v1")
    # 真实省考职位表字段（2027 起）
    region_code = Column(String)            # 地区代码（6位）
    unit_code = Column(String)              # 单位代码（3位）
    position_code = Column(String)          # 职位代码（2位）
    full_code = Column(String, index=True)  # 地区+单位+职位，跨年度数据关联键
    position_name = Column(String)          # 职位名称
    position_desc = Column(Text)            # 职位简介
    exam_kind = Column(String)              # 考试类别 A/B/C
    open_ratio = Column(Float)              # 开考比例
    source_file = Column(String)            # 来源文件（溯源）


class ScoreLine(Base):
    __tablename__ = "score_line"
    id = Column(Integer, primary_key=True)
    position_id = Column(Integer, ForeignKey("position.id"))
    year = Column(Integer)
    kind = Column(String, default="进面线")
    score = Column(Float)
    ratio = Column(Float)               # 竞争比
    applicants = Column(Integer)
    approved = Column(Integer)
    source_url = Column(String)


class RegStats(Base):
    __tablename__ = "reg_stats"
    id = Column(Integer, primary_key=True)
    position_id = Column(Integer, ForeignKey("position.id"))
    date = Column(Date)
    approved_count = Column(Integer)
    source_url = Column(String)


class MajorCatalog(Base):
    __tablename__ = "major_catalog"
    id = Column(Integer, primary_key=True)
    province = Column(String, nullable=False)
    year = Column(Integer, nullable=False)
    code = Column(String, nullable=False)   # 教育部专业目录代码，如 080901
    name = Column(String, nullable=False)
    level = Column(String)                  # 门类/专业类/专业
    parent_code = Column(String)


class AuditCase(Base):
    __tablename__ = "audit_case"
    id = Column(Integer, primary_key=True)
    province = Column(String)
    major_text = Column(String)             # 毕业证专业原文
    req_text = Column(String)               # 岗位要求原文
    verdict = Column(String)                # PASS / FAIL
    evidence = Column(Text)                 # 口径依据（审核案例/官方答复）
    year = Column(Integer)


class UserProfile(Base):
    __tablename__ = "user_profile"
    id = Column(Integer, primary_key=True)
    name = Column(String)
    edu = Column(String)
    degree = Column(String)
    major_text = Column(String)
    grad_year = Column(Integer)
    is_fresh = Column(Boolean)              # None=未知 → UNCERTAIN
    hukou = Column(String)
    gender = Column(String)                 # 男/女（人民警察等职位硬性要求）
    political = Column(String)              # 中共党员/中共预备党员/共青团员/群众
    grassroots_years = Column(Float)
    certs = Column(JSON, default=list)
    est_score = Column(Float)
    region_pref = Column(JSON, default=list)
