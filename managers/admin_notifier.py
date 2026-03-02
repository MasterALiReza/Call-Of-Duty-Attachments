"""
سرویس نوتیفیکیشن ادمین
ارسال اعلان به ادمین(ها) هنگام رویدادهای مهم مانند start کاربر جدید
"""

import asyncio
from datetime import datetime
from typing import Optional

from telegram import User as TelegramUser, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from utils.logger import get_logger, log_exception
from utils.i18n import t

logger = get_logger('admin_notifier', 'admin.log')


class AdminNotifier:
    """سرویس ارسال نوتیفیکیشن به ادمین‌ها"""

    def __init__(self, db):
        self.db = db

    async def _is_enabled(self) -> bool:
        """بررسی فعال بودن نوتیفیکیشن start ادمین"""
        try:
            val = await self.db.get_setting('admin_start_notif_enabled', 'true')
            return str(val).lower() in ('true', '1', 'yes')
        except Exception:
            return True  # فعال به صورت پیش‌فرض

    async def _is_new_only(self) -> bool:
        """آیا فقط برای کاربران جدید ارسال شود"""
        try:
            val = await self.db.get_setting('admin_start_notif_new_only', 'true')
            return str(val).lower() in ('true', '1', 'yes')
        except Exception:
            return True

    async def is_existing_user(self, user_id: int) -> bool:
        """بررسی اینکه آیا کاربر قبلاً در دیتابیس وجود دارد"""
        try:
            query = "SELECT 1 FROM users WHERE user_id = %s LIMIT 1"
            result = await self.db.execute_query(query, (user_id,), fetch_one=True)
            return result is not None
        except Exception as e:
            logger.debug(f"Could not check user existence for {user_id}: {e}")
            return False

    async def _get_total_users_count(self) -> int:
        """دریافت تعداد کل کاربران"""
        try:
            query = "SELECT COUNT(*) as cnt FROM users"
            result = await self.db.execute_query(query, fetch_one=True)
            return result['cnt'] if result else 0
        except Exception:
            return 0

    async def _get_new_users_today_count(self) -> int:
        """دریافت تعداد کاربران جدید امروز"""
        try:
            query = """
                SELECT COUNT(*) as cnt FROM users
                WHERE created_at >= CURRENT_DATE
            """
            result = await self.db.execute_query(query, fetch_one=True)
            return result['cnt'] if result else 0
        except Exception:
            return 0

    async def _get_admin_ids(self) -> list:
        """دریافت لیست آیدی ادمین‌هایی که باید نوتیف بگیرند"""
        try:
            admins = await self.db.get_all_admins()
            return [a['user_id'] for a in admins if a.get('user_id')]
        except Exception as e:
            logger.error(f"Error getting admin IDs for notification: {e}")
            return []

    async def _build_message(self, user: TelegramUser, is_new: bool) -> str:
        """ساخت پیام نوتیفیکیشن"""
        if is_new:
            status_emoji = "🆕"
            status_text = "کاربر جدید"
        else:
            status_emoji = "🔄"
            status_text = "کاربر بازگشتی"

        # اطلاعات کاربر
        name = user.first_name or ""
        if user.last_name:
            name += f" {user.last_name}"
        username = f"@{user.username}" if user.username else "ندارد"

        # آمار
        total_users = await self._get_total_users_count()
        new_today = await self._get_new_users_today_count()

        message = (
            f"{status_emoji} *{status_text} ربات را استارت زد!*\n"
            f"\n"
            f"👤 نام: {name}\n"
            f"📝 یوزرنیم: {username}\n"
            f"🆔 آیدی: `{user.id}`\n"
            f"\n"
            f"📊 *آمار:*\n"
            f"• کل کاربران: {total_users:,}\n"
            f"• کاربران جدید امروز: {new_today}"
        )

        return message

    async def notify_user_start(
        self,
        context: ContextTypes.DEFAULT_TYPE,
        user: TelegramUser,
        is_new_user: bool
    ):
        """
        ارسال نوتیفیکیشن به ادمین(ها) هنگام start کاربر
        """
        try:
            # بررسی فعال بودن
            if not await self._is_enabled():
                return

            # بررسی فقط کاربران جدید
            if await self._is_new_only() and not is_new_user:
                return

            # ساخت پیام
            message = await self._build_message(user, is_new_user)

            # ساخت دکمه inline برای دسترسی مستقیم
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("👤 مشاهده جزئیات", callback_data=f"um_detail_{user.id}")]
            ])

            # دریافت لیست ادمین‌ها
            admin_ids = await self._get_admin_ids()
            if not admin_ids:
                return

            # ارسال به ادمین‌ها
            for admin_id in admin_ids:
                try:
                    await context.bot.send_message(
                        chat_id=admin_id,
                        text=message,
                        parse_mode='Markdown',
                        reply_markup=keyboard
                    )
                except Exception as e:
                    logger.debug(f"Failed to notify admin {admin_id}: {e}")

        except Exception as e:
            logger.error(f"Error in notify_user_start: {e}")
            log_exception(logger, e, "notify_user_start")
