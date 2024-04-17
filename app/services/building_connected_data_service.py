import requests
from databases import Database
from dateutil import parser
from pathlib import Path

from app.config import settings
from app import db

import magic


class BuildingConnectedDataService:
  LOGIN_URL = 'https://app.buildingconnected.com/login'
  EMAIL_API_ENDPOINT = 'https://app.buildingconnected.com/api/sso/status/login'
  LOGIN_API_ENDPOINT = 'https://app.buildingconnected.com/api/sessions'
  OPPORTUNITIES_API_ENDPONT = 'https://app.buildingconnected.com/api/opportunities/v2/pipeline'
  LOCAL_FILENAME_PATH = '/Users/harish/data/bidboard' 
 
  def __init__(self, db: Database, company: db.Company):
    self.db = db
    self.company = company
    self.session = None
    self.mime = magic.Magic(mime=True)

  
  def init_session(self):
    self.session = requests.Session()
    self.session.get(BuildingConnectedDataService.LOGIN_URL)
    self.session.get(
      BuildingConnectedDataService.EMAIL_API_ENDPOINT,
      params={ 'email': settings.building_connected_username }
    )
    self.authenticate()

  def authenticate(self):
    response = self.session.post(
      BuildingConnectedDataService.LOGIN_API_ENDPOINT,
      data={
        'grant_type': 'password',
        'username': settings.building_connected_username,
        'password': settings.building_connected_password
      }
    )

  async def upsert_company(self, company_dict):
    client = await db.BCCompany.objects.get_or_none(bc_id=company_dict['_id'])
    if client is None:
      client = await db.BCCompany(
        bc_id=company_dict['_id'],
        name=company_dict['name'],
        data=company_dict
      ).save()
    return client

  async def upsert_bid(self, bid_dict):
    created = True
    bid = await db.BCBid.objects.get_or_none(
      company_id=self.company.id,
      bc_id=bid_dict['_id']
    )
    if bid is None:
      created = False
      bid = db.BCBid.construct(company_id=self.company.id, bc_id=bid_dict['_id'])
    bid.data = bid_dict
    bc_company = await self.upsert_company(bid_dict['client']['company'])
    bid.bc_company_id = bc_company.id
    bid.name = bid_dict['name']
    if bid_dict.get('location') and bid_dict.get('location').get('complete'):
      bid.location = bid_dict['location']['complete']
    bid.date_invited = parser.parse(bid_dict['dateInvited']).replace(tzinfo=None) if bid_dict.get('dateInvited') else None
    bid.is_archived = bid_dict['isArchived']
    bid.status = db.BCBidStatus[bid_dict['workflowState']].value
    if created is False:
      await bid.save()
    else:
      await bid.update()
    
    await self.sync_bid_files(bid)

    return bid

  async def cache_bid_file(self, bid_file, force=False):
    if bid_file.local_filename is not None and not force:
      return bid_file

    output_folder = "%s/%s" % (BuildingConnectedDataService.LOCAL_FILENAME_PATH, bid_file.id)
    Path(output_folder).mkdir(parents=True, exist_ok=True)

    local_filename = "%s/source_file" % output_folder

    # Stream the download to handle large files without consuming too much memory
    response = self.session.get("https://app.buildingconnected.com/%s" % bid_file.download_url, stream=True)
    # Check if the request was successful
    if response.status_code == 200:
      with open(local_filename, 'wb') as file:
        for chunk in response.iter_content(chunk_size=8192):  # 8K chunks
          file.write(chunk)
    else:
        print(f"Failed to download bid file {bid_file.id} from {bid_file.download_url}. Status code: {response.status_code}")

    bid_file.local_filename = local_filename
    bid_file.mime_type = self.mime.from_file(local_filename)
    await bid_file.update()
    return bid_file
  
  async def upsert_bid_file(self, bid, file_dict, parent_folder=None):
    created = True
    file = await db.BCBidFile.objects.get_or_none(
      bc_bid_id=bid.id,
      bc_id=file_dict['_id']
    )
    if file is None:
      created = False
      file = db.BCBidFile.construct(bc_bid_id=bid.id, bc_id=file_dict['_id'])
    file.data = file_dict
    file.name = file_dict['name']
    file.file_system_type = db.BCBidFileSystemType[file_dict['type']].value
    file.download_url = file_dict['downloadUrl'] if 'downloadUrl' in file_dict.keys() else None
    file.date_created = parser.parse(file_dict['dateCreated']).replace(tzinfo=None) if file_dict.get('dateCreated', None) is not None else None
    file.date_modified = parser.parse(file_dict['dateModified']).replace(tzinfo=None) if file_dict.get('dateModified', None) is not None else None
    if parent_folder is not None:
      file.parent_folder_id = str(parent_folder.id)
    if created is False:
      await file.save()
    else:
      await file.update()
    return file

  async def sync_bid_files(self, bid, parent_folder=None):
    bc_id = bid.bc_id
    endpoint = "https://app.buildingconnected.com/api/opportunities/%s/files" % bc_id
    if parent_folder is not None:
      endpoint += '/%s' % parent_folder.bc_id
    response = self.session.get(endpoint)
    if response.status_code == 403:
      return
    items = response.json()['items']
    for item in items:
      try:
        file = await self.upsert_bid_file(bid, item, parent_folder)
      except:
        print(item)
        raise
      if item['type'] == 'FOLDER':
        await self.sync_bid_files(bid, file)

  async def sync_bids(self):
    self.init_session()
    for archive_state in ['ACTIVE_ONLY']:#['ARCHIVED_ONLY', 'ACTIVE_ONLY']:
      for workflow_state in db.BCBidStatus:
        startIndex = 0
        print("Syncing %s - %s bids, index %s" % (archive_state, workflow_state, startIndex))
        while True:
          response = self.session.get(BuildingConnectedDataService.OPPORTUNITIES_API_ENDPONT, params={
            'startIndex': startIndex,
            'count': 50,
            'order': 'desc',
            'userFilter': 'IM_FOLLOWING',
            'workflowStates[]': workflow_state.name,
            'sortKey': 'DATE_INVITED',
            'archiveFilter': archive_state
          })
          results = response.json()['results']
          if len(results) == 0:
            break
          for bid in results:
            bid_row = await self.upsert_bid(bid)
          startIndex += len(results)

  async def parse_bids(self):
    for building_connected_bid in await db.BCBid.objects.filter(company_id=self.company.id).all():
      await self.upsert_bid(building_connected_bid.data)
