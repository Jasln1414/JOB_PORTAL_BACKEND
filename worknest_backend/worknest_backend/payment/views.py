"""Module for handling subscription-related views in the subscription app.

This module provides API endpoints for managing subscription plans, creating
subscriptions, and verifying payments using Razorpay. It includes authentication
and admin-only restrictions where applicable.
"""


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


class CreateSubscription(APIView):
    """View to create a new subscription order.

    This view allows authenticated employers to create a subscription order
    using Razorpay. It deactivates existing active subscriptions and generates
    a new payment order.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request):
        """Handle POST request to create a subscription order.

        Args:
            request: HTTP request object containing plan_id.

        Returns:
            Response: JSON response with order details or error message.

        Raises:
            Employer.DoesNotExist: If the employer is not found.
            SubscriptionPlan.DoesNotExist: If the plan ID is invalid.
            Exception: If an unexpected error occurs.
        """
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

            # Deactivate existing active subscription
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

            # Create Razorpay order
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

            # Create pending payment and subscription
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
                razorpay_subscription_id=order_id,
                payment=payment,
                status='pending'
            )

            return Response(
                {
                    'message': 'Order created. Please complete payment.',
                    'order_id': order_id,
                    'amount': order_amount,
                    'key_id': settings.RAZORPAY_KEY_ID,
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
    """View to verify payment and activate subscription.

    This view verifies the Razorpay payment signature and updates the payment
    and subscription status accordingly.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request):
        """Handle POST request to verify payment details.

        Args:
            request: HTTP request object containing payment details
                    (razorpay_payment_id, razorpay_order_id, razorpay_signature).

        Returns:
            Response: JSON response with success or error message.

        Raises:
            Employer.DoesNotExist: If the employer is not found.
            Payment.DoesNotExist: If the payment record is not found.
            EmployerSubscription.DoesNotExist: If the subscription record is
                                               not found.
            SignatureVerificationError: If the payment signature is invalid.
            Exception: If an unexpected error occurs.
        """
        user = request.user
        razorpay_payment_id = request.data.get('razorpay_payment_id')
        razorpay_order_id = request.data.get('razorpay_order_id')
        razorpay_signature = request.data.get('razorpay_signature')

        if not all([razorpay_payment_id, razorpay_order_id, razorpay_signature]):
            return Response(
                {'message': 'Missing required payment parameters'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            employer = Employer.objects.get(user=user)
            payment = Payment.objects.get(transaction_id=razorpay_order_id,
                                         employer=employer)

            # Verify signature
            params_dict = {
                'razorpay_payment_id': razorpay_payment_id,
                'razorpay_order_id': razorpay_order_id,
                'razorpay_signature': razorpay_signature,
            }
            razorpay_client.utility.verify_payment_signature(params_dict)

            # Update payment and subscription
            payment.status = 'success'
            payment.transaction_id = razorpay_payment_id
            payment.save()

            subscription = EmployerSubscription.objects.get(
                razorpay_subscription_id=razorpay_order_id,
                employer=employer
            )
            subscription.status = 'active'
            subscription.save()

            return Response(
                {'message': 'Payment successful. Subscription activated.'},
                status=status.HTTP_200_OK
            )

        except Employer.DoesNotExist:
            return Response(
                {'message': 'Employer not found.'},
                status=status.HTTP_404_NOT_FOUND
            )
        except Payment.DoesNotExist:
            return Response(
                {'message': 'Payment record not found.'},
                status=status.HTTP_404_NOT_FOUND
            )
        except EmployerSubscription.DoesNotExist:
            return Response(
                {'message': 'Subscription record not found.'},
                status=status.HTTP_404_NOT_FOUND
            )
        except SignatureVerificationError:
            return Response(
                {'message': 'Payment verification failed - invalid signature'},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            logger.error(f"Unexpected error in VerifyPayment: {str(e)}")
            return Response(
                {'message': f'An error occurred: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


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
    """API view for renewing an employer's subscription via Razorpay payment."""
    
    permission_classes = [IsAuthenticated]

    def post(self, request):
        """Handle POST request to renew an employer's subscription.

        Args:
            request: The HTTP request containing subscription ID and user data.

        Returns:
            Response: JSON response with payment details or error message.
        """
        user = request.user
        subscription_id = request.data.get('sub_id')

        # Validate input
        if not subscription_id or not str(subscription_id).isdigit():
            return Response(
                {'message': 'Valid subscription ID is required.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            # Debug: Log settings availability
            logger.debug('Checking Razorpay settings: KEY_ID=%s, KEY_SECRET=%s',
                        'present' if hasattr(settings, 'RAZORPAY_KEY_ID') else 'missing',
                        'present' if hasattr(settings, 'RAZORPAY_KEY_SECRET') else 'missing')

            # Initialize Razorpay client
            if not hasattr(settings, 'RAZORPAY_KEY_ID') or not hasattr(
                settings, 'RAZORPAY_KEY_SECRET'
            ):
                raise ImproperlyConfigured(
                    'Razorpay keys are not configured in settings. '
                    'Please set RAZORPAY_KEY_ID and RAZORPAY_KEY_SECRET in settings.py.'
                )
            razorpay_client = Client(
                auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET)
            )

            employer = Employer.objects.get(user=user)
            employer_subscription = EmployerSubscription.objects.get(
                pk=subscription_id,
                employer=employer
            )
            plan = employer_subscription.plan

            # Validate plan data
            if not isinstance(plan.price, (int, float)) or plan.price <= 0:
                return Response(
                    {'message': 'Invalid plan price.'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            if not isinstance(plan.duration, int) or plan.duration <= 0:
                return Response(
                    {'message': 'Invalid plan duration.'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Create Razorpay order
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
            logger.info(
                'Creating order for employer %s, plan %s, amount %s',
                employer.id, plan.id, order_amount
            )
            razorpay_order_response = razorpay_client.order.create(
                data=order_data
            )
            order_id = razorpay_order_response['id']

            # Update subscription and create payment within a transaction
            with transaction.atomic():
                payment = Payment.objects.create(
                    user=user,
                    employer=employer,
                    amount=plan.price,
                    method='Razorpay',
                    transaction_id=order_id,
                    status='pending'
                )
                employer_subscription.end_date = (
                    timezone.now() + timedelta(days=plan.duration)
                )
                employer_subscription.razorpay_subscription_id = order_id
                employer_subscription.payment = payment
                employer_subscription.status = 'pending'
                employer_subscription.save()

            return Response(
                {
                    'message': 'Order created. Please complete payment.',
                    'order_id': order_id,
                    'amount': order_amount,
                    'key_id': settings.RAZORPAY_KEY_ID,
                    'planId': plan.id
                },
                status=status.HTTP_201_CREATED
            )

        except Employer.DoesNotExist:
            return Response(
                {'message': 'Employer not found.'},
                status=status.HTTP_404_NOT_FOUND
            )
        except EmployerSubscription.DoesNotExist:
            return Response(
                {'message': 'Invalid subscription ID.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        except ImproperlyConfigured as config_error:
            logger.error('Configuration error: %s', str(config_error))
            return Response(
                {'message': str(config_error)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        except APIException as api_error:
            logger.error('API error: %s', str(api_error))
            return Response(
                {'message': str(api_error)},
                status=status.HTTP_503_SERVICE_UNAVAILABLE
            )
        except Exception as error:
            logger.error('Error creating subscription: %s', str(error), exc_info=True)
            return Response(
                {'message': f'Unexpected error: {str(error)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
