@echo off
REM Bugun gelen siparisler -> Desktop\SIPARIS-BUGUN.xlsx (gunluk gorev AtolyeSiparisBugun, 21:30)
cd /d "C:\Users\serdar\Desktop\atolye-temiz"
set PYTHONIOENCODING=utf-8
set PYTHONPATH=src;src\marketplaces
for /f "usebackq tokens=1,* delims==" %%a in ("C:\Users\serdar\Desktop\atolyesocialbotmasaustu\.env") do (if not "%%a"=="" if not "%%a:~0,1%"=="#" set "%%a=%%b")
for /f "usebackq tokens=1,* delims==" %%a in (".env") do (if not "%%a"=="" if not "%%a:~0,1%"=="#" set "%%a=%%b")
"C:\Users\serdar\AppData\Local\Programs\Python\Python312\python.exe" -m stok.siparis --liste --bugun >> "state\siparis_bugun.log" 2>&1
