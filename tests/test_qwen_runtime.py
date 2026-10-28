import importlib

import torch
import torchaudio.compliance.kaldi as kaldi
from transformers import BertConfig, BertModel


def test_the_qwen_tts_runtime_is_importable():
    qwen_tts = importlib.import_module("qwen_tts")

    assert hasattr(qwen_tts, "Qwen3TTSModel")


def test_the_qwen_tts_runtime_can_use_the_installed_audio_engine():
    features = kaldi.fbank(torch.zeros(1, 16000), num_mel_bins=8)

    assert features.shape[1] == 8


def test_the_pinned_transformers_release_runs_on_this_torch():
    config = BertConfig(
        hidden_size=8,
        num_hidden_layers=1,
        num_attention_heads=2,
        intermediate_size=16,
        vocab_size=32,
    )
    model = BertModel(config)

    output = model(torch.zeros(1, 4, dtype=torch.long))

    assert output.last_hidden_state.shape == (1, 4, 8)
