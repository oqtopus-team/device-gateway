ARG PYTHON_VERSION=3.12
FROM python:$PYTHON_VERSION-slim
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/
WORKDIR /app
# install tools
RUN apt-get update && apt-get install -y --no-install-recommends \
  build-essential \
  cmake \
  git \
  bison \
  flex \
  libboost-all-dev \
  && apt-get clean && rm -rf /var/lib/apt/lists/*
# copy application files
COPY . /app
# setup user and permissions
RUN adduser --disabled-password --gecos "" appuser && chown -R appuser:appuser /app
USER appuser
# install python dependencies
RUN uv sync --no-dev
# run application
CMD ["uv", "run", "python", "src/device_gateway/service.py", "-c", "config/config.yaml", "-l", "config/logging.yaml"]
