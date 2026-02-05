import requests

class APIClient:
    def __init__(self, base_url, timeout=40):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def get(self, endpoint):
        if endpoint.startswith("http"):
            url = endpoint
        else:
            url = f"{self.base_url}{endpoint}"

        resp = requests.get(url, timeout=self.timeout)
        resp.raise_for_status()
        return resp.json()
