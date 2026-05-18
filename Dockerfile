FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

WORKDIR /opt/app

COPY pyproject.toml uv.lock README.md ./
COPY core/ ./core/
COPY servers/ ./servers/
COPY app.py ./

RUN uv sync --frozen --no-cache

CMD ["uv", "run", "uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
