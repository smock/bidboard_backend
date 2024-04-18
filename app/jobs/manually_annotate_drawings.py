import asyncio

from app import db
from app.services.bid_file_annotation_service import BidFileAnnotationService

async def manually_annotate_drawings():
  async with db.database:
    bfas = BidFileAnnotationService(db.database)
    for unique_image in await db.UniqueImage.objects.select_related('unique_image_annotations').filter(has_architectural_page_number=True).all():
      await bfas.manually_annotate_page_number(unique_image)

if __name__ == '__main__':
  import sys

  drawings = asyncio.run(manually_annotate_drawings())

  sys.exit()
