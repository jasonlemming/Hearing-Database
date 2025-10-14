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
    api_key: Optional[str] = Field(default=None, env='API_KEY')
    api_base_url: str = Field(default='https://api.congress.gov/v3', env='API_BASE_URL')
    rate_limit: int = Field(default=5000, env='RATE_LIMIT')
    request_timeout: int = Field(default=30, env='REQUEST_TIMEOUT')

    # Error Handling & Retry Configuration
    retry_attempts: int = Field(default=5, env='RETRY_ATTEMPTS')
    retry_backoff_factor: float = Field(default=2.0, env='RETRY_BACKOFF_FACTOR')
    circuit_breaker_enabled: bool = Field(default=True, env='CIRCUIT_BREAKER_ENABLED')
    circuit_breaker_threshold: int = Field(default=5, env='CIRCUIT_BREAKER_THRESHOLD')
    circuit_breaker_timeout: int = Field(default=60, env='CIRCUIT_BREAKER_TIMEOUT')

    # Database Configuration
    database_path: str = Field(default='database.db', env='DATABASE_PATH')

    def __init__(self, **kwargs):
        """Initialize settings with Vercel-specific configuration"""
        super().__init__(**kwargs)
        # For Vercel deployment, database.db is already in the working directory
        # No need to override the path

    # Import Configuration
    target_congress: int = Field(default=119, env='TARGET_CONGRESS')
    batch_size: int = Field(default=50, env='BATCH_SIZE')
    validation_mode: bool = Field(default=False, env='VALIDATION_MODE')

    # Batch Processing Configuration (Phase 2.3.1)
    enable_batch_processing: bool = Field(default=False, env='ENABLE_BATCH_PROCESSING')
    batch_processing_size: int = Field(default=50, env='BATCH_PROCESSING_SIZE')

    # Update Configuration
    update_window_days: int = Field(default=30, env='UPDATE_WINDOW_DAYS')
    update_schedule_hour: int = Field(default=2, env='UPDATE_SCHEDULE_HOUR')

    # Logging Configuration
    log_level: str = Field(default='INFO', env='LOG_LEVEL')
    log_file: str = Field(default='logs/import.log', env='LOG_FILE')

    # Notification Configuration
    notification_enabled: bool = Field(default=False, env='NOTIFICATION_ENABLED')
    notification_type: str = Field(default='log', env='NOTIFICATION_TYPE')  # log, email, webhook
    notification_webhook_url: Optional[str] = Field(default=None, env='NOTIFICATION_WEBHOOK_URL')
    notification_email: Optional[str] = Field(default=None, env='NOTIFICATION_EMAIL')
    sendgrid_api_key: Optional[str] = Field(default=None, env='SENDGRID_API_KEY')

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