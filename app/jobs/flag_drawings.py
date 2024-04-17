import asyncio

from app import db
from app.services.bid_file_annotation_service import BidFileAnnotationService

async def flag_drawings():
  async with db.database:
    bfas = BidFileAnnotationService(db.database)
    for bid_file_image in await db.UniqueImage.objects.filter(has_architectural_page_number=None).all():
      await bfas.flag_architectural_page_number(bid_file_image)


if __name__ == '__main__':
  import sys

  asyncio.run(flag_drawings())

  sys.exit()
