# chat/urls.py (updated)
from django.urls import path
from . import views

urlpatterns = [
    path('messages/<int:candidate_id>/<int:employer_id>/', 
         views.ChatMessagesAPIView.as_view(), name='chat-messages'),
    path('chats/', views.ChatsView.as_view(), name='chats'),
    path('upload/', views.MediaUploadView.as_view(), name='media-upload'),
    path('mark-read/<int:candidate_id>/<int:employer_id>/', views.MarkMessagesReadView.as_view(), name='mark-messages-read'),
    path('notifications/count/', views.NotificationCountView.as_view(), name='api-notification-count'),
   
    path('notifications/count/', views.NotificationCountView.as_view(), name='notification-count'),
    path('notificationStatus/', views.NotificationStatusView.as_view(), name='notification-status'),
]


