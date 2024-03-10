import asyncio

from app import db
from app.services.gc_chart_service import GCChartService

async def sync_chart_rankings():
  async with db.database:
    gccs = GCChartService(db.database)
    i = 0
    for chart in await db.GCChart.objects.order_by('start_date').all():
      print("Calculating rankings for %s" % chart.slug)
      await gccs.calculate_chart_rankings(chart)
      await gccs.calculate_chart_deltas(chart)
      i += 1
      print("Calculated %s/%s" % (i, i))

if __name__ == '__main__':
  import sys

  asyncio.run(sync_chart_rankings())

  sys.exit()
