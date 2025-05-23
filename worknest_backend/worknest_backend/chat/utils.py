# chat/utils.py
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
import json
from datetime import datetime

def send_notification(user_id, message, sender_id=None, chat_key=None):
    """
    Send a notification to a specific user
    
    Args:
        user_id (str): ID of the user to send notification to
        message (str): Notification message content
        sender_id (str, optional): ID of the sender
        chat_key (str, optional): Chat session key if related to a chat
    """
    channel_layer = get_channel_layer()
    notification_group = f"notifications_{user_id}"
    
    notification_data = {
        'type': 'notification',
        'message': message,
        'timestamp': datetime.now().isoformat(),
        'id': f"notif_{int(datetime.now().timestamp() * 1000)}",  # Unique ID for the notification
    }
    
    if sender_id:
        notification_data['sender_id'] = sender_id
    
    if chat_key:
        notification_data['chat_key'] = chat_key
    
    async_to_sync(channel_layer.group_send)(
        notification_group,
        {
            'type': 'send_notification',
            'data': notification_data
        }
    )
    
    return notification_data