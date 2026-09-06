FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    tesseract-ocr \
    && rm -rf /var/lib/apt/lists/*

COPY ai_rfp_excel/requirements.txt .
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --default-timeout=300 --retries=5 -r requirements.txt

COPY . .
ENV PYTHONPATH="/app"


EXPOSE 8000

CMD ["uvicorn", "ai_rfp_excel.app.main:app", "--host", "0.0.0.0", "--port", "8000"]
