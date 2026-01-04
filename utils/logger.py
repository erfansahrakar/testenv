"""
سیستم Logging حرفه‌ای برای ربات فروشگاه مانتو

ویژگی‌ها:
- لاگ در فایل و کنسول
- Rotation خودکار (محدودیت حجم)
- سطوح مختلف لاگ (DEBUG, INFO, WARNING, ERROR, CRITICAL)
- فرمت فارسی و خوانا
- جداسازی لاگ‌های مختلف
"""

import logging
import sys
from pathlib import Path
from logging.handlers import RotatingFileHandler
from datetime import datetime
from typing import Optional


class PersianLogger:
    """کلاس مدیریت لاگ‌های فارسی"""
    
    def __init__(self):
        self.logs_dir = Path("logs")
        self.logs_dir.mkdir(exist_ok=True)
        
        # فرمت لاگ
        self.log_format = logging.Formatter(
            '%(asctime)s | %(levelname)-8s | %(name)s | %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        
        # لاگرهای مختلف
        self.loggers = {}
    
    def get_logger(
        self,
        name: str,
        level: int = logging.INFO,
        log_to_file: bool = True,
        log_to_console: bool = True,
        max_bytes: int = 10 * 1024 * 1024,  # 10MB
        backup_count: int = 5
    ) -> logging.Logger:
        """
        دریافت یک logger با تنظیمات دلخواه
        
        Args:
            name: نام logger
            level: سطح لاگ (DEBUG, INFO, WARNING, ERROR, CRITICAL)
            log_to_file: ذخیره در فایل؟
            log_to_console: نمایش در کنسول؟
            max_bytes: حداکثر حجم فایل لاگ (قبل از rotation)
            backup_count: تعداد فایل‌های backup
        """
        
        # اگر قبلاً ساخته شده، برگردان
        if name in self.loggers:
            return self.loggers[name]
        
        # ساخت logger جدید
        logger = logging.getLogger(name)
        logger.setLevel(level)
        logger.handlers.clear()  # پاک کردن handler های قبلی
        
        # Handler برای فایل
        if log_to_file:
            log_file = self.logs_dir / f"{name}.log"
            file_handler = RotatingFileHandler(
                log_file,
                maxBytes=max_bytes,
                backupCount=backup_count,
                encoding='utf-8'
            )
            file_handler.setLevel(level)
            file_handler.setFormatter(self.log_format)
            logger.addHandler(file_handler)
        
        # Handler برای کنسول
        if log_to_console:
            console_handler = logging.StreamHandler(sys.stdout)
            console_handler.setLevel(level)
            console_handler.setFormatter(self.log_format)
            logger.addHandler(console_handler)
        
        # ذخیره logger
        self.loggers[name] = logger
        
        return logger
    
    def log_user_action(
        self,
        user_id: int,
        username: Optional[str],
        action: str,
        details: str = ""
    ):
        """لاگ اقدامات کاربران"""
        logger = self.get_logger('user_actions')
        
        username_str = f"@{username}" if username else "بدون نام کاربری"
        message = f"کاربر {user_id} ({username_str}) | {action}"
        
        if details:
            message += f" | {details}"
        
        logger.info(message)
    
    def log_admin_action(
        self,
        admin_id: int,
        admin_username: Optional[str],
        action: str,
        details: str = ""
    ):
        """لاگ اقدامات ادمین‌ها"""
        logger = self.get_logger('admin_actions')
        
        username_str = f"@{admin_username}" if admin_username else "بدون نام کاربری"
        message = f"ادمین {admin_id} ({username_str}) | {action}"
        
        if details:
            message += f" | {details}"
        
        logger.info(message)
    
    def log_order(
        self,
        order_id: int,
        user_id: int,
        action: str,
        details: str = ""
    ):
        """لاگ سفارشات"""
        logger = self.get_logger('orders')
        
        message = f"سفارش #{order_id} | کاربر {user_id} | {action}"
        
        if details:
            message += f" | {details}"
        
        logger.info(message)
    
    def log_error(
        self,
        error: Exception,
        context: str = "",
        user_id: Optional[int] = None
    ):
        """لاگ خطاها"""
        logger = self.get_logger('errors', level=logging.ERROR)
        
        message = f"خطا"
        
        if context:
            message += f" در {context}"
        
        if user_id:
            message += f" | کاربر {user_id}"
        
        message += f" | {type(error).__name__}: {str(error)}"
        
        logger.error(message, exc_info=True)
    
    def log_database(self, operation: str, details: str = ""):
        """لاگ عملیات دیتابیس"""
        logger = self.get_logger('database')
        
        message = f"DB | {operation}"
        
        if details:
            message += f" | {details}"
        
        logger.debug(message)
    
    def log_bot_event(self, event: str, details: str = ""):
        """لاگ رویدادهای ربات"""
        logger = self.get_logger('bot_events')
        
        message = f"رویداد ربات | {event}"
        
        if details:
            message += f" | {details}"
        
        logger.info(message)
    
    def log_security(self, event: str, user_id: Optional[int] = None, details: str = ""):
        """لاگ مسائل امنیتی"""
        logger = self.get_logger('security', level=logging.WARNING)
        
        message = f"امنیت | {event}"
        
        if user_id:
            message += f" | کاربر {user_id}"
        
        if details:
            message += f" | {details}"
        
        logger.warning(message)


# نمونه سراسری
persian_logger = PersianLogger()


def get_logger(name: str, **kwargs) -> logging.Logger:
    """
    تابع کمکی برای دریافت logger
    
    مثال:
        logger = get_logger('my_module')
        logger.info('پیام من')
    """
    return persian_logger.get_logger(name, **kwargs)


def log_startup():
    """لاگ راه‌اندازی ربات"""
    logger = get_logger('startup')
    logger.info("=" * 50)
    logger.info("🚀 ربات در حال راه‌اندازی...")
    logger.info(f"⏰ زمان: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("=" * 50)


def log_shutdown():
    """لاگ خاموش شدن ربات"""
    logger = get_logger('shutdown')
    logger.info("=" * 50)
    logger.info("🛑 ربات در حال خاموش شدن...")
    logger.info(f"⏰ زمان: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("=" * 50)


# توابع کوتاه برای راحتی کار
def log_user(user_id: int, username: Optional[str], action: str, details: str = ""):
    """لاگ اقدام کاربر"""
    persian_logger.log_user_action(user_id, username, action, details)


def log_admin(admin_id: int, username: Optional[str], action: str, details: str = ""):
    """لاگ اقدام ادمین"""
    persian_logger.log_admin_action(admin_id, username, action, details)


def log_order(order_id: int, user_id: int, action: str, details: str = ""):
    """لاگ سفارش"""
    persian_logger.log_order(order_id, user_id, action, details)


def log_error(error: Exception, context: str = "", user_id: Optional[int] = None):
    """لاگ خطا"""
    persian_logger.log_error(error, context, user_id)


def log_db(operation: str, details: str = ""):
    """لاگ دیتابیس"""
    persian_logger.log_database(operation, details)


def log_event(event: str, details: str = ""):
    """لاگ رویداد"""
    persian_logger.log_bot_event(event, details)


def log_security(event: str, user_id: Optional[int] = None, details: str = ""):
    """لاگ امنیتی"""
    persian_logger.log_security(event, user_id, details)


if __name__ == "__main__":
    # تست سیستم لاگ
    print("🧪 تست سیستم لاگ...\n")
    
    # تست logger عادی
    logger = get_logger('test')
    logger.debug("این یک پیام DEBUG است")
    logger.info("این یک پیام INFO است")
    logger.warning("این یک پیام WARNING است")
    logger.error("این یک پیام ERROR است")
    
    # تست لاگ کاربر
    log_user(12345, "test_user", "شروع خرید", "محصول: مانتو مشکی")
    
    # تست لاگ ادمین
    log_admin(99999, "admin", "افزودن محصول", "مانتو قرمز - قیمت 500000")
    
    # تست لاگ سفارش
    log_order(1, 12345, "ایجاد سفارش", "تعداد 2 - مبلغ 1000000")
    
    # تست لاگ خطا
    try:
        raise ValueError("این یک خطای تستی است")
    except Exception as e:
        log_error(e, "تست خطا", 12345)
    
    # تست لاگ دیتابیس
    log_db("SELECT", "users table - found 150 users")
    
    # تست لاگ رویداد
    log_event("ربات راه‌اندازی شد", "نسخه 2.0")
    
    # تست لاگ امنیتی
    log_security("تلاش ناموفق برای دسترسی ادمین", 12345, "IP: 192.168.1.1")
    
    print("\n✅ تست‌ها کامل شد! فایل‌های لاگ رو توی پوشه logs/ چک کن.")
