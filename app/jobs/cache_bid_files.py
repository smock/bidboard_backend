import asyncio

from app import db
from app.services.building_connected_data_service import BuildingConnectedDataService

async def cache_bids():
  async with db.database:
    # right now its only tristate
    company = await db.Company.objects.get(name='Tristate Plumbing')
    bcds = BuildingConnectedDataService(db.database, company)
    bcds.init_session()
    i = 0
    for bid_file in await db.BCBidFile.objects.all():
      await bcds.cache_bid_file(bid_file)
      i += 1
      if i % 10 == 0:
        print("Cached up to %s" % i)


if __name__ == '__main__':
  import sys

  asyncio.run(cache_bids())

  sys.exit()
