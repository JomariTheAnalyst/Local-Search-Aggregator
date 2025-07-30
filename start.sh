#!/bin/bash

echo "Starting AI Search Assistant..."

echo "Starting backend server..."
cd backend
python run.py &
BACKEND_PID=$!

echo "Waiting for backend to initialize..."
sleep 5

echo "Starting frontend server..."
cd ../frontend
npm start &
FRONTEND_PID=$!

echo ""
echo "AI Search Assistant is starting!"
echo "Backend: http://localhost:8000"
echo "Frontend: http://localhost:3000"
echo ""
echo "Press Ctrl+C to stop all servers"

# Wait for user to press Ctrl+C
trap "kill $BACKEND_PID $FRONTEND_PID; exit" INT
wait 