@echo off
:: ===========================================
:: ROOTSKEEPERS - DEMARRAGE SERVEUR LOCAL
:: ===========================================

echo.
echo ========================================
echo    ROOTSKEEPERS - Serveur de Reperage
echo ========================================
echo.

:: Aller dans le bon dossier
cd /d "D:\Downloads\HTML Multilingues\reperage-production"

echo [1/3] Verification du dossier...
if not exist "app.py" (
    echo ERREUR: Fichier app.py introuvable !
    echo Verifiez que vous etes dans le bon dossier.
    pause
    exit /b
)
echo OK - Fichier app.py trouve

echo.
echo [2/3] Verification Python...
python --version
if errorlevel 1 (
    echo ERREUR: Python n'est pas installe ou pas dans le PATH !
    pause
    exit /b
)
echo OK - Python detecte

echo.
echo [3/3] Demarrage du serveur...
echo.
echo ========================================
echo  SERVEUR DEMARRE !
echo  URL: http://127.0.0.1:5000
echo  
echo  Admin: http://127.0.0.1:5000/admin
echo  
echo  Pour ARRETER: Appuyez sur Ctrl+C
echo ========================================
echo.

:: Lancer le serveur
python app.py

pause
