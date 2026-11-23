@echo off
echo Starting ShieldDocs Executable...
.\obfuscated_src\dist\ShieldDocs\ShieldDocs.exe
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo The executable crashed!
    pause
) else (
    pause
)
