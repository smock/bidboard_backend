import asyncio

from app import db
from app.services.bid_file_annotation_service import BidFileAnnotationService

async def manually_annotate_drawings():
  async with db.database:
    bfas = BidFileAnnotationService(db.database)
    for unique_image in await db.UniqueImage.objects.select_related('unique_image_annotations').filter(
      has_architectural_page_number=True
    ).all():
      valid_annotations = [a for a in unique_image.unique_image_annotations if a.valid_roi]
      if len(valid_annotations) > 0:
        continue
      ret = await bfas.manually_annotate_page_number(unique_image)
      while True:
        if ret == -1:
          ret = await bfas.manually_annotate_page_number(unique_image, use_panels=False)
        elif ret == None or ret.valid_roi != None:
          break
        else:
          ret = await bfas.manually_annotate_page_number(unique_image, panel_coords={
            'x1': ret.page_number_x1,
            'x2': ret.page_number_x2,
            'y1': ret.page_number_y1,
            'y2': ret.page_number_y2
          })


if __name__ == '__main__':
  import sys

  drawings = asyncio.run(manually_annotate_drawings())

  sys.exit()
