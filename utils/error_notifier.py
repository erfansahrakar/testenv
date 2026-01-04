"""
سیستم اطلاع‌رسانی خطا به ادمین از طریق تلگرام

ویژگی‌ها:
- ارسال خطاهای مهم به ادمین
- دسته‌بندی خطاها (بحرانی، مهم، عادی)
- جلوگیری از اسپم (throttling)
- فرمت زیبا و خوانا
"""

import asyncio
from datetime import datetime, timedelta
from typing import Optional, Dict
from telegram import Bot
from telegram.error import TelegramError
import traceback

from .logger import log_error, get_logger


class ErrorNotifier:
    """کلاس اطلاع‌رسانی خطا به ادمین"""
    
    def __init__(self, bot_token: str, admin_chat_id: int):
        """
        Args:
            bot_token: توکن ربات
            admin_chat_id: شناسه چت ادمین
        """
        self.bot = Bot(token=bot_token)
        self.admin_chat_id = admin_chat_id
        self.logger = get_logger('error_notifier')
        
        # برای جلوگیری از اسپم
        self.last_notification: Dict[str, datetime] = {}
        self.throttle_seconds = 300  # 5 دقیقه
        
        # آمار خطاها
        self.error_counts: Dict[str, int] = {}
    
    async def notify(
        self,
        error: Exception,
        severity: str = "normal",
        context: str = "",
        user_id: Optional[int] = None,
        additional_info: str = ""
    ):
        """
        ارسال نوتیفیکیشن خطا به ادمین
        
        Args:
            error: خطای رخ داده
            severity: شدت خطا (critical, high, normal, low)
            context: محل رخ دادن خطا
            user_id: شناسه کاربری که خطا برایش رخ داده
            additional_info: اطلاعات اضافی
        """
        
        # چک throttling
        error_key = f"{type(error).__name__}_{context}"
        if not self._should_notify(error_key, severity):
            self.logger.debug(f"خطا throttle شد: {error_key}")
            return
        
        # آماده‌سازی پیام
        message = self._format_error_message(
            error, severity, context, user_id, additional_info
        )
        
        # ارسال به ادمین
        try:
            await self.bot.send_message(
                chat_id=self.admin_chat_id,
                text=message,
                parse_mode='HTML'
            )
            
            self.logger.info(f"نوتیفیکیشن خطا ارسال شد: {error_key}")
            
            # به‌روزرسانی آمار
            self.error_counts[error_key] = self.error_counts.get(error_key, 0) + 1
            
        except TelegramError as e:
            self.logger.error(f"خطا در ارسال نوتیفیکیشن: {e}")
    
    def _should_notify(self, error_key: str, severity: str) -> bool:
        """بررسی اینکه آیا باید نوتیفیکیشن ارسال شود یا نه"""
        
        # خطاهای بحرانی همیشه ارسال می‌شوند
        if severity == "critical":
            return True
        
        # چک آخرین زمان ارسال
        last_time = self.last_notification.get(error_key)
        
        if last_time is None:
            self.last_notification[error_key] = datetime.now()
            return True
        
        # محاسبه زمان گذشته
        elapsed = (datetime.now() - last_time).total_seconds()
        
        # خطاهای high بعد از 2 دقیقه
        if severity == "high" and elapsed >= 120:
            self.last_notification[error_key] = datetime.now()
            return True
        
        # بقیه خطاها بعد از 5 دقیقه
        if elapsed >= self.throttle_seconds:
            self.last_notification[error_key] = datetime.now()
            return True
        
        return False
    
    def _format_error_message(
        self,
        error: Exception,
        severity: str,
        context: str,
        user_id: Optional[int],
        additional_info: str
    ) -> str:
        """فرمت کردن پیام خطا"""
        
        # ایموجی بر اساس شدت
        emoji_map = {
            "critical": "🔴",
            "high": "🟠",
            "normal": "🟡",
            "low": "🔵"
        }
        emoji = emoji_map.get(severity, "⚠️")
        
        # شروع پیام
        lines = [
            f"{emoji} <b>خطای جدید!</b>",
            "",
            f"🕐 <b>زمان:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            f"⚡️ <b>شدت:</b> {severity.upper()}",
        ]
        
        # نوع خطا
        lines.append(f"❌ <b>نوع خطا:</b> {type(error).__name__}")
        
        # پیام خطا
        error_msg = str(error)
        if len(error_msg) > 200:
            error_msg = error_msg[:200] + "..."
        lines.append(f"📝 <b>پیام:</b> {error_msg}")
        
        # محل رخ دادن
        if context:
            lines.append(f"📍 <b>محل:</b> {context}")
        
        # کاربر
        if user_id:
            lines.append(f"👤 <b>کاربر:</b> {user_id}")
        
        # اطلاعات اضافی
        if additional_info:
            lines.append(f"ℹ️ <b>اطلاعات:</b> {additional_info}")
        
        # آمار این خطا
        error_key = f"{type(error).__name__}_{context}"
        count = self.error_counts.get(error_key, 0)
        if count > 0:
            lines.append(f"📊 <b>تعداد تکرار:</b> {count + 1}")
        
        # Traceback (فقط 5 خط آخر)
        tb_lines = traceback.format_exception(type(error), error, error.__traceback__)
        tb_short = "".join(tb_lines[-5:])
        if len(tb_short) > 500:
            tb_short = tb_short[-500:]
        lines.append("")
        lines.append("<b>🔍 Traceback:</b>")
        lines.append(f"<pre>{tb_short}</pre>")
        
        return "\n".join(lines)
    
    async def send_daily_report(self):
        """ارسال گزارش روزانه خطاها"""
        
        if not self.error_counts:
            message = "✅ <b>گزارش روزانه</b>\n\nهیچ خطایی در 24 ساعت گذشته ثبت نشده است."
        else:
            lines = [
                "📊 <b>گزارش روزانه خطاها</b>",
                "",
                f"📅 تاریخ: {datetime.now().strftime('%Y-%m-%d')}",
                f"🔢 تعداد کل خطاها: {sum(self.error_counts.values())}",
                "",
                "<b>🔝 پرتکرارترین خطاها:</b>"
            ]
            
            # مرتب‌سازی بر اساس تعداد
            sorted_errors = sorted(
                self.error_counts.items(),
                key=lambda x: x[1],
                reverse=True
            )
            
            for i, (error_key, count) in enumerate(sorted_errors[:10], 1):
                lines.append(f"{i}. {error_key}: {count} بار")
            
            message = "\n".join(lines)
            
            # ریست آمار
            self.error_counts.clear()
        
        try:
            await self.bot.send_message(
                chat_id=self.admin_chat_id,
                text=message,
                parse_mode='HTML'
            )
            self.logger.info("گزارش روزانه ارسال شد")
        except TelegramError as e:
            self.logger.error(f"خطا در ارسال گزارش روزانه: {e}")
    
    async def send_startup_notification(self):
        """اطلاع‌رسانی راه‌اندازی ربات"""
        message = (
            "🚀 <b>ربات راه‌اندازی شد</b>\n\n"
            f"⏰ زمان: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
            "✅ سیستم لاگ فعال است"
        )
        
        try:
            await self.bot.send_message(
                chat_id=self.admin_chat_id,
                text=message,
                parse_mode='HTML'
            )
            self.logger.info("نوتیفیکیشن راه‌اندازی ارسال شد")
        except TelegramError as e:
            self.logger.error(f"خطا در ارسال نوتیفیکیشن راه‌اندازی: {e}")
    
    async def send_shutdown_notification(self):
        """اطلاع‌رسانی خاموش شدن ربات"""
        message = (
            "🛑 <b>ربات خاموش شد</b>\n\n"
            f"⏰ زمان: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        )
        
        try:
            await self.bot.send_message(
                chat_id=self.admin_chat_id,
                text=message,
                parse_mode='HTML'
            )
            self.logger.info("نوتیفیکیشن خاموش شدن ارسال شد")
        except TelegramError as e:
            self.logger.error(f"خطا در ارسال نوتیفیکیشن خاموش شدن: {e}")


# نمونه سراسری (باید در main.py مقداردهی شود)
error_notifier: Optional[ErrorNotifier] = None


def init_error_notifier(bot_token: str, admin_chat_id: int):
    """مقداردهی اولیه error notifier"""
    global error_notifier
    error_notifier = ErrorNotifier(bot_token, admin_chat_id)


async def notify_error(
    error: Exception,
    severity: str = "normal",
    context: str = "",
    user_id: Optional[int] = None,
    additional_info: str = ""
):
    """ارسال نوتیفیکیشن خطا (تابع کمکی)"""
    
    # لاگ کردن خطا
    log_error(error, context, user_id)
    
    # ارسال نوتیفیکیشن
    if error_notifier:
        try:
            await error_notifier.notify(
                error, severity, context, user_id, additional_info
            )
        except Exception as e:
            # اگر خود نوتیفایر خطا داد، فقط لاگ کن
            get_logger('error_notifier').error(
                f"خطا در ارسال نوتیفیکیشن: {e}"
            )


async def notify_startup():
    """نوتیفیکیشن راه‌اندازی"""
    if error_notifier:
        await error_notifier.send_startup_notification()


async def notify_shutdown():
    """نوتیفیکیشن خاموش شدن"""
    if error_notifier:
        await error_notifier.send_shutdown_notification()


async def send_daily_report():
    """ارسال گزارش روزانه"""
    if error_notifier:
        await error_notifier.send_daily_report()


if __name__ == "__main__":
    # تست (نیاز به توکن واقعی و chat_id دارد)
    print("⚠️  برای تست این ماژول، توکن ربات و chat_id ادمین لازم است.")
    print("این فایل باید در main.py استفاده شود.")
