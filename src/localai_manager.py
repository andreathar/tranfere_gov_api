import logging

import requests

from config.settings import LOCALAI_BASE_URL

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)


class LocalAIManager:
    def __init__(self, base_url: str = LOCALAI_BASE_URL):
        # Base url usually is http://localhost:8080/v1, we need http://localhost:8080
        self.base_url = base_url.replace("/v1", "").rstrip("/")

    def get_all_models(self) -> list[str]:
        """Retorna todos os modelos configurados no LocalAI."""
        try:
            resp = requests.get(f"{self.base_url}/v1/models", timeout=5)
            if resp.status_code == 200:
                data = resp.json()
                return [m["id"] for m in data.get("data", [])]
        except Exception as e:
            log.warning(f"Erro ao buscar modelos no LocalAI: {e}")
        return []

    def is_model_loaded(self, model_id: str) -> bool:
        """Verifica se um modelo está atualmente na memória."""
        try:
            resp = requests.get(
                f"{self.base_url}/backend/monitor", params={"model": model_id}, timeout=3
            )
            # Se a resposta contiver 'is not currently loaded' ou 'error', não está carregado.
            if resp.status_code == 200:
                return True
            if resp.status_code == 500 and "is not currently loaded" in resp.text:
                return False
            if resp.status_code == 500 and "no grpc backend found" in resp.text:
                return False
        except requests.Timeout:
            return True
        except Exception:
            return False
        return False

    def unload_model(self, model_id: str) -> bool:
        """Força o descarregamento (shutdown) do backend de um modelo."""
        try:
            log.info(f"Descarregando modelo da memória: {model_id} ...")
            resp = requests.post(
                f"{self.base_url}/backend/shutdown", json={"model": model_id}, timeout=10
            )
            if resp.status_code in (200, 204) or resp.text.strip() == "":
                log.info(f"Modelo {model_id} descarregado com sucesso.")
                return True
            else:
                log.warning(f"Falha ao descarregar {model_id}: {resp.text}")
        except Exception as e:
            log.warning(f"Exceção ao descarregar {model_id}: {e}")
        return False

    def ensure_model_loaded(self, target_model: str):
        """Garante que apenas o target_model esteja na memória (exclusividade)."""
        log.info(f"Garantindo que o modelo {target_model} tenha recursos exclusivos...")
        all_models = self.get_all_models()

        for m in all_models:
            if m == target_model:
                continue
            if self.is_model_loaded(m):
                self.unload_model(m)

        log.info(f"O ambiente está limpo e pronto para invocar {target_model}.")


manager = LocalAIManager()
