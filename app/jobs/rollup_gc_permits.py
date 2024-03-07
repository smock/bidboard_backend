import datetime
import asyncio

from app import db
from app.services.gc_chart_service import GCChartService

async def create_charts():
  async with db.database:
    gccs = GCChartService(db.database)
    await gccs.upsert_charts()

async def rollup_permits():
  async with db.database:
    gccs = GCChartService(db.database)
    i = 0
    for chart in await db.GCChart.objects.order_by('-start_date').all():
      print("Rolling up permits for %s" % chart.slug)
      await gccs.rollup_permits_for_chart(chart)
      i += 1
      print("Rolled up %s/%s" % (i, i))

async def sync_chart_rankings():
  async with db.database:
    gccs = GCChartService(db.database)
    i = 0
    for chart in db.GCChart.objects.order('-start_date').all():
      print("Calculating rankings for %s" % chart.slug)
      await gccs.calculate_chart_rankings_and_deltas(chart)
      i += 1
      print("Rolled up %s/%s" % (i, i))

if __name__ == '__main__':
  import sys

  asyncio.run(rollup_permits())

  sys.exit()
