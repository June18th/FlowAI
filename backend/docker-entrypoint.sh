#!/bin/bash
set -e

echo "Waiting for MySQL at $FLOWAGENT_MYSQL_HOST:$FLOWAGENT_MYSQL_PORT..."
python -c "
import socket, time, os
host = os.environ['FLOWAGENT_MYSQL_HOST']
port = int(os.environ.get('FLOWAGENT_MYSQL_PORT', 3306))
for i in range(30):
    try:
        s = socket.create_connection((host, port), timeout=2)
        s.close()
        print('MySQL is ready!')
        break
    except OSError:
        print(f'Waiting... ({i+1}/30)')
        time.sleep(2)
else:
    raise SystemExit('ERROR: MySQL not available after 60s')
"

echo "Running database migrations..."
cd /app && python -m alembic upgrade head || {
    echo "Migration failed (tables may already exist), stamping current head..."
    python -m alembic stamp head
}

echo "Starting FlowAI backend on port ${FLOWAGENT_SERVER_PORT:-8084}..."
exec uvicorn main:app --host 0.0.0.0 --port ${FLOWAGENT_SERVER_PORT:-8084}
