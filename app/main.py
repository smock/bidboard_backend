# app/main.py
from typing import Dict, List

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware


from app import db
from app.services.gc_chart_service import GCChartService
from app import schemas

app = FastAPI(title="BidBoard")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
async def startup():
  if not db.database.is_connected:
    await db.database.connect()

@app.on_event("shutdown")
async def shutdown():
  if db.database.is_connected:
    await db.database.disconnect()

@app.get('/api/v1/gc_charts', response_model=schemas.GCChart)
async def get_gc_charts(slug: str):
  gc_chart_service = GCChartService(db.database)
  gc_chart = await gc_chart_service.get_chart_by_slug(slug, format_for_frontend=True)
  return gc_chart

@app.get('/api/v1/gc_chart_children', response_model=List[schemas.GCChart])
async def get_gc_chart_children(path: str):
  gc_chart_service = GCChartService(db.database)
  gc_charts = await gc_chart_service.get_chart_children(path)
  return gc_charts
