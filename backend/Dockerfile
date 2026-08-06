FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml .
COPY relayflow ./relayflow
COPY render-start.sh ./render-start.sh

RUN pip install --no-cache-dir . \
    && chmod +x /app/render-start.sh

CMD ["sh", "/app/render-start.sh"]