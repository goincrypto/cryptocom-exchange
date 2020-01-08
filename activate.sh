find . -type f -name '*.py[co]' -delete
find . -type d -name '__pycache__' -delete

source ./venv/bin/activate

if [ -f "local.sh" ]; then
    source local.sh
fi
