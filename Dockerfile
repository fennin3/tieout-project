FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

COPY pyproject.toml manage.py ./
COPY config ./config
COPY recon ./recon
RUN pip install -e ".[dev]"

RUN useradd --create-home --uid 1000 app
USER app

CMD ["python", "manage.py", "check"]
