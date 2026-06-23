# Use a lightweight Python base image
FROM python:3.11-slim

# Set environment variables
# PYTHONUNBUFFERED=1 ensures that standard output/error streams are sent straight to terminal/client without buffering
# PYTHONDONTWRITEBYTECODE=1 prevents Python from writing .pyc files
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# Set the working directory in the container
WORKDIR /app

# Copy the requirements file first to leverage Docker cache
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the server application code
COPY server.py .

# Run the MCP server via standard input/output (stdio)
ENTRYPOINT ["python", "server.py"]
