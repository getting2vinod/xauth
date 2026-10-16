FROM python:3.11-slim

# Copy the uv binary from Astral's official image
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

WORKDIR /workspace

# Enable bytecode compilation for faster python startup
ENV UV_COMPILE_BYTECODE=1

# Step 1: Copy only dependency definitions first (for optimal Docker layer caching)
COPY pyproject.toml uv.lock ./

# Step 2: Install dependencies from the lockfile into a virtual environment (.venv) without installing the project yet
RUN uv sync --frozen --no-dev --no-install-project

# Step 3: Copy the rest of your application source code
COPY . .

# Step 4: Complete the sync (registers your workspace package into the virtual environment)
RUN uv sync --frozen --no-dev

# Place the virtual environment's binaries at the front of PATH
ENV PATH="/workspace/.venv/bin:$PATH"
ENV PYTHONPATH=/workspace
ENV ROUTE_PATH=xauth

EXPOSE 4014

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "4014"]