FROM ghcr.io/astral-sh/uv:python3.14-bookworm-slim AS builder

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

WORKDIR /app

COPY pyproject.toml uv.lock* ./

RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-install-project --no-dev

COPY src/ ./src
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev

FROM python:3.14-slim-bookworm

WORKDIR /app

ARG UID=1000
ARG GID=1000

RUN set -eux; \
    groupadd -r --gid $GID silero; \
    useradd -r --gid silero --uid $UID --home-dir /app --shell /bin/bash silero

RUN set -eux; \
    apt-get update; \
	apt-get install -y --no-install-recommends \
        # grab gosu for easy step-down from root
        gosu \
    ; \
	rm -rf /var/lib/apt/lists/*; \
    # verify that the gosu binary works
	gosu nobody true

COPY --from=builder /app/.venv /app/.venv
COPY data/ ./data
COPY config.yml .
COPY src/ ./src

RUN chown -R silero:silero .

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1

EXPOSE 10200

COPY --chmod=555 docker-entrypoint.sh /usr/local/bin
ENTRYPOINT ["docker-entrypoint.sh"]

CMD ["silero-server"]