import json
import logging
import requests
from typing import Dict, Generator, Any

from configuration import Configuration

DEFAULT_PAGE_SIZE = 100
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

    def get_contact_list(self, page_size: int = DEFAULT_PAGE_SIZE) -> Generator[Dict[str, Any], None, None]:
        """
        Streams contact list (PIIs) using paginated endpoint.
        Yields each contact record as-is.
        """
        base_url = self._get_base_url("v1.1")
        start = 0

        while True:
            url = f"{base_url}/piis/{self.user_id}"
            params = {"start": start, "limit": page_size}
            logging.debug(f"Requesting contacts: start={start}, limit={page_size}")

            try:
                response = requests.get(url, headers=self.headers, params=params)
                response.raise_for_status()
                data = response.json()
            except Exception as e:
                logging.warning(f"Failed to fetch contacts at start={start}: {e}")
                break

            if not data.get("success", False):
                logging.warning(f"API response indicates failure at start={start}: {data}")
                break

            results = data.get("data", {}).get("results")

            if results is None:
                logging.info(f"No more contacts at start={start}. Ending pagination.")
                break

            if not isinstance(results, list):
                logging.warning(f"Unexpected contacts response structure at start={start}: {data}")
                break

            if not results:
                logging.info(f"Empty contacts page at start={start}. Ending pagination.")
                break

            for record in results:
                yield record

            start += page_size

    def get_contact_details_by_custom_ids(self, contact_ids: list[str]) -> Generator[Dict[str, Any], None, None]:
        """
        Fetches individual contact details by customer ID.
        """
        base_url = self._get_base_url("v1.1")
        for contact_id in contact_ids:
            url = f"{base_url}/piis/{self.user_id}/{contact_id}"
            logging.debug(f"Requesting contact detail for custom ID: {contact_id}")

            try:
                response = requests.get(url, headers=self.headers)
                response.raise_for_status()
                data = response.json()
            except Exception as e:
                logging.warning(f"Failed request for contact {contact_id}: {e}")
                continue

            if not data.get("success", False):
                logging.warning(f"API call failed for contact {contact_id}: {json.dumps(data, indent=2)}")
                continue

            result = data.get("data")
            if result:
                yield result

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

    def get_loyalty_points_for_contacts(
            self, contact_ids: list[str]
    ) -> Generator[Dict[str, Any], None, None]:
        """
        Streams full loyalty point records per contact.
        Preserves full JSON structure (including nested fields like 'events') as-is.
        """
        base_url = self._get_base_url("v1.1")
        start, end = self.config.sync_options.date_range_unix(self.state)

        for contact_id in contact_ids:
            url = f"{base_url}/contact/loyaltyPoints/timeline/{self.user_id}/{contact_id}"
            params = {"start": start, "end": end}
            logging.debug(f"Requesting loyalty timeline for contact: {contact_id}")

            try:
                response = requests.get(url, headers=self.headers, params=params)
                response.raise_for_status()
                data = response.json()
            except Exception as e:
                logging.warning(f"Failed request for contact {contact_id}: {e}")
                continue

            if not data.get("success", False):
                logging.warning(f"API call failed for contact {contact_id}: {json.dumps(data, indent=2)}")
                continue

            payload = data.get("data")
            if not isinstance(payload, dict):
                logging.warning(f"Unexpected 'data' structure for contact {contact_id}:\n{json.dumps(data, indent=2)}")
                continue

            yield payload

    def get_audiences(self, page_size: int = DEFAULT_PAGE_SIZE) -> Generator[Dict[str, Any], None, None]:
        """
        Streams audience records via pagination.
        Ends when 'data' is null or an empty list.
        """
        base_url = self._get_base_url("v1.1")
        start = 0

        while True:
            url = f"{base_url}/audiences/{self.user_id}"
            params = {"start": start, "limit": page_size}
            logging.debug(f"Requesting audiences: start={start}, limit={page_size}")

            try:
                response = requests.get(url, headers=self.headers, params=params)
                response.raise_for_status()
                data = response.json()
            except Exception as e:
                logging.warning(f"Failed request at start={start}: {e}")
                break

            if not data.get("success", False):
                logging.warning(f"API response indicates failure at start={start}: {data}")
                break

            records = data.get("data")

            if records is None:
                logging.info(f"No more audience data at start={start}. Ending pagination.")
                break

            if not isinstance(records, list):
                logging.warning(f"Unexpected audience response structure at start={start}: {data}")
                break

            if not records:
                logging.info(f"Empty audience page at start={start}. Ending pagination.")
                break

            for record in records:
                yield record

            start += page_size

    def get_brand_products(self, page_size: int = DEFAULT_PAGE_SIZE) -> Generator[Dict[str, Any], None, None]:
        """
        Streams brand product records from the /api/v2/brand/products endpoint using pagination.
        """
        base_url = self._get_base_url("v2")
        start = 0

        while True:
            url = f"{base_url}/brand/products"
            params = {"start": start, "limit": page_size}
            logging.debug(f"Requesting brand products: start={start}, limit={page_size}")

            try:
                response = requests.get(url, headers=self.headers, params=params)
                response.raise_for_status()
                data = response.json()
            except Exception as e:
                raise RuntimeError(f"Failed to fetch brand products: {e}")

            if not data.get("success", False):
                logging.warning(f"API call failed at start={start}: {json.dumps(data, indent=2)}")
                break

            results = data.get("data", {}).get("results")

            if results is None:
                logging.info("No more brand products returned. Ending pagination.")
                break

            if not isinstance(results, list):
                logging.error("Unexpected brand product response format:\n%s", json.dumps(data, indent=2))
                break

            for item in results:
                yield item

            start += page_size

    def get_discounts(self) -> Generator[Dict[str, Any], None, None]:
        """
        Fetches discount records for the given user from the v2 API.
        """
        base_url = self._get_base_url("v2")
        url = f"{base_url}/discount/{self.user_id}"
        logging.debug(f"Requesting: {url}")

        try:
            response = requests.get(url, headers=self.headers)
            response.raise_for_status()
            data = response.json()
        except Exception as e:
            raise RuntimeError(f"Failed to fetch discounts: {e}")

        if not data.get("success", False):
            raise RuntimeError(f"API call failed: {data}")

        items = data.get("data") or []

        if not isinstance(items, list):
            logging.error("Unexpected API structure:\n%s", json.dumps(data, indent=2))
            raise RuntimeError("API response 'data' field must be a list or null")

        for item in items:
            yield item

    def get_stores(self) -> Generator[Dict[str, Any], None, None]:
        """
        Fetches store records for the given user from the v1.1 API.
        """
        base_url = self._get_base_url("v1.1")
        url = f"{base_url}/stores/{self.user_id}"
        logging.debug(f"Requesting: {url}")

        try:
            response = requests.get(url, headers=self.headers)
            response.raise_for_status()
            data = response.json()
        except Exception as e:
            raise RuntimeError(f"Failed to fetch stores: {e}")

        if not data.get("success", False):
            raise RuntimeError(f"API call failed: {json.dumps(data, indent=2)}")

        stores_container = data.get("data") or {}
        items = stores_container.get("stores", [])

        if not isinstance(items, list):
            logging.error("Unexpected API structure:\n%s", json.dumps(data, indent=2))
            raise RuntimeError("API response 'data.stores' field must be a list")

        for item in items:
            yield item

    def get_campaigns(self) -> Generator[Dict[str, Any], None, None]:
        """
        Fetches campaign data from the v2 API.
        """
        base_url = self._get_base_url("v2")
        url = f"{base_url}/campaigns"
        logging.debug(f"Requesting: {url}")

        try:
            response = requests.get(url, headers=self.headers)
            response.raise_for_status()
            data = response.json()
        except Exception as e:
            raise RuntimeError(f"Failed to fetch campaigns: {e}")

        if not data.get("success", False):
            raise RuntimeError(f"API call failed: {data}")

        items = data.get("data") or []

        if not isinstance(items, list):
            logging.error("Unexpected 'data' format in campaigns response:\n%s", json.dumps(data, indent=2))
            raise RuntimeError("Campaigns API response 'data' must be a list or null")

        for item in items:
            yield item

    def get_campaign_stats_by_ids(self, campaign_ids: list[str]) -> Generator[Dict[str, Any], None, None]:
        """
        Fetches campaign stats by campaign ID.
        """
        base_url = self._get_base_url("v2")
        for campaign_id in campaign_ids:
            url = f"{base_url}/campaign/stats/{campaign_id}"
            logging.debug(f"Requesting campaign stats for ID: {campaign_id}")

            try:
                response = requests.get(url, headers=self.headers)
                response.raise_for_status()
                data = response.json()
            except Exception as e:
                logging.warning(f"Failed to fetch campaign stats for {campaign_id}: {e}")
                continue

            if not data.get("success", False):
                logging.warning(f"API call failed for campaign {campaign_id}: {json.dumps(data, indent=2)}")
                continue

            result = data.get("data")
            if result and isinstance(result, dict):
                result["id"] = campaign_id
                yield result
