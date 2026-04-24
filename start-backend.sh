#!/bin/bash
# Start the TruthNuke backend server.
# The server runs in the background and survives terminal/IDE closure.
#
# Usage:
#   ./start-backend.sh          Start the backend
#   ./start-backend.sh stop     Stop the backend
#   ./start-backend.sh status   Check if it's running
#   ./start-backend.sh logs     Tail the log file

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
BACKEND_DIR="$SCRIPT_DIR/backend"
VENV_PYTHON="$SCRIPT_DIR/.venv/bin/python"
PIDFILE="$SCRIPT_DIR/.backend.pid"
LOGFILE="$SCRIPT_DIR/backend.log"

# Check for venv
if [ ! -f "$VENV_PYTHON" ]; then
  echo "❌ Python venv not found at .venv/"
  echo "   Run: python -m venv .venv && .venv/bin/pip install -r backend/requirements.txt"
  exit 1
fi

case "${1:-start}" in
  start)
    # Stop existing instance if running
    if [ -f "$PIDFILE" ]; then
      OLD_PID=$(cat "$PIDFILE")
      if kill -0 "$OLD_PID" 2>/dev/null; then
        echo "Stopping existing backend (PID $OLD_PID)..."
        kill "$OLD_PID" 2>/dev/null
        sleep 1
      fi
      rm -f "$PIDFILE"
    fi

    echo "Starting TruthNuke backend..."
    cd "$BACKEND_DIR"
    nohup "$VENV_PYTHON" -m uvicorn app.main:app --host 0.0.0.0 --port 8000 \
      > "$LOGFILE" 2>&1 &
    echo $! > "$PIDFILE"
    sleep 2

    if kill -0 "$(cat "$PIDFILE")" 2>/dev/null; then
      echo "✅ Backend running (PID $(cat "$PIDFILE"))"
      echo "   API: http://localhost:8000"
      echo "   Health: http://localhost:8000/health"
      echo "   Logs: $LOGFILE"
    else
      echo "❌ Backend failed to start. Check $LOGFILE"
      rm -f "$PIDFILE"
      exit 1
    fi
    ;;

  stop)
    if [ -f "$PIDFILE" ]; then
      PID=$(cat "$PIDFILE")
      if kill -0 "$PID" 2>/dev/null; then
        kill "$PID"
        echo "✅ Backend stopped (PID $PID)"
      else
        echo "Backend was not running (stale PID $PID)"
      fi
      rm -f "$PIDFILE"
    else
      echo "No PID file found. Backend may not be running."
    fi
    ;;

  status)
    if [ -f "$PIDFILE" ] && kill -0 "$(cat "$PIDFILE")" 2>/dev/null; then
      echo "✅ Backend is running (PID $(cat "$PIDFILE"))"
    else
      echo "❌ Backend is not running"
    fi
    ;;

  logs)
    if [ -f "$LOGFILE" ]; then
      tail -f "$LOGFILE"
    else
      echo "No log file found."
    fi
    ;;

  *)
    echo "Usage: $0 {start|stop|status|logs}"
    exit 1
    ;;
esac
