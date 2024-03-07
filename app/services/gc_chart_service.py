import statistics
import uuid
from decimal import Decimal, ROUND_HALF_UP
import datetime

from sqlalchemy import select, func, and_
from databases import Database
from dateutil.relativedelta import relativedelta
from slugify import slugify

from app import db


class GCChartService:
  START_YEAR = 2023
  BUILDING_CODE_CATEGORIES = {
    'A': 'Single Family',
    'B': 'Two Family',
    'C': 'Walk-Up Apartments',
    'D': 'Elevator Apartments',
    'E': 'Warehouses',
    'F': 'Factories & Industrial',
    'G': 'Garages',
    'H': 'Hotels',
    'I': 'Hosptials & Health',
    'J': 'Theatres',
    'K': 'Stores',
    'L': 'Lofts',
    'M': 'Religious',
    'N': 'Asylums & Homes',
    'O': 'Office Buildings',
    'P': 'Indoor Assembly & Cultural',
    'Q': 'Outdoor Recreational',
    'R': 'Condos',
    'S': 'Mixed-Use',
    'T': 'Transportation',
    'U': 'Utility Bureau',
    'V': 'Vacant',
    'W': 'Educational',
    'Y': 'Government',
    'Z': 'Misc.'
  }

  def __init__(self, db: Database):
    self.db = db
  
  def get_date_ranges(year):
    ranges = []
    # full year
    ranges.append([datetime.date(year, 1, 1), datetime.date(year + 1, 1, 1), str(year)])
    for month in range(1, 12):
      start_date = datetime.date(year, month, 1)
      ranges.append([start_date, start_date + relativedelta(months=+1), slugify(str(start_date.strftime("%B")))+'-'+str(year)])
    for quarter in range(1, 4):
      start_date = datetime.date(year, 3 * (quarter - 1) + 1, 1)
      ranges.append([start_date, start_date + relativedelta(months=+3), 'q'+str(quarter)+'-'+str(year)])
    return ranges
  
  def assemble_slug(metric, date_slug, borough, building_code_prefix):
    slug = ''
    if borough:
      slug += '/' + slugify(borough)
    else:
      slug += '/nyc'
    if building_code_prefix:
      slug += '/' + slugify(GCChartService.BUILDING_CODE_CATEGORIES[building_code_prefix])
    else:
      slug += '/all-buildings'
    if metric == 'num_permits':
      slug += '/most-active'
    if metric == 'median_estimated_job_costs':
      slug += '/largest-projects'
    slug += '-' + date_slug
    return slug

  async def upsert_chart(self, slug, metric, start_date, end_date, borough, building_code):
    created = True
    chart = await db.GCChart.objects.get_or_none(
      metric=metric,
      start_date=start_date,
      end_date=end_date,
      borough=borough,
      building_code=building_code
    )
    if chart is None:
      created = False
      chart = db.GCChart.construct(
        metric=metric,
        start_date=start_date,
        end_date=end_date,
        borough=borough,
        building_code=building_code
      )
    chart.slug=slug
    if created is False:
      await chart.save()
    else:
      await chart.update()
    return chart

  async def upsert_charts(self):
    upserted_charts = []
    for metric in ['num_permits', 'average_estimated_job_costs', 'median_estimated_job_costs']:
      for year in range(GCChartService.START_YEAR, datetime.date.today().year):
        for (start_date, end_date, date_slug) in GCChartService.get_date_ranges(year):
          for borough in [None, 'Brooklyn', 'Manhattan', 'Queens', 'Bronx', 'Staten Island']:
            for building_code_ord in [None] + list(range(ord('A'), ord('Z') + 1)):
              building_code_prefix = chr(building_code_ord) if building_code_ord else None
              if building_code_prefix == 'X':
                continue
              slug = GCChartService.assemble_slug(metric, date_slug, borough, building_code_prefix)
              chart = await self.upsert_chart(slug, metric, start_date, end_date, borough, building_code_prefix)
              upserted_charts.append(chart)
    return upserted_charts

  async def upsert_rollup(self, dob_company_id, start_date, end_date, borough, building_code, num_permits, median_estimated_job_costs, average_estimated_job_costs):
    created = True
    rollup = await db.GCPermitRollup.objects.get_or_none(
      dob_company_id=dob_company_id,
      start_date=start_date,
      end_date=end_date,
      borough=borough,
      building_code=building_code
    )
    if rollup is None:
      created = False
      rollup = db.GCPermitRollup.construct(
        dob_company_id=dob_company_id,
        start_date=start_date,
        end_date=end_date,
        borough=borough,
        building_code=building_code
      )
    rollup.num_permits = num_permits
    rollup.median_estimated_job_costs = median_estimated_job_costs
    rollup.average_estimated_job_costs = average_estimated_job_costs
    if created is False:
      await rollup.save()
    else:
      await rollup.update()
    return rollup

  async def rollup_permits_for_chart(self, chart):
    start_date = chart.start_date
    end_date = chart.end_date
    borough = chart.borough
    building_code_prefix = chart.building_code
    permits_table = db.DobApprovedPermit.Meta.table
    lots_table = db.PlutoLot.Meta.table

    conditions = [
      permits_table.c.work_type == "General Construction",
      permits_table.c.filing_reason == "Initial Permit",
      permits_table.c.approved_date >= start_date,
      permits_table.c.approved_date < end_date
    ]
    if building_code_prefix:
      conditions.append(lots_table.c.building_code.like(building_code_prefix + "%"))
    if borough:
      conditions.append(lots_table.c.normalized_borough == borough)

    subquery = select([
        permits_table.c.applicant_business_id.label('dob_company_id'),
        permits_table.c.job_filing_number.label("job_filing_number"),
        func.max(permits_table.c.estimated_job_costs).label("estimated_job_costs")
    ]).select_from(
        permits_table
        .join(lots_table, and_(
            permits_table.c.normalized_borough == lots_table.c.normalized_borough,
            permits_table.c.lot == lots_table.c.lot,
            permits_table.c.block == lots_table.c.block
        ))
    ).where(and_(*conditions)
    ).group_by(permits_table.c.applicant_business_id, permits_table.c.job_filing_number).alias("subquery")

    main_query = select([
        subquery.c.dob_company_id,
        func.count().label("num_permits"),
        func.array_agg(subquery.c.estimated_job_costs).label("estimated_job_costs")
    ]).group_by(subquery.c.dob_company_id)
    
    for row in await self.db.fetch_all(main_query):
      median_job_costs = Decimal(statistics.median(row.estimated_job_costs)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
      average_job_costs = Decimal(statistics.mean(row.estimated_job_costs)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

      await self.upsert_rollup(
        uuid.UUID(row.dob_company_id),
        start_date,
        end_date,
        borough,
        building_code_prefix,
        row.num_permits,
        median_job_costs,
        average_job_costs)
  
  async def calculate_chart_rankings_and_deltas(self, chart):
    start_date = chart.start_date
    end_date = chart.end_date
    borough = chart.borough
    building_code_prefix = chart.building_code
    gc_permit_rollups = await db.GCPermitRollup.objects.filter(
      start_date=start_date,
      end_date=end_date,
      borough=borough,
      building_code=building_code_prefix
    ).order_by("-%s" % chart.metric).values_list('dob_company_id')
    chart.dob_company_ids = [str(permit_rollup[0]) for permit_rollup in gc_permit_rollups]
    await chart.update()
