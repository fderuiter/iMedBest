#!/bin/sh
# Exit immediately if a command exits with a non-zero status
set -e

# Derive DATABASE_HOST from DATABASE_URL if not explicitly set
if [ -z "$DATABASE_HOST" ] && [ -n "$DATABASE_URL" ]; then
    # Extract host from postgres://user:pass@host:port/db
    DATABASE_HOST=$(echo "$DATABASE_URL" | sed -E 's|.*@([^:/]+)[:/].*|\1|')
    DATABASE_PORT=$(echo "$DATABASE_URL" | sed -E 's|.*:([0-9]+)/.*|\1|')
    DATABASE_USER=$(echo "$DATABASE_URL" | sed -E 's|[^/]*//([^:]+):.*|\1|')
fi

# Wait for PostgreSQL to become available
if [ -n "$DATABASE_HOST" ]; then
    echo "Waiting for database at $DATABASE_HOST:${DATABASE_PORT:-5432}..."
    until pg_isready -h "$DATABASE_HOST" -p "${DATABASE_PORT:-5432}" -U "${DATABASE_USER:-postgres}"; do
        echo "Database is unavailable - sleeping"
        sleep 1
    done
    echo "Database is up and running!"
fi

# Run migrations if enabled (defaults to running unless RUN_MIGRATIONS=false)
if [ "$RUN_MIGRATIONS" != "false" ]; then
    echo "Running Django database migrations..."
    python src/manage.py migrate --noinput
fi

# Collect static files if in production and not explicitly disabled
if [ "$DJANGO_SETTINGS_MODULE" = "config.settings.prod" ] && [ "$COLLECT_STATIC" != "false" ]; then
    echo "Collecting Django static files..."
    python src/manage.py collectstatic --noinput
fi

# Execute the main container command (replaces the shell process with the application)
echo "Starting application with command: $@"
exec "$@"
