from celery import shared_task # type: ignore
from django.utils import timezone
from .models import EmployerSubscription

@shared_task
def expire_subscriptions():
    now = timezone.now()
    subscriptions = EmployerSubscription.objects.filter(
        status='active',
        end_date__lte=now
    )
    count = subscriptions.update(status='expired')
    return f"{count} subscriptions expired."