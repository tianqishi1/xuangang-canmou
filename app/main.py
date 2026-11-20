# -*- coding: utf-8 -*-
import os
from fastapi import FastAPI
from fastapi.responses import FileResponse
from app.db import engine, Base, ensure_schema
from app import models  # noqa: F401
from app.api.routes import router

app = FastAPI(title="选岗参谋 M0", version="0.1.0")
app.include_router(router)
HERE = os.path.dirname(os.path.abspath(__file__))


@app.on_event("startup")
def startup():
    ensure_schema()


@app.get("/")
def index():
    return FileResponse(os.path.join(HERE, "static", "demo.html"))
