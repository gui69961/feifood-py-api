"""Cliente HTTP que conversa com o Catalog Service (comunicação entre microsserviços)."""
import os

import httpx


class CatalogUnavailable(Exception):
    """O Catalog Service está fora do ar ou demorou demais para responder."""


class CatalogClient:
    def __init__(self, base_url: str | None = None, transport: httpx.BaseTransport | None = None):
        self.base_url = base_url or os.getenv("CATALOG_URL", "http://localhost:8001")
        self.transport = transport  # permite trocar a rede real por uma falsa nos testes

    def get_product(self, product_id: int) -> dict | None:
        """Busca um produto no catálogo. Retorna None se ele não existir."""
        try:
            with httpx.Client(base_url=self.base_url, timeout=3.0, transport=self.transport) as http:
                response = http.get(f"/products/{product_id}")
        except httpx.RequestError as error:
            raise CatalogUnavailable(str(error)) from error

        if response.status_code == 404:
            return None
        if response.status_code != 200:
            raise CatalogUnavailable(f"Resposta inesperada do catálogo: {response.status_code}")
        return response.json()


def get_catalog_client() -> CatalogClient:
    return CatalogClient()
