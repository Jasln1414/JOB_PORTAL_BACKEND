"""Module for handling subscription-related views in the subscription app.

This module provides API endpoints for managing subscription plans, creating
subscriptions, and verifying payments using Razorpay. It includes authentication
and admin-only restrictions where applicable.
"""


import uuid
from django.conf import settings
from django.http import JsonResponse

import json
import razorpay
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from .models import SubscriptionPlan, EmployerSubscription, Payment
from user_account.models import Employer
from Empjob.models import Jobs
from .serializer import SubscriptionPlanSerializer
from django.core.exceptions import ImproperlyConfigured, ObjectDoesNotExist
from django.db import transaction

from razorpay import Client
from rest_framework.exceptions import APIException


from django.utils import timezone
from datetime import timedelta
from django.db import transaction

from razorpay import Client
from razorpay.errors import BadRequestError, SignatureVerificationError
import logging


# Initialize Razorpay client
razorpay_client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID,
                                       settings.RAZORPAY_KEY_SECRET))

# Configure logging
logger = logging.getLogger(__name__)


class SubscriptionPlansList(APIView):
    """View to list all available subscription plans.

    This view is accessible to authenticated users and returns a list of
    subscription plans with their details (id, name, description, price,
    job_limit).
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        """Handle GET request to retrieve all subscription plans.

        Args:
            request: HTTP request object.

        Returns:
            Response: JSON response with list of plans or error message.

        Raises:
            Exception: If an unexpected error occurs while fetching plans.
        """
        try:
            plans = SubscriptionPlan.objects.all()
            data = [
                {
                    'id': plan.id,
                    'name': plan.get_name_display(),
                    'description': plan.description,
                    'price': plan.price,
                    'job_limit': plan.job_limit,
                } for plan in plans
            ]
            return Response(data, status=status.HTTP_200_OK)
        except Exception as e:
            return Response(
                {'message': f'Error fetching plans: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )










razorpay_client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))

class CreateSubscription(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        user = request.user
        plan_id = request.data.get('plan_id')

        if not plan_id:
            return Response(
                {'message': 'Plan ID is required.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            employer = Employer.objects.get(user=user)
            plan = SubscriptionPlan.objects.get(id=plan_id)

            active_sub = EmployerSubscription.objects.filter(
                employer=employer,
                status="active",
                end_date__gt=timezone.now()
            ).first()
            if active_sub:
                logger.info(
                    f"Deactivating existing subscription ID: {active_sub.id} "
                    f"for user {user.id}"
                )
                active_sub.status = "inactive"
                active_sub.save()

            order_amount = plan.price * 100
            order_data = {
                'amount': order_amount,
                'currency': 'INR',
                'receipt': f'order_rcpt_{employer.id}_{plan.id}',
                'notes': {
                    'plan_id': str(plan.id),
                    'employer_id': str(employer.id)
                }
            }
            razorpay_order = razorpay_client.order.create(data=order_data)
            order_id = razorpay_order['id']

            payment = Payment.objects.create(
                user=user,
                employer=employer,
                amount=plan.price,
                method='Razorpay',
                transaction_id=order_id,
                status='pending',
            )
            subscription = EmployerSubscription.objects.create(
                employer=employer,
                plan=plan,
                end_date=timezone.now() + timedelta(days=plan.duration),
                razorpay_subscription_id=f"sub_{uuid.uuid4().hex[:14]}",
                payment=payment,
                status='pending'
            )

            return Response(
                {
                    'message': 'Order created. Please complete payment.',
                    'order_id': order_id,
                    'amount': order_amount,
                    'key_id': settings.RAZORPAY_KEY_ID,
                    'subscription_id': subscription.razorpay_subscription_id,
                    'subscription_type': 'new'
                },
                status=status.HTTP_201_CREATED
            )

        except Employer.DoesNotExist:
            return Response(
                {'message': 'Employer not found.'},
                status=status.HTTP_404_NOT_FOUND
            )
        except SubscriptionPlan.DoesNotExist:
            return Response(
                {'message': 'Invalid plan ID.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            logger.error(f"Error creating subscription: {str(e)}")
            return Response(
                {'message': f'Unexpected error: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class VerifyPayment(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        user = request.user
        razorpay_payment_id = request.data.get('razorpay_payment_id')
        razorpay_order_id = request.data.get('razorpay_order_id')
        razorpay_signature = request.data.get('razorpay_signature')

        if not all([razorpay_payment_id, razorpay_order_id, razorpay_signature]):
            logger.error(f"Missing payment verification data: payment_id={razorpay_payment_id}, order_id={razorpay_order_id}")
            return Response({'message': 'Missing required payment parameters'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            employer = Employer.objects.get(user=user)
            payment = Payment.objects.get(transaction_id=razorpay_order_id, employer=employer, status='pending')
            subscription = EmployerSubscription.objects.get(payment=payment, employer=employer)

            razorpay_client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))
            params_dict = {
                'razorpay_payment_id': razorpay_payment_id,
                'razorpay_order_id': razorpay_order_id,
                'razorpay_signature': razorpay_signature
            }
            razorpay_client.utility.verify_payment_signature(params_dict)

            payment.status = 'success'
            payment.razorpay_payment_id = razorpay_payment_id
            payment.completed_at = timezone.now()
            payment.save()

            subscription.status = 'active'
            subscription.start_date = timezone.now() if subscription.status != 'active' else subscription.start_date
            subscription.save()

            logger.info(f"Payment verified: payment_id={razorpay_payment_id}, order_id={razorpay_order_id}, subscription_id={subscription.razorpay_subscription_id}")
            return Response({'message': 'Payment successful. Subscription activated.'}, status=status.HTTP_200_OK)
        except Employer.DoesNotExist:
            logger.error(f"Employer not found for user {user.id}")
            return Response({'message': 'Employer not found'}, status=status.HTTP_404_NOT_FOUND)
        except Payment.DoesNotExist:
            logger.error(f"Payment not found for order_id={razorpay_order_id}")
            return Response({'message': 'Payment record not found'}, status=status.HTTP_404_NOT_FOUND)
        except EmployerSubscription.DoesNotExist:
            logger.error(f"Subscription not found for payment with order_id={razorpay_order_id}")
            return Response({'message': 'Subscription record not found'}, status=status.HTTP_404_NOT_FOUND)
        except SignatureVerificationError:
            logger.error(f"Invalid signature for payment_id={razorpay_payment_id}")
            return Response({'message': 'Payment verification failed - invalid signature'}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f"Unexpected error in VerifyPayment: {str(e)}")
            return Response({'message': f'An error occurred: {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)








class CreateSubscriptionPlan(APIView):
    """View to create a new subscription plan (admin-only).

    This view allows admin users to create new subscription plans using a
    serializer.
    """

    permission_classes = [IsAdminUser]

    def post(self, request):
        """Handle POST request to create a new subscription plan.

        Args:
            request: HTTP request object containing plan data.

        Returns:
            Response: JSON response with created plan data or validation errors.

        Raises:
            Exception: If an unexpected error occurs during validation or saving.
        """
        logger.debug(f"Received subscription plan creation request: {request.data}")
        serializer = SubscriptionPlanSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            logger.info(f"Created new subscription plan: {serializer.data}")
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        logger.error(f"Validation errors: {serializer.errors}")
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class RenewSubscription(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        user = request.user
        sub_id = request.data.get('sub_id')
        if not sub_id:
            logger.error("No sub_id provided in renewal request")
            return Response({'message': 'Subscription ID required'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            employer = Employer.objects.get(user=user)
            subscription = EmployerSubscription.objects.get(
                razorpay_subscription_id=sub_id, employer=employer
            )
            plan = subscription.plan

            if subscription.status == 'active' and subscription.end_date > timezone.now():
                # Extend the existing subscription
                subscription.end_date = subscription.end_date + timedelta(days=plan.duration)
                subscription.status = 'pending'  # Set to pending until payment is verified
                subscription.subscribed_job = 0  # Reset subscribed_job for the new cycle
                subscription.save()
            else:
                # Create a new subscription if expired
                subscription = EmployerSubscription.objects.create(
                    employer=employer,
                    plan=plan,
                    razorpay_subscription_id=f"sub_{uuid.uuid4().hex[:14]}",
                    status='pending',
                    start_date=timezone.now(),
                    end_date=timezone.now() + timedelta(days=plan.duration),
                    subscribed_job=0,  # Initialize subscribed_job to 0
                    job_limit=plan.job_limit,  # Set job_limit from plan
                )

            order_amount = int(plan.price * 100)
            order_data = {
                'amount': order_amount,
                'currency': 'INR',
                'receipt': f'order_rcpt_{employer.id}_{plan.id}',
                'notes': {'plan_id': str(plan.id), 'employer_id': str(employer.id)}
            }
            razorpay_client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))
            razorpay_order = razorpay_client.order.create(data=order_data)
            order_id = razorpay_order['id']

            payment = Payment.objects.create(
                user=user,
                employer=employer,
                amount=plan.price,
                method='Razorpay',
                transaction_id=order_id,
                status='pending',
            )
            subscription.payment = payment
            subscription.save()

            logger.info(f"Renewal order created: order_id={order_id}, sub_id={subscription.razorpay_subscription_id}")
            return Response({
                'message': 'Order created. Please complete payment.',
                'order_id': order_id,
                'amount': order_amount,
                'key_id': settings.RAZORPAY_KEY_ID,
                'planId': plan.id,
                'subscription_id': subscription.razorpay_subscription_id,
                'subscription_type': 'extension'
            }, status=status.HTTP_201_CREATED)
        except Employer.DoesNotExist:
            logger.error(f"Employer not found for user {user.id}")
            return Response({'message': 'Employer not found'}, status=status.HTTP_404_NOT_FOUND)
        except EmployerSubscription.DoesNotExist:
            logger.error(f"Subscription not found for razorpay_subscription_id: {sub_id}")
            return Response({'message': 'Invalid subscription ID'}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f"Error renewing subscription: {str(e)}")
            return Response({'message': f'Unexpected error: {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)