FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1
WORKDIR /app

COPY pyproject.toml README.md /app/
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir .

COPY src /app/src

CMD ["uvicorn", "cortexwatcher.api.main:app", "--host", "0.0.0.0", "--port", "8080"]
