REM make sure the 'openssl.exe' commandline tool is in your path before starting!
REM set the path below;
set opensslpath=c:\program files (x86)\openssl-win32\bin



setlocal
set path=%opensslpath%;%path%
call roota.bat
call rootb.bat
call servera.bat
call serverb.bat
call clienta.bat
call clientb.bat
