@echo off
echo Starting ShieldDocs...
call .\.venv\Scripts\activate.bat
python app.py
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo The program crashed!
    pause
) else (
    pause
)
