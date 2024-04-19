import asyncio

from app import db
from app.services.bid_file_annotation_service import BidFileAnnotationService

async def validate_annotated_drawings():
  async with db.database:
    bfas = BidFileAnnotationService(db.database)
    for unique_image in await db.UniqueImage.objects.filter(has_architectural_page_number=True).all():
      await bfas.review_annotation(annotation, force=True)

if __name__ == '__main__':
  import sys

  drawings = asyncio.run(validate_architectural_drawings())

  sys.exit()
