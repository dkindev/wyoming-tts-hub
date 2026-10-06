from collections.abc import Callable

from src.config import Settings
from src.tts.engine import TtsEngine
from src.tts.models import BackendType, Model
from src.tts.silero_engine import SileroTtsEngine


class TtsEngineFactory:
    def __init__(self, settings: Settings):
        self._builders: dict[str, Callable[[Model], TtsEngine]] = {
            # key: "{engine_type}__{backend_type}"
            "silero__torch": lambda model: SileroTtsEngine(
                model=model,
                device=settings.torch.device,
                sample_rate=settings.silero.sample_rate,
                models_dir=settings.models_dir,
                models_yml_url=str(settings.silero.models_yml_url),
                models_yml_hash=settings.silero.models_yml_hash,
            ),
        }

    def create(self, model: Model, backendType: BackendType) -> TtsEngine:
        if model is None:
            raise TypeError("model cannot be None")

        builder = self._builders.get(f"{model.engine_type.value}__{backendType.value}")

        if builder is None:
            raise ValueError(
                f"No TTS engine registered for family '{model.engine_type.value}' with backend '{backendType.value}'"
            )

        return builder(model)
