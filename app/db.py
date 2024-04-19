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

class UniqueImage(BaseModel):
  class Meta(BaseMeta):
    tablename = "unique_images"
  md5_hash: str = ormar.String(nullable=False, max_length=100, unique=True)
  local_filename: str = ormar.String(nullable=True, max_length=100, unique=True)
  has_architectural_page_number: bool = ormar.Boolean(nullable=True)

class BCBidFileImage(BaseModel):
  class Meta(BaseMeta):
    tablename = "bc_bid_file_images"
    constraints = [
      sqlalchemy.UniqueConstraint('bc_bid_file_id', 'page_number')
    ]
  bc_bid_file_id: BCBidFile = ormar.ForeignKey(BCBidFile, nullable=False)
  page_number: int = ormar.Integer(nullable=False)
  unique_image_id: UniqueImage = ormar.ForeignKey(UniqueImage, nullable=False)

class AnnotationSource(Enum):
  HEURISTICS = 0
  MANUAL = 1

class UniqueImageAnnotation(BaseModel):
  class Meta(BaseMeta):
    tablename = "unique_image_annotations"
  unique_image_id: UniqueImage = ormar.ForeignKey(UniqueImage, nullable=False, related_name='unique_image_annotations')
  page_number: str = ormar.String(nullable=False, max_length=100)
  page_number_x1: int = ormar.Integer(nullable=False)
  page_number_y1: int = ormar.Integer(nullable=False)
  page_number_x2: int = ormar.Integer(nullable=False)
  page_number_y2: int = ormar.Integer(nullable=False)
  valid: bool = ormar.Boolean(nullable=True)
  valid_roi: bool = ormar.Boolean(nullable=True)
  annotation_source: int = ormar.Integer(nullable=True, choices=list(AnnotationSource))
