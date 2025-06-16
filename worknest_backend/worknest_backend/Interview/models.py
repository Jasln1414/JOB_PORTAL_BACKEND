from django.db import models
from user_account.models import Candidate, Employer
from Empjob.models import Jobs

class InterviewShedule(models.Model):
    STATUS_CHOICES = (
        ("Upcoming", "Upcoming"),
        ("Completed", "Completed"),
        ("Accepted", "Accepted"),  
        ("Canceled", "Canceled"),
        ("Rejected", "Rejected"),
        ("You missed", "You missed"),
    )
    
    candidate = models.ForeignKey(Candidate, on_delete=models.CASCADE)
    employer = models.ForeignKey(Employer, on_delete=models.CASCADE)
    job = models.ForeignKey(Jobs, on_delete=models.CASCADE)
    date = models.DateTimeField()
    selected = models.BooleanField(default=False)  
    active = models.BooleanField(default=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="Upcoming")
    notification_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    attended = models.BooleanField(default=False)
    
    def __str__(self):
        return f"{self.job.title} - {self.candidate.user.email}"
    
    class Meta:
        unique_together = ('job', 'candidate', 'date')
        
    def save(self, *args, **kwargs):
        if self.active and self.pk is None:
            InterviewShedule.objects.filter(
                job=self.job, 
                candidate=self.candidate,
                active=True
            ).update(active=False)
        super().save(*args, **kwargs)

