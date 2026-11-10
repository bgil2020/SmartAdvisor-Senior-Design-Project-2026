FROM node:22-alpine AS frontend-build

WORKDIR /frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM mcr.microsoft.com/playwright/python:v1.56.0-noble

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8000 \
    DISPLAY=:99 \
    SMARTADVISOR_SERVE_FRONTEND=true \
    ACQUISITION_BROWSER_MODE=headed

WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
COPY --from=frontend-build /frontend/dist /app/frontend/dist
RUN chmod +x /app/scripts/container-entrypoint.sh

EXPOSE 8000
ENTRYPOINT ["/app/scripts/container-entrypoint.sh"]
CMD ["bash", "-lc", "exec python -m uvicorn backend.api:app --host 0.0.0.0 --port ${PORT} --workers 1"]
