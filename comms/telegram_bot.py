from __future__ import annotations

import asyncio
import logging
import re
from collections.abc import Awaitable, Callable
from typing import Any

from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import Application, CommandHandler, ContextTypes

try:
    from telegram import BotCommand
except ImportError:  # pragma: no cover - compatibility with stripped test stubs
    BotCommand = None


StatusProvider = Callable[[], dict[str, Any]]
ProcessesProvider = Callable[[], list[dict[str, Any]]]
ModeProvider = Callable[[], str]
AskProvider = Callable[[str], Awaitable[str]]
ModelGetter = Callable[[], Awaitable[str]]
ModelSetter = Callable[[str], Awaitable[str]]
NoteProvider = Callable[[str], Awaitable[str]]
MemoryProvider = Callable[[], Awaitable[list[str]]]
HealthProvider = Callable[[], Awaitable[dict[str, str]]]
QueueLoader = Callable[[], Awaitable[list[str]]]
QueueSaver = Callable[[str], Awaitable[None]]
QueueRemover = Callable[[str], Awaitable[None]]

MARKDOWN_V2_SPECIALS = re.compile(r"([_\*\[\]\(\)~`>#+\-=|{}.!])")


def escape_markdown(text: str) -> str:
    return MARKDOWN_V2_SPECIALS.sub(r"\\\1", text)


def _build_commands() -> list[Any]:
    if BotCommand is None:
        return []
    return [
        BotCommand("help", "Show available commands"),
        BotCommand("ping", "Check bot connectivity"),
        BotCommand("status", "Show companion status"),
        BotCommand("processes", "Show top CPU processes"),
        BotCommand("mode", "Show current presence mode"),
        BotCommand("model", "Get or set the active AI backend"),
        BotCommand("ask", "Send a prompt to the active AI backend"),
        BotCommand("note", "Append a note to memory"),
        BotCommand("memory", "List stored memory notes"),
    ]


class TelegramBotService:
    COMMANDS = _build_commands()

    def __init__(
        self,
        config: dict,
        status_provider: StatusProvider,
        processes_provider: ProcessesProvider,
        mode_provider: ModeProvider,
        ask_provider: AskProvider | None = None,
        model_getter: ModelGetter | None = None,
        model_setter: ModelSetter | None = None,
        note_provider: NoteProvider | None = None,
        memory_provider: MemoryProvider | None = None,
        health_provider: HealthProvider | None = None,
        queue_loader: QueueLoader | None = None,
        queue_saver: QueueSaver | None = None,
        queue_remover: QueueRemover | None = None,
    ) -> None:
        telegram_config = config["telegram"]
        self.token = str(telegram_config["token"] or "")
        self.chat_id = str(telegram_config["chat_id"] or "")
        self.status_provider = status_provider
        self.processes_provider = processes_provider
        self.mode_provider = mode_provider
        self.ask_provider = ask_provider
        self.model_getter = model_getter
        self.model_setter = model_setter
        self.note_provider = note_provider
        self.memory_provider = memory_provider
        self.health_provider = health_provider
        self.queue_loader = queue_loader
        self.queue_saver = queue_saver
        self.queue_remover = queue_remover
        self.logger = logging.getLogger("comms.telegram_bot")
        self.application: Application | None = None
        self.started = False
        self.failed_queue: list[str] = []

    @property
    def enabled(self) -> bool:
        return bool(self.token and self.chat_id)

    async def start(self) -> None:
        if not self.enabled:
            self.logger.info("Telegram disabled; token/chat_id not configured")
            return
        if self.started:
            return

        self.application = Application.builder().token(self.token).build()
        self.application.add_handler(CommandHandler("start", self._handle_start))
        self.application.add_handler(CommandHandler("help", self._handle_help))
        self.application.add_handler(CommandHandler("ping", self._handle_ping))
        self.application.add_handler(CommandHandler("status", self._handle_status))
        self.application.add_handler(CommandHandler("processes", self._handle_processes))
        self.application.add_handler(CommandHandler("mode", self._handle_mode))
        self.application.add_handler(CommandHandler("model", self._handle_model))
        self.application.add_handler(CommandHandler("ask", self._handle_ask))
        self.application.add_handler(CommandHandler("note", self._handle_note))
        self.application.add_handler(CommandHandler("memory", self._handle_memory))
        await self.application.initialize()
        if self.COMMANDS and hasattr(self.application.bot, "set_my_commands"):
            await self.application.bot.set_my_commands(self.COMMANDS)
        await self.application.start()
        await self.application.updater.start_polling()
        self.started = True
        self.logger.info("Telegram bot started")

    async def stop(self) -> None:
        if self.application is None or not self.started:
            return
        await self.application.updater.stop()
        await self.application.stop()
        await self.application.shutdown()
        self.started = False
        self.logger.info("Telegram bot stopped")

    async def send_alert(self, message: str) -> None:
        if not self.enabled:
            self.logger.info("Telegram alert skipped because bot is disabled")
            return
        await self._send_with_backoff(message)

    async def flush_queue(self) -> None:
        queued_messages = list(self.failed_queue)
        self.failed_queue.clear()
        if self.queue_loader is not None:
            persisted = await self.queue_loader()
            for message in persisted:
                if message not in queued_messages:
                    queued_messages.append(message)
        for message in queued_messages:
            try:
                await self._send_with_backoff(message)
            except Exception:
                continue

    async def _send_with_backoff(self, message: str) -> None:
        assert self.application is not None
        for attempt in range(3):
            try:
                await self.application.bot.send_message(
                    chat_id=self.chat_id,
                    text=escape_markdown(message),
                    parse_mode=ParseMode.MARKDOWN_V2,
                )
                if self.queue_remover is not None:
                    await self.queue_remover(message)
                return
            except Exception as exc:
                delay = 2**attempt
                self.logger.warning(
                    "Telegram send failed on attempt %s: %s", attempt + 1, exc
                )
                if attempt == 2:
                    self.failed_queue.append(message)
                    if self.queue_saver is not None:
                        await self.queue_saver(message)
                    raise
                await asyncio.sleep(delay)

    async def _reply(self, update: Update, message: str) -> None:
        if update.effective_message is not None:
            await update.effective_message.reply_text(
                message,
                parse_mode=ParseMode.MARKDOWN_V2,
            )

    async def _handle_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        await self._handle_help(update, context)

    async def _handle_help(self, update: Update, _context: ContextTypes.DEFAULT_TYPE) -> None:
        await self._reply(
            update,
            "*AI Windows Companion*\n"
            "Commands:\n"
            "`/ping` ` /status` ` /processes` ` /mode`\n"
            "`/model` ` /model <name>`\n"
            "`/ask <prompt>`\n"
            "`/note <text>`\n"
            "`/memory`",
        )

    async def _handle_ping(self, update: Update, _context: ContextTypes.DEFAULT_TYPE) -> None:
        await self._reply(update, "*pong*")

    async def _handle_status(self, update: Update, _context: ContextTypes.DEFAULT_TYPE) -> None:
        snapshot = self.status_provider()
        top = snapshot["top_processes"][:3]
        process_summary = ", ".join(
            f"{item['name']} ({item['cpu_percent']:.1f}%)" for item in top
        ) or "none"
        selected_model = "unknown"
        if self.model_getter is not None:
            selected_model = await self.model_getter()
        health_summary = "unknown"
        if self.health_provider is not None:
            health = await self.health_provider()
            health_summary = ", ".join(f"{k}={v}" for k, v in health.items())
        await self._reply(
            update,
            "\n".join(
                [
                    "*Companion Status*",
                    f"*Mode:* `{escape_markdown(self.mode_provider())}`",
                    f"*CPU:* `{snapshot['cpu_percent']:.1f}%`",
                    f"*RAM:* `{snapshot['ram_percent']:.1f}%`",
                    f"*Model:* `{escape_markdown(selected_model)}`",
                    f"*AI:* {escape_markdown(health_summary)}",
                    f"*Top:* {escape_markdown(process_summary)}",
                ]
            ),
        )

    async def _handle_processes(self, update: Update, _context: ContextTypes.DEFAULT_TYPE) -> None:
        processes = self.processes_provider()[:5]
        if not processes:
            await self._reply(update, "No process data available\\.")
            return
        lines = [
            f"`{escape_markdown(item['name'])}` pid=`{item['pid']}` cpu=`{item['cpu_percent']:.1f}%`"
            for item in processes
        ]
        await self._reply(update, "*Top Processes*\n" + "\n".join(lines))

    async def _handle_mode(self, update: Update, _context: ContextTypes.DEFAULT_TYPE) -> None:
        await self._reply(update, f"*Current mode:* `{escape_markdown(self.mode_provider())}`")

    async def _handle_model(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        requested = " ".join(context.args).strip() if context.args else ""
        if not requested:
            if self.model_getter is None:
                await self._reply(update, "Model service is unavailable\\.")
                return
            current = await self.model_getter()
            await self._reply(update, f"*Current model:* `{escape_markdown(current)}`")
            return
        if requested not in {"ollama", "groq", "gemini"}:
            await self._reply(update, "Model must be one of: `ollama`, `groq`, `gemini`")
            return
        if self.model_setter is None:
            await self._reply(update, "Model service is unavailable\\.")
            return
        selected = await self.model_setter(requested)
        await self._reply(update, f"*Active model set to* `{escape_markdown(selected)}`")

    async def _handle_ask(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        prompt = " ".join(context.args).strip() if context.args else ""
        if not prompt:
            await self._reply(update, "Usage: `/ask <prompt>`")
            return
        if self.ask_provider is None:
            await self._reply(update, "AI service is unavailable\\.")
            return
        try:
            response = await self.ask_provider(prompt)
            await self._reply(update, "*AI Reply*\n" + escape_markdown(response))
        except Exception as exc:
            await self._reply(update, f"*AI request failed:* {escape_markdown(str(exc))}")

    async def _handle_note(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        note_text = " ".join(context.args).strip() if context.args else ""
        if not note_text:
            await self._reply(update, "Usage: `/note <text>`")
            return
        if self.note_provider is None:
            await self._reply(update, "Memory service is unavailable\\.")
            return
        path = await self.note_provider(note_text)
        await self._reply(update, f"*Saved note to* `{escape_markdown(path)}`")

    async def _handle_memory(self, update: Update, _context: ContextTypes.DEFAULT_TYPE) -> None:
        if self.memory_provider is None:
            await self._reply(update, "Memory service is unavailable\\.")
            return
        notes = await self.memory_provider()
        if not notes:
            await self._reply(update, "*Memory notes:* none")
            return
        lines = [f"- `{escape_markdown(name)}`" for name in notes]
        await self._reply(update, "*Memory notes*\n" + "\n".join(lines))
