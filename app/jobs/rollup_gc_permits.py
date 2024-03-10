import asyncio

from app import db
from app.services.gc_chart_service import GCChartService

async def rollup_permits():
  async with db.database:
    gccs = GCChartService(db.database)
    i = 0
    for chart in await db.GCChart.objects.order_by('-start_date').all():
      if chart.start_date.year == 2023:
        continue
      print("Rolling up permits for %s" % chart.slug)
      await gccs.rollup_permits_for_chart(chart)
      i += 1
      print("Rolled up %s/%s" % (i, i))

if __name__ == '__main__':
  import sys

  asyncio.run(rollup_permits())

  sys.exit()
