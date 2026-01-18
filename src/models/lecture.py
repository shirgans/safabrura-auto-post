"""Data models for lecture metadata."""

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional


@dataclass
class Lecture:
    """Represents a lecture with its metadata and processing state."""

    # Source info
    drive_file_id: str
    filename: str
    title: str
    lecture_date: Optional[datetime] = None

    # Local paths
    video_path: Optional[Path] = None
    mp3_path: Optional[Path] = None

    # Upload results
    s3_url: Optional[str] = None
    s3_embed_code: Optional[str] = None

    # Captivate results
    captivate_episode_id: Optional[str] = None
    captivate_mp3_url: Optional[str] = None
    captivate_embed_code: Optional[str] = None

    # WordPress results
    wordpress_post_id: Optional[int] = None
    wordpress_post_url: Optional[str] = None

    # Processing state
    processed: bool = False
    errors: list[str] = field(default_factory=list)

    @classmethod
    def from_drive_file(cls, file_id: str, filename: str) -> "Lecture":
        """Create a Lecture from a Google Drive file.

        Parses the filename to extract title and date.
        Expected format: "Meet שידור מבית הרבנית - 2026/01/17 21:07 IST – Recording"
        """
        import re
        
        title = filename
        lecture_date = None

        # Try to parse date from Google Meet filename format
        # Pattern: YYYY/MM/DD HH:MM
        date_pattern = r'(\d{4})/(\d{2})/(\d{2})\s+(\d{2}):(\d{2})'
        match = re.search(date_pattern, filename)
        
        if match:
            try:
                year, month, day, hour, minute = match.groups()
                lecture_date = datetime(
                    int(year), int(month), int(day),
                    int(hour), int(minute)
                )
            except ValueError:
                pass
        
        # Extract the meeting name (before the date)
        # Remove RTL markers and clean up
        name_without_ext = Path(filename).stem
        
        # Try to extract just the meeting name part
        # Format: "Meet מפגש - 2026/01/17 21:07 IST – Recording"
        parts = re.split(r'\s*[-–]\s*\d{4}/', name_without_ext)
        if parts:
            title = parts[0].strip()
            # Remove "Meet " prefix
            for prefix in ["Meet ", "‏Meet ", "Meet‏ ", "‏Meet‏ "]:
                if title.startswith(prefix):
                    title = title[len(prefix):]
                    break
        else:
            title = name_without_ext

        return cls(
            drive_file_id=file_id,
            filename=filename,
            title=title.strip(),
            lecture_date=lecture_date,
        )

    def add_error(self, error: str) -> None:
        """Add an error message to the lecture."""
        self.errors.append(error)

    @property
    def has_errors(self) -> bool:
        """Check if the lecture has any errors."""
        return len(self.errors) > 0

    @property
    def formatted_date(self) -> str:
        """Get the lecture date as a formatted string."""
        if self.lecture_date:
            return self.lecture_date.strftime("%Y-%m-%d")
        return "Unknown Date"
