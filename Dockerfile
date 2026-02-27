# Use the official Python image
FROM python:3.10-slim

# Set working directory
WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code
COPY . .

# Expose Streamlit port
EXPOSE 8501

# Command to run (This gets overridden by docker-compose)
CMD ["python", "monitor.py"]
