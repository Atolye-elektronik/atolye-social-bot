@echo off
cd /d "D:\Masaustu\atolye-temiz"
set PYTHONIOENCODING=utf-8
"C:\Users\serdar\AppData\Local\Programs\Python\Python312\python.exe" tools\siparis_bugun.py >> "state\siparis_bugun.log" 2>&1
