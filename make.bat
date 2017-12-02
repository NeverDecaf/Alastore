@echo off
REM pyi-makespec --onefile --noconsole --name=Alastore --icon=book.ico Alastore.py

REM added [(r'book.ico',r'book.ico','DATA')] as an arg to EXE() in the spec

C:\Python27\Scripts\pyinstaller --clean --noconfirm Alastore.spec
