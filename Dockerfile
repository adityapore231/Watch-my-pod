# --- Stage 1: Base with Python and Dependencies ---
# Use a slim and secure Python base image
FROM python:3.9-slim AS base

# Set the working directory
WORKDIR /app

# Install system dependencies that might be needed by Python packages
# (e.g., for compiling some libraries from source)
# We do this in a separate layer to improve caching.
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# --- Stage 2: Builder with Dependencies Installed ---
FROM base AS builder

# Copy the requirements file first to leverage Docker's layer caching
COPY service-agent/requirements.txt .

# Install the Python dependencies
# --no-cache-dir reduces image size
RUN pip install --no-cache-dir -r requirements.txt

# --- Stage 3: Final Image ---
FROM base AS final

# Create a non-root user to run the application
RUN addgroup -S appgroup && adduser -S appuser -G appgroup

# Copy the installed packages from the builder stage
COPY --from=builder /usr/local/lib/python3.9/site-packages /usr/local/lib/python3.9/site-packages

# Copy the application code
COPY service-agent/ /app/

# Ensure the app directory is owned by the non-root user
RUN chown -R appuser:appgroup /app

# Switch to the non-root user
USER appuser

# Expose the port the app runs on
EXPOSE 8000

# Define the command to run the application
# We point to the main:app object inside the service-agent directory
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
