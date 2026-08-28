@echo off
REM Her sabah siparis hattini ucdan uca dener (odeme adimina kadar).
REM Gercek siparis verilmez; bkz. tools\siparis_nobeti.py aciklamasi.
cd /d "C:\Users\serdar\Desktop\atolye-temiz"
set PYTHONIOENCODING=utf-8
echo ---------- %DATE% %TIME% ---------->> "state\siparis_nobeti.log"
"C:\Users\serdar\AppData\Local\Programs\Python\Python312\python.exe" tools\siparis_nobeti.py >> "state\siparis_nobeti.log" 2>&1
