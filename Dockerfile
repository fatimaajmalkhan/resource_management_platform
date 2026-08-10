# Stage 1: Build the React frontend
FROM node:20-slim AS frontend-builder
WORKDIR /frontend
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# Stage 2: Set up the Python backend
FROM python:3.11-slim
WORKDIR /app

# Install system dependencies (needed for compilation and database drivers)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend files
COPY app/ ./app/
COPY data/ ./data/

# Copy the built React frontend from Stage 1
COPY --from=frontend-builder /frontend/dist ./frontend/dist

# Expose port and run uvicorn
EXPOSE 8000
ENV PORT=8000
ENV DISABLE_EXCEL_SYNC=true

CMD ["sh", "-c", "uvicorn app.server:app --host 0.0.0.0 --port $PORT"]
