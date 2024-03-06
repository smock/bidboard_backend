import asyncio

from app import db
from app.services.buildflow_data_service import BuildflowDataService


async def get_or_create_company(company_name):
  async with db.database:
    company = await db.Company.objects.get_or_none(name=company_name)
    if company is None:
      company = await db.Company(name=company_name).save()
    return company


async def parse_bids(company):
  async with db.database:
    bcds = BuildflowDataService(db.database, company)
    await bcds.sync_bids()

if __name__ == '__main__':
  import sys

  company = asyncio.run(get_or_create_company('Tristate Plumbing'))
  asyncio.run(parse_bids(company))

  sys.exit()