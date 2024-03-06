import asyncio

from app import db
from app.services.dob_now_data_service import DobNowDataService

async def sync_dob():
  async with db.database:
    dobds = DobNowDataService(db.database)
    await dobds.parse_approved_permits()

if __name__ == '__main__':
  import sys

  asyncio.run(sync_dob())

  sys.exit()
