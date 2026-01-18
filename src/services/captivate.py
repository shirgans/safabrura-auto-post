"""Captivate.fm service for uploading podcast episodes."""

from pathlib import Path
from typing import Optional

import requests

from src.config.settings import settings


class CaptivateService:
    """Service for interacting with Captivate.fm API."""

    BASE_URL = "https://api.captivate.fm"

    def __init__(
        self,
        user_id: str | None = None,
        api_token: str | None = None,
        show_id: str | None = None,
    ):
        """Initialize the Captivate service.

        Args:
            user_id: Captivate.fm User ID.
            api_token: Captivate.fm API token.
            show_id: Captivate.fm show ID.
        """
        self.user_id = user_id or settings.CAPTIVATE_API_USER_ID
        self.api_token = api_token or settings.CAPTIVATE_API_TOKEN
        self.show_id = show_id or settings.CAPTIVATE_SHOW_ID
        self._jwt_token: str | None = None

    def _authenticate(self) -> str:
        """Authenticate with Captivate API and get JWT token.

        Returns:
            JWT token for API requests.

        Raises:
            RuntimeError: If authentication fails.
        """
        if self._jwt_token:
            return self._jwt_token

        url = f"{self.BASE_URL}/authenticate/token"
        data = {
            "username": self.user_id,
            "token": self.api_token,
        }

        response = requests.post(url, json=data)

        if response.status_code != 200:
            raise RuntimeError(
                f"Failed to authenticate with Captivate: {response.status_code} - {response.text}"
            )

        result = response.json()
        self._jwt_token = result.get("user", {}).get("token")

        if not self._jwt_token:
            raise RuntimeError("No token received from Captivate authentication")

        return self._jwt_token

    @property
    def headers(self) -> dict:
        """Get the authorization headers."""
        token = self._authenticate()
        return {
            "Authorization": f"Bearer {token}",
        }

    def upload_episode(
        self,
        mp3_path: Path,
        title: str,
        description: str | None = None,
        publish: bool = False,
    ) -> dict:
        """Upload a new podcast episode.

        Args:
            mp3_path: Path to the MP3 file.
            title: Episode title.
            description: Episode description.
            publish: Whether to publish immediately (False = draft).

        Returns:
            Dict with episode_id, mp3_url, and embed_code.

        Raises:
            FileNotFoundError: If the MP3 file doesn't exist.
            RuntimeError: If the upload fails.
        """
        if not mp3_path.exists():
            raise FileNotFoundError(f"MP3 file not found: {mp3_path}")

        # Step 1: Upload the media file
        media_id = self._upload_media(mp3_path)

        # Step 2: Create the episode
        episode_data = self._create_episode(
            media_id=media_id,
            title=title,
            description=description or title,
            publish=publish,
        )

        return episode_data

    def _upload_media(self, mp3_path: Path) -> str:
        """Upload media file to Captivate.

        Args:
            mp3_path: Path to the MP3 file.

        Returns:
            The media ID.

        Raises:
            RuntimeError: If the upload fails.
        """
        url = f"{self.BASE_URL}/shows/{self.show_id}/media"

        with open(mp3_path, "rb") as f:
            files = {"file": (mp3_path.name, f, "audio/mpeg")}
            response = requests.post(
                url,
                headers=self.headers,
                files=files,
            )

        if response.status_code not in (200, 201):
            raise RuntimeError(
                f"Failed to upload media to Captivate: {response.status_code} - {response.text}"
            )

        data = response.json()
        return data.get("media", {}).get("id") or data.get("id")

    def _create_episode(
        self,
        media_id: str,
        title: str,
        description: str,
        publish: bool = False,
    ) -> dict:
        """Create a podcast episode.

        Args:
            media_id: The uploaded media ID.
            title: Episode title.
            description: Episode description.
            publish: Whether to publish immediately.

        Returns:
            Dict with episode_id, mp3_url, and embed_code.

        Raises:
            RuntimeError: If episode creation fails.
        """
        url = f"{self.BASE_URL}/episodes"

        payload = {
            "shows_id": self.show_id,
            "media_id": media_id,
            "title": title,
            "shownotes": description,
            "status": "Published" if publish else "Draft",
            "episode_type": "full",
        }

        response = requests.post(
            url,
            headers={**self.headers, "Content-Type": "application/json"},
            json=payload,
        )

        if response.status_code not in (200, 201):
            raise RuntimeError(
                f"Failed to create episode: {response.status_code} - {response.text}"
            )

        data = response.json()
        episode = data.get("episode", data)

        episode_id = episode.get("id")
        mp3_url = episode.get("media", {}).get("url") or episode.get("media_url", "")

        return {
            "episode_id": episode_id,
            "mp3_url": mp3_url,
            "embed_code": self.generate_embed_code(episode_id),
        }

    def generate_embed_code(self, episode_id: str) -> str:
        """Generate the embed code for an episode.

        Args:
            episode_id: The episode ID.

        Returns:
            HTML embed code for the episode player.
        """
        return (
            f'<iframe src="https://player.captivate.fm/episode/{episode_id}" '
            f'width="100%" height="170" frameborder="0" scrolling="no"></iframe>'
        )

    def get_episode(self, episode_id: str) -> dict:
        """Get episode details.

        Args:
            episode_id: The episode ID.

        Returns:
            Episode data dict.

        Raises:
            RuntimeError: If the request fails.
        """
        url = f"{self.BASE_URL}/episodes/{episode_id}"
        response = requests.get(url, headers=self.headers)

        if response.status_code != 200:
            raise RuntimeError(
                f"Failed to get episode: {response.status_code} - {response.text}"
            )

        return response.json()

    def check_api_access(self) -> bool:
        """Check if the API is accessible.

        Returns:
            True if API is accessible, False otherwise.
        """
        try:
            self._authenticate()
            url = f"{self.BASE_URL}/shows/{self.show_id}"
            response = requests.get(url, headers=self.headers)
            return response.status_code == 200
        except (requests.RequestException, RuntimeError):
            return False
