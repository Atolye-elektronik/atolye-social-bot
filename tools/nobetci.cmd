@echo off
REM Masaustu nobetci - GitHub Actions cron'u tamamen takilirsa devreye girer.
REM Saatlik Windows zamanlanmis gorevi cagirir. Ciktiyi state/nobetci.log'a yazar.
cd /d "C:\Users\serdar\Desktop\atolye-temiz"
set PYTHONIOENCODING=utf-8
echo ---------- %DATE% %TIME% ---------->> "state\nobetci.log"
"C:\Users\serdar\AppData\Local\Programs\Python\Python312\python.exe" tools\nobetci.py --tetikle >> "state\nobetci.log" 2>&1
