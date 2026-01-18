"""Service for tracking processed files to avoid duplicates."""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class ProcessingTracker:
    """Tracks which files have been successfully processed.
    
    Uses a simple JSON file to persist the state.
    """

    def __init__(self, tracking_file: str = "processed_files.json"):
        """Initialize the tracker.
        
        Args:
            tracking_file: Path to the JSON file for tracking.
        """
        self.tracking_file = Path(tracking_file)
        self._data: dict = self._load()

    def _load(self) -> dict:
        """Load tracking data from file."""
        if self.tracking_file.exists():
            try:
                with open(self.tracking_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError) as e:
                logger.warning(f"Could not load tracking file: {e}")
                return {"processed": {}}
        return {"processed": {}}

    def _save(self) -> None:
        """Save tracking data to file."""
        with open(self.tracking_file, "w", encoding="utf-8") as f:
            json.dump(self._data, f, indent=2, ensure_ascii=False)

    def is_processed(self, file_id: str) -> bool:
        """Check if a file has been successfully processed.
        
        Args:
            file_id: Google Drive file ID.
            
        Returns:
            True if the file was processed successfully.
        """
        return file_id in self._data.get("processed", {})

    def mark_processed(
        self,
        file_id: str,
        filename: str,
        wordpress_url: Optional[str] = None,
        captivate_episode_id: Optional[str] = None,
        s3_url: Optional[str] = None,
    ) -> None:
        """Mark a file as successfully processed.
        
        Args:
            file_id: Google Drive file ID.
            filename: Original filename.
            wordpress_url: URL of the created WordPress post.
            captivate_episode_id: Captivate episode ID.
            s3_url: S3 video URL.
        """
        if "processed" not in self._data:
            self._data["processed"] = {}

        self._data["processed"][file_id] = {
            "filename": filename,
            "processed_at": datetime.now().isoformat(),
            "wordpress_url": wordpress_url,
            "captivate_episode_id": captivate_episode_id,
            "s3_url": s3_url,
        }
        self._save()
        logger.info(f"Marked as processed: {filename}")

    def get_unprocessed_files(self, all_files: list[dict]) -> list[dict]:
        """Filter out already processed files.
        
        Args:
            all_files: List of file dicts with 'id' and 'name' keys.
            
        Returns:
            List of files that haven't been processed yet.
        """
        unprocessed = []
        for file in all_files:
            if not self.is_processed(file["id"]):
                unprocessed.append(file)
            else:
                logger.debug(f"Skipping already processed: {file['name']}")
        return unprocessed

    def get_processed_count(self) -> int:
        """Get the number of processed files."""
        return len(self._data.get("processed", {}))

    def list_processed(self) -> list[dict]:
        """List all processed files with their metadata."""
        return [
            {"file_id": fid, **info}
            for fid, info in self._data.get("processed", {}).items()
        ]
