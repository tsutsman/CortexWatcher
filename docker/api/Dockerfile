FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1
WORKDIR /app

COPY pyproject.toml README.md /app/
COPY src /app/src

RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir .

CMD ["uvicorn", "cortexwatcher.api.main:app", "--host", "0.0.0.0", "--port", "8080"]
