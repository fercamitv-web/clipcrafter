@echo off
:: --- Pasta do repositório ---
cd /d "%~dp0"

:: --- Python do venv ---
set VENV=clipcrafter\venv
set PYTHON=%VENV%\Scripts\python.exe
set SCRIPT=clipcrafter\daily_review.py

:: --- Executa o script de revisão ---
echo.
echo Iniciando revisão diária...
%PYTHON% %SCRIPT%
set ERRLEVEL=%errorlevel%

:: --- Se der erro, mostra mensagem e pausa ---
if %ERRLEVEL% neq 0 (
    echo.
    echo ⚠️  ERRO detectado (código %ERRLEVEL%).
    echo O script encontrou um problema na revisão.
    echo Verifique o relatório acima ou o log da Actions (GitHub).
    echo.
    pause "Pressione ENTER para fechar esta janela e analisar o erro."
)

echo.
echo Revisão concluída com código %ERRLEVEL%.
exit /b %ERRLEVEL%