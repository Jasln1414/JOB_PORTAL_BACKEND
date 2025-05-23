from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import Jobs, ApplyedJobs, Approvals

@receiver(post_save, sender=ApplyedJobs)
def create_or_get_approval(sender, instance, created, **kwargs):
    if created:
        employer = instance.job.employer  # Ensure Job model has an 'employer' FK
        Approvals.objects.get_or_create(
            candidate=instance.candidate,
            employer=employer,
            defaults={'message': ''}  # Set default values as needed
        )