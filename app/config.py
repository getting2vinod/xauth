import os
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    ROUTE_PATH: str = os.getenv("ROUTE_PATH", "")
    GOOGLE_CREDENTIALS_FILE: str = os.getenv("GOOGLE_CREDENTIALS_FILE", "credentials.json")
    GOOGLE_SHEET_NAME: str = os.getenv("GOOGLE_SHEET_NAME", "https://docs.google.com/spreadsheets/d/1ge1ICzCRMXXHbllb9Rl9A90UiVWCXZkgGRuDvIBfgpA/")
    SECRET_KEY: str = os.getenv("SECRET_KEY", "super-secret-key")
    PWD_HASH_KEY: str = os.getenv("PWD_HASH_KEY", "your-pwdhashkey-here")

    class Config:
        env_file = ".env"
        extra = "ignore"

settings = Settings()