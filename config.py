"""
تنظیمات ربات فروشگاه مانتو

این فایل شامل تمام تنظیمات و پیکربندی‌های ربات است
"""

import os
from dataclasses import dataclass
from typing import List
from dotenv import load_dotenv
load_dotenv()
from utils.logger import get_logger, log_event

# Logger این ماژول
logger = get_logger('config')


@dataclass
class BotConfig:
    """کلاس تنظیمات ربات"""
    
    # تنظیمات ربات تلگرام
    bot_token: str
    admin_ids: List[int]
    channel_id: int  # برای ارسال پست‌ها
    
    # تنظیمات دیتابیس
    database_path: str = "data/shop.db"
    
    # تنظیمات Rate Limiting
    max_requests_per_minute: int = 20
    max_requests_per_hour: int = 100
    
    # تنظیمات محصولات
    min_price: int = 10000  # حداقل قیمت: 10,000 تومان
    max_price: int = 10000000  # حداکثر قیمت: 10 میلیون تومان
    min_stock: int = 0
    max_stock: int = 10000
    
    # تنظیمات سفارش
    max_cart_items: int = 100  # حداکثر تعداد آیتم در سبد
    order_timeout_hours: int = 24  # تایم‌اوت سفارش (48 ساعت)
    
    # تنظیمات امنیتی
    enable_logging: bool = True
    enable_error_notifications: bool = True
    
    def __post_init__(self):
        """بررسی و اعتبارسنجی بعد از ساخت شیء"""
        logger.info("در حال بارگذاری تنظیمات ربات...")
        
        # بررسی توکن ربات
        if not self.bot_token or len(self.bot_token) < 30:
            logger.error("❌ توکن ربات معتبر نیست!")
            raise ValueError("توکن ربات معتبر نیست")
        
        logger.info("✅ توکن ربات معتبر است")
        
        # بررسی ادمین‌ها
        if not self.admin_ids:
            logger.warning("⚠️  هیچ ادمینی تعریف نشده است!")
        else:
            logger.info(f"✅ تعداد {len(self.admin_ids)} ادمین تعریف شده")
        
        # بررسی channel_id
        if not self.channel_id:
            logger.warning("⚠️  شناسه کانال تعریف نشده است!")
        else:
            logger.info(f"✅ کانال: {self.channel_id}")
        
        # ساخت پوشه data اگر وجود نداشت
        os.makedirs(os.path.dirname(self.database_path), exist_ok=True)
        logger.info(f"✅ مسیر دیتابیس: {self.database_path}")
        
        # لاگ تنظیمات rate limiting
        logger.info(f"⏱️  Rate Limit: {self.max_requests_per_minute}/دقیقه، {self.max_requests_per_hour}/ساعت")
        
        # لاگ تنظیمات محصولات
        logger.info(f"💰 محدوده قیمت: {self.min_price:,} - {self.max_price:,} تومان")
        logger.info(f"📦 محدوده موجودی: {self.min_stock} - {self.max_stock}")
        
        # لاگ تنظیمات سفارش
        logger.info(f"🛒 حداکثر آیتم در سبد: {self.max_cart_items}")
        logger.info(f"⏰ تایم‌اوت سفارش: {self.order_timeout_hours} ساعت")
        
        logger.info("✅ تمام تنظیمات با موفقیت بارگذاری شد")
        log_event("تنظیمات ربات بارگذاری شد", "تمام مقادیر معتبر هستند")
    
    def is_admin(self, user_id: int) -> bool:
        """بررسی ادمین بودن کاربر"""
        is_admin_user = user_id in self.admin_ids
        
        if is_admin_user:
            logger.debug(f"کاربر {user_id} ادمین است")
        else:
            logger.debug(f"کاربر {user_id} ادمین نیست")
        
        return is_admin_user
    
    def validate_price(self, price: int) -> bool:
        """اعتبارسنجی قیمت"""
        is_valid = self.min_price <= price <= self.max_price
        
        if not is_valid:
            logger.warning(f"قیمت نامعتبر: {price:,} (محدوده: {self.min_price:,} - {self.max_price:,})")
        
        return is_valid
    
    def validate_stock(self, stock: int) -> bool:
        """اعتبارسنجی موجودی"""
        is_valid = self.min_stock <= stock <= self.max_stock
        
        if not is_valid:
            logger.warning(f"موجودی نامعتبر: {stock} (محدوده: {self.min_stock} - {self.max_stock})")
        
        return is_valid


def load_config() -> BotConfig:
    """بارگذاری تنظیمات از environment variables"""
    
    logger.info("=" * 60)
    logger.info("🔧 شروع بارگذاری تنظیمات از Environment Variables...")
    
    try:
        # دریافت مقادیر از محیط
        bot_token = os.getenv('BOT_TOKEN', '')
        
        # Parse admin IDs (فرمت: "123,456,789")
        admin_ids_str = os.getenv('ADMIN_IDS', '')
        admin_ids = []
        
        if admin_ids_str:
            try:
                admin_ids = [int(x.strip()) for x in admin_ids_str.split(',') if x.strip()]
                logger.info(f"✅ {len(admin_ids)} ادمین پارس شد")
            except ValueError as e:
                logger.error(f"❌ خطا در پارس کردن ADMIN_IDS: {e}")
                raise
        
        # دریافت channel ID
        channel_id_str = os.getenv('CHANNEL_ID', '')
        channel_id = 0
        
        if channel_id_str:
            try:
                channel_id = int(channel_id_str)
                logger.info(f"✅ Channel ID پارس شد: {channel_id}")
            except ValueError as e:
                logger.error(f"❌ خطا در پارس کردن CHANNEL_ID: {e}")
                raise
        
        # دریافت مسیر دیتابیس (اختیاری)
        database_path = os.getenv('DATABASE_PATH', 'data/shop.db')
        logger.info(f"✅ مسیر دیتابیس: {database_path}")
        
        # ساخت شیء Config
        config = BotConfig(
            bot_token=bot_token,
            admin_ids=admin_ids,
            channel_id=channel_id,
            database_path=database_path
        )
        
        logger.info("✅ تنظیمات با موفقیت بارگذاری شد")
        logger.info("=" * 60)
        
        return config
        
    except Exception as e:
        logger.error(f"❌ خطا در بارگذاری تنظیمات: {e}", exc_info=True)
        raise


# بارگذاری تنظیمات (فقط یک بار)
config: BotConfig = None

try:
    config = load_config()
except Exception as e:
    logger.critical("❌ بارگذاری تنظیمات با شکست مواجه شد!")
    logger.critical(f"لطفاً Environment Variables را چک کنید")
    raise


if __name__ == "__main__":
    # تست
    print("🧪 تست تنظیمات...\n")
    
    # نمایش تنظیمات
    print(f"توکن: {config.bot_token[:20]}...")
    print(f"تعداد ادمین‌ها: {len(config.admin_ids)}")
    print(f"کانال: {config.channel_id}")
    print(f"دیتابیس: {config.database_path}")
    print(f"Rate Limit: {config.max_requests_per_minute}/دقیقه")
    print(f"محدوده قیمت: {config.min_price:,} - {config.max_price:,}")
    
    # تست توابع
    print(f"\nآیا 12345 ادمین است؟ {config.is_admin(12345)}")
    print(f"آیا قیمت 500000 معتبر است؟ {config.validate_price(500000)}")
    print(f"آیا موجودی 100 معتبر است؟ {config.validate_stock(100)}")
    
    print("\n✅ تست با موفقیت انجام شد!")
