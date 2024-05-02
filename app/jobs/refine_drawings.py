import asyncio

from app import db
from app.services.bid_file_annotation_service import BidFileAnnotationService

async def refine_drawings():
  async with db.database:
    bfas = BidFileAnnotationService(db.database)
    i = 0
    for annotation in await db.UniqueImageAnnotation.objects.filter(valid_roi=None, refined=None).all():
      i += 1
      annos = await db.UniqueImageAnnotation.objects.filter(unique_image_id=annotation.unique_image_id, valid_roi=True).all()
      if len(annos) > 0:
        continue
      await bfas.refine_annotation(annotation, force=True)
    print(i)


if __name__ == '__main__':
  import sys

  asyncio.run(refine_drawings())

  sys.exit()
