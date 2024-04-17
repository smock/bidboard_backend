import asyncio

from app import db
from app.services.bid_file_annotation_service import BidFileAnnotationService

async def review_annotation_candidates():
  async with db.database:
    bfas = BidFileAnnotationService(db.database)
    for annotation in await db.UniqueImageAnnotation.objects.filter(valid=None).all():
      await bfas.review_annotation(annotation)

if __name__ == '__main__':
  import sys

  asyncio.run(review_annotation_candidates())

  sys.exit()
