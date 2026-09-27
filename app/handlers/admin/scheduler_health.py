from __future__ import annotations

import logging

from aiogram import F, Router
from aiogram.types import CallbackQuery

from app.bot.filters.admin import IsAdmin
from app.utils.message_manager import MessageCleanupService
from app.workers.job_health import job_health
from app.workers.scheduler import get_scheduler

logger = logging.getLogger(__name__)
router = Router()
router.message.filter(IsAdmin())
router.callback_query.filter(IsAdmin())

# Emojis are deliberately plain so the output is readable in logs and in
# clients with limited glyph support.
_STATUS_ICON = {"ok": "OK", "failed": "FAIL", "misfired": "WARN", "never_run": "IDLE"}


def render_health() -> str:
    """Render scheduler health for admins. Contains no secrets or payloads."""
    scheduler = get_scheduler()
    running = scheduler is not None and scheduler.running
    lines = [
        "Scheduler Health",
        f"Scheduler: {'Running' if running else 'Stopped'}",
        "",
    ]

    jobs = sorted(job_health.all(), key=lambda j: j.job_id)
    if not jobs:
        lines.append("No jobs registered.")
        return "\n".join(lines)

    for job in jobs:
        icon = _STATUS_ICON.get(job.last_status, "??")
        age = job.seconds_since_last_run
        lines.append(f"[{icon}] {job.job_id} ({job.criticality})")
        if age is None:
            lines.append("    Last run: never")
        else:
            lines.append(f"    Last run: {age:.0f}s ago")
        if job.last_duration is not None:
            lines.append(f"    Duration: {job.last_duration:.2f}s")
        lines.append(f"    Processed: {job.last_processed}")
        if job.consecutive_failures:
            lines.append(
                f"    Consecutive failures: {job.consecutive_failures}"
            )
        if job.last_error_type:
            # Type name only: an exception message could contain a provider
            # response body with credentials.
            lines.append(f"    Last error type: {job.last_error_type}")
        if job.total_misfires:
            lines.append(f"    Misfires (total): {job.total_misfires}")
        if job.skipped_locked:
            lines.append(f"    Skipped (lock held): {job.skipped_locked}")
        lines.append("")

    return "\n".join(lines).rstrip()


@router.callback_query(F.data == "admin:scheduler_health")
async def admin_scheduler_health(callback: CallbackQuery, lang="fa"):
    text = render_health()
    await MessageCleanupService.show_screen(
        chat_id=callback.message.chat.id,
        text=text,
        reply_markup=None,
        force_new=True,
    )
    await callback.answer()
