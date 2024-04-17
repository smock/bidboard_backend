# app/db.py
import datetime
from enum import Enum
from typing import Optional, AsyncGenerator, Dict, Any
import uuid

import databases
import ormar
import sqlalchemy

from .config import settings

database = databases.Database(settings.db_url)
metadata = sqlalchemy.MetaData()

class BaseMeta(ormar.ModelMeta):
  metadata = metadata
  database = database

class BaseModel(ormar.Model):
  class Meta(BaseMeta):
    abstract = True  # This makes sure the class itself is not treated as a model to be created in the DB

  id: uuid.UUID = ormar.UUID(primary_key=True, default=uuid.uuid4)
  created_at: datetime.datetime = ormar.DateTime(default=datetime.datetime.utcnow, nullable=False, index=True)
  updated_at: Optional[datetime.datetime] = ormar.DateTime(nullable=True)

  @classmethod
  def __declare_last__(cls):
    @sqlalchemy.event.listens_for(cls, 'before_update')
    def receive_before_update(mapper, connection, target):
      target.updated_at = datetime.datetime.utcnow()

  @classmethod
  async def process_in_batches(cls, batch_size: int = 100, **filters: Dict[str, Any]) -> AsyncGenerator["BaseModel", None]:
    last_created_at = None
    while True:
      query = cls.objects.filter(**filters)
      if last_created_at is not None:
        query = query.filter(created_at__gt=last_created_at)
      query = query.order_by("created_at").limit(batch_size)

      batch = await query.all()
      if not batch:
        break

      for item in batch:
        yield item

      last_created_at = batch[-1].created_at

class Company(BaseModel):
  class Meta(BaseMeta):
    tablename = "companies"

  name: str = ormar.String(max_length=50, nullable=False, unique=True)


class BCCompany(BaseModel):
  class Meta(BaseMeta):
    tablename = "bc_companies"
  bc_id: str = ormar.String(max_length=24, nullable=False, unique=True)
  name: str = ormar.Text(nullable=False)
  data: dict = ormar.JSON(nullable=False)

class BCBidStatus(Enum):
  UNDECIDED = 0
  NEEDS_PROPOSAL = 1
  SUBMITTED = 2
  WON = 3
  LOST = 4
  OTHER = 5
  DECLINED = 6

class BCBid(BaseModel):
  class Meta(BaseMeta):
    tablename = "bc_bids"
    constraints = [
      sqlalchemy.UniqueConstraint('company_id', 'bc_id')
    ]
  company_id: Company = ormar.ForeignKey(Company, nullable=False)
  bc_id: str = ormar.String(max_length=24, nullable=False)
  bc_company_id: BCCompany = ormar.ForeignKey(BCCompany, nullable=False)
  name: str = ormar.Text(nullable=False)
  location: str = ormar.Text(nullable=True)
  date_invited: datetime.datetime = ormar.DateTime(nullable=True)
  status: int = ormar.Integer(nullable=False, choices=list(BCBidStatus))
  is_archived: bool = ormar.Boolean(nullable=False)
  data: dict = ormar.JSON(nullable=False)

class BCBidFileSystemType(Enum):
  FOLDER = 0
  FILE = 1

class BCBidFile(BaseModel):
  class Meta(BaseMeta):
    tablename = "bc_bid_files"
    constraints = [
      sqlalchemy.UniqueConstraint('bc_bid_id', 'bc_id')
    ]
  bc_bid_id: BCBid = ormar.ForeignKey(BCBid, nullable=False)
  bc_id: str = ormar.String(max_length=24, nullable=False)
  file_system_type: int = ormar.Integer(nullable=False, choices=list(BCBidFileSystemType))
  name: str = ormar.Text(nullable=False)
  download_url: str = ormar.Text(nullable=True)
  date_created: datetime.datetime = ormar.DateTime(nullable=True)
  date_modified: datetime.datetime = ormar.DateTime(nullable=True)
  parent_folder_id: str = ormar.String(max_length=36, nullable=True)
  data: dict = ormar.JSON(nullable=False)
  local_filename: str = ormar.String(nullable=True, max_length=100)
  mime_type: str = ormar.String(nullable=True, max_length=100)
  images_extracted: bool = ormar.Boolean(nullable=False, default=False)

class BCBidFileImage(BaseModel):
  class Meta(BaseMeta):
    tablename = "bc_bid_file_images"
    constraints = [
      sqlalchemy.UniqueConstraint('bc_bid_file_id', 'page_number')
    ]
  bc_bid_file_id: BCBidFile = ormar.ForeignKey(BCBidFile, nullable=False)
  page_number: int = ormar.Integer(nullable=False)
  local_filename: str = ormar.String(nullable=True, max_length=100)
  has_architectural_page_number: bool = ormar.Boolean(nullable=True)


class BCBidFileImageAnnotation(BaseModel):
  class Meta(BaseMeta):
    tablename = "bc_bid_file_image_annotations"
  bc_bid_file_image_id: BCBidFileImage = ormar.ForeignKey(BCBidFileImage, nullable=False, unique=True)
  page_number: str = ormar.String(nullable=False, max_length=100)
  page_number_x1: int = ormar.Integer(nullable=False)
  page_number_y1: int = ormar.Integer(nullable=False)
  page_number_x2: int = ormar.Integer(nullable=False)
  page_number_y2: int = ormar.Integer(nullable=False)


class DobCompany(BaseModel):
  class Meta(BaseMeta):
    tablename = "dob_companies"
  name: str = ormar.Text(nullable=False, unique=True)

class DobApprovedPermit(BaseModel):
  class Meta(BaseMeta):
    tablename = "dob_approved_permits"
    constraints = [
      sqlalchemy.UniqueConstraint('job_filing_number', 'filing_reason', 'work_type', 'applicant_business_id', 'issued_date', name='uc_dob_approved_permit_pk')
    ]
  job_filing_number: str = ormar.String(max_length=24, nullable=False)
  filing_reason: str = ormar.String(max_length=100, nullable=False)
  work_type: str = ormar.String(max_length=100, nullable=False)
  applicant_business_id: DobCompany = ormar.ForeignKey(DobCompany, nullable=False)
  borough: str = ormar.String(max_length=100, nullable=True)
  block: str = ormar.String(max_length=100, nullable=True)
  lot: str = ormar.String(max_length=100, nullable=True)
  normalized_borough: str = ormar.String(max_length=100, nullable=True)
  approved_date: datetime.datetime = ormar.DateTime(nullable=False)
  issued_date: datetime.datetime = ormar.DateTime(nullable=False)
  estimated_job_costs: float = ormar.Decimal(max_digits=12, decimal_places=2, nullable=True)
  data: dict = ormar.JSON(nullable=False)

class DobJobApplication(BaseModel):
  class Meta(BaseMeta):
    tablename = "dob_job_applications"
  job_filing_number: str = ormar.String(max_length=24, nullable=False, unique=True)
  filing_status: str = ormar.String(max_length=100, nullable=False)
  borough: str = ormar.String(max_length=100, nullable=True)
  block: str = ormar.String(max_length=100, nullable=True)
  lot: str = ormar.String(max_length=100, nullable=True)
  filing_date: datetime.datetime = ormar.DateTime(nullable=False)
  initial_cost: float = ormar.Decimal(max_digits=12, decimal_places=2, nullable=True)
  data: dict = ormar.JSON(nullable=False)

class PlutoLot(BaseModel):
  class Meta(BaseMeta):
    tablename = "pluto_lots"
    constraints = [
      sqlalchemy.UniqueConstraint('borough', 'block', 'lot')
    ]
  borough: str = ormar.String(max_length=100, nullable=True)
  block: str = ormar.String(max_length=100, nullable=True)
  lot: str = ormar.String(max_length=100, nullable=True)
  address: str = ormar.Text(nullable=False)
  building_code: str = ormar.String(max_length=100, nullable=False)
  normalized_borough: str = ormar.String(max_length=100, nullable=True)
  data: dict = ormar.JSON(nullable=False)

class GCPermitRollup(BaseModel):
  class Meta(BaseMeta):
    tablename = "gc_permit_rollups"
    constraints = [
      sqlalchemy.UniqueConstraint('dob_company_id', 'start_date', 'end_date', 'borough', 'building_code', name='uc_gc_permit_rollups')
    ]
  dob_company_id: DobCompany = ormar.ForeignKey(DobCompany, nullable=False)
  start_date: datetime.date = ormar.Date(nullable=False)
  end_date: datetime.date = ormar.Date(nullable=False)
  borough: str = ormar.String(max_length=100, nullable=True)
  building_code: str = ormar.String(max_length=100, nullable=True)
  num_permits: int = ormar.Integer(nullable=False, index=True)
  average_estimated_job_costs: float = ormar.Decimal(max_digits=12, decimal_places=2, nullable=False, index=True)
  median_estimated_job_costs: float = ormar.Decimal(max_digits=12, decimal_places=2, nullable=False, index=True)

class GCChart(BaseModel):
  class Meta(BaseMeta):
    tablename = "gc_charts"
    constraints = [
      sqlalchemy.UniqueConstraint('start_date', 'end_date', 'borough', 'building_code', name='uc_gc_permit_charts')
    ]
  slug: str = ormar.String(max_length=500, nullable=False, unique=True)
  start_date: datetime.date = ormar.Date(nullable=False)
  end_date: datetime.date = ormar.Date(nullable=False)
  borough: str = ormar.String(max_length=100, nullable=True)
  building_code: str = ormar.String(max_length=100, nullable=True)
  permits_rolled_up_at: Optional[datetime.datetime] = ormar.DateTime(nullable=True)
  rankings_synced_dat: Optional[datetime.datetime] = ormar.DateTime(nullable=True)


class GCChartRanking(BaseModel):
  class Meta(BaseMeta):
    tablename = "gc_chart_rankings"
    constraints = [
      sqlalchemy.UniqueConstraint('gc_chart_id', 'metric')
    ]
  gc_chart_id: GCChart = ormar.ForeignKey(GCChart, nullable=False)
  metric: str = ormar.String(max_length=100, nullable=False)
  dob_company_ids: list = ormar.JSON(nullable=True, default=[])
  deltas: list = ormar.JSON(nullable=True, default=[])

engine = sqlalchemy.create_engine(settings.db_url)
