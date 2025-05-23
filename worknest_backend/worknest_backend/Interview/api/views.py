from modulefinder import test
from django.http import HttpResponse
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .serializer import SheduleInterviewSerializer, InterviewSheduleSerializer
from user_account.models import Employer, Candidate, User
from Interview.models import InterviewShedule
from Empjob.models import Jobs, ApplyedJobs
from chat.models import Notifications
from rest_framework.permissions import IsAuthenticated, AllowAny
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
from Interview.tasks import send_shedule_mail, cancell_shedule_mail
from datetime import datetime




class InterviewSheduleView(APIView):
    permission_classes=[IsAuthenticated]
    def post(self, request):
        print("step1")
        user = request.user
        employer = Employer.objects.get(user=user)
        candidate_id = request.data.get('candidate')
        job_id = request.data.get('job')
        date = request.data.get('date')
       
        try:
            candidate=Candidate.objects.get(id=candidate_id)
            job=Jobs.objects.get(id=job_id)
            email=candidate.user.email
            title=job.title
            username = employer.user.full_name
            print(email,date,user,title)
        except Candidate.DoesNotExist:
            print("error")
        
        
        print(request.data)
        serializer = SheduleInterviewSerializer(data=request.data, context={'request': request})
        if serializer.is_valid():
            serializer.save()
            send_shedule_mail.delay(email,date,username,title)
            print(serializer.data)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)














class CancelApplicationView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        user = request.user
        try:
            employer = Employer.objects.get(user=user)
        except Employer.DoesNotExist:
            return Response({"message": "Employer not found"}, status=status.HTTP_404_NOT_FOUND)

        candidate_id = request.data.get('candidate_id')
        job_id = request.data.get('job_id')

        try:
            job = Jobs.objects.get(id=job_id)
            candidate = Candidate.objects.get(id=candidate_id)
            
            # Get all active interviews for this job-candidate pair
            applications = InterviewShedule.objects.filter(
                job=job_id,
                candidate=candidate_id,
                active=True
            )
            
            if not applications.exists():
                return Response({"message": "No active interview found"}, status=status.HTTP_404_NOT_FOUND)
                
            applyed = ApplyedJobs.objects.get(candidate=candidate_id, job=job_id)
            email = candidate.user.email
            username = employer.user.full_name
            
            # Get the most recent interview for notification purposes
            latest_interview = applications.order_by('-date').first()
            date = latest_interview.date if latest_interview else None
            title = job.title

            # Cancel all active interviews
            applications.update(active=False, status="Canceled")

        except (Jobs.DoesNotExist, Candidate.DoesNotExist) as e:
            print(f"Error: {str(e)}")
            return Response({"message": "Candidate or Job not found"}, status=status.HTTP_404_NOT_FOUND)
        except ApplyedJobs.DoesNotExist:
            print("No application found for this candidate and job")
            # Still proceed with cancelling interviews even if application record is missing
            pass

        # Update application status if it exists
        if 'applyed' in locals():
            applyed.status = 'Interview Cancelled'
            applyed.save()
        
        message = f'Interview for {job.title} has been cancelled.'
        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            f'notification_{candidate_id}',
            {
                'type': 'notify_message',
                'message': {
                    'text': message,
                    'sender': "InterviewSystem",
                    'is_read': False,
                    'timestamp': datetime.now().isoformat(),
                    'chat_id': None
                },
                'unread_count': 1
            }
        )
        
        try:
            if date:  # Only send email if we have a date
                cancell_shedule_mail.delay(email, date, username, title)
                print("Cancel email task queued successfully")
        except Exception as e:
            print(f"Warning: Failed to queue cancel email task: {e}")
            
        return Response({"message": "Interview cancelled successfully"}, status=status.HTTP_200_OK)














class getShedulesView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        print(f"getShedulesView: User {user}")
        try:
            try:
                candidate = Candidate.objects.get(user=user)
                shedules = InterviewShedule.objects.filter(candidate=candidate)
            except Candidate.DoesNotExist:
                employer = Employer.objects.get(user=user)
                shedules = InterviewShedule.objects.filter(employer=employer)
        
            print(f"Schedules...........................: {shedules}")
            serializer = InterviewSheduleSerializer(shedules, many=True)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except (Candidate.DoesNotExist, Employer.DoesNotExist):
            return Response({"message": "User is neither a candidate nor an employer"}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            print(f"Error: {e}")
            return Response({"message": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class InterviewView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        print("InterviewView: Processing POST request", request.data)
        roomId = request.data.get("roomId")
        interviewId = request.data.get("interviewId")
        try:
            interview = InterviewShedule.objects.get(id=interviewId)
            candidate_id = interview.candidate.user.id
            print(f"Interview: {interview}, Candidate ID: {candidate_id}")
            message = f'Interview call - {roomId} - {interviewId}'
            channel_layer = get_channel_layer()
            async_to_sync(channel_layer.group_send)(
                f'notification_{candidate_id}',
                {
                    'type': 'notify_message',
                    'message': {
                        'text': message,
                        'sender': "InterviewSystem",
                        'is_read': False,
                        'timestamp': datetime.now().isoformat(),
                        'chat_id': None
                    },
                    'unread_count': 1
                }
            )
            return Response({"message": "Notification sent"}, status=status.HTTP_200_OK)
        except InterviewShedule.DoesNotExist:
            print("Interview not found")
            return Response({"message": "No interview data found"}, status=status.HTTP_404_NOT_FOUND)

class InterviewStatusView(APIView):
    permission_classes = [AllowAny]

    def post(self, request, interview_id):
        action = request.data.get('action')
        print(f"InterviewStatusView: Processing POST request for interview ID {interview_id} with action {action}")
        try:
            interview = InterviewShedule.objects.get(id=interview_id)
            job = Jobs.objects.get(id=interview.job_id)
            candidate = Candidate.objects.get(id=interview.candidate_id)
            user = User.objects.get(id=candidate.user.id)
            applyedjobs = ApplyedJobs.objects.get(candidate=candidate, job=job)
            print(f"Interview: {interview}, Job: {job}, Candidate: {candidate}, ApplyedJobs: {applyedjobs}")
        except (Jobs.DoesNotExist, Candidate.DoesNotExist, InterviewShedule.DoesNotExist, ApplyedJobs.DoesNotExist):
            print("Required data not found")
            return Response({"message": "Something went wrong"}, status=status.HTTP_404_NOT_FOUND)

        if action == 'Accepted':
            interview.status = 'Selected'
            interview.selected = True
            message = f"Congratulations! You have been selected for the interview for the job {job.title}."
            applyedjobs.status = 'Accepted'
        elif action == 'Rejected':
            interview.status = 'Rejected'
            interview.selected = True
            message = f'"Sorry, you have been rejected for the interview for the job {job.title}."'
            applyedjobs.status = 'Rejected'
        else:
            return Response({"message": "Invalid action"}, status=status.HTTP_400_BAD_REQUEST)
        
        notifications = Notifications.objects.create(user = user,message = message)
        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            f'notification_{user.id}',
            {
                'type': 'notify_message',
                'message': {
                    'text': message,
                    'sender': "employer",
                    'is_read': False,
                    'timestamp': datetime.now().isoformat(),
                    'chat_id': None
                },
                'unread_count': 1
            }
        )

        interview.save()
        applyedjobs.save()
        return Response({"message": "Status changed"}, status=status.HTTP_200_OK)

def testView(request):
    test.delay()
    return HttpResponse("Done")
