# Use a lightweight Python base image
FROM python:3.11-slim

# Set environment variables
# - PYTHONUNBUFFERED=1 ensures logs/responses are sent immediately
# - PYTHONDONTWRITEBYTECODE=1 prevents python from writing .pyc files
# - MCP_TRANSPORT=sse configures server.py to default to SSE mode on ECS
# - PORT=8000 is the port the container will listen on
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    MCP_TRANSPORT=sse \
    PORT=8000

# Set the working directory inside the container
WORKDIR /app

# Copy the requirements file first to leverage Docker cache
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the server application code and AWS Config data
COPY server.py .
COPY all_aws_config_exports.json .

# Expose the port that the application listens on
EXPOSE 8000

# Run the MCP server
ENTRYPOINT ["python", "server.py"]
