# ==========================================
# STAGE 1a: Builder for Development Virtualenv
# ==========================================
FROM python:3.12-slim-bookworm AS dev-builder

WORKDIR /app

# Install system dependencies needed for compiling python libraries
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Install uv using the official installer binary
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Copy dependency configuration files
COPY pyproject.toml uv.lock ./

# Compile development and main dependencies into the /venv directory using cache mounts
RUN --mount=type=cache,target=/root/.cache/uv \
    UV_PROJECT_ENVIRONMENT=/venv uv sync --frozen --no-install-project


# ==========================================
# STAGE 1b: Builder for Production Virtualenv
# ==========================================
FROM python:3.12-slim-bookworm AS prod-builder

WORKDIR /app

# Install system dependencies needed for compiling python libraries
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Install uv using the official installer binary
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Copy dependency configuration files
COPY pyproject.toml uv.lock ./

# Compile production-only dependencies into the /venv directory using cache mounts
RUN --mount=type=cache,target=/root/.cache/uv \
    UV_PROJECT_ENVIRONMENT=/venv uv sync --frozen --no-dev --no-install-project


# ==========================================
# STAGE 2: Development Runtime Image
# ==========================================
FROM python:3.12-slim-bookworm AS development

WORKDIR /app

# Install runtime system dependencies (libpq5, postgresql-client, and git for local development tools)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    postgresql-client \
    git \
    && rm -rf /var/lib/apt/lists/*

# Copy the development virtual environment
COPY --from=dev-builder /venv /venv

# Update system PATH so commands run out of our virtualenv by default
ENV PATH="/venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    DJANGO_SETTINGS_MODULE=config.settings.local

# Copy project source code
COPY src/ /app/src/
COPY docker/entrypoint.sh /app/docker/entrypoint.sh
RUN chmod +x /app/docker/entrypoint.sh

EXPOSE 8000

ENTRYPOINT ["/app/docker/entrypoint.sh"]
CMD ["python", "src/manage.py", "runserver", "0.0.0.0:8000"]


# ==========================================
# STAGE 3: Production Runtime Image
# ==========================================
FROM python:3.12-slim-bookworm AS production

WORKDIR /app

# Install lightweight runtime system dependencies (Postgres client library)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Copy the production virtual environment
COPY --from=prod-builder /venv /venv

# Update system PATH so commands run out of our virtualenv by default
ENV PATH="/venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    DJANGO_SETTINGS_MODULE=config.settings.prod

# Copy project source code
COPY src/ /app/src/

# Set up unprivileged user
RUN useradd -u 1000 -m django-user && \
    chown -R django-user:django-user /app

# Copy and configure entrypoint script
COPY docker/entrypoint.sh /app/docker/entrypoint.sh
RUN chmod +x /app/docker/entrypoint.sh && \
    chown django-user:django-user /app/docker/entrypoint.sh

USER django-user

EXPOSE 8000

ENTRYPOINT ["/app/docker/entrypoint.sh"]
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "config.wsgi:application"]
