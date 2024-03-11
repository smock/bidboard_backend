# app/schemas.py
import datetime
import uuid
from typing import List, Optional, Dict
from dateutil.relativedelta import relativedelta

from pydantic import BaseModel, root_validator

from app import constants

class GCChartEntry(BaseModel):
  rank: int
  name: str
  delta: Optional[int]

class GCChartRanking(BaseModel):
  metric: str
  metric_title: str
  entries: List[GCChartEntry]

  @root_validator(pre=True)
  def set_metric_title(cls, values):
    if values['metric'] == 'num_permits':
      values['metric_title'] = 'Most Active'
    else:
      values['metric_title'] = 'Largest Projects'
    return values

class GCChart(BaseModel):
  slug: str
  title: str
  borough: Optional[str]
  building_code: Optional[str]
  start_date: datetime.date
  end_date: datetime.date
  date_title: str
  rankings: Optional[Dict[str, GCChartRanking]]

  @root_validator(pre=True)
  def set_title(cls, values):
    title = ''
    if values['borough'] is None:
      title += 'New York City'
    else:
      title += values['borough']
    if values['building_code'] is None:
      title += ' &mdash; All Building Types'
    else:
      title += ' &mdash; ' + constants.BUILDING_CODE_CATEGORIES[values['building_code']]
    
    values['title'] = title
    return values

  @root_validator(pre=True)
  def set_date_title(cls, values):
    title = ''
    if values['end_date'].month - values['start_date'].month == 3:
      if values['start_date'].month == 1:
        title += 'Q1 %s &mdash; ' % values['start_date'].year
      if values['start_date'].month == 4:
        title += 'Q2 %s &mdash; ' % values['start_date'].year
      if values['start_date'].month == 7:
        title += 'Q3 %s &mdash; ' % values['start_date'].year
      if values['start_date'].month == 10:
        title += 'Q4 %s &mdash; ' % values['start_date'].year

    values['date_title'] = title + '%s - %s' % (values['start_date'].strftime("%B %d"), (values['end_date'] + relativedelta(days=-1)).strftime("%B %d, %Y"))
    return values
