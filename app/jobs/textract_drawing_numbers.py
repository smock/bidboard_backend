import asyncio
import json
import re

from app import db
from app.services.textract_service import TextractService
from app.services.bid_file_annotation_service import BidFileAnnotationService

async def validate_textract_results():
  pattern = r'^[A-Z]-?\d([\d .]*)?$'

  async with db.database:
    bfas = BidFileAnnotationService(db.database)
    for unique_image in await db.UniqueImage.objects.select_related('unique_image_annotations').filter(textract_filename__isnull=False).all():
      annos = [anno for anno in unique_image.unique_image_annotations if anno.valid==True]
      if len(annos) > 0:
        print(annos[0].page_number)
      print(unique_image.textract_filename)
      with open(unique_image.textract_filename, 'r') as file:
        textract_data = json.load(file)
      block_types = set()
      for block in textract_data['Blocks']:
        if block['BlockType'] == 'WORD':
          matches = re.findall(pattern, block['Text'].strip())
          if len(matches) > 0:
            print(block)
        #return
        block_types.add(block['BlockType'])
      print(block_types)

async def textract_drawing_number_on_unique_image(textract_service, unique_image):
  await textract_service.upload_pdf_to_s3_from_unique_image(unique_image)
  await textract_service.analyze_pdf(unique_image)
    

async def textract_drawing_numbers():
  async with db.database:
    textract_service = TextractService(db.database)
    unique_image = await db.UniqueImage.objects.get_or_none(md5_hash='bbef6885f8b3eac5ae58dcb006a0fdc1')
    await textract_drawing_number_on_unique_image(textract_service, unique_image)
    return
    max_analyze = 10
    idx = 0
    for anno in await db.UniqueImageAnnotation.objects.select_related('unique_image_id').filter(valid_roi=True).all():
      await textract_drawing_number_on_unique_image(textract_service, anno.unique_image_id)
      idx += 1
      if idx >= max_analyze:
        return


if __name__ == '__main__':
  import sys

  asyncio.run(textract_drawing_numbers())
  #asyncio.run(validate_textract_results())

  sys.exit()
