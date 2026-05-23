@echo off
setlocal

echo Creating Python virtual environment...
if not exist venv (
  py -m venv venv
)

echo Installing backend dependencies...
call venv\Scripts\activate.bat
python -m pip install --upgrade pip
pip install -r requirements.txt

echo Installing frontend dependencies...
cd frontend
npm install
cd ..

echo Setup complete.
endlocal
