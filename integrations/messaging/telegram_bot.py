import os
import asyncio

from telegram import Update

from telegram.ext import (
    Application,
    ContextTypes,
    MessageHandler,
    filters
)
from telegram.constants import (
    ChatAction
)
from orchestrator.hermes import (
    Hermes
)

from integrations.messaging.message_router import (
    MessageRouter
)

from integrations.messaging.telegram_adapter import (
    TelegramAdapter
)

from integrations.messaging.response_formatter import (
    ResponseFormatter
)


class TelegramBot:

    def __init__(
        self
    ):

        self.token = os.getenv(
            "TELEGRAM_BOT_TOKEN"
        )

        if not self.token:
            raise RuntimeError(
                "TELEGRAM_BOT_TOKEN is not configured"
            )

        self.hermes = Hermes()

        self.router = MessageRouter(
            self.hermes
        )

        self.adapter = TelegramAdapter(
            self.router
        )

        self.formatter = (
            ResponseFormatter()
        )
        
    async def handle_message(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE
    ):

        print(
            "TELEGRAM UPDATE RECEIVED"
        )

        message = update.effective_message

        if message is None:

            print(
                "Telegram update contained "
                "no effective message"
            )

            return


        print(
            "Telegram chat ID:",
            (
                update.effective_chat.id
                if update.effective_chat
                else None
            )
        )

        print(
            "Telegram message:",
            message.text
        )


        text = (
            message.text
            or ""
        ).strip()


        if not text:
            return
        
        normalized = (
            self.adapter.normalize(
                text=text,
                user_id=(
                    update.effective_user.id
                    if update.effective_user
                    else None
                ),
                channel_id=(
                    update.effective_chat.id
                    if update.effective_chat
                    else None
                ),
                message_id=(
                    message.message_id
                )
            )
        )
        
        try:
            print(
                "Routing Telegram message "
                "to Hermes"
            )

            status_message = await message.reply_text(
                "🔎 Processing your request..."
            )

            await context.bot.send_chat_action(
                chat_id=update.effective_chat.id,
                action=ChatAction.TYPING
            )

            result = await asyncio.to_thread(
                self.adapter.route,
                normalized
            )

            print(
                "Hermes result status:",
                (
                    result.get(
                        "status"
                    )
                    if isinstance(
                        result,
                        dict
                    )
                    else "invalid"
                )
            )

            await status_message.edit_text(
                "✅ Analysis complete. Preparing response..."
            )

            response_text = (
                self.formatter.format(
                    result
                )
            )

            print(
                "Sending Telegram response"
            )

            response_parts = (
                self.formatter.split(
                    response_text
                )
            )

            for part in response_parts:

                await message.reply_text(
                    part
                )

            await status_message.delete()
            
        except Exception as exc:

            print(
                "TELEGRAM HANDLER ERROR:",
                repr(
                    exc
                )
            )

            status_message = None

            try:

                await status_message.edit_text(
                    "❌ I couldn't complete that request."
                )

            except Exception:

                pass
    
    def run(
        self
    ):

        application = (
            Application
            .builder()
            .token(
                self.token
            )
            .build()
        )

        application.add_handler(
            MessageHandler(
                filters.TEXT
                & ~filters.COMMAND,
                self.handle_message
            )
        )

        application.run_polling()


if __name__ == "__main__":

    TelegramBot().run()
