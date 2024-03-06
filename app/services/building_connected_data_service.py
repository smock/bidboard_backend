import requests
from databases import Database
from dateutil import parser

from app.config import settings
from app import db


class BuildingConnectedDataService:
  LOGIN_URL = 'https://app.buildingconnected.com/login'
  EMAIL_API_ENDPOINT = 'https://app.buildingconnected.com/api/sso/status/login'
  LOGIN_API_ENDPOINT = 'https://app.buildingconnected.com/api/sessions'
  OPPORTUNITIES_API_ENDPONT = 'https://app.buildingconnected.com/api/opportunities/v2/pipeline'

  def __init__(self, db: Database, company: db.Company):
    self.db = db
    self.company = company
    self.session = None
  
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
    return bid

  async def sync_bids(self):
    self.init_session()
    for archive_state in ['ARCHIVED_ONLY', 'ACTIVE_ONLY']:
      for workflow_state in db.BCBidStatus:
        startIndex = 0
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
            await self.upsert_bid(bid)
          startIndex += len(results)

  async def parse_bids(self):
    for building_connected_bid in await db.BCBid.objects.filter(company_id=self.company.id).all():
      await self.upsert_bid(building_connected_bid.data)
