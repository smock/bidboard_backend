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
  aws_access_key_id: str = Field(..., env='AWS_ACCESS_KEY_ID')
  aws_secret_access_key: str = Field(..., env='AWS_SECRET_ACCESS_KEY')
  aws_region: str = Field(..., env='AWS_REGION')
  textract_bucket_name: str = Field(..., env='TEXTRACT_BUCKET_NAME')

settings = Settings()
