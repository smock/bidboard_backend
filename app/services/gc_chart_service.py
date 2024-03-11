import statistics
import uuid
from decimal import Decimal, ROUND_HALF_UP
import datetime

from sqlalchemy import select, func, and_
from databases import Database
from dateutil.relativedelta import relativedelta
from slugify import slugify

from app import db
from app import schemas
from app import constants


class GCChartService:
  START_YEAR = 2023

  def __init__(self, db: Database):
    self.db = db
  
  def get_date_ranges(year):
    ranges = []
    # full year
    ranges.append([datetime.date(year, 1, 1), datetime.date(year + 1, 1, 1), str(year)])
    for quarter in range(1, 5):
      start_date = datetime.date(year, 3 * (quarter - 1) + 1, 1)
      ranges.append([start_date, start_date + relativedelta(months=+3), 'q'+str(quarter)+'-'+str(year)])
    """
    for month in range(1, 12):
      start_date = datetime.date(year, month, 1)
      ranges.append([start_date, start_date + relativedelta(months=+1), slugify(str(start_date.strftime("%B")))+'-'+str(year)])
    """
    return ranges
  
  def get_previous_range(start_date, end_date):
    delta = relativedelta(end_date, start_date)
    return (start_date - delta, end_date - delta)

  def assemble_slug(date_slug, borough, building_code_prefix):
    path = ''
    if borough:
      path += '/' + slugify(borough)
    else:
      path += '/nyc'
    if building_code_prefix:
      path += '/' + slugify(constants.BUILDING_CODE_CATEGORIES[building_code_prefix])
    else:
      path += '/all-buildings'
    path += '/' + date_slug
    return path

  async def get_parent_chart(self, chart):
    if chart.borough is not None:
      return await db.GCChart.objects.get_or_none(
        start_date=chart.start_date,
        end_date=chart.end_date,
        borough=None,
        building_code=chart.building_code        
      )
    elif chart.building_code is not None:
      return await db.GCChart.objects.get_or_none(
        start_date=chart.start_date,
        end_date=chart.end_date,
        borough=chart.borough,
        building_code=None
      )
    else:
      return None

  async def get_previous_chart(self, chart):
    (start_date, end_date) = GCChartService.get_previous_range(chart.start_date, chart.end_date)
    return await db.GCChart.objects.get_or_none(
      start_date=start_date,
      end_date=end_date,
      borough=chart.borough,
      building_code=chart.building_code
    )

  async def upsert_chart(self, slug, start_date, end_date, borough, building_code):
    created = True
    chart = await db.GCChart.objects.get_or_none(
      start_date=start_date,
      end_date=end_date,
      borough=borough,
      building_code=building_code
    )
    if chart is None:
      created = False
      chart = db.GCChart.construct(
        start_date=start_date,
        end_date=end_date,
        borough=borough,
        building_code=building_code
      )
    chart.parent_gc_chart_id = getattr(await self.get_parent_chart(chart), 'id', None)
    chart.previous_gc_chart_id = getattr(await self.get_previous_chart(chart), 'id', None)    
    chart.slug=slug
    if created is False:
      await chart.save()
    else:
      await chart.update()
    return chart

  async def upsert_charts(self):
    upserted_charts = []
    for year in range(GCChartService.START_YEAR, datetime.date.today().year + 1):
      for (start_date, end_date, date_slug) in GCChartService.get_date_ranges(year):
        for borough in [None, 'Brooklyn', 'Manhattan', 'Queens', 'Bronx', 'Staten Island']:
          for building_code_ord in [None] + list(range(ord('A'), ord('Z') + 1)):
            building_code_prefix = chr(building_code_ord) if building_code_ord else None
            if building_code_prefix == 'X':
              continue
            slug = GCChartService.assemble_slug(date_slug, borough, building_code_prefix)
            chart = await self.upsert_chart(slug, start_date, end_date, borough, building_code_prefix)
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

  async def rollup_permits_for_chart(self, chart, skip_if_exists=True):
    start_date = chart.start_date
    end_date = chart.end_date
    borough = chart.borough
    building_code_prefix = chart.building_code
    if skip_if_exists:
      if await db.GCPermitRollup.objects.filter(
        start_date=start_date,
        end_date=end_date,
        borough=borough,
        building_code=building_code_prefix
      ).count() > 0:
        print("Skipping calculation")
        return False
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

  async def upsert_chart_ranking(self, gc_chart_id, metric, dob_company_ids, deltas):
    created = True
    chart_ranking = await db.GCChartRanking.objects.get_or_none(
      gc_chart_id=gc_chart_id,
      metric=metric,
    )
    if chart_ranking is None:
      created = False
      chart_ranking = db.GCChartRanking.construct(
        gc_chart_id=gc_chart_id,
        metric=metric
      )
    chart_ranking.dob_company_ids = dob_company_ids
    chart_ranking.deltas = deltas
    if created is False:
      await chart_ranking.save()
    else:
      await chart_ranking.update()
    return chart_ranking

  async def calculate_chart_rankings(self, chart):
    start_date = chart.start_date
    end_date = chart.end_date
    borough = chart.borough
    building_code = chart.building_code
    for metric in ['num_permits', 'average_estimated_job_costs', 'median_estimated_job_costs']:
      gc_permit_rollups = await db.GCPermitRollup.objects.filter(
        start_date=start_date,
        end_date=end_date,
        borough=borough,
        building_code=building_code,
        num_permits__gte=2
      ).order_by("-%s" % metric).values_list('dob_company_id')
      dob_company_ids = [str(permit_rollup[0]) for permit_rollup in gc_permit_rollups]
      deltas = [None] * len(dob_company_ids)
      if chart.previous_gc_chart_id is not None:
        previous_chart = await db.GCChart.objects.get(id=chart.previous_gc_chart_id)
        previous_chart_rankings = await db.GCChartRanking.objects.get_or_none(
          gc_chart_id=previous_chart.id,
          metric=metric
        )
        if previous_chart_rankings is not None:
          deltas = []
          for index, dob_company_id in enumerate(dob_company_ids):
            try:
              previous_index = previous_chart_rankings.dob_company_ids.index(dob_company_id)
              deltas.append(previous_index - index)
            except ValueError:
              deltas.append(None)
      await self.upsert_chart_ranking(chart.id, metric, dob_company_ids, deltas)
  
  async def get_chart_rankings_for_chart(self, chart, format_for_frontend=True, ranking_limit=20):
    rankings = await db.GCChartRanking.objects.filter(gc_chart_id=chart.id).all()
    if not format_for_frontend:
      return rankings
    frontend_rankings = {}
    for ranking in rankings:
      entries = []
      dob_companies = {company.id: company for company in await db.DobCompany.objects.filter(
        id__in=[uuid.UUID(dob_company_id) for dob_company_id in ranking.dob_company_ids[0:20]]
      ).all()}
      for index, dob_company_id in enumerate(ranking.dob_company_ids[0:20]):
        entries.append(schemas.GCChartEntry(
          rank=index + 1,
          name=dob_companies[uuid.UUID(dob_company_id)].name,
          delta=ranking.deltas[index]
        ))
      frontend_rankings[ranking.metric] = schemas.GCChartRanking(
        metric=ranking.metric,
        entries=entries
      )
    return schemas.GCChart(
      slug=chart.slug,
      borough=chart.borough,
      building_code=chart.building_code,
      start_date=chart.start_date,
      end_date=chart.end_date,
      rankings=frontend_rankings
    )
  
  async def get_children_charts_by_path(self, path, format_for_frontend=True):
    charts = {}
    for chart in await db.GCChart.objects.filter(path=path).all():
      entries = []
      dob_companies = {company.id: company for company in await db.DobCompany.objects.filter(
        id__in=[uuid.UUID(dob_company_id) for dob_company_id in chart.dob_company_ids[0:20]]
      ).all()}
      for index, dob_company_id in enumerate(chart.dob_company_ids[0:20]):
        entries.append(schemas.GCChartEntry(
          rank=index + 1,
          name=dob_companies[uuid.UUID(dob_company_id)].name,
          delta=chart.deltas[index]
        ))
      charts[chart.metric] = schemas.GCChart(
        slug=chart.slug,
        path=chart.path,
        borough=chart.borough,
        building_code=chart.building_code,
        start_date=chart.start_date,
        end_date=chart.end_date,
        metric=chart.metric,
        entries=entries
      )
    return charts


