@echo off
pushd "%~dp0"
python -m unittest discover -s tests -v
set "test_exit=%errorlevel%"
popd
exit /b %test_exit%
