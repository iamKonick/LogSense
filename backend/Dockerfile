FROM python:3.14-slim
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
COPY requirements.lock .
RUN apt-get update && apt-get install -y --no-install-recommends libgomp1 && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir -r requirements.lock
COPY app ./app
COPY tests ./tests
RUN useradd --create-home logsense
USER logsense
CMD ["uvicorn", "app.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
