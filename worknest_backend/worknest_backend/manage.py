import os
import sys
from pathlib import Path
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
# Add project directory to Python path
BASE_DIR = Path(__file__).resolve().parent
sys.path.append(str(BASE_DIR))

def main():
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError("Couldn't import Django") from exc
    execute_from_command_line(sys.argv)

if __name__ == '__main__':
    main()