# ── Base image ────────────────────────────────────────────────────────
FROM python:3.10-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source
COPY . .

# $PORT is injected by Render at runtime
# monitor.py reads $PORT for its health HTTP server (default 10000)
# app.py receives $PORT from Render's startCommand override
EXPOSE 10000

# Default CMD runs the monitor; the dashboard service overrides this
# via render.yaml startCommand / Docker Command field.
CMD ["python", "monitor.py"]
