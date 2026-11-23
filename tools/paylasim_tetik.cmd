@echo off
REM 10 dakikada bir: zamani gelmis paylasilmamis post varsa publish.yml tetikler. Bkz. tools\paylasim_tetik.py
cd /d "D:\Masaustu\atolye-temiz"
set PYTHONIOENCODING=utf-8
"C:\Users\serdar\AppData\Local\Programs\Python\Python312\python.exe" tools\paylasim_tetik.py >> "state\paylasim_tetik.log" 2>&1
