#!/bin/sh
set -e

echo "Creating test database if not exists..."

# Connect to postgres and create test database
psql -v ON_ERROR_STOP=0 --username "$POSTGRES_USER" --dbname "postgres" <<EOF
    CREATE DATABASE petmarket_test;
    GRANT ALL PRIVILEGES ON DATABASE petmarket_test TO $POSTGRES_USER;
EOF

echo "Test database created successfully."