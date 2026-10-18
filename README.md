# Wyoming TTS Hub

A [Wyoming protocol](https://github.com/OHF-Voice/wyoming) server built around a
TTS Engine Hub: it aggregates TTS Engines and routes each synthesis request to
the engine that owns the requested Model Info. Supports Home Assistant
integration, streaming audio, and optional per-voice LLM normalization.

The Silero TTS Engine is the one implemented today.

## Quick Start

### Local Development

1. **Clone the repository**
   ```bash
   git clone https://github.com/dkindev/wyoming-tts-hub.git
   cd wyoming-tts-hub
   ```

2. **Create a virtual environment**
   ```bash
   python -m venv .venv
   source .venv/bin/activate
   ```

3. **Install dependencies**
   ```bash
   uv sync --extra dev
   ```

4. **Run the application**
   ```bash
   wyoming-tts-hub
   ```

   The server listens on `tcp://127.0.0.1:10200` by default.

   The command can be run from anywhere. The configuration it reads is found relative
   to where you run it, though — `data/data.yml` and `models/` both resolve against
   the working directory — so from somewhere else, point it at a configuration file:

   ```bash
   wyoming-tts-hub --config /path/to/config.yml
   ```

### Docker

1. **Build the image**
   ```bash
   docker build -t wyoming-tts-hub:latest .
   ```

2. **Run the container**
   ```bash
   docker run -p 10200:10200 \
     -v ./data:/app/data \
     -v ./models:/app/models \
     wyoming-tts-hub:latest
   ```

   The server exposes port `10200` for Wyoming TCP connections.

### Connecting a client

Point any Wyoming client at the server's URI. To try one out, run a test HTTP
server in front of it:

```bash
uv run --with "wyoming[http]" python -m wyoming.http.tts_server --uri tcp://127.0.0.1:10200
```

What a client sees when it connects:

- **Voices** are named `<model id>-<voice name>`, so the Model Info `v5_5_ru`
  speaking as `aidar` is offered as `v5_5_ru-aidar`.
- **Languages** come from the Model Info, not the Voice. Every Voice of a Model
  Info is advertised with that Model Info's declared Languages.
- **Only Active Model Infos are offered** — a Model Info that is disabled, or
  that is not listed in `active_models`, contributes no Voices at all.
- **Discovery** is advertised over zeroconf as `wyoming-tts-hub`. Set `zeroconf`
  to an empty string to turn it off.
- **Errors** reach the client in full when `env_type` is `development`, and as a
  bare "Internal Server Error" when it is `production`. Run in `development` while
  you are setting things up.

## Configuration

Configuration is resolved with the following priority (highest first):

1. **CLI arguments** — `--uri`, `--torch_device`, `--frame_duration`, etc. The `silero`
   and `normalization` sections are environment-only.
2. **Environment variables** — `TTS_URI`, `TTS_TORCH__DEVICE`, `TTS_SILERO__SAMPLE_RATE`, etc.
3. **config.yml** — YAML file at the project root
4. **Defaults** — Default values in code

See `config.yml` for full configuration reference with all fields, CLI argument names, and environment variable names.

## Voice and Model Configuration

Voice and model mappings are defined in `data/data.yml`. The file has two top-level sections: `models` and `prompts`.

### Models

```yaml
models:
  v5_5_ru:
    engine_type: silero
    languages: [ru]
    ssml_supported: true
    warmup: true
    voices:
      - name: aidar
      - name: eugene
      - name: baya
      - name: kseniya
      - name: xenia
  v3_en:
    engine_type: silero
    languages: [en]
    ssml_supported: true
    voices:
      - name: henry
        speaker: en_2
      - name: sophia
        speaker: en_3
```

Each key under `models:` (e.g. `v5_5_ru`) is the model's id, and names a **Model Info**. Supported fields:

| Field | Required | Default | Description |
|-------|----------|---------|-------------|
| `engine_type` | Yes | — | Which TTS Engine family builds it: `silero`, `qwen`, `openai` |
| `languages` | Yes | — | Non-empty list of language codes it can speak, e.g. `[ru]`. A request carrying any other language is refused |
| `ssml_supported` | No | `false` | `true` when it accepts SSML. An SSML request against `false` is refused |
| `language_auto_detected` | No | `false` | `true` when it may be asked to synthesize without a language |
| `enabled` | No | `true` | `false` to drop the model and its voices |
| `warmup` | No | `false` | `true` to preload at startup, up to `max_models` of them; otherwise loaded on the first request for it |
| `hash_prefix` | No | — | SHA-256 prefix checked against the downloaded model files |
| `voices` | No | none | The voices this model speaks with |

A model is served only when it is both `enabled` **and** listed in `active_models` in
`config.yml`. Neither switch implies the other.

#### Engine families

`engine_type` names the TTS Engine family that builds the model. Those families
are declared up front, but only one is implemented behind them: a `silero` model
on the `torch` backend is the only combination that builds an engine. A model
written as `qwen` or `openai` is read and served like any other, and then fails
when its engine would be built — at startup for a model marked `warmup`,
otherwise on the first request for it — with an error naming the family and the
backend.

#### Adding a new model

1. Add an entry under `models:` in `data/data.yml` with its `engine_type` and a
   non-empty `languages` list.
2. Add its `voices` under that entry.
3. Add the model's id to `active_models` in `config.yml`, or it will not be served.

#### Disabling a model

Set `enabled: false` on the model entry. Its voices are automatically excluded from discovery.

### Voices

Each voice entry has the following fields:

| Field | Required | Default | Description |
|-------|----------|---------|-------------|
| `name` | Yes | — | Voice name, and the second half of the voice id |
| `speaker` | No | the voice name | The speaker profile the TTS Engine selects within the model |
| `ref_audio` | No | — | Reference audio for cloning-style engines. Read, but not yet consumed by any engine |
| `ref_text` | No | — | Reference text for cloning-style engines. Read, but not yet consumed by any engine |
| `instruct` | No | — | Instruction text for cloning-style engines. Read, but not yet consumed by any engine |

A voice is identified by its computed ID: `<model id>-<voice name>` (e.g. `v5_5_ru-aidar`).

#### Adding or renaming voices

Add or edit entries under `models.<model id>.voices` in `data/data.yml`. Set `speaker` to the engine's native speaker name only if it differs from the voice name.

#### Voice normalization

Per-voice override of the server-wide normalization settings (defined in `config.yml`), keyed
by language and then by text format. Override the normalization type, disable it entirely, or
reference a custom LLM prompt.

```yaml
models:
  v5_5_ru:
    engine_type: silero
    languages: [ru]
    voices:
      - name: aidar
        normalization:
          ru:
            text:
              enabled: true
              type: openai
              prompt_id: ru_text

prompts:
  - id: ru_text
    text: "Normalize Russian text for TTS..."
    model: qwen3.5:4b
```

Each override is per voice, per text format, per language:

| Field | Required | Default | Description |
|-------|----------|---------|-------------|
| `normalization.<language>.text.enabled` | No | `true` | Override whether normalization runs for that language and text format |
| `normalization.<language>.text.type` | No | `simple` | Normalizer for plain text: `simple`, `openai` |
| `normalization.<language>.text.prompt_id` | No | — | Prompt from `prompts` to use for LLM-based normalization |
| `normalization.<language>.ssml.enabled` | No | `true` | Override whether normalization runs for that language and text format |
| `normalization.<language>.ssml.type` | No | `simple` | Normalizer for SSML: `simple`, `openai` |
| `normalization.<language>.ssml.prompt_id` | No | — | Prompt from `prompts` to use for LLM-based normalization |

Without a `normalization` block on a voice, the server-wide defaults from `config.yml` apply.

### Prompts

Reusable LLM prompt definitions referenced by `prompt_id` in voice normalization.

| Field | Required | Default | Description |
|-------|----------|---------|-------------|
| `id` | Yes | — | Unique identifier referenced by `prompt_id` |
| `text` | Yes | — | LLM prompt instruction text |
| `model` | Yes | — | LLM model name (e.g., `qwen3.5:4b`) |

## Audio

### Supported Input Types

- `TEXT` — plain text
- `SSML` — Speech Synthesis Markup Language

### Audio Output

- Format: raw PCM (WAV-compatible)
- Sample rate: announced per model, not configured per client. `silero.sample_rate`
  is the rate you ask for; the server emits the nearest rate that model supports
  (8000, 16000, 24000 or 48000 Hz) and tells the client that rate
- Bit depth: 16-bit signed integer
- Channels: mono (1 channel)

## Development

### Running Tests

```bash
pytest tests/
```

### Linting and Formatting

```bash
ruff check src tests
ruff format src tests
```

### Pre-commit Hooks

```bash
pre-commit install
```

## CI/CD

The project uses GitHub Actions for continuous integration. On every push:

1. **Lint**: Ruff checks code quality across Python 3.11, 3.12, 3.13, and 3.14
2. **Test**: pytest runs all tests across the same Python versions

See `.github/workflows/ci.yml` for details.

## License

MIT License — see LICENSE file for details.
