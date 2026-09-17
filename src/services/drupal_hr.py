import base64
import json
import urllib.request
from typing import Dict, List, Tuple


DEFAULT_FIELD_MAP = {
    'email': 'attributes.mail',
    'display_name': 'attributes.display_name',
    'department': 'attributes.field_department',
    'manager_email': 'attributes.field_manager_email',
    'hr_id': 'attributes.drupal_internal__uid',
    'active': 'attributes.status'
}


class DrupalHrError(RuntimeError):
    pass


def _fetch_default(url: str, headers: Dict[str, str]) -> Tuple[int, str]:
    """Default fetch implementation using urllib.request with 30s timeout."""
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            return response.getcode(), response.read().decode('utf-8')
    except Exception as e:
        # Re-raise the exception to be handled by the caller
        raise DrupalHrError(f"HTTP request failed: {str(e)}")


class DrupalHrClient:
    def __init__(self, base_url: str, auth_mode: str, user: str, password: str, token: str, field_map: dict, filter_query: str, fetch=None):
        self.base_url = base_url.rstrip('/')
        self.auth_mode = auth_mode
        self.user = user
        self.password = password
        self.token = token
        self.field_map = {**DEFAULT_FIELD_MAP, **field_map}
        self.filter_query = filter_query
        self.fetch = fetch or _fetch_default

    def _get_headers(self) -> Dict[str, str]:
        """Build the headers for the request."""
        headers = {
            'Accept': 'application/vnd.api+json'
        }
        if self.auth_mode == 'basic':
            credentials = f"{self.user}:{self.password}"
            encoded_credentials = base64.b64encode(credentials.encode('utf-8')).decode('utf-8')
            headers['Authorization'] = f"Basic {encoded_credentials}"
        elif self.auth_mode == 'token':
            headers['Authorization'] = f"Bearer {self.token}"
        return headers

    def _get_field_value(self, item: dict, field_path: str):
        """Get a nested field value using dot notation."""
        keys = field_path.split('.')
        current = item
        try:
            for key in keys:
                current = current[key]
            return current
        except (KeyError, TypeError):
            return ''

    def fetch_employees(self) -> Tuple[List[Dict], int]:
        """Fetch all employees from the Drupal JSON:API."""
        url = f"{self.base_url}/jsonapi/user/user?page[limit]=50"
        if self.filter_query:
            url += f"&{self.filter_query}"

        headers = self._get_headers()
        all_records = []
        skipped = 0

        while url:
            status_code, body_text = self.fetch(url, headers)

            if status_code < 200 or status_code >= 300:
                raise DrupalHrError(f"HTTP {status_code}: {body_text[:200]}")

            try:
                data = json.loads(body_text)
            except json.JSONDecodeError:
                raise DrupalHrError("Invalid JSON response")

            # Process the data
            for item in data.get('data', []):
                record = {}
                for field_name, field_path in self.field_map.items():
                    value = self._get_field_value(item, field_path)
                    if field_name == 'email':
                        value = str(value).strip().lower()
                    elif field_name == 'active':
                        # Coerce to bool
                        if isinstance(value, str):
                            value = value.lower() in ('true', '1', 'yes')
                        elif isinstance(value, int):
                            value = bool(value)
                        else:
                            value = bool(value)
                    elif field_name in ('department', 'manager_email'):
                        # Default to empty string for these fields
                        value = str(value) if value is not None else ''
                    record[field_name] = value

                # Handle hr_id fallback to item's 'id'
                if not record.get('hr_id'):
                    record['hr_id'] = str(item.get('id', ''))
                else:
                    # Ensure hr_id is a string
                    record['hr_id'] = str(record['hr_id'])

                # Skip records without email
                if not record['email']:
                    skipped += 1
                    continue

                all_records.append(record)

            # Check for next page
            links = data.get('links', {})
            next_link = links.get('next', {}).get('href')
            url = next_link if next_link else None

        return all_records, skipped