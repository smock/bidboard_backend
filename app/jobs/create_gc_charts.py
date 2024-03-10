import asyncio

from app import db
from app.services.gc_chart_service import GCChartService

async def create_charts():
  async with db.database:
    gccs = GCChartService(db.database)
    await gccs.upsert_charts()

if __name__ == '__main__':
  import sys

  asyncio.run(create_charts())

  sys.exit()
