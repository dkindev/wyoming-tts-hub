from collections.abc import Callable

from src.config import Settings
from src.tts.engine import TtsEngine
from src.tts.models import BackendType, ModelInfo
from src.tts.qwen_engine import QwenTtsEngine
from src.tts.silero_engine import SileroTtsEngine


class TtsEngineFactory:
    def __init__(self, settings: Settings):
        self._builders: dict[str, Callable[[ModelInfo], TtsEngine]] = {
            # key: "{engine_type}__{backend_type}"
            "silero__torch": lambda model_info: SileroTtsEngine(
                model_info=model_info,
                device=settings.torch.device,
                sample_rate=settings.silero.sample_rate,
                models_dir=settings.models_dir,
                models_yml_url=str(settings.silero.models_yml_url),
                models_yml_hash=settings.silero.models_yml_hash,
            ),
            "qwen3__torch": lambda model_info: QwenTtsEngine(
                model_info=model_info,
                device=settings.torch.device,
                models_dir=settings.models_dir,
            ),
        }

    def create(self, model_info: ModelInfo, backendType: BackendType) -> TtsEngine:
        if model_info is None:
            raise TypeError("model cannot be None")

        builder = self._builders.get(f"{model_info.engine_type.value}__{backendType.value}")

        if builder is None:
            raise ValueError(
                f"No TTS engine registered for family '{model_info.engine_type.value}' with backend '{backendType.value}'"
            )

        return builder(model_info)
