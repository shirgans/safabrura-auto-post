"""Google Drive service for watching and downloading files."""

import io
from pathlib import Path
from typing import Generator

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload

from src.config.settings import settings
from src.models.lecture import Lecture


class GoogleDriveService:
    """Service for interacting with Google Drive."""

    SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]
    VIDEO_MIME_TYPES = [
        "video/mp4",
        "video/webm",
        "video/x-matroska",
        "video/quicktime",
    ]

    def __init__(
        self,
        folder_id: str | None = None,
        service_account_file: str | None = None,
    ):
        """Initialize the Google Drive service.

        Args:
            folder_id: Google Drive folder ID to watch.
            service_account_file: Path to service account JSON file.
        """
        self.folder_id = folder_id or settings.GOOGLE_DRIVE_FOLDER_ID
        self.service_account_file = (
            service_account_file or settings.GOOGLE_SERVICE_ACCOUNT_FILE
        )
        self._service = None

    @property
    def service(self):
        """Get or create the Google Drive API service."""
        if self._service is None:
            credentials = service_account.Credentials.from_service_account_file(
                self.service_account_file,
                scopes=self.SCOPES,
            )
            self._service = build("drive", "v3", credentials=credentials)
        return self._service

    def list_video_files(
        self,
        processed_ids: set[str] | None = None,
    ) -> list[dict]:
        """List video files in the watched folder.

        Args:
            processed_ids: Set of file IDs that have already been processed.

        Returns:
            List of file metadata dicts with 'id' and 'name' keys.
        """
        processed_ids = processed_ids or set()

        # Build query for video files in the folder
        mime_query = " or ".join(
            f"mimeType='{mime}'" for mime in self.VIDEO_MIME_TYPES
        )
        query = f"'{self.folder_id}' in parents and ({mime_query}) and trashed=false"

        results = (
            self.service.files()
            .list(
                q=query,
                fields="files(id, name, createdTime, size, mimeType, videoMediaMetadata)",
                orderBy="createdTime desc",
            )
            .execute()
        )

        files = results.get("files", [])

        # Filter out already processed files
        return [f for f in files if f["id"] not in processed_ids]

    def get_new_lectures(
        self,
        processed_ids: set[str] | None = None,
    ) -> list[Lecture]:
        """Get new lectures from the watched folder.

        Args:
            processed_ids: Set of file IDs that have already been processed.

        Returns:
            List of Lecture objects for new files.
        """
        files = self.list_video_files(processed_ids)
        return [
            Lecture.from_drive_file(file["id"], file["name"])
            for file in files
        ]

    def get_file_stream(self, file_id: str) -> Generator[bytes, None, None]:
        """Get a streaming download of a file from Google Drive.

        Args:
            file_id: The Google Drive file ID.

        Yields:
            Chunks of file data.
        """
        request = self.service.files().get_media(fileId=file_id)
        buffer = io.BytesIO()
        downloader = MediaIoBaseDownload(buffer, request, chunksize=10 * 1024 * 1024)  # 10MB chunks

        done = False
        while not done:
            status, done = downloader.next_chunk()
            buffer.seek(0)
            yield buffer.read()
            buffer.seek(0)
            buffer.truncate()

    def stream_to_s3(self, file_id: str, s3_client, bucket: str, s3_key: str) -> str:
        """Stream a file directly from Google Drive to S3.

        Args:
            file_id: The Google Drive file ID.
            s3_client: Boto3 S3 client.
            bucket: S3 bucket name.
            s3_key: S3 object key.

        Returns:
            The S3 key where the file was uploaded.
        """
        request = self.service.files().get_media(fileId=file_id)
        buffer = io.BytesIO()
        downloader = MediaIoBaseDownload(buffer, request)

        # Download entire file to memory buffer (streaming to S3 requires seekable file)
        done = False
        while not done:
            status, done = downloader.next_chunk()

        buffer.seek(0)

        # Upload to S3
        s3_client.upload_fileobj(buffer, bucket, s3_key)

        return s3_key

    def download_file(
        self,
        file_id: str,
        destination: Path,
    ) -> Path:
        """Download a file from Google Drive to local disk.

        Args:
            file_id: The Google Drive file ID.
            destination: Path where the file should be saved.

        Returns:
            Path to the downloaded file.

        Raises:
            RuntimeError: If the download fails.
        """
        # Ensure destination directory exists
        destination.parent.mkdir(parents=True, exist_ok=True)

        request = self.service.files().get_media(fileId=file_id)

        with open(destination, "wb") as f:
            downloader = MediaIoBaseDownload(f, request)
            done = False
            while not done:
                status, done = downloader.next_chunk()

        if not destination.exists():
            raise RuntimeError(f"Failed to download file: {file_id}")

        return destination

    def download_lecture(
        self,
        lecture: Lecture,
        download_dir: Path | None = None,
    ) -> Path:
        """Download a lecture video to the temp directory.

        Args:
            lecture: The Lecture object to download.
            download_dir: Directory to download to. Uses settings if not provided.

        Returns:
            Path to the downloaded video file.
        """
        download_dir = download_dir or settings.ensure_temp_dir()
        destination = download_dir / lecture.filename

        return self.download_file(lecture.drive_file_id, destination)
