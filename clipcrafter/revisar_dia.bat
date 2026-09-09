@echo off
:: Revisao diaria automatica (auto-fix quando possivel)
cd /d "C:\Users\ferca\OneDrive\Documentos\1"
set VENV=C:\Users\ferca\OneDrive\Documentos\clipe-pro\venv\Scripts\python.exe
if not exist "%VENV%" set VENV=python
echo.
echo Iniciando revisao diaria (ops_daily)...
"%VENV%" clipcrafter\ops_daily.py
set ERRLEVEL=%errorlevel%
if %ERRLEVEL% neq 0 (
    echo.
    echo ============================================
    echo  ERRO detectado (codigo %ERRLEVEL%).
    echo  O sistema tentou auto-consertar fila/queue.
    echo  Se for token, rode: python %%TEMP%%\opencode\reauth.py
    echo  e me chame para atualizar o secret YT_TOKEN_PICKLE.
    echo  Log salvo em %%USERPROFILE%%\.clipcrafter\logs\
    echo ============================================
    pause
) else (
    echo.
    echo Revisao concluida sem erros. Janela fecha em 5s...
    timeout /t 5 >nul
)
exit /b %ERRLEVEL%
