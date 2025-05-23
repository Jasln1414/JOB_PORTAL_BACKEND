from rest_framework import serializers
from chat.models import ChatMessage, ChatRoom
from user_account.models import Candidate, Employer

class ChatMessageSerializer(serializers.ModelSerializer):
    """Serializer for ChatMessage model."""
    class Meta:
        model = ChatMessage
        fields = ['id', 'chatroom', 'message', 'sendername', 'is_read', 'timestamp', 'file_url','se_id']

class ChatRoomSerializer(serializers.ModelSerializer):
    """Serializer for ChatRoom model with additional user context."""
    candidate_name = serializers.SerializerMethodField()
    employer_name = serializers.SerializerMethodField()
    last_message = serializers.SerializerMethodField()

    class Meta:
        model = ChatRoom
        fields = ['id', 'candidate', 'employer', 'created_at', 'candidate_name', 'employer_name', 'last_message']

    def get_candidate_name(self, obj):
        """Get the candidate's name."""
        return obj.candidate.user.get_username() if obj.candidate and obj.candidate.user else None

    def get_employer_name(self, obj):
        """Get the employer's name."""
        return obj.employer.user.get_username() if obj.employer and obj.employer.user else None

    def get_last_message(self, obj):
        """Get the content of the last message in the chat room."""
        last_msg = ChatMessage.objects.filter(chatroom=obj).order_by('-timestamp').first()
        if last_msg:
            return {
                'message': last_msg.message,
                'sendername': last_msg.sendername,
                'timestamp': last_msg.timestamp.isoformat(),
                'file_url': last_msg.file_url
            }
        return None

















