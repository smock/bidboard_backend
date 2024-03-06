import csv
from io import StringIO, BytesIO
import zipfile

import requests
from databases import Database
from dateutil import parser

from app import db


class PlutoDataService:
  CSV_ENDPOINT = "https://s-media.nyc.gov/agencies/dcp/assets/files/zip/data-tools/bytes/nyc_pluto_23v3_1_csv.zip"
  def __init__(self, db: Database):
    self.db = db


  async def upsert_lot(self, lot_dict):
    created = True
    lot = await db.PlutoLot.objects.get_or_none(
      borough=lot_dict['borough'],
      block=lot_dict['block'],
      lot=lot_dict['lot']
    )
    if lot is None:
      created = False
      lot = db.PlutoLot.construct(
        borough=lot_dict['borough'],
        block=lot_dict['block'],
        lot=lot_dict['lot']
      )
    if 'address' in lot_dict:
      lot.address = lot_dict['address']
    lot.building_code = lot_dict['bldgclass']
    lot.data = lot_dict

    if created is False:
      await lot.save()
    else:
      await lot.update()
    return lot

  async def sync_lots(self):
    response = requests.get(PlutoDataService.CSV_ENDPOINT)
    response.raise_for_status()

    zip_in_memory = BytesIO(response.content)
    with zipfile.ZipFile(zip_in_memory) as zip_file:
      csv_filename = [name for name in zip_file.namelist() if name.endswith('.csv')][0]
      with zip_file.open(csv_filename) as csv_file:
        csv_content = csv_file.read()

    file_like_object = StringIO(csv_content.decode('utf-8'))
    csv_reader = csv.DictReader(file_like_object)
    
    rows = 0
    for row in csv_reader:
      await self.upsert_lot(row)
      rows += 1
      if rows % 1000 == 0:
        print(rows)

