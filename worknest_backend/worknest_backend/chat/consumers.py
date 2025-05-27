"""Module for WebSocket consumers handling chat and notifications.

This module provides WebSocket consumers for real-time chat functionality
and notification updates. It manages chat rooms, messages, user online status,
and notifications using Django Channels.
"""

import json
import logging
from datetime import datetime

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer
from django.contrib.auth import get_user_model

from chat.models import ChatMessage, ChatRoom, Notifications
from user_account.models import Candidate, Employer

# Configure logging
logger = logging.getLogger(__name__)


class ChatConsumer(AsyncJsonWebsocketConsumer):
    """WebSocket consumer for handling chat functionality.

    Manages real-time chat between candidates and employers, including
    message sending, online status updates, and active user tracking.
    """

    active_users = set()
    online_users = set()

    async def connect(self):
        """Handle WebSocket connection.

        Initializes the chat room, retrieves existing messages, and updates
        user status.
        """
        self.candidate_id = self.scope['url_route']['kwargs']['candidate_id']
        self.employer_id = self.scope['url_route']['kwargs']['employer_id']
        self.user_id = self.scope['url_route']['kwargs']['user_id']
        self.chat_room_name = f'chat_{self.candidate_id}_{self.employer_id}'

        self.candidate = await self.get_candidate_instance(self.candidate_id)
        self.employer = await self.get_employer_instance(self.employer_id)
        if not self.candidate or not self.employer:
            await self.close()
            return

        await self.channel_layer.group_add(self.chat_room_name,
                                          self.channel_name)
        ChatConsumer.active_users.add(str(self.user_id))
        ChatConsumer.online_users.add(str(self.user_id))
        await self.notify_online_status_update()
        await self.notify_active_users_update()
        await self.accept()

        existing_messages = await self.get_existing_messages()
        for message in existing_messages:
            await self.send(text_data=json.dumps(message))

    async def disconnect(self, close_code):
        """Handle WebSocket disconnection.

        Removes the user from the chat room and updates their status.

        Args:
            close_code (int): Code indicating reason for disconnection.
        """
        await self.channel_layer.group_discard(self.chat_room_name,
                                              self.channel_name)
        if hasattr(self, 'user_id'):
            ChatConsumer.active_users.discard(str(self.user_id))
            ChatConsumer.online_users.discard(str(self.user_id))
            await self.notify_online_status_update()
            await self.notify_active_users_update()

    async def receive(self, text_data):
        """Handle incoming WebSocket messages.

        Processes different message types including chat messages, status
        updates, and user list requests.

        Args:
            text_data (str): JSON-encoded message received from the client.
        """
        data = json.loads(text_data)
        message_type = data.get('type')

        if message_type == 'get_active_users':
            await self.send_active_users()
            return
        elif message_type == 'get_online_users':
            await self.send_online_users()
            return
        elif message_type == 'set_status':
            status = data.get('status')
            if status == 'online':
                ChatConsumer.online_users.add(str(self.user_id))
            elif status == 'offline':
                ChatConsumer.online_users.discard(str(self.user_id))
            await self.notify_online_status_update()
            return

        message = data.get('message')
        if not message:
            await self.send(text_data=json.dumps(
                {'error': 'Message content is required'}
            ))
            return

        sendername = data.get('sendername', 'Anonymous')
        sender_id = data.get('sender_id')
        se_id = data.get("se_id")
        reciver_id = data.get('reciverId')
        timestamp = datetime.now().isoformat()
        recipient_id = reciver_id
        is_read = str(recipient_id) in ChatConsumer.active_users
        message_to_save = f"Message received from {sendername}: {message}"
        print("recccccccccc",reciver_id)
        print("savvvvvvvvvvvvvvvvvvv",recipient_id )




        print("rrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrr",message_to_save )



        
        print("recieptyttttttt",recipient_id )
        print("senderrrrrrrrrrrrrrr........................", sendername)
        print("3333333333333333........................",message)
        print("senderrrrrrrrrrrrrrr........................",sender_id)

        await self.save_message(sendername, message, is_read, se_id)
        await self.save_notification(recipient_id, message_to_save)
        await self.send_notification(recipient_id, sendername, message,
                                    sender_id)

        await self.channel_layer.group_send(
            self.chat_room_name,
            {
                'type': 'chat_message',
                'data': {
                    'message': message,
                    'sendername': sendername,
                    'is_read': is_read,
                    'timestamp': timestamp,
                    'se_id': se_id
                }
            }
        )

    async def chat_message(self, event):
        """Send a chat message to the WebSocket client.

        Args:
            event (dict): Event data containing the message details.
        """
        await self.send(text_data=json.dumps(event['data']))

    async def send_active_users(self):
        """Send the list of active users to the WebSocket client."""
        await self.send(text_data=json.dumps({
            'type': 'active_users',
            'users': list(ChatConsumer.active_users)
        }))

    async def send_online_users(self):
        """Send the list of online users to the WebSocket client."""
        await self.send(text_data=json.dumps({
            'type': 'online_users',
            'users': list(ChatConsumer.online_users)
        }))

    async def notify_active_users_update(self):
        """Notify all clients in the chat room of an active users update."""
        await self.channel_layer.group_send(
            self.chat_room_name,
            {
                'type': 'active_users_update',
                'users': list(ChatConsumer.active_users)
            }
        )

    async def notify_online_status_update(self):
        """Notify all clients in the chat room of an online status update."""
        await self.channel_layer.group_send(
            self.chat_room_name,
            {
                'type': 'online_status_update',
                'online_users': list(ChatConsumer.online_users)
            }
        )

    async def active_users_update(self, event):
        """Handle active users update event and send to the client.

        Args:
            event (dict): Event data containing the updated active users list.
        """
        await self.send(text_data=json.dumps({
            'type': 'active_users',
            'users': event['users']
        }))

    async def online_status_update(self, event):
        """Handle online status update event and send to the client.

        Args:
            event (dict): Event data containing the updated online users list.
        """
        await self.send(text_data=json.dumps({
            'type': 'online_users',
            'users': event['online_users']
        }))

    async def send_notification(self, recipient_id, sendername, message,
                               sender_id):
        """Send a notification to the specified recipient.

        Args:
            recipient_id (str): ID of the recipient user.
            sendername (str): Name of the sender.
            message (str): Message content.
            sender_id (str): ID of the sender.
        """

        if not recipient_id or recipient_id == '0' :
        #  or \  str(recipient_id) == str(self.user_id):
            logger.warning(
                f"Invalid recipient ID or same as sender: "
                f"recipient_id={recipient_id}, user_id={self.user_id}"
            )

            print("...................start...........")
            return

        try:
            print("...................end...........")
            await self.channel_layer.group_send(
                f'notification_{recipient_id}',
                {
                    'type': 'notify_message',
                    'message': {
                        'text': f"New message from {sendername}: {message}",
                        'sender': sendername,
                        'sender_id': sender_id,
                        'is_read': False,
                        'timestamp': datetime.now().isoformat(),
                        'chat_id': self.chat_room_name
                    },
                    'unread_count': 1
                }
            )
        except Exception as e:
            logger.error(f"Error sending notification: {str(e)}")

    @database_sync_to_async
    def get_existing_messages(self):
        """Retrieve existing messages for the chat room.

        Returns:
            list: List of message dictionaries.
        """
        try:
            chatroom, _ = ChatRoom.objects.get_or_create(
                candidate=self.candidate,
                employer=self.employer
            )
            messages = ChatMessage.objects.filter(
                chatroom=chatroom
            ).order_by('timestamp')
            return [
                {
                    'message': m.message,
                    'sendername': m.sendername,
                    'is_read': m.is_read,
                    'timestamp': (m.timestamp.isoformat()
                                  if m.timestamp else None)
                } for m in messages
            ]
        except Exception as e:
            logger.error(f"Error retrieving existing messages: {str(e)}")
            return []

    @database_sync_to_async
    def get_candidate_instance(self, candidate_id):
        """Retrieve a candidate instance by ID.

        Args:
            candidate_id (str): ID of the candidate.

        Returns:
            Candidate: Candidate instance or None if not found.
        """
        try:
            return Candidate.objects.get(id=candidate_id)
        except Candidate.DoesNotExist:
            logger.warning(f"Candidate with ID {candidate_id} not found")
            return None

    @database_sync_to_async
    def get_employer_instance(self, employer_id):
        """Retrieve an employer instance by ID.

        Args:
            employer_id (str): ID of the employer.

        Returns:
            Employer: Employer instance or None if not found.
        """
        try:
            return Employer.objects.get(id=employer_id)
        except Employer.DoesNotExist:
            logger.warning(f"Employer with ID {employer_id} not found")
            return None

    @database_sync_to_async
    def save_message(self, sendername, message, is_read, se_id):
        """Save a chat message to the database.

        Args:
            sendername (str): Name of the sender.
            message (str): Message content.
            is_read (bool): Whether the message is read.
            se_id (str): Sender ID.
        """
        try:
            chatroom, _ = ChatRoom.objects.get_or_create(
                candidate=self.candidate,
                employer=self.employer
            )
            ChatMessage.objects.create(
                chatroom=chatroom,
                message=message,
                sendername=sendername,
                is_read=is_read,
                se_id=se_id
            )
        except Exception as e:
            logger.error(f"Error saving message: {str(e)}")

    @database_sync_to_async
    def save_notification(self, user_id, message):
        """Save a notification for a user.

        Args:
            user_id (str): ID of the user to notify.
            message (str): Notification message.

        Returns:
            Notifications: Created notification instance or None if failed.
        """
        try:
            user = get_user_model().objects.get(id=user_id)
            return Notifications.objects.create(user=user, message=message)
        except Exception as e:
            logger.error(f"Error saving notification: {str(e)}")
            return None

    @database_sync_to_async
    def get_unread_notifications_count(self):
        """Retrieve the count of unread notifications for the user.

        Returns:
            int: Number of unread notifications.
        """
        try:
            User = get_user_model()
            user = User.objects.get(id=self.user_id)
            return Notifications.objects.filter(
                user=user,
                is_read=False
            ).count()
        except User.DoesNotExist:
            logger.warning(f"User {self.user_id} not found")
            return 0
        except Exception as e:
            logger.error(f"Error getting unread count: {str(e)}")
            return 0


class NotificationConsumer(AsyncJsonWebsocketConsumer):
    """WebSocket consumer for handling notifications.

    Manages real-time notification updates for a user, including unread counts
    and notification messages.
    """

    async def connect(self):
        """Handle WebSocket connection.

        Adds the user to a notification group and sends initial notification data.
        """
        self.user_id = self.scope['url_route']['kwargs']['user_id']
        self.notification_group_name = f'notification_{self.user_id}'
        await self.channel_layer.group_add(self.notification_group_name,
                                          self.channel_name)
        await self.accept()

        unread_count = await self.get_unread_notifications_count()
        user_notifications = await self.get_user_notifications(self.user_id)

        await self.send(text_data=json.dumps({
            'type': 'initial_data',
            'unread_count': unread_count,
            'notifications': user_notifications
        }))

    async def disconnect(self, close_code):
        """Handle WebSocket disconnection.

        Removes the user from the notification group.

        Args:
            close_code (int): Code indicating reason for disconnection.
        """
        await self.channel_layer.group_discard(self.notification_group_name,
                                              self.channel_name)

    async def notify_message(self, event):
        """Send a notification message to the WebSocket client.

        Args:
            event (dict): Event data containing the notification message.
        """
        message = event['message']
        sender_id = message.get('sender_id')

        # if str(sender_id) == str(self.user_id):
        #     return

        await self.send(text_data=json.dumps({
            'type': 'notification',
            'message': message,
            'unread_count': event['unread_count']
        }))

    @database_sync_to_async
    def get_user_notifications(self, user_id):
        """Retrieve notifications for a user.

        Args:
            user_id (str): ID of the user.

        Returns:
            list: List of notification dictionaries.
        """
        try:
            user = get_user_model().objects.get(id=user_id)
            notifications = Notifications.objects.filter(
                user=user
            ).order_by('-created_at')
            return [
                {
                    'message': n.message,
                    'created_at': (n.created_at.isoformat()
                                   if n.created_at else None)
                } for n in notifications
            ]
        except get_user_model().DoesNotExist:
            logger.warning(f"User with ID {user_id} does not exist")
            return []
        except Exception as e:
            logger.error(f"Error in get_user_notifications: {str(e)}")
            return []

    @database_sync_to_async
    def get_unread_notifications_count(self):
        """Retrieve the count of unread notifications for the user.

        Returns:
            int: Number of unread notifications.
        """
        try:
            User = get_user_model()
            user = User.objects.get(id=self.user_id)
            return Notifications.objects.filter(
                user=user,
                is_read=False
            ).count()
        except User.DoesNotExist:
            logger.warning(f"User {self.user_id} not found")
            return 0
        except Exception as e:
            logger.error(f"Error getting unread count: {str(e)}")
            return 0