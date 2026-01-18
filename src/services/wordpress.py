"""WordPress service for creating draft posts."""

from typing import Optional

import requests
from requests.auth import HTTPBasicAuth

from src.config.settings import settings
from src.models.lecture import Lecture


class WordPressService:
    """Service for interacting with WordPress REST API."""

    def __init__(
        self,
        url: str | None = None,
        username: str | None = None,
        app_password: str | None = None,
    ):
        """Initialize the WordPress service.

        Args:
            url: WordPress site URL.
            username: WordPress username.
            app_password: WordPress application password.
        """
        self.base_url = (url or settings.WORDPRESS_URL).rstrip("/")
        self.username = username or settings.WORDPRESS_USERNAME
        self.app_password = app_password or settings.WORDPRESS_APP_PASSWORD

    @property
    def api_url(self) -> str:
        """Get the WordPress REST API base URL."""
        return f"{self.base_url}/wp-json/wp/v2"

    @property
    def auth(self) -> HTTPBasicAuth:
        """Get the authentication object."""
        return HTTPBasicAuth(self.username, self.app_password)

    @property
    def headers(self) -> dict:
        """Get headers for requests (needed to bypass Cloudflare)."""
        return {
            "User-Agent": "SafaBrura-Automation/1.0",
        }

    def create_draft_post(
        self,
        title: str,
        content: str,
        categories: list[int] | None = None,
        tags: list[int] | None = None,
        status: str = "publish",
        meta: dict | None = None,
    ) -> dict:
        """Create a post in WordPress.

        Args:
            title: Post title.
            content: Post content (HTML).
            categories: List of category IDs.
            tags: List of tag IDs.
            status: Post status - "publish", "draft", "pending", "private".
            meta: Custom fields as dict (requires ACF or similar plugin).

        Returns:
            Dict with post_id and post_url.

        Raises:
            RuntimeError: If post creation fails.
        """
        url = f"{self.api_url}/posts"

        payload = {
            "title": title,
            "content": content,
            "status": status,
        }

        if categories:
            payload["categories"] = categories
        if tags:
            payload["tags"] = tags
        if meta:
            payload["meta"] = meta

        response = requests.post(url, json=payload, auth=self.auth, headers=self.headers)

        if response.status_code not in (200, 201):
            raise RuntimeError(
                f"Failed to create WordPress post: {response.status_code} - {response.text}"
            )

        data = response.json()
        return {
            "post_id": data["id"],
            "post_url": data["link"],
            "edit_url": f"{self.base_url}/wp-admin/post.php?post={data['id']}&action=edit",
        }

    def create_lecture_post(
        self,
        lecture: Lecture,
    ) -> dict:
        """Create a draft post for a lecture.

        Args:
            lecture: The Lecture object with all media URLs.

        Returns:
            Dict with post_id and post_url.
        """
        content = self._build_lecture_content(lecture)
        title = f"{lecture.title} - {lecture.formatted_date}"

        return self.create_draft_post(title=title, content=content)

    def _build_lecture_content(self, lecture: Lecture) -> str:
        """Build the HTML content for a lecture post.

        Args:
            lecture: The Lecture object with media URLs.

        Returns:
            HTML content string.
        """
        sections = []

        # Video section
        if lecture.s3_url:
            poster_attr = f' poster="{settings.VIDEO_POSTER_URL}"' if settings.VIDEO_POSTER_URL else ''
            sections.append(
                f"<h2>צפייה בהרצאה</h2>\n"
                f'<video controls width="100%" preload="metadata"{poster_attr}>\n'
                f'  <source src="{lecture.s3_url}" type="video/mp4">\n'
                f"  הדפדפן שלך לא תומך בתגית וידאו.\n"
                f"</video>"
            )

        # Podcast player section
        if lecture.captivate_embed_code:
            sections.append(
                f"<h2>האזנה לפודקאסט</h2>\n"
                f"{lecture.captivate_embed_code}"
            )

        # Download section
        if lecture.captivate_mp3_url:
            sections.append(
                f"<h2>הורדת MP3</h2>\n"
                f'<p><a href="{lecture.captivate_mp3_url}" download>לחץ כאן להורדת ההרצאה כקובץ MP3</a></p>'
            )

        return "\n\n".join(sections)

    def update_post(
        self,
        post_id: int,
        title: str | None = None,
        content: str | None = None,
        status: str | None = None,
    ) -> dict:
        """Update an existing post.

        Args:
            post_id: The post ID to update.
            title: New title (optional).
            content: New content (optional).
            status: New status (optional): draft, publish, pending, private.

        Returns:
            Updated post data.

        Raises:
            RuntimeError: If update fails.
        """
        url = f"{self.api_url}/posts/{post_id}"

        payload = {}
        if title:
            payload["title"] = title
        if content:
            payload["content"] = content
        if status:
            payload["status"] = status

        response = requests.post(url, json=payload, auth=self.auth, headers=self.headers)

        if response.status_code != 200:
            raise RuntimeError(
                f"Failed to update WordPress post: {response.status_code} - {response.text}"
            )

        return response.json()

    def check_api_access(self) -> bool:
        """Check if the WordPress API is accessible.

        Returns:
            True if accessible, False otherwise.
        """
        url = f"{self.api_url}/posts?per_page=1"
        try:
            response = requests.get(url, auth=self.auth, headers=self.headers)
            return response.status_code == 200
        except requests.RequestException:
            return False

    def get_categories(self) -> list[dict]:
        """Get all categories from WordPress.

        Returns:
            List of category dicts with 'id' and 'name'.
        """
        url = f"{self.api_url}/categories?per_page=100"
        try:
            response = requests.get(url, auth=self.auth, headers=self.headers)
            if response.status_code == 200:
                return [{"id": cat["id"], "name": cat["name"]} for cat in response.json()]
        except requests.RequestException:
            pass
        return []

    def find_category_by_name(self, name: str) -> Optional[int]:
        """Find a category ID by name.

        Args:
            name: The category name to search for.

        Returns:
            Category ID if found, None otherwise.
        """
        categories = self.get_categories()
        for cat in categories:
            if cat["name"] == name:
                return cat["id"]
        return None
