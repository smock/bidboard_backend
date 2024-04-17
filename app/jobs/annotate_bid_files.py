import asyncio

from app import db
from app.services.building_connected_data_service import BuildingConnectedDataService
from app.services.bid_file_annotation_service import BidFileAnnotationService


async def annotate_bids():
  async with db.database:
    company = await db.Company.objects.get(name='Tristate Plumbing')
    bcds = BuildingConnectedDataService(db.database, company)
    bcds.init_session()
    bfas = BidFileAnnotationService(db.database)
    company = await db.Company.objects.get(name='Tristate Plumbing')
    # just one bid for now
    bid = await db.BCBid.objects.get(company_id=company.id, bc_id='661e92762ef084005cb33d03')
    for bid_file in await db.BCBidFile.objects.filter(bc_bid_id=bid.id, file_system_type=db.BCBidFileSystemType.FILE.value).all():
      await bcds.cache_bid_file(bid_file)
      await bfas.annotate_bid_file(bid_file)


if __name__ == '__main__':
  import sys

  asyncio.run(annotate_bids())

  sys.exit()
