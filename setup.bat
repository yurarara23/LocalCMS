@echo off
set /p userinput=Do you want to run the setup? (type yes to start):

if /i "%userinput%"=="yes" (
    echo Creating virtual environment...
    python -m venv venv

    echo Activating virtual environment...
    call venv\Scripts\activate

    echo Installing dependencies...
    pip install --upgrade pip
    pip install -r requirements.txt

    echo Setup complete!
) else (
    echo Setup canceled.
)

pause
