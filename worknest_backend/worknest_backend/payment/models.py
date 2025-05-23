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
    STATUS_CHOICES = (
        ('active', 'Active'),
        ('expired', 'Expired'),
        ('cancelled', 'Cancelled'),
        ('pending', 'Pending'),  # Add 'pending' to match your usage
    )
    
    employer = models.ForeignKey(Employer, on_delete=models.CASCADE, related_name="subscriptions")
    plan = models.ForeignKey(SubscriptionPlan, on_delete=models.CASCADE)
    start_date = models.DateTimeField(auto_now_add=True)
    end_date = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')  # Changed default to 'pending'
    razorpay_subscription_id = models.CharField(max_length=255, null=True, blank=True)
    payment = models.OneToOneField(Payment, on_delete=models.SET_NULL, null=True, blank=True)
    job_limit = models.IntegerField(default=0, help_text="Employer-specific job limit")  # Added field
    subscribed_job=models.IntegerField(default=0)
    def __str__(self):
        return f"{self.employer} - {self.plan.name} ({self.status})"

    def save(self, *args, **kwargs):
        if not self.pk and self.plan:  # On creation, set job_limit from plan
            self.job_limit = self.plan.job_limit
        super().save(*args, **kwargs)

    def is_active(self):
        return self.status == 'active' and self.end_date and self.end_date > timezone.now()


