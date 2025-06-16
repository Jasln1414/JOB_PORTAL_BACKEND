from __future__ import absolute_import, unicode_literals
import os
import logging
from celery import Celery
from django.utils import timezone
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
import django
django.setup()  

app = Celery('worknest')


app.config_from_object('django.conf:settings', namespace='CELERY')


app.conf.task_time_limit = 300  
app.conf.task_soft_time_limit = 240  


app.conf.update(
    broker_url='redis://localhost:6379/0',  
    result_backend='redis://localhost:6379/0',
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    enable_utc=False,
    timezone='America/New_York',
    beat_scheduler='django_celery_beat.schedulers:DatabaseScheduler',
)


app.autodiscover_tasks()

@app.task(bind=True)
def debug_task(self):
    print(f'Request: {self.request!r}')


logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('celery.log'),
    ]
)




