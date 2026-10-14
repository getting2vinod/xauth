# Stage 1: Build dependencies
FROM python:3.11-slim AS builder

# Copy uv binary from the official Astral image
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

WORKDIR /app

# Enable bytecode compilation and copy configuration
ENV UV_COMPILE_BYTECODE=1
COPY pyproject.toml ./

# Create a virtual environment and install project dependencies
RUN uv venv /app/.venv
ENV VIRTUAL_ENV=/app/.venv
ENV PATH="/app/.venv/bin:$PATH"

RUN uv pip install --no-cache .

# Stage 2: Lightweight runtime image
FROM python:3.11-slim

WORKDIR /app

# Copy the prebuilt virtual environment from the builder stage
COPY --from=builder /app/.venv /app/.venv
ENV PATH="/app/.venv/bin:$PATH"

# Copy the application code
COPY . .

EXPOSE 4014

# Run the FastAPI application using uvicorn
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "4014"]