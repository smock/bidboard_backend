import asyncio

from app import db
from app.services.pluto_data_service import PlutoDataService

async def sync_pluto():
  async with db.database:
    pds = PlutoDataService(db.database)
    await pds.sync_lots()

if __name__ == '__main__':
  import sys

  asyncio.run(sync_pluto())

  sys.exit()
