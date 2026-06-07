FROM python:3.13-slim

WORKDIR /app

# Install dependencies (cached layer — only rebuilds when pyproject.toml changes)
COPY pyproject.toml ./
RUN mkdir -p app && touch app/__init__.py && \
    pip install --no-cache-dir . && \
    pip install --no-cache-dir alembic && \
    rm -rf app app.egg-info

# Copy application code
COPY . .

EXPOSE 8084

ENTRYPOINT ["bash", "docker-entrypoint.sh"]
