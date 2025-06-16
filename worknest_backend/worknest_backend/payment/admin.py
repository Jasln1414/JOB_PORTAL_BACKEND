# payment/admin.py
from django.contrib import admin
from .models import Payment, SubscriptionPlan, EmployerSubscription

@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ('transaction_id', 'user', 'employer', 'job', 'amount', 'method', 'status', 'created_at', 'updated_at')
    list_filter = ('status', 'method', 'created_at')
    search_fields = ('transaction_id', 'user__username', 'employer__name')
    readonly_fields = ('created_at', 'updated_at')

@admin.register(SubscriptionPlan)
class SubscriptionPlanAdmin(admin.ModelAdmin):
    list_display = ('name', 'price', 'job_limit', 'duration')
    search_fields = ('name',)
    ordering = ('price',)

@admin.register(EmployerSubscription)
class EmployerSubscriptionAdmin(admin.ModelAdmin):
    list_display = ('employer', 'plan', 'status', 'start_date', 'end_date', 'job_limit', 'subscribed_job')
    list_filter = ('status', 'plan')
    search_fields = ('employer__name', 'plan__name', 'razorpay_subscription_id')
    readonly_fields = ('start_date', 'end_date')
