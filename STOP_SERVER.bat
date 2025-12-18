@echo off
:: ===========================================
:: ROOTSKEEPERS - ARRET SERVEUR LOCAL
:: ===========================================

echo.
echo ========================================
echo    ROOTSKEEPERS - Arret du serveur
echo ========================================
echo.

echo Recherche du processus Python...

:: Tuer tous les processus Python (Flask)
taskkill /F /IM python.exe /T >nul 2>&1

if errorlevel 1 (
    echo Aucun serveur Python en cours d'execution.
) else (
    echo Serveur arrete avec succes !
)

echo.
pause
