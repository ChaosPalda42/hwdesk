FROM python:3.13-slim
RUN pip install --no-cache-dir uv && apt-get update && apt-get install -y --no-install-recommends fonts-dejavu-core && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev
COPY src ./src
COPY templates ./templates
COPY static ./static
ENV HWDESK_DATABASE=/data/hwdesk.db HWDESK_PROTOCOL_DIR=/data/protocols HWDESK_OUTBOX_DIR=/data/outbox
VOLUME ["/data"]
EXPOSE 8000
CMD ["uv", "run", "--no-dev", "gunicorn", "-b", "0.0.0.0:8000", "-w", "2", "src.app:create_app()"]
