# # D:\Django_second_project\WorkNest\backend\celery_app.py

# from __future__ import absolute_import, unicode_literals
# import os
# import logging
# from celery import Celery # type: ignore

# # Set default Django settings module for 'celery'
# os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')

# # Instantiate Celery
# app = Celery('worknest')

# # Set timezone
# app.conf.enable_utc = False
# app.conf.timezone = 'America/New_York'

# # Load settings from Django settings using CELERY namespace
# app.config_from_object('django.conf:settings', namespace='CELERY')

# # Use Django database as beat scheduler
# app.conf.beat_scheduler = 'django_celery_beat.schedulers:DatabaseScheduler'

# # Auto-discover tasks from installed apps
# app.autodiscover_tasks()

# # Optional debug task
# @app.task(bind=True)
# def debug_task(self):
#     print(f'Request: {self.request!r}')

# # Setup logging
# logger = logging.getLogger(__name__)
# logging.basicConfig(level=logging.INFO)
# logger.info('Celery worker initialized')
# logger.info(f'Using broker: {app.conf.get("broker_url", "Not Configured")}')


from __future__ import absolute_import, unicode_literals
import os
import logging
from celery import Celery

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')

app = Celery('worknest')

# Load settings with CELERY namespace
app.config_from_object('django.conf:settings', namespace='CELERY')

# Explicitly set critical settings
app.conf.update(
    broker_url='redis://localhost:6379/0',  # Ensure Redis is running
    result_backend='redis://localhost:6379/0',
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    enable_utc=False,
    timezone='America/New_York',
    beat_scheduler='django_celery_beat.schedulers:DatabaseScheduler',
)

# Auto-discover tasks
app.autodiscover_tasks()

@app.task(bind=True)
def debug_task(self):
    print(f'Request: {self.request!r}')

# Logging setup
logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('celery.log'),
    ]
)
logger.info('Celery worker initialized')
logger.info(f'Using broker: {app.conf.get("broker_url", "Not Configured")}')