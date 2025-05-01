import json
import logging
import requests
from typing import Dict, Generator, Any

from configuration import Configuration

API_BASE_URL = "https://lab.alpineiq.com/api"

class APIClient:
    def __init__(self, config: Configuration, state: Dict[str, str]):
        self.config = config
        self.state = state
        self.api_key = self.config.authorization.api_key
        self.user_id = self.config.authorization.user_id
        self.headers = {"X-APIKEY": self.api_key}

    def _get_base_url(self, version: str) -> str:
        return f"{API_BASE_URL}/{version}"

    def get_contact_adjustments(self) -> Generator[Dict[str, Any], None, None]:
        base_url = self._get_base_url("v1.1")
        start, end = self.config.sync_options.date_range_unix(self.state)
        url = f"{base_url}/adjustments/{self.user_id}/{start}/{end}"
        logging.debug(f"Requesting: {url}")

        response = requests.get(url, headers=self.headers)
        response.raise_for_status()

        try:
            data = response.json()
        except Exception as e:
            raise RuntimeError(f"Failed to parse JSON: {response.text}") from e

        if not data.get("success", False):
            raise RuntimeError(f"API call failed: {json.dumps(data, indent=2)}")

        items = data.get("data") or []

        if not isinstance(items, list):
            logging.error("Unexpected API structure:\n%s", json.dumps(data, indent=2))
            raise RuntimeError("API response 'data' field must be a list or null")

        for item in items:
            yield item


