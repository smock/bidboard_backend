# app/config.py
from dotenv import load_dotenv
from pydantic import BaseSettings, Field

load_dotenv()

class Settings(BaseSettings):
  db_url: str = Field(..., env='DATABASE_URL')
  building_connected_username: str = Field(..., env='BUILDING_CONNECTED_USERNAME')
  building_connected_password: str = Field(..., env='BUILDING_CONNECTED_PASSWORD')
  buildflow_username: str = Field(..., env='BUILDFLOW_USERNAME')
  buildflow_password: str = Field(..., env='BUILDFLOW_PASSWORD')

settings = Settings()
