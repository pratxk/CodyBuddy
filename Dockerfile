FROM python:3.12-slim
WORKDIR /app
# psycopg2-binary needs libpq at runtime
RUN apt-get update && apt-get install -y --no-install-recommends libpq5 \
 && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY agent/ agent/
COPY api/ api/
COPY auth/ auth/
COPY db/ db/
RUN useradd --no-create-home --shell /bin/false appuser
USER appuser
EXPOSE 7860
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "7860"]
