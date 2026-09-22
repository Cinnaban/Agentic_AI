import os
import asyncio

import discord

from orchestrator.hermes import (
    Hermes
)

from integrations.messaging.message_router import (
    MessageRouter
)

from integrations.messaging.discord_adapter import (
    DiscordAdapter
)

from integrations.messaging.response_formatter import (
    ResponseFormatter
)


class DiscordBot:

    def __init__(
        self
    ):

        self.token = os.getenv(
            "DISCORD_BOT_TOKEN"
        )

        questions_channel = os.getenv(
            "DISCORD_QUESTIONS_CHANNEL_ID"
        )


        if not self.token:

            raise RuntimeError(
                "DISCORD_BOT_TOKEN "
                "is not configured"
            )


        if not questions_channel:

            raise RuntimeError(
                "DISCORD_QUESTIONS_CHANNEL_ID "
                "is not configured"
            )


        self.questions_channel_id = int(
            questions_channel
        )


        self.hermes = (
            Hermes()
        )


        self.router = (
            MessageRouter(
                self.hermes
            )
        )


        self.adapter = (
            DiscordAdapter(
                self.router
            )
        )


        self.formatter = (
            ResponseFormatter()
        )


        intents = (
            discord.Intents.default()
        )

        intents.message_content = True


        self.client = (
            discord.Client(
                intents=intents
            )
        )

        self._register_events()
    
    
    def _register_events(
        self
    ):

        @self.client.event
        async def on_ready():

            print(
                "Discord connected"
            )

            print(
                "Questions channel:",
                self.questions_channel_id
            )


        @self.client.event
        async def on_message(
            message
        ):

            await self._handle_message(
                message
            )
    
    async def _handle_message(
        self,
        message
    ):

        if message.author == (
            self.client.user
        ):

            return


        if message.channel.id != (
            self.questions_channel_id
        ):

            return


        text = (
            message.content
            or ""
        ).strip()


        if not text:

            return
        status_message = (
            await message.channel.send(
                "🔎 Processing your request..."
            )
        )


        try:

            normalized = (
                self.adapter.normalize(
                    text=text,

                    user_id=str(
                        message.author.id
                    ),

                    channel_id=str(
                        message.channel.id
                    ),

                    message_id=str(
                        message.id
                    )
                )
            )


            async with (
                message.channel.typing()
            ):

                result = await asyncio.to_thread(
                    self.adapter.route,
                    normalized
                )
        
                response_text = (
                    self.formatter.format(
                        result
                    )
                )


                await status_message.edit(
                    content=(
                        "✅ Analysis complete. "
                        "Preparing response..."
                    )
                )


                response_parts = (
                    self.formatter.split(
                        response_text,
                        max_length=1800
                    )
                )


                for part in response_parts:

                    await message.channel.send(
                        part
                    )


                await status_message.delete()
                
        except Exception as exc:

            print(
                "DISCORD HANDLER ERROR:",
                repr(
                    exc
                )
            )


            try:

                await status_message.edit(
                    content=(
                        "❌ I couldn't complete "
                        "that request."
                    )
                )

            except Exception:

                pass
        
    def run(
        self
    ):

        self.client.run(
            self.token
        )

if __name__ == "__main__":

    DiscordBot().run()