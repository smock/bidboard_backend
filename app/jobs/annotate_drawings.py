import asyncio

from app import db
from app.services.bid_file_annotation_service import BidFileAnnotationService

async def annotate_drawings():
  async with db.database:
    bfas = BidFileAnnotationService(db.database)
    for bid_file_image in await db.BCBidFileImage.objects.filter(has_architectural_page_number=True).all():
      await bfas.annotate_page_number(bid_file_image)

if __name__ == '__main__':
  import sys

  asyncio.run(annotate_drawings())

  sys.exit()
