# payment/urls.py
from django.urls import path
from .views import (
   SubscriptionPlansList, 
    CreateSubscription, 
    VerifyPayment, 
   CreateSubscriptionPlan
)
urlpatterns = [
    
    # Subscription-related endpoints
    path('subscription/plans/', SubscriptionPlansList.as_view(), name='subscription-plans-list'),
    path('subscription/create/', CreateSubscription.as_view(), name='create-subscription'),
    path('subscription/verify/', VerifyPayment.as_view(), name='verify-subscription-payment'),
    path('addsubscriptionplan/', CreateSubscriptionPlan.as_view(), name='add-subscriptionplan'),
]

