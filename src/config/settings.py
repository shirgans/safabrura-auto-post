"""Configuration settings loaded from environment variables."""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


class Settings:
    """Application settings from environment variables."""

    # Google Drive
    GOOGLE_DRIVE_FOLDER_ID: str = os.getenv("GOOGLE_DRIVE_FOLDER_ID", "")
    GOOGLE_SERVICE_ACCOUNT_FILE: str = os.getenv("GOOGLE_SERVICE_ACCOUNT_FILE", "")

    # AWS S3
    AWS_ACCESS_KEY_ID: str = os.getenv("AWS_ACCESS_KEY_ID", "")
    AWS_SECRET_ACCESS_KEY: str = os.getenv("AWS_SECRET_ACCESS_KEY", "")
    AWS_S3_BUCKET: str = os.getenv("AWS_S3_BUCKET", "")
    AWS_S3_REGION: str = os.getenv("AWS_S3_REGION", "us-east-1")

    # WordPress
    WORDPRESS_URL: str = os.getenv("WORDPRESS_URL", "")
    WORDPRESS_USERNAME: str = os.getenv("WORDPRESS_USERNAME", "")
    WORDPRESS_APP_PASSWORD: str = os.getenv("WORDPRESS_APP_PASSWORD", "")

    # Captivate.fm
    CAPTIVATE_API_USER_ID: str = os.getenv("CAPTIVATE_API_USER_ID", "")
    CAPTIVATE_API_TOKEN: str = os.getenv("CAPTIVATE_API_TOKEN", "")
    CAPTIVATE_SHOW_ID: str = os.getenv("CAPTIVATE_SHOW_ID", "")

    # Local paths
    TEMP_DOWNLOAD_PATH: Path = Path(os.getenv("TEMP_DOWNLOAD_PATH", "./temp"))
    FFMPEG_PATH: str = os.getenv("FFMPEG_PATH", "ffmpeg")

    # Audio trimming (seconds to skip from beginning of recording)
    AUDIO_TRIM_START: int = int(os.getenv("AUDIO_TRIM_START", "0"))

    # Video poster image URL
    VIDEO_POSTER_URL: str = os.getenv("VIDEO_POSTER_URL", "")

    @classmethod
    def validate(cls) -> list[str]:
        """Validate that required settings are present.

        Returns:
            List of missing required settings.
        """
        missing = []
        required = [
            ("GOOGLE_DRIVE_FOLDER_ID", cls.GOOGLE_DRIVE_FOLDER_ID),
            ("GOOGLE_SERVICE_ACCOUNT_FILE", cls.GOOGLE_SERVICE_ACCOUNT_FILE),
            ("AWS_ACCESS_KEY_ID", cls.AWS_ACCESS_KEY_ID),
            ("AWS_SECRET_ACCESS_KEY", cls.AWS_SECRET_ACCESS_KEY),
            ("AWS_S3_BUCKET", cls.AWS_S3_BUCKET),
            ("WORDPRESS_URL", cls.WORDPRESS_URL),
            ("WORDPRESS_USERNAME", cls.WORDPRESS_USERNAME),
            ("WORDPRESS_APP_PASSWORD", cls.WORDPRESS_APP_PASSWORD),
            ("CAPTIVATE_API_TOKEN", cls.CAPTIVATE_API_TOKEN),
            ("CAPTIVATE_SHOW_ID", cls.CAPTIVATE_SHOW_ID),
        ]
        for name, value in required:
            if not value:
                missing.append(name)
        return missing

    @classmethod
    def ensure_temp_dir(cls) -> Path:
        """Ensure the temp download directory exists."""
        cls.TEMP_DOWNLOAD_PATH.mkdir(parents=True, exist_ok=True)
        return cls.TEMP_DOWNLOAD_PATH


settings = Settings()
