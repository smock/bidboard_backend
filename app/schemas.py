# app/schemas.py
import datetime
import uuid
from typing import List, Optional

from pydantic import BaseModel, root_validator

from app import constants

class GCChartEntry(BaseModel):
  rank: int
  name: str
  delta: Optional[int]

class GCChart(BaseModel):
  slug: str
  path: str
  title: str
  borough: Optional[str]
  building_code: Optional[str]
  start_date: datetime.date
  end_date: datetime.date
  entries: List[GCChartEntry]
  metric: str
  metric_title: str

  @root_validator(pre=True)
  def set_title(cls, values):
    title = ''
    if values['borough'] is None:
      title += 'New York City'
    else:
      title += values['borough']
    if values['building_code'] is None:
      title += ': All Building Types'
    else:
      title += ': ' + constants.BUILDING_CODE_CATEGORIES[values['building_code']]
    if values['end_date'].year == values['start_date'].year + 1:
      title += ': %s' % values['start_date'].year
    
    values['title'] = title
    return values

  @root_validator(pre=True)
  def set_metric_title(cls, values):
    if values['metric'] == 'num_permits':
      values['metric_title'] = 'Most Active'
    else:
      values['metric_title'] = 'Largest Projects'
    return values