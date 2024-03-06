import requests
from databases import Database
from dateutil import parser

from app import db


class DobNowDataService:
  APPROVED_PERMIT_API_ENDPOINT = "https://data.cityofnewyork.us/resource/rbx6-tga4.json"
  JOB_APPLICATION_API_ENDPOINT = "https://data.cityofnewyork.us/resource/w9ak-ipjd.json"


  def __init__(self, db: Database):
    self.db = db

  async def upsert_company(self, company_name):
    company = await db.DobCompany.objects.get_or_none(name=company_name)
    if company is None:
      company = await db.DobCompany(
        name=company_name
      ).save()
    return company

  async def upsert_permit(self, permit_dict):
    for key in ['applicant_business_name', 'job_filing_number', 'approved_date', 'issued_date']:
      if key not in permit_dict:
        return None
    company = await self.upsert_company(permit_dict['applicant_business_name'])

    created = True
    permit = await db.DobApprovedPermit.objects.get_or_none(
      job_filing_number=permit_dict['job_filing_number'],
      filing_reason=permit_dict['filing_reason'],
      applicant_business_id=company.id,
      work_type=permit_dict['work_type'],
      issued_date=parser.parse(permit_dict['issued_date'])
    )
    if permit is None:
      created = False
      permit = db.DobApprovedPermit.construct(
        job_filing_number=permit_dict['job_filing_number'],
        filing_reason=permit_dict['filing_reason'],
        applicant_business_id=company.id,
        work_type=permit_dict['work_type'],
        issued_date=parser.parse(permit_dict['issued_date'])
      )
    permit.approved_date=parser.parse(permit_dict['approved_date'])
    for key in ['borough', 'block', 'lot', 'estimated_job_costs']:
      if key in permit_dict:
        setattr(permit, key, permit_dict[key])
    permit.data = permit_dict

    if created is False:
      await permit.save()
    else:
      await permit.update()
    return permit

  async def sync_approved_permits(self):
    offset = 0
    bad_rows = 0
    rows = 0
    while True:
      response = requests.get(DobNowDataService.APPROVED_PERMIT_API_ENDPOINT, params={'$offset': offset})
      results = response.json()
      if len(results) == 0:
        break
      rows += len(results)
      for permit in results:
        row = await self.upsert_permit(permit)
        if row is None:
          bad_rows+=1
      offset += len(results)
      print(bad_rows)
      print(rows)
      print('---')

  async def parse_approved_permits(self):
    rows = 0
    bad_rows = 0
    async for permit in db.DobApprovedPermit.process_in_batches():
      row = await self.upsert_permit(permit.data)
      if row is None:
        bad_rows+=1
      rows += 1
      if rows % 1000 == 0:
        print(permit.created_at)
        print(bad_rows)
        print(rows)
        print('---')
  

  async def upsert_job_application(self, job_application_dict):
    if 'filing_date' not in job_application_dict:
      return None

    created = True
    job_application = await db.DobJobApplication.objects.get_or_none(
      job_filing_number=job_application_dict['job_filing_number'],
    )
    if job_application is None:
      created = False
      job_application = db.DobJobApplication.construct(
        job_filing_number=job_application_dict['job_filing_number']
      )
    job_application.filing_date=parser.parse(job_application_dict['filing_date'])
    job_application.filing_status=job_application_dict['filing_status']
    job_application.data = job_application_dict
    for key in ['borough', 'block', 'lot', 'initial_cost']:
      if key in job_application_dict:
        setattr(job_application, key, job_application_dict[key])

    if created is False:
      await job_application.save()
    else:
      await job_application.update()
    return job_application

  async def sync_job_applications(self):
    offset = 0
    bad_rows = 0
    rows = 0
    while True:
      response = requests.get(DobNowDataService.JOB_APPLICATION_API_ENDPOINT, params={'$offset': offset})
      results = response.json()
      if len(results) == 0:
        break
      rows += len(results)
      for job_application in results:
        row = await self.upsert_job_application(job_application)
        if row is None:
          bad_rows+=1
      offset += len(results)
      print(bad_rows)
      print(rows)
      print('---')