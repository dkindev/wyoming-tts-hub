FROM mcr.microsoft.com/devcontainers/python:3.14-bookworm

RUN set -ex; \
    apt-get update; \
    apt-get install -y --no-install-recommends \
        ffmpeg \
        sox \
        libsox-fmt-all \
    ; \
    rm -rf /var/lib/apt/lists/*