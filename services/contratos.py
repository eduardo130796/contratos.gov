from services.api_client import APIClient

class ContratosService:
    def __init__(self, client: APIClient):
        self.client = client

    def listar_por_ug(self, ug: str):
        return self.client.get(f"/contrato/ug/{ug}")

    def obter_link(self, url: str):
        return self.client.get(url)
