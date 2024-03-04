import asyncio
import json
from channels.generic.websocket import AsyncWebsocketConsumer
from urllib import parse

class WebsocketConsumer(AsyncWebsocketConsumer):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.message_retry_queue = []

    async def connect(self):
        asyncio.create_task(self.retry_unsent_messages())

        query_string = self.scope.get("query_string", b"").decode("utf-8")
        query_params = parse.parse_qs(query_string)
        self.auth_id = query_params.get("auth_id", [None])[0]

        self.course_id = self.scope['url_route']['kwargs']['course_id']
        self.room_group_name = f'poll_{self.course_id}'

        if self.auth_id:
            await self.channel_layer.group_add(
                self.room_group_name,
                self.channel_name
            )

            await self.accept()
        else:
            await self.close()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )

    async def receive(self, text_data):
        try:
            await self.send(text_data=json.dumps({'message': 'Message received successfully'}))
        except Exception as e:
            await self.send(text_data=json.dumps({'error': str(e)}))

    async def send_message(self, e):
        if e['send_auth_id'] == self.auth_id:
            return

        try:
            await self.send(text_data=json.dumps({
                'key': e['key'],
                'value': e['value'] if 'value' in e else None
            }))
        except Exception as e:
            self.message_retry_queue.append(e)

    async def retry_unsent_messages(self):
        while True:
            for message in self.message_retry_queue:
                try:
                    await self.send_message(message)
                except Exception:
                    pass

            self.message_retry_queue = []
            await asyncio.sleep(5)