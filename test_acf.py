"""Test ACF field creation on WordPress via meta."""
import os
import requests
from requests.auth import HTTPBasicAuth
from dotenv import load_dotenv

load_dotenv()

# WordPress config
base_url = os.getenv("WORDPRESS_URL", "").rstrip("/")
username = os.getenv("WORDPRESS_USERNAME")
password = os.getenv("WORDPRESS_APP_PASSWORD")

api_url = f"{base_url}/wp-json/wp/v2"
auth = HTTPBasicAuth(username, password)
headers = {"User-Agent": "SafaBrura-Automation/1.0"}

print("=" * 60)
print("TEST: Creating post with meta fields (after PHP update)")
print("=" * 60)

# Create test post with meta fields
payload = {
    "title": "TEST - Meta Fields After PHP Update",
    "content": "Testing meta fields",
    "status": "draft",
    "meta": {
        "hebrew_date": "כ\"ב שבט",
        "gregorian_date": "22.01.26",
        "captivate_episode_player_url": "https://player.captivate.fm/episode/test-123",
        "captivate_episode_mp3_url": "https://episodes.captivate.fm/episode/test.mp3",
        "audio_file": "https://episodes.captivate.fm/episode/test.mp3",
    }
}

print(f"Sending meta fields: {list(payload['meta'].keys())}")

response = requests.post(f"{api_url}/posts", json=payload, auth=auth, headers=headers)
print(f"Status: {response.status_code}")

if response.status_code in (200, 201):
    data = response.json()
    post_id = data["id"]
    print(f"Post ID: {post_id}")
    print()
    print("Meta fields in response:")
    meta = data.get("meta", {})
    for key in ["hebrew_date", "gregorian_date", "captivate_episode_player_url", "captivate_episode_mp3_url", "audio_file"]:
        value = meta.get(key, "NOT FOUND")
        print(f"  {key}: {value}")
    
    # Also fetch the post to double-check
    print()
    print("Fetching post to verify...")
    get_resp = requests.get(f"{api_url}/posts/{post_id}?context=edit", auth=auth, headers=headers)
    if get_resp.status_code == 200:
        get_data = get_resp.json()
        get_meta = get_data.get("meta", {})
        print("Meta after fetch:")
        for key in ["hebrew_date", "gregorian_date", "captivate_episode_player_url", "captivate_episode_mp3_url", "audio_file"]:
            value = get_meta.get(key, "NOT FOUND")
            print(f"  {key}: {value}")
else:
    print(f"Error: {response.text}")
