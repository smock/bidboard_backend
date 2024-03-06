import requests
from databases import Database
from dateutil import parser

from app.config import settings
from app import db


class BuildflowDataService:
  LOGIN_URL = 'https://login.buildflow.com/login/?'
  LOGIN_ENDPOINT = 'https://login.buildflow.com/homepage/userlogin.ashx'

  def __init__(self, db: Database, company: db.Company):
    self.db = db
    self.company = company
    self.session = None
  
  def init_session(self):
    self.session = requests.Session()
    self.session.get(BuildflowDataService.LOGIN_URL)
    self.authenticate()

  def authenticate(self):
    response = self.session.post(
      BuildflowDataService.LOGIN_ENDPOINT,
      data={
        'u': settings.buildflow_username,
        'p': settings.buildflow_password,
        'sp': '',
        'rme': 0
      }
    )
    self.idval = response.json()['idval']

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
    resp = self.session.get('https://login.buildflow.com/bfref/projectlisting.ashx', params={
      'id': self.idval,
      'larch': '1',
      'lactive': '1',
      'lt': 'projectlist'
    })
    payload = resp.json()
    jobs_payload = [item for item in payload if item['oname'] == 'projects'][0]['objc']
    for job in jobs_payload:
      await self.sync_bid(job['projectid'])

  async def sync_bid(self, project_id):
    resp = self.session.post('https://login.buildflow.com/bfref/projectlisting.ashx', params={
      'id': self.idval,
      'lt': 'pdetails'
    }, data = {
      'p': project_id
    })
    print(resp.json())
