FROM mcr.microsoft.com/playwright/python:v1.56.0-noble

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8000 \
    DISPLAY=:99 \
    ACQUISITION_BROWSER_MODE=headed

WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
RUN chmod +x /app/scripts/container-entrypoint.sh

EXPOSE 8000
ENTRYPOINT ["/app/scripts/container-entrypoint.sh"]
CMD ["bash", "-lc", "exec python -m uvicorn backend.api:app --host 0.0.0.0 --port ${PORT} --workers 1"]
