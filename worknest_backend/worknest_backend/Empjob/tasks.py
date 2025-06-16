from django.utils import timezone
from celery import shared_task
import logging

logger = logging.getLogger(__name__)

@shared_task
def deactivate_expired_jobs():
    from Empjob.models import Jobs
    today = timezone.localtime(timezone.now()).date() 
    expired_jobs = Jobs.objects.filter(applyBefore__lt=today, active=True)
   
    count = expired_jobs.update(active=False)
    logger.info(f"{count} expired jobs deactivated at {timezone.now}")
    return f"{count} jobs deactivated"
