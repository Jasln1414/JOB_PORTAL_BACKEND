from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.exceptions import ParseError

from user_account.api.utiliti_mail import resend_otp_via_mail, send_otp_via_mail
from .serializer import *
from .utiliti_mail import *

from Empjob.api.serializer import *
from user_account.models import *
from Empjob.models import *
from django.contrib.auth import authenticate
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework.permissions import IsAuthenticated, AllowAny
from google.oauth2 import id_token # type: ignore
from google.auth.transport import requests # type: ignore

from django.views.decorators.csrf import csrf_exempt
from django.core.exceptions import ValidationError
from django.middleware.csrf import get_token
from rest_framework import status

from rest_framework.permissions import IsAuthenticated
from django.utils.decorators import method_decorator

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
          
            
            response_data = {
                "access_token": access_token,
                "refresh_token": refresh_token,
                "user_data": {
                    "id": employer.id,
                    "user_id": user.id,
                    "email": user.email,
                    "completed": employer.completed,  
                    "profile_pic": employer_data.get('profile_pic'),
                   
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



@method_decorator(csrf_exempt, name='dispatch')
class EmployerProfileUpdateView(APIView):
    permission_classes = [IsAuthenticated]

    def put(self, request):
       

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
class EmployerProfileCreatView(APIView):
    permission_classes = [IsAuthenticated]
    def post(self,request):
        user = request.user
        employer,created = Employer.objects.get_or_create(user=user)
        serializer = EmployerProfileSerializer(employer,data=request.data, partial=True)
        if serializer.is_valid():
           
            employer.is_verified=True 
            employer.completed=True
            serializer.save()
            employer.save()
           
           
            
            return Response({"message": "Profile updated successfully.","data":serializer.data}, status=status.HTTP_200_OK)
        else:
            print(serializer.errors)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
# !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!! CANDIDATE !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!

class ProfileUpdateView(APIView):
    """Update a candidate's profile details."""
    permission_classes = [IsAuthenticated]

    def put(self, request):
       
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













class AuthEmployerView(APIView):
    """Handle employer authentication via Google OAuth."""
    permission_classes = [AllowAny]

    def post(self, request):
        GOOGLE_AUTH_API = settings.GOOGLE_CLIENT_ID
        credential = request.data.get('credential') or request.data.get('client_id')

        logger.debug(f"Received data: {request.data}")

        if not credential:
            logger.error("No Google credential provided")
            return Response(
                {"error": "Google credential is required"},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Verify the Google OAuth token
        try:
            google_request = requests.Request()
            user_info = id_token.verify_oauth2_token(
                credential, google_request,  GOOGLE_AUTH_API 
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

        # Get or create user
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
                logger.info(f"Created new user: {email}")
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

        # Get or create Employer profile
        try:
            employer = Employer.objects.get(user=user)
            logger.info(f"Found existing Employer for user {email}")
        except Employer.DoesNotExist:
            profile_picture = user_info.get('picture', '')
            employer = Employer.objects.create(
                user=user,
                profile_pic=profile_picture,
                completed=False
            )
            logger.info(f"Created missing Employer profile for user {email}")

        # Serialize employer data
        employer_data = EmployerSerializer(employer).data

        # Check admin approval
        if not employer.is_approved_by_admin:
            return Response(
                {"message": "Your account is not yet approved by the admin."},
                status=status.HTTP_403_FORBIDDEN
            )

        # Create JWT tokens
        refresh = RefreshToken.for_user(user)
        refresh["name"] = str(user.full_name)
        access_token = str(refresh.access_token)
        refresh_token = str(refresh)

        # Prepare response data
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
        
        GOOGLE_AUTH_API = settings.GOOGLE_CLIENT_ID
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