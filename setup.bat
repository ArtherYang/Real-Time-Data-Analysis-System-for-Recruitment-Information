@echo off
chcp 65001 >nul
echo ============================================
echo   职言 — 一键启动
echo ============================================
echo.

:: Check Node.js
where node >nul 2>&1
if %errorlevel% neq 0 (
    echo [错误] 未找到 Node.js，请先安装：
    echo   https://nodejs.org/zh-cn/download/
    echo   下载 LTS 版本并安装，完成后重新运行本脚本
    pause
    exit /b 1
)
echo [OK] Node.js: %node_version%

:: Check npm
where npm >nul 2>&1
if %errorlevel% neq 0 (
    echo [错误] npm 未找到
    pause
    exit /b 1
)

:: Install frontend dependencies
echo.
echo [1/3] 安装前端依赖...
cd /d "%~dp0frontend"
call npm install
if %errorlevel% neq 0 (
    echo [错误] npm install 失败
    pause
    exit /b 1
)
echo [OK] 前端依赖安装完成

:: Start backend
echo.
echo [2/3] 启动后端...
cd /d "%~dp0backend"
start "RDAS-Backend" cmd /c "python run_dev.py"
echo [OK] 后端启动中... (http://localhost:5000)

:: Wait for backend
timeout /t 3 /nobreak >nul

:: Start frontend
echo.
echo [3/3] 启动前端...
cd /d "%~dp0frontend"
start "RDAS-Frontend" cmd /c "npm run dev"
echo [OK] 前端启动中... (http://localhost:5173)

echo.
echo ============================================
echo   启动完成！
echo   浏览器打开: http://localhost:5173
echo   测试账号:   test@rdas.com
echo   测试密码:   Test1234
echo   角色:       管理员
echo ============================================
echo.
echo 按任意键退出...
pause >nul
