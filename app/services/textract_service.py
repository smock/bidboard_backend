import re
import tempfile
import json

from databases import Database
import boto3
from PyPDF2 import PdfReader, PdfWriter

from app import db
from app.config import settings

class TextractService:
  def __init__(self, db: Database):
    self.db = db
    self.textract_client = boto3.client(
      'textract',
      aws_access_key_id=settings.aws_access_key_id,
      aws_secret_access_key=settings.aws_secret_access_key,
      region_name=settings.aws_region
    )
    self.s3_client = boto3.client(
      's3',
      aws_access_key_id=settings.aws_access_key_id,
      aws_secret_access_key=settings.aws_secret_access_key,
      region_name=settings.aws_region
    )

  async def upload_pdf_to_s3_from_unique_image(self, unique_image):
    print(unique_image.local_filename)
    # first backtrack to the pdf from the unique image
    bc_bid_file_image = await db.BCBidFileImage.objects \
                                .select_related('bc_bid_file_id') \
                                .get_or_none(unique_image_id=unique_image.id)
    # then grab the page corresponding to the image
    outfile_name = None
    input_filename = bc_bid_file_image.bc_bid_file_id.local_filename
    print(input_filename)
    with open(input_filename, "rb") as infile, tempfile.NamedTemporaryFile(delete=False) as outfile:
      reader = PdfReader(infile)
      writer = PdfWriter()
      print(bc_bid_file_image.page_number)

      writer.add_page(reader.pages[bc_bid_file_image.page_number - 1])
      writer.write(outfile)
      outfile_name = outfile.name
    print(outfile_name)

    # finally, upload to s3
    s3_key = f'{unique_image.md5_hash}.pdf'
    print(s3_key)
    self.s3_client.upload_file(outfile_name, settings.textract_bucket_name, s3_key)
    return True

  async def analyze_pdf(self, unique_image):
    s3_key = f'{unique_image.md5_hash}.pdf'
    # Start document analysis
    response = self.textract_client.analyze_document(
      Document={'S3Object': {'Bucket': settings.textract_bucket_name, 'Name': s3_key}},
      FeatureTypes=[
          'TABLES', 'FORMS', 'LAYOUT',
      ],
    )
    
    textract_filename = f'{unique_image.local_filename}_textract.json'
    with open(textract_filename, 'w') as fh:
      json.dump(response, fh, indent=4)
    unique_image.textract_filename = textract_filename
    await unique_image.update()
    print(unique_image.textract_filename)
    return
