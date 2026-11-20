import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

# 开发默认 SQLite；生产设 DATABASE_URL=postgresql+psycopg://... 即切换 PG
DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///./xuangang.db")

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {},
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
Base = declarative_base()


def ensure_schema():
    # 建表 + 轻量迁移：为已有表补齐模型新增列（SQLite/PG 通用）
    from sqlalchemy import inspect, text
    Base.metadata.create_all(engine)
    insp = inspect(engine)
    for table in Base.metadata.sorted_tables:
        if not insp.has_table(table.name):
            continue
        existing = {c["name"] for c in insp.get_columns(table.name)}
        for col in table.columns:
            if col.name not in existing:
                ddl = "ALTER TABLE %s ADD COLUMN %s %s" % (
                    table.name, col.name, col.type.compile(engine.dialect))
                with engine.begin() as conn:
                    conn.execute(text(ddl))


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
