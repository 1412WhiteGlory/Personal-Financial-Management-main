@echo off
echo ============================================================
echo  Personal Financial Management - Start All Services
echo ============================================================
echo.

echo [1/3] Starting MongoDB...
echo   (Make sure MongoDB is installed and mongod is running)
echo.

echo [2/3] Starting Backend (port 8000)...
start "Backend" cmd /k "cd /d %~dp0..\backend && npm run dev"
timeout /t 5 /nobreak >nul

echo [3/3] Starting Frontend (port 5173)...
start "Frontend" cmd /k "cd /d %~dp0..\frontend\financial-management && npm run dev"
timeout /t 5 /nobreak >nul

echo.
echo ============================================================
echo  All services started!
echo  Backend:  http://localhost:8000
echo  Frontend: http://localhost:5173
echo ============================================================
echo.
echo  Now you can run the tests:
echo    cd selenium_tests
echo    python run_all_tests.py
echo.
pause
