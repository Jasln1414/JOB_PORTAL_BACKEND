# payment/models.py
from django.db import models
from user_account.models import Employer, User
from Empjob.models import Jobs
from django.utils import timezone
from django.db.models.functions import Lower
from django.db.models import UniqueConstraint


class Payment(models.Model):
    STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('success', 'Success'),
        ('failed', 'Failed'),

    )

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="payments")
    employer = models.ForeignKey(Employer, on_delete=models.CASCADE, related_name="payments")
    job = models.ForeignKey(Jobs, on_delete=models.SET_NULL, null=True, blank=True)
    amount = models.FloatField()
    method = models.CharField(max_length=50)  
    transaction_id = models.CharField(max_length=255, unique=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)
    
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Payment {self.transaction_id} - {self.status}"

class SubscriptionPlan(models.Model):
    PLAN_TYPES = (
        ('basic', 'Basic'),
        ('standard', 'Standard'),
        ('premium', 'Premium'),
    )
    
    name = models.CharField(max_length=20, choices=PLAN_TYPES, unique=True)
    description = models.TextField()
    price = models.FloatField(help_text="Monthly price in INR")
    job_limit = models.IntegerField(help_text="Maximum number of jobs allowed per month")
    duration = models.IntegerField(default=30, help_text="Duration in days", editable=False)
    def save(self, *args, **kwargs):
        self.name = self.name.lower()  
        super().save(*args, **kwargs)
    def __str__(self):
        return f"{self.get_name_display()} - ₹{self.price}/month"
    class Meta:
        constraints = [
            UniqueConstraint(
                Lower('name'),
                name='unique_lower_name',
            ),
        ]






class EmployerSubscription(models.Model):
    employer = models.ForeignKey(Employer, on_delete=models.CASCADE)
    plan = models.ForeignKey(SubscriptionPlan, on_delete=models.CASCADE)
    razorpay_subscription_id = models.CharField(max_length=100, unique=True)
    payment = models.ForeignKey(Payment, on_delete=models.SET_NULL, null=True, blank=True)
    status = models.CharField(
        max_length=20,
        choices=[('pending', 'Pending'), ('active', 'Active'), ('inactive', 'Inactive'), ('restricted', 'Restricted')],
        default='pending'
    )
    start_date = models.DateTimeField(null=True, blank=True)
    end_date = models.DateTimeField(null=True, blank=True)
    job_limit = models.PositiveIntegerField(default=0)  
    subscribed_job = models.PositiveIntegerField(default=0)  

    def __str__(self):
        return f"{self.employer} - {self.plan.name} ({self.status})"

    def can_post_job(self):
        """Check if the employer can post more jobs."""
        return self.status == 'active' and self.subscribed_job < self.job_limit