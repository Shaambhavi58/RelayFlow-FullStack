#!/bin/sh
set -eu

echo "Starting RelayFlow worker-1..."
RELAYFLOW_WORKER_ID=worker-1 python -m relayflow.worker &
WORKER_1_PID=$!

echo "Starting RelayFlow worker-2..."
RELAYFLOW_WORKER_ID=worker-2 python -m relayflow.worker &
WORKER_2_PID=$!

echo "Starting RelayFlow API..."
exec uvicorn relayflow.main:app \
  --host 0.0.0.0 \
  --port "${PORT:-8000}"