# Makefile for HumaNai Infrastructure and Services

.PHONY: up down status logs reset-db seed test lint shell

# Start all Docker services
up:
	docker-compose up -d --build

# Stop all Docker services
down:
	docker-compose down

# Check container status
status:
	docker-compose ps

# Show logs from containers
logs:
	docker-compose logs -f

# Reset the database volume and restart
reset-db:
	docker-compose down -v
	docker-compose up -d postgres

# Seed the postgres database with mock data
seed:
	docker-compose exec -T postgres psql -U postgres -d humanai -f /docker-entrypoint-initdb.d/03_seed.sql

# Run unit and integration tests on the host/backend directory
test:
	cd ../humanai_backend && python -m pytest

# Run lint checks on backend
lint:
	cd ../humanai_backend && flake8 .
