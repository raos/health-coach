#!/bin/bash
# Stop all Health Coach App processes

echo "Stopping Health Coach App..."

# Kill by port
lsof -ti:8000 | xargs kill -9 2>/dev/null && echo "✓ Backend stopped (port 8000)" || echo "  Backend was not running"
lsof -ti:5173 | xargs kill -9 2>/dev/null && echo "✓ Frontend stopped (port 5173)" || echo "  Frontend was not running"

# Also kill by process name (backup)
pkill -f "uvicorn main:app" 2>/dev/null
pkill -f "vite" 2>/dev/null

echo "Done."
