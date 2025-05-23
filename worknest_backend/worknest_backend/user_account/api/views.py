from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.exceptions import ParseError
from .serializer import *
from .email import *
from Empjob.api.serializer import *
from user_account.models import *
from Empjob.models import *
from django.contrib.auth import authenticate
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework.permissions import IsAuthenticated, AllowAny
from google.oauth2 import id_token  # type: ignore
from google.auth.transport import requests  # type: ignore
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.core.exceptions import ValidationError
from django.middleware.csrf import get_token
from django.http import JsonResponse
import logging
import os

logger = logging.getLogger(__name__)

# Utility function to get CSRF token
def get_csrf_token(request):
    """Retrieve and return the CSRF token for the current request."""
    csrf_token = get_token(request)
    return JsonResponse({'csrfToken': csrf_token})

# !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!! EMPLOYER !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!

class EmployerRegisterView(APIView):
    """Handle employer registration and OTP sending."""
    permission_classes = []

    def post(self, request):
        """
        Register a new employer and send an OTP for email verification.

        Args:
            request: HTTP request with employer registration data (e.g., email).

        Returns:
            Response: Success message with email or error details.
        """
        email = request.data.get('email')

        # Check if user already exists
        if User.objects.filter(email=email).exists():
            return Response({"message": "User with this email already exists"},
                            status=status.HTTP_203_NON_AUTHORITATIVE_INFORMATION)

        # Validate serializer data
        serializer = EmployerRegisterSerializer(data=request.data)
        if not serializer.is_valid():
            return Response({"message": "Validation error", "errors": serializer.errors},
                            status=status.HTTP_400_BAD_REQUEST)

        try:
            # Save user with inactive status
            user = serializer.save(is_active=False)
            # Create or get employer profile
            employer, created = Employer.objects.get_or_create(user=user)
            # Send OTP for verification
            send_otp_via_mail(user.email, user.otp)

            response_data = {
                'message': 'OTP sent successfully.',
                'email': user.email
            }
            return Response(response_data, status=status.HTTP_200_OK)

        except Exception as e:
            logger.error(f"Error in EmployerRegisterView: {str(e)}")
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        






class EmpLoginView(APIView):
    """Handle employer login and JWT token generation."""
    permission_classes = []

    def post(self, request):
        """
        Authenticate an employer and return access/refresh tokens.
        """
        email = request.data.get('email')
        password = request.data.get('password')
        logger.info(f"Login attempt for email: {email}")

        try:
            user = User.objects.get(email=email)
            logger.info(f"User found: {user.full_name}")
        except User.DoesNotExist:
            logger.warning(f"User with email {email} does not exist")
            return Response({"message": "Invalid email address!"}, status=status.HTTP_404_NOT_FOUND)

        if not user.is_active:
            logger.warning(f"User {email} is inactive")
            return Response({"message": "Account is inactive!"}, status=status.HTTP_403_FORBIDDEN)

        if user.user_type != 'employer':
            logger.warning(f"User {email} is not an employer")
            return Response({"message": "Only employers can login here!"}, status=status.HTTP_403_FORBIDDEN)

        user = authenticate(username=email, password=password)
        if not user:
            logger.warning(f"Invalid password for {email}")
            return Response({"message": "Invalid credentials!"}, status=status.HTTP_401_UNAUTHORIZED)

        try:
            employer = Employer.objects.get(user=user)
           
            if not employer.is_approved_by_admin:
                logger.warning(f"Employer {email} not approved by admin")
                return Response({"message": "Account pending admin approval"}, 
                              status=status.HTTP_403_FORBIDDEN)

            # Generate JWT tokens
            refresh = RefreshToken.for_user(user)
            refresh["name"] = user.full_name
            access_token = str(refresh.access_token)
            refresh_token = str(refresh)

            # Get serialized employer data
            employer_data = EmployerSerializer(employer, context={'request': request}).data

            # Prepare response data without 'company_name'
            response_data = {
                "access_token": access_token,
                "refresh_token": refresh_token,
                "user_data": {
                    "id": employer.id,
                    "user_id": user.id,
                    "email": user.email,
                    "completed": employer.completed,  # This controls navigation
                    "profile_pic": employer_data.get('profile_pic'),
                    # Removed "company_name": employer.company_name
                    "is_verified": employer.is_verified,
                    "is_approved": employer.is_approved_by_admin
                }
            }

            logger.info(f"Login successful for {email}")
            return Response(response_data, status=status.HTTP_200_OK)

        except Employer.DoesNotExist:
            logger.error(f"Missing employer profile for {email}")
            return Response({"message": "Profile not found - contact support"}, 
                          status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class CurrentUser(APIView):
    """Retrieve details of the currently authenticated user."""
    def get(self, request):
        """
        Fetch details of the authenticated user (candidate or employer).

        Args:
            request: HTTP request with authenticated user.

        Returns:
            Response: Serialized candidate/employer data or error message.
        """
        user = request.user
        if not user.is_authenticated:
            return Response({"error": "User is not authenticated"}, status=status.HTTP_401_UNAUTHORIZED)

        try:
            candidate = Candidate.objects.get(user=user)
            serializer = CandidateSerializer(candidate)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Candidate.DoesNotExist:
            pass

        try:
            employer = Employer.objects.get(user=user)
            serializer = EmployerSerializer(employer)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Employer.DoesNotExist:
            pass

        return Response({"error": "User is not a candidate or an employer"}, status=status.HTTP_404_NOT_FOUND)

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
import os
import logging

logger = logging.getLogger(__name__)

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
import os
import logging

logger = logging.getLogger(__name__)

@method_decorator(csrf_exempt, name='dispatch')
class EmployerProfileUpdateView(APIView):
    permission_classes = [IsAuthenticated]

    def put(self, request):
        logger.info(f"PUT /api/account/employer/profile/update/ received from user: {request.user.email if request.user.is_authenticated else 'Anonymous'}")
        logger.info(f"Headers: {dict(request.headers)}")
        logger.info(f"Data: {request.data}")
        logger.info(f"Files: {request.FILES}")

        if not request.user.is_authenticated:
            logger.error("Unauthorized access attempt")
            return Response({"status": "error", "message": "Authentication required"},
                            status=status.HTTP_401_UNAUTHORIZED)

        try:
            user = request.user
            employer = Employer.objects.get(user=user)
            logger.info(f"Found employer ID: {employer.id}")

            # Update fields
            if 'phone' in request.data:
                employer.phone = request.data['phone']
            if 'industry' in request.data:
                employer.industry = request.data['industry']
            if 'headquarters' in request.data:
                employer.headquarters = request.data['headquarters']
            if 'address' in request.data:
                employer.address = request.data['address']
            if 'about' in request.data:
                employer.about = request.data['about']
            if 'website_link' in request.data:
                employer.website_link = request.data['website_link']

            if 'profile_pic' in request.FILES:
                if employer.profile_pic and os.path.isfile(employer.profile_pic.path):
                    os.remove(employer.profile_pic.path)
                employer.profile_pic = request.FILES['profile_pic']

            employer.completed = True
            employer.save()
            logger.info(f"Profile saved for employer ID: {employer.id}, completed: {employer.completed}")

            serializer = EmployerSerializer(employer, context={'request': request})
            return Response({
                "status": "success",
                "message": "Profile updated successfully",
                "data": serializer.data
            }, status=status.HTTP_200_OK)

        except Employer.DoesNotExist:
            logger.error(f"Employer profile not found for user: {user.email}")
            return Response({"status": "error", "message": "Employer profile not found"},
                            status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.error(f"Profile update error: {str(e)}")
            return Response({"status": "error", "message": str(e)},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)

from django.db import transaction

logger = logging.getLogger(__name__)






logger = logging.getLogger(__name__)

class EmployerProfileCreateView(APIView):
    """Handle complete employer profile creation and updates"""
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def post(self, request):
        """
        Complete or update employer profile
        POST /api/employer/profile/
        {
            "phone": "+1234567890",
            "website": "httpsAzN3w",
            "industry": "Tech",
            "about": "We are a tech company",
            ...
        }
        """
        user = request.user
        logger.info(f"Profile update initiated for user: {user.email}")

        try:
            # Get or create employer profile with row lock
            employer = Employer.objects.select_for_update().get(user=user)
        except Employer.DoesNotExist:
            logger.warning(f"No employer profile found for user: {user.id}")
            return Response(
                {"detail": "Employer profile not found"},
                status=status.HTTP_404_NOT_FOUND
            )

        serializer = EmployerProfileSerializer(
            employer,
            data=request.data,
            partial=True,
            context={'request': request}
        )

        if not serializer.is_valid():
            logger.warning(f"Validation errors: {serializer.errors}")
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        try:
            # Check profile completion requirements
            required_fields = ['phone', 'website', 'industry', 'about']
            missing_fields = [field for field in required_fields if not serializer.validated_data.get(field)]

            if not missing_fields:
                employer.completed = True
                logger.info(f"Marking profile as complete for user: {user.email}")
            else:
                logger.info(f"Profile incomplete for user: {user.email}. Missing fields: {missing_fields}")

            with transaction.atomic():
                serializer.save()
                # Explicitly save completed status
                employer.completed = employer.completed  # Ensure it's set
                employer.save(update_fields=['completed'])
                logger.info(f"Profile updated for user: {user.email}, completed: {employer.completed}")

                return Response({
                    "status": "complete" if employer.completed else "incomplete",
                    "data": serializer.data,
                    "completed": employer.completed,  # Explicitly include completed
                    "message": "Profile successfully updated"
                }, status=status.HTTP_200_OK)

        except Exception as e:
            logger.error(f"Profile update failed for user: {user.email}: {str(e)}")
            return Response(
                {"detail": "Error updating profile"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


# !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!! CANDIDATE !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!

class ProfileUpdateView(APIView):
    """Update a candidate's profile details."""
    permission_classes = [IsAuthenticated]

    def put(self, request):
        """
        Update candidate profile, including profile picture, resume, and education.

        Args:
            request: HTTP request with profile data and optional files.

        Returns:
            Response: Success message or error details.
        """
        try:
            user = request.user
            profile = Candidate.objects.get(user=user)

            # Validate and update profile data
            profile_serializer = CandidateProfileSerializer(profile, data=request.data, partial=True)
            if profile_serializer.is_valid():
                profile_serializer.save()
            else:
                return Response({"status": "error", "message": profile_serializer.errors},
                                status=status.HTTP_400_BAD_REQUEST)

            # Handle profile picture update
            if 'profile_pic' in request.FILES:
                if profile.profile_pic and os.path.isfile(profile.profile_pic.path):
                    os.remove(profile.profile_pic.path)
                profile.profile_pic = request.FILES['profile_pic']
                profile.save()

            # Handle resume update
            if 'resume' in request.FILES:
                if profile.resume and os.path.isfile(profile.resume.path):
                    os.remove(profile.resume.path)
                profile.resume = request.FILES['resume']
                profile.save()

            # Update education details
            education_data = {
                'education': request.data.get('education'),
                'specilization': request.data.get('specilization'),
                'college': request.data.get('college'),
                'completed': request.data.get('completed'),
                'mark': request.data.get('mark')
            }

            edu_record, created = Education.objects.get_or_create(user=user, defaults=education_data)
            if not created:
                edu_serializer = EducationSerializer(edu_record, data=education_data, partial=True)
                if edu_serializer.is_valid():
                    edu_serializer.save()
                else:
                    return Response({"status": "error", "message": edu_serializer.errors},
                                    status=status.HTTP_400_BAD_REQUEST)

            return Response({"status": "success", "message": "Profile updated successfully"},
                            status=status.HTTP_200_OK)

        except Candidate.DoesNotExist:
            return Response({"status": "error", "message": "Profile not found"},
                            status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({"status": "error", "message": str(e)},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)



class UserDetails(APIView):
    """Retrieve details of the authenticated user."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        """
        Fetch user details with additional candidate/employer data if applicable.

        Args:
            request: HTTP request with authenticated user.

        Returns:
            Response: User data with optional candidate/employer details.
        """
        user = User.objects.get(id=request.user.id)
        data = UserSerializer(user).data
        if user.user_type == 'candidate':
            candidate = Candidate.objects.get(user=user)
            candidate = CandidateSerializer(candidate).data
            user_data = candidate
            content = {'data': data, 'user_data': user_data}
        elif user.user_type == 'employer':
            employer = Employer.objects.get(user=user)
            employer = EmployerSerializer(employer).data
            user_data = employer
            content = {'data': data, 'user_data': user_data}
        else:
            content = {'data': data}
        return Response(content)

class CandidateRegisterView(APIView):
    """Handle candidate registration and OTP sending."""
    permission_classes = []

    def post(self, request):
        """
        Register a new candidate and send an OTP for email verification.

        Args:
            request: HTTP request with candidate registration data (e.g., email).

        Returns:
            Response: Success message with email or error details.
        """
        email = request.data.get('email')
        if User.objects.filter(email=email).exists():
            return Response({"message": "User with this email is already exist"},
                            status=status.HTTP_203_NON_AUTHORITATIVE_INFORMATION)

        serializer = CandidateRegisterSerializer(data=request.data)
        if serializer.is_valid():
            try:
                user = serializer.save(is_active=False)
                Candidate.objects.get_or_create(user=user)
                Education.objects.get_or_create(user=user)
                send_otp_via_mail(user.email, user.otp)
                response_data = {
                    'message': 'OTP sent successfully.',
                    'email': user.email,
                }
                return Response(response_data, status=status.HTTP_200_OK)
            except Exception as e:
                return Response({'error': 'Internal Server Error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        else:
            return Response({"message": "error"}, status=status.HTTP_400_BAD_REQUEST)

class CandidateLoginView(APIView):
    """Handle candidate login and JWT token generation."""
    permission_classes = []

    def post(self, request):
        """
        Authenticate a candidate and return access/refresh tokens.

        Args:
            request: HTTP request with email and password.

        Returns:
            Response: Candidate details with tokens or error message.
        """
        email = request.data.get('email')
        password = request.data.get('password')

        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            return Response({"message": "Invalid email address!"}, status=status.HTTP_203_NON_AUTHORITATIVE_INFORMATION)

        if not user.is_active:
            return Response({"message": "Your account is inactive!"}, status=status.HTTP_203_NON_AUTHORITATIVE_INFORMATION)

        if not user.user_type == 'candidate':
            return Response({"message": "Only candidates can login!"}, status=status.HTTP_203_NON_AUTHORITATIVE_INFORMATION)

        user = authenticate(username=email, password=password)
        if user is None:
            return Response({"message": "Incorrect Password!"}, status=status.HTTP_203_NON_AUTHORITATIVE_INFORMATION)

        try:
            candidate = Candidate.objects.get(user=user)
            candidate = CandidateSerializer(candidate).data
            user_data = candidate
        except Candidate.DoesNotExist:
            return Response({"message": "something went Wrong"}, status=status.HTTP_203_NON_AUTHORITATIVE_INFORMATION)

        refresh = RefreshToken.for_user(user)
        refresh["name"] = str(user.full_name)
        access_token = str(refresh.access_token)
        refresh_token = str(refresh)
        content = {
            'email': user.email,
            'name': user.full_name,
            'user_id': user.id,
            'access_token': access_token,
            'refresh_token': refresh_token,
            'isAdmin': user.is_superuser,
            'user_type': user.user_type,
            'user_data': user_data
        }
        return Response(content, status=status.HTTP_200_OK)





logger = logging.getLogger(__name__)

User = get_user_model()

class AuthEmployerView(APIView):
    """Handle employer authentication via Google OAuth."""
    permission_classes = [AllowAny]

    def post(self, request):
        """
        Authenticate an employer using Google OAuth and return tokens.

        Args:
            request: HTTP request with Google credential or client_id.

        Returns:
            Response: Employer details with tokens or error message.
        """
        GOOGLE_CLIENT_ID = "718921547648-htg9q59o6ka7j7jsp45cc4dai6olfqs5.apps.googleusercontent.com"
        credential = request.data.get('credential') or request.data.get('client_id')

        logger.debug(f"Received data: {request.data}")

        if not credential:
            logger.error("No Google credential provided")
            return Response(
                {"error": "Google credential is required"},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            google_request = requests.Request()
            user_info = id_token.verify_oauth2_token(
                credential, google_request, GOOGLE_CLIENT_ID
            )
            email = user_info.get('email')
            if not email:
                logger.error("No email in Google token")
                return Response(
                    {"error": "Invalid token: No email provided"},
                    status=status.HTTP_400_BAD_REQUEST
                )
        except ValueError as e:
            logger.error(f"Token verification failed: {e}")
            return Response(
                {"error": f"Invalid token: {str(e)}"},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            logger.error(f"Unexpected error during token verification: {e}")
            return Response(
                {"error": "An unexpected error occurred"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

        try:
            user, created = User.objects.get_or_create(
                email=email,
                defaults={
                    'full_name': user_info.get('name', ''),
                    'user_type': 'employer',
                    'is_active': True,
                    'is_email_verified': True,
                }
            )

            if created:
                profile_picture = user_info.get('picture', '')
                Employer.objects.create(
                    user=user,
                    profile_pic=profile_picture,
                    completed=False
                )
        except Exception as e:
            logger.error(f"User creation/retrieval failed: {e}")
            return Response(
                {"error": "Failed to create or retrieve user"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

        if not user.is_active:
            return Response(
                {"message": "Your account is inactive!"},
                status=status.HTTP_403_FORBIDDEN
            )
        if user.user_type != 'employer':
            return Response(
                {"message": "Only employers can login!"},
                status=status.HTTP_403_FORBIDDEN
            )

        try:
            employer = Employer.objects.get(user=user)
            employer_data = EmployerSerializer(employer).data

            if not employer.is_approved_by_admin:
                return Response(
                    {"message": "Your account is not yet approved by the admin."},
                    status=status.HTTP_403_FORBIDDEN
                )
        except Employer.DoesNotExist:
            logger.error(f"Employer not found for user - {user.email}")
            return Response(
                {"message": "Employer not found"},
                status=status.HTTP_404_NOT_FOUND
            )

        refresh = RefreshToken.for_user(user)
        refresh["name"] = str(user.full_name)
        access_token = str(refresh.access_token)
        refresh_token = str(refresh)

        content = {
            'email': user.email,
            'user_id': user.id,
            'name': user.full_name,
            'access_token': access_token,
            'refresh_token': refresh_token,
            'isAdmin': user.is_superuser,
            'user_type': user.user_type,
            'user_data': {
                'id': employer.id,
                'completed': employer.completed,
                'profile_pic': employer_data.get('profile_pic'),
                'phone': employer_data.get('phone'),
                'isAdmin': employer_data.get('isAdmin', False),
            },
        }
        logger.debug(f"Auth response for {user.email}: {content}")
        return Response(content, status=status.HTTP_200_OK)
class AuthCandidateView(APIView):
    """Handle candidate authentication via Google OAuth."""
    permission_classes = [AllowAny]

    def post(self, request):
        """
        Authenticate a candidate using Google OAuth and return tokens.

        Args:
            request: HTTP request with Google client_id.

        Returns:
            Response: Candidate details with tokens or error message.
        """
        GOOGLE_AUTH_API = "718921547648-htg9q59o6ka7j7jsp45cc4dai6olfqs5.apps.googleusercontent.com"
        email = None
        try:
            google_request = requests.Request()
            user_info = id_token.verify_oauth2_token(
                request.data['client_id'], google_request, GOOGLE_AUTH_API
            )
            email = user_info['email']
        except Exception as e:
            return Response({"error": "Invalid token or user information"}, status=status.HTTP_400_BAD_REQUEST)

        if not User.objects.filter(email=email).exists():
            user = User.objects.create(
                full_name=user_info['name'],
                email=email,
                user_type='candidate',
                is_active=True,
                is_email_verified=True
                
            )
            candidate = Candidate.objects.create(user=user)
            user.save()
            candidate.save()

        user = User.objects.get(email=email)
        if not user.is_active:
            return Response({"message": "Your account is inactive!"}, status=status.HTTP_203_NON_AUTHORITATIVE_INFORMATION)
        elif user.user_type != 'candidate':
            return Response({"message": "Only candidates can login!"}, status=status.HTTP_203_NON_AUTHORITATIVE_INFORMATION)
        else:
            try:
                candidate = Candidate.objects.get(user=user)
                candidate = CandidateSerializer(candidate).data
                user_data = candidate
            except Candidate.DoesNotExist:
                return Response({"message": "Something went wrong"}, status=status.HTTP_203_NON_AUTHORITATIVE_INFORMATION)

        refresh = RefreshToken.for_user(user)
        refresh["name"] = str(user.full_name)
        access_token = str(refresh.access_token)
        refresh_token = str(refresh)
        content = {
            'user_id': user.id,
            'email': user.email,
            'name': user.full_name,
            'access_token': access_token,
            'refresh_token': refresh_token,
            'isAdmin': user.is_superuser,
            'user_type': user.user_type,
            'user_data': user_data
        }
        return Response(content, status=status.HTTP_200_OK)

class CandidateProfileCreation(APIView):
    """Create or update a candidate's profile."""
    permission_classes = [AllowAny]

    def post(self, request):
        """
        Create or update candidate profile with education details.

        Args:
            request: HTTP request with profile and education data.

        Returns:
            Response: Success message with serialized data or error details.
        """
        user = request.user
        candidate, created = Candidate.objects.get_or_create(user=user)

        serializer = CandidateProfileSerializer(candidate, data=request.data, partial=True)

        if serializer.is_valid():
            serializer.save()

            # Update or create education instance
            education, created = Education.objects.get_or_create(user=user)
            education.education = request.data.get('education')
            education.college = request.data.get('college')
            education.specilization = request.data.get('specilization')
            education.completed = request.data.get('completed')
            education.mark = request.data.get('mark')
            education.save()

            return Response({"message": "Profile updated successfully.", "data": serializer.data},
                            status=status.HTTP_200_OK)
        else:
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

# !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!! VERIFY OTP AND RESEND OTP !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
# !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!! FORGOT RESET PASSWORD !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!

class ForgotPassView(APIView):
    """Handle forgot password OTP sending."""
    permission_classes = []

    def post(self, request):
        """
        Send an OTP to the user's email for password reset.

        Args:
            request: HTTP request with email.

        Returns:
            Response: Success message with email or error details.
        """
        email = request.data.get('email')
        if not email:
            return Response({"message": "Email is required."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            logger.info(f"Received forgot password request for email: {email}")

            if not User.objects.filter(email=email).exists():
                logger.warning(f"User with email {email} does not exist.")
                return Response({"message": "Invalid email address."}, status=status.HTTP_203_NON_AUTHORITATIVE_INFORMATION)

            if not User.objects.filter(email=email, is_active=True).exists():
                logger.warning(f"User with email {email} is blocked.")
                return Response({"message": "Your account is blocked by the admin."},
                                status=status.HTTP_203_NON_AUTHORITATIVE_INFORMATION)

            send_otp_via_mail(email)
            logger.info(f"OTP sent to {email}.")
            return Response({"message": "OTP has been sent to your email.", "email": email},
                            status=status.HTTP_200_OK)

        except Exception as e:
            logger.error(f"Error processing forgot password request: {e}")
            return Response({"message": "Error processing your request."}, status=status.HTTP_400_BAD_REQUEST)

class ResetPassword(APIView):
    """Handle password reset with new password."""
    permission_classes = []

    def post(self, request):
        """
        Reset the user's password after OTP verification.

        Args:
            request: HTTP request with email and new password.

        Returns:
            Response: Success message or error details.
        """
        email = request.data.get('email')
        password = request.data.get('password')

        if not email or not password:
            return Response({"error": "Email and password are required."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            user = User.objects.get(email=email)
            user.set_password(password)
            user.save()
            logger.info(f"Password reset successfully for user: {email}.")
            return Response({"message": "Password reset successfully."}, status=status.HTTP_200_OK)
        except User.DoesNotExist:
            logger.warning(f"User with email {email} not found.")
            return Response({"error": "User not found."}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.error(f"Error resetting password: {e}")
            return Response({"error": "Internal Server Error."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class OtpVarificationView(APIView):
    """Handle OTP verification for user activation."""
    permission_classes = []

    def post(self, request):
        """
        Verify the OTP and activate the user account.

        Args:
            request: HTTP request with email and OTP.

        Returns:
            Response: Success message with email or error details.
        """
        serializer = OtpVerificationSerializer(data=request.data)
        if not serializer.is_valid():
            logger.warning(f"Invalid OTP verification request: {serializer.errors}")
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        email = serializer.validated_data.get('email')
        entered_otp = serializer.validated_data.get('otp')

        try:
            user = User.objects.get(email=email)
            logger.info(f"Stored OTP: {user.otp}, Entered OTP: {entered_otp}")
            if user.otp == entered_otp:
                user.is_active = True
                user.save()
                logger.info(f"OTP verified successfully for user: {email}.")
                return Response({"message": "User registered and verified successfully", "email": email},
                                status=status.HTTP_200_OK)
            else:
                logger.warning(f"Invalid OTP for user: {email}.")
                return Response({'error': 'Invalid OTP, Please check your email and verify'},
                                status=status.HTTP_400_BAD_REQUEST)
        except User.DoesNotExist:
            logger.warning(f"User with email {email} not found.")
            return Response({'error': 'User not found or already verified'}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.error(f"Error verifying OTP: {e}")
            return Response({'error': 'Internal Server Error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class ResendOtpView(APIView):
    """Handle resending OTP to user's email."""
    permission_classes = []

    def post(self, request):
        """
        Resend OTP to the user's email.

        Args:
            request: HTTP request with email.

        Returns:
            Response: Success message with email or error details.
        """
        email = request.data.get('email')
        if not email:
            return Response({"error": "Email is required."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            logger.info(f"Resending OTP to email: {email}.")
            resend_otp_via_mail(email)
            return Response({'message': 'OTP sent successfully.', 'email': email}, status=status.HTTP_200_OK)
        except Exception as e:
            logger.error(f"Error resending OTP: {e}")
            return Response({'error': 'Internal Server Error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class AdminLoginView(APIView):
    """Handle admin login and JWT token generation."""
    permission_classes = [AllowAny]

    def post(self, request):
        """
        Authenticate an admin and return access/refresh tokens.

        Args:
            request: HTTP request with email and password.

        Returns:
            Response: Admin details with tokens or error message.
        """
        try:
            email = request.data.get('email')
            password = request.data.get('password')
            if not email or not password:
                raise ParseError("Both email and password are required.")
        except KeyError:
            raise ParseError("Both email and password are required.")

        try:
            user = User.objects.get(email=email)
            if not user.is_superuser:
                return Response({"message": "Only Admin can login"}, status=status.HTTP_403_FORBIDDEN)
        except User.DoesNotExist:
            return Response({"message": "Invalid email address."}, status=status.HTTP_400_BAD_REQUEST)

        user = authenticate(username=email, password=password)
        if user is None:
            return Response({"message": "Invalid email or password."}, status=status.HTTP_400_BAD_REQUEST)

        refresh = RefreshToken.for_user(user)
        refresh["name"] = str(user.full_name)
        access_token = str(refresh.access_token)
        refresh_token = str(refresh)

        content = {
            'email': user.email,
            'name': user.full_name,
            'access_token': access_token,
            'refresh_token': refresh_token,
            'isAdmin': user.is_superuser,
            'user_type': user.user_type,
        }
        return Response(content, status=status.HTTP_200_OK)