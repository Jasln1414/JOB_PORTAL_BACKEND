from django.urls import path
from . import views

urlpatterns = [
    path('schedule/', views.InterviewSheduleView.as_view(), name='schedule'),
    path('cancelApplication/', views.CancelApplicationView.as_view(), name='cancel_application'),  
    path('schedules/', views.getShedulesView.as_view(), name='schedules'),
    path('status/<int:interview_id>/', views.InterviewStatusView.as_view(), name='status'),
    path('link/<int:interview_id>/', views.InterviewLinkSend.as_view(), name='status'),
    
    path('test/', views.testView, name='test'),

    path('interviewjoinstatus/<int:interview_id>/',views.InterviewJoinStatus.as_view(), name='status'),



   
]