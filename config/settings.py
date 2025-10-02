"""
Configuration management for Congressional Hearing Database
"""
import os
from typing import Optional
from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings with environment variable support"""

    # API Configuration
    api_key: str = Field(..., env='API_KEY')
    api_base_url: str = Field(default='https://api.congress.gov/v3', env='API_BASE_URL')
    rate_limit: int = Field(default=5000, env='RATE_LIMIT')
    request_timeout: int = Field(default=30, env='REQUEST_TIMEOUT')

    # Database Configuration
    database_path: str = Field(default='data/congressional_hearings.db', env='DATABASE_PATH')

    # Import Configuration
    target_congress: int = Field(default=119, env='TARGET_CONGRESS')
    batch_size: int = Field(default=50, env='BATCH_SIZE')
    validation_mode: bool = Field(default=False, env='VALIDATION_MODE')

    # Update Configuration
    update_window_days: int = Field(default=30, env='UPDATE_WINDOW_DAYS')
    update_schedule_hour: int = Field(default=2, env='UPDATE_SCHEDULE_HOUR')

    # Logging Configuration
    log_level: str = Field(default='INFO', env='LOG_LEVEL')
    log_file: str = Field(default='logs/import.log', env='LOG_FILE')

    class Config:
        env_file = '.env'
        env_file_encoding = 'utf-8'
        case_sensitive = False
        extra = 'ignore'

    def get_database_directory(self) -> str:
        """Get the directory containing the database file"""
        return os.path.dirname(self.database_path)

    def get_log_directory(self) -> str:
        """Get the directory containing log files"""
        return os.path.dirname(self.log_file)


def get_settings() -> Settings:
    """Get application settings instance"""
    return Settings()


# Global settings instance
settings = get_settings()