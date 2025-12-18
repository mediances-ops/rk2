@echo off
:: ===========================================
:: ROOTSKEEPERS - OUVRIR APPLICATION
:: ===========================================

echo.
echo ========================================
echo    ROOTSKEEPERS - Ouverture navigateur
echo ========================================
echo.

echo Ouverture de l'application...
echo.

:: Ouvrir l'admin dans le navigateur par défaut
start http://127.0.0.1:5000/admin

echo.
echo Application ouverte dans votre navigateur !
echo.
echo URLS disponibles:
echo  - Admin: http://127.0.0.1:5000/admin
echo  - Fixer test: http://127.0.0.1:5000/fixer/test-abc123
echo.

timeout /t 3
