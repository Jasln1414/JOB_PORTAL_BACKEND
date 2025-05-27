from django.urls import path
from . import views

urlpatterns = [
    path('schedule/', views.InterviewSheduleView.as_view(), name='schedule'),
    path('cancelApplication/', views.CancelApplicationView.as_view(), name='cancel_application'),  # Fixed typo: cancell -> cancel
    path('schedules/', views.getShedulesView.as_view(), name='schedules'),
    path('interviewCall/', views.InterviewView.as_view(), name='makeInterview'),
    path('status/<int:interview_id>/', views.InterviewStatusView.as_view(), name='status'),
    path('api/interview/schedules/<int:interview_id>/', views.InterviewSheduleStatusUpdateView.as_view(), name='interview-status-update'),
    path('test/', views.testView, name='test'),
]