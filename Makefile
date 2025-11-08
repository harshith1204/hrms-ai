# HRMS AI Development Makefile

.PHONY: help build up down test format lint clean

# Default target
help: ## Show this help message
	@echo "HRMS AI Development Commands:"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2}'

# Development
build: ## Build Docker image
	@echo "🏗️  Building Docker image..."
	docker-compose build

up: ## Start development server
	@echo "🚀 Starting development server..."
	docker-compose up -d
	@echo "📋 API available at:"
	@echo "  • API: http://localhost:8000"
	@echo "  • Health: http://localhost:8000/health"
	@echo "  • Docs: http://localhost:8000/docs"

down: ## Stop development server
	@echo "🛑 Stopping development server..."
	docker-compose down

test: ## Run tests
	@echo "🧪 Running tests..."
	docker-compose run --rm app pytest -v

format: ## Format code
	@echo "🎨 Formatting code..."
	docker-compose run --rm app black app.py profile_creator.py
	docker-compose run --rm app isort app.py profile_creator.py

lint: ## Lint code
	@echo "🔍 Linting code..."
	docker-compose run --rm app flake8 app.py profile_creator.py
	docker-compose run --rm app mypy app.py profile_creator.py

shell: ## Open shell in container
	docker-compose exec app bash

logs: ## Show logs
	docker-compose logs -f app

clean: ## Clean up Docker resources
	@echo "🧹 Cleaning up..."
	docker-compose down -v
	docker system prune -f
