@echo off
REM Hermes Gemini bridge — auto-start at logon (Cockpit-auth GCA backend)
cd /d C:\Users\admindev\gemini-hermes
C:\Users\admindev\AppData\Local\hermes\hermes-agent\venv\Scripts\python.exe -m uvicorn gemini_cli_bridge:app --host 127.0.0.1 --port 8787
