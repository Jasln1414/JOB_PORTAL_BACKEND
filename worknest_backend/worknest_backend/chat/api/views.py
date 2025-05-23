"""Module for handling chat-related API views.

This module provides API endpoints for managing chat messages, chat rooms,
notifications, and media uploads. It includes views for authenticated users
to retrieve messages, mark notifications as read, upload media to Cloudinary,
and manage unread message counts.
"""

from rest_framework import generics, status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404
import cloudinary.uploader  # type: ignore

from chat.models import ChatMessage, ChatRoom, Notifications
from user_account.models import Candidate, Employer
from chat.api.serializer import ChatMessageSerializer, ChatRoomSerializer


class ChatMessagesAPIView(APIView):
    """View to retrieve and manage chat messages between a candidate and employer.

    This view allows authenticated users to fetch chat messages from a specific
    chat room and mark messages as read.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request, candidate_id, employer_id):
        """Handle GET request to retrieve chat messages.

        Args:
            request: HTTP request object.
            candidate_id (int): ID of the candidate.
            employer_id (int): ID of the employer.

        Returns:
            Response: JSON response with chat messages or error message.
        """
        try:
            chatroom = get_object_or_404(ChatRoom,
                                         candidate_id=candidate_id,
                                         employer_id=employer_id)
            chatmessages = ChatMessage.objects.filter(
                chatroom=chatroom
            ).order_by('timestamp')

            self.update_unread_messages(request.user.id, candidate_id,
                                        employer_id)

            serializer = ChatMessageSerializer(chatmessages, many=True)
            return Response(serializer.data, status=status.HTTP_200_OK)

        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_404_NOT_FOUND)

    def update_unread_messages(self, user_id, candidate_id, employer_id):
        """Mark messages as read when the recipient views them.

        Args:
            user_id (int): ID of the current user.
            candidate_id (int): ID of the candidate.
            employer_id (int): ID of the employer.
        """
        try:
            is_candidate = str(user_id) == str(candidate_id)
            chatroom = ChatRoom.objects.get(
                candidate_id=candidate_id,
                employer_id=employer_id
            )

            messages = ChatMessage.objects.filter(
                chatroom=chatroom,
                sendername__isnull=False,
                is_read=False,
            )

            if is_candidate:
                messages.exclude(sendername=candidate_id).update(is_read=True)
            else:
                messages.exclude(sendername=employer_id).update(is_read=True)

        except ChatRoom.DoesNotExist as e:
            print(f"Error updating unread messages: ChatRoom not found - {e}")
        except Exception as e:
            print(f"Error updating unread messages: {e}")


class ChatsView(APIView):
    """View to retrieve chat rooms for the authenticated user.

    This view returns chat rooms associated with the user, whether they are a
    candidate or an employer.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        """Handle GET request to retrieve user's chat rooms.

        Args:
            request: HTTP request object.

        Returns:
            Response: JSON response with chat rooms or error message.
        """
        user = request.user
        try:
            candidate = Candidate.objects.get(user=user)
            chatroom = ChatRoom.objects.filter(candidate=candidate)
        except Candidate.DoesNotExist:
            try:
                employer = Employer.objects.get(user=user)
                chatroom = ChatRoom.objects.filter(employer=employer)
            except Employer.DoesNotExist:
                return Response(
                    {'error': 'User is neither a candidate nor an employer'},
                    status=status.HTTP_400_BAD_REQUEST
                )

        serializer = ChatRoomSerializer(chatroom, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class NotificationStatusView(APIView):
    """View to mark notifications as read for the authenticated user."""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        """Handle POST request to mark notifications as read.

        Args:
            request: HTTP request object.

        Returns:
            Response: JSON response with the number of notifications marked
                      as read or an error message.
        """
        user = request.user
        try:
            notifications = Notifications.objects.filter(
                user=user,
                is_read=False
            )
            updated_count = notifications.update(is_read=True)

            return Response(
                {
                    'message': (f'Successfully marked {updated_count} '
                                'notifications as read'),
                    'marked_read': updated_count
                },
                status=status.HTTP_200_OK
            )

        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class MediaUploadView(generics.CreateAPIView):
    """View to upload media files (images and videos) to Cloudinary."""

    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        """Handle POST request to upload media files.

        Args:
            request: HTTP request containing the file to upload.
            *args: Additional positional arguments.
            **kwargs: Additional keyword arguments.

        Returns:
            Response: JSON response with the file URL or an error message.
        """
        try:
            file = request.FILES.get("file")
            if not file:
                return Response(
                    {"error": "No file was submitted"},
                    status=status.HTTP_400_BAD_REQUEST
                )

            content_type = file.content_type
            if content_type.startswith('image/'):
                upload_result = cloudinary.uploader.upload(file)
                file_url = upload_result.get('secure_url')
            elif content_type.startswith('video/'):
                upload_result = cloudinary.uploader.upload_large(
                    file,
                    resource_type="video"
                )
                file_url = upload_result.get('secure_url')
            else:
                return Response(
                    {"error": "Unsupported file type"},
                    status=status.HTTP_400_BAD_REQUEST
                )

            return Response(
                {"file_url": file_url},
                status=status.HTTP_200_OK
            )

        except Exception as e:
            return Response(
                {"error": "Failed to upload media", "details": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class NotificationCountView(APIView):
    """View to retrieve unread message count and recent notifications.

    This view returns the count of unread messages and the most recent unread
    notifications for a user (candidate or employer).
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        """Handle GET request to retrieve unread message count and notifications.

        Args:
            request: HTTP request object with user_id parameter.

        Returns:
            Response: JSON response with unread count and recent notifications
                      or an error message.
        """
        user_id = request.GET.get('user_id')
        if not user_id:
            return Response(
                {'error': 'user_id parameter is required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            try:
                candidate = Candidate.objects.get(id=user_id)
                chatrooms = ChatRoom.objects.filter(candidate=candidate)
                username = candidate.user.get_username()
            except Candidate.DoesNotExist:
                employer = Employer.objects.get(id=user_id)
                chatrooms = ChatRoom.objects.filter(employer=employer)
                username = employer.user.get_username()

            unread_count = ChatMessage.objects.filter(
                chatroom__in=chatrooms,
                is_read=False
            ).exclude(sendername=username).count()

            notifications = ChatMessage.objects.filter(
                chatroom__in=chatrooms,
                is_read=False
            ).exclude(sendername=username).order_by('-timestamp')[:5]

            notification_data = [
                {
                    'id': msg.id,
                    'sendername': msg.sendername,
                    'message': msg.message,
                    'timestamp': (msg.timestamp.isoformat()
                                  if msg.timestamp else None),
                    'chatroom': msg.chatroom.id,
                    'is_read': msg.is_read
                } for msg in notifications
            ]

            return Response(
                {
                    'unread_count': unread_count,
                    'notifications': notification_data
                },
                status=status.HTTP_200_OK
            )

        except (Candidate.DoesNotExist, Employer.DoesNotExist):
            return Response(
                {'error': 'User profile not found'},
                status=status.HTTP_404_NOT_FOUND
            )


class MarkMessagesReadView(APIView):
    """View to mark all messages in a chat room as read."""

    permission_classes = [IsAuthenticated]

    def post(self, request, candidate_id, employer_id):
        """Handle POST request to mark messages as read.

        Args:
            request: HTTP request object.
            candidate_id (int): ID of the candidate.
            employer_id (int): ID of the employer.

        Returns:
            Response: JSON response with success status or error message.
        """
        try:
            chatroom = ChatRoom.objects.get(
                candidate_id=candidate_id,
                employer_id=employer_id
            )
            ChatMessage.objects.filter(
                chatroom=chatroom,
                is_read=False
            ).update(is_read=True)
            return Response({'status': 'success'})
        except ChatRoom.DoesNotExist:
            return Response(
                {'error': 'Chat room not found'},
                status=status.HTTP_404_NOT_FOUND
            )