@echo off
REM 5 dakikada bir stok/siparis is akisini UYGULA modunda tetikler. Bkz. tools\stok_tetik.py
cd /d "C:\Users\serdar\Desktop\atolye-temiz"
set PYTHONIOENCODING=utf-8
"C:\Users\serdar\AppData\Local\Programs\Python\Python312\python.exe" tools\stok_tetik.py >> "state\stok_tetik.log" 2>&1
