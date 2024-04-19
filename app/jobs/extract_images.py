import asyncio
import uuid

from app import db
from app.services.bid_file_annotation_service import BidFileAnnotationService

async def extract_bid_images():
  async with db.database:
    bfas = BidFileAnnotationService(db.database)
    i = 0
    for bid_file in await db.BCBidFile.objects.filter(mime_type='application/pdf', images_extracted=False).all():
      if bid_file.id == uuid.UUID('05b90232b228-4b95-97a1-8bc6b12c660e'):
        continue
      await bfas.extract_images(bid_file)
      i += 1
      if i % 10 == 0:
        print("Extracted up to %s" % i)


if __name__ == '__main__':
  import sys

  asyncio.run(extract_bid_images())

  sys.exit()
