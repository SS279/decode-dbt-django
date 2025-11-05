#!/bin/bash

# Create dbt workspaces directory
mkdir -p /app/dbt_workspaces

# Run database migrations
python manage.py migrate --noinput

# Collect static files
python manage.py collectstatic --noinput

# Start Gunicorn server
gunicorn decode_data.wsgi:application --bind 0.0.0.0:$PORT --workers 4 --timeout 120