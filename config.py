"""
تنظیمات ربات فروشگاه مانتو

این فایل شامل تمام تنظیمات و پیکربندی‌های ربات است
"""

import os
from dataclasses import dataclass
from typing import List

# بارگذاری .env
from dotenv import load_dotenv
load_dotenv()


@dataclass
class BotConfig:
    """کلاس تنظیمات ربات"""
    
    # تنظیمات ربات تلگرام
    bot_token: str
    admin_ids: List[int]
    channel_id: int
    
    # تنظیمات دیتابیس
    database_path: str = "data/shop.db"
    
    # تنظیمات Rate Limiting
    max_requests_per_minute: int = 20
    max_requests_per_hour: int = 100
    
    # تنظیمات محصولات
    min_price: int = 10000
    max_price: int = 10000000
    min_stock: int = 0
    max_stock: int = 10000
    
    # تنظیمات سفارش
    max_cart_items: int = 50
    order_timeout_hours: int = 48
    
    # تنظیمات امنیتی
    enable_logging: bool = True
    enable_error_notifications: bool = True
    
    def __post_init__(self):
        """بررسی و اعتبارسنجی بعد از ساخت شیء"""
        # Lazy import تا از circular import جلوگیری بشه
        from utils.logger import get_logger, log_event
        
        logger = get_logger('config')
        logger.info("در حال بارگذاری تنظیمات ربات...")
        
        if not self.bot_token or len(self.bot_token) < 30:
            logger.error("❌ توکن ربات معتبر نیست!")
            raise ValueError("توکن ربات معتبر نیست")
        
        logger.info("✅ توکن ربات معتبر است")
        
        if not self.admin_ids:
            logger.warning("⚠️  هیچ ادمینی تعریف نشده است!")
        else:
            logger.info(f"✅ تعداد {len(self.admin_ids)} ادمین تعریف شده")
        
        if not self.channel_id:
            logger.warning("⚠️  شناسه کانال تعریف نشده است!")
        else:
            logger.info(f"✅ کانال: {self.channel_id}")
        
        os.makedirs(os.path.dirname(self.database_path), exist_ok=True)
        logger.info(f"✅ مسیر دیتابیس: {self.database_path}")
        
        logger.info(f"⏱️  Rate Limit: {self.max_requests_per_minute}/دقیقه، {self.max_requests_per_hour}/ساعت")
        logger.info(f"💰 محدوده قیمت: {self.min_price:,} - {self.max_price:,} تومان")
        logger.info(f"📦 محدوده موجودی: {self.min_stock} - {self.max_stock}")
        logger.info(f"🛒 حداکثر آیتم در سبد: {self.max_cart_items}")
        logger.info(f"⏰ تایم‌اوت سفارش: {self.order_timeout_hours} ساعت")
        
        logger.info("✅ تمام تنظیمات با موفقیت بارگذاری شد")
        log_event("تنظیمات ربات بارگذاری شد", "تمام مقادیر معتبر هستند")
    
    def is_admin(self, user_id: int) -> bool:
        """بررسی ادمین بودن کاربر"""
        return user_id in self.admin_ids
    
    def validate_price(self, price: int) -> bool:
        """اعتبارسنجی قیمت"""
        return self.min_price <= price <= self.max_price
    
    def validate_stock(self, stock: int) -> bool:
        """اعتبارسنجی موجودی"""
        return self.min_stock <= stock <= self.max_stock


def load_config() -> BotConfig:
    """بارگذاری تنظیمات از environment variables"""
    
    print("=" * 60)
    print("🔧 شروع بارگذاری تنظیمات...")
    
    try:
        bot_token = os.getenv('BOT_TOKEN', '')
        
        admin_ids_str = os.getenv('ADMIN_IDS', '')
        admin_ids = []
        
        if admin_ids_str:
            admin_ids = [int(x.strip()) for x in admin_ids_str.split(',') if x.strip()]
            print(f"✅ {len(admin_ids)} ادمین پارس شد")
        
        channel_id_str = os.getenv('CHANNEL_ID', '')
        channel_id = 0
        
        if channel_id_str:
            channel_id = int(channel_id_str)
            print(f"✅ Channel ID پارس شد: {channel_id}")
        
        database_path = os.getenv('DATABASE_PATH', 'data/shop.db')
        
        config = BotConfig(
            bot_token=bot_token,
            admin_ids=admin_ids,
            channel_id=channel_id,
            database_path=database_path
        )
        
        print("✅ تنظیمات بارگذاری شد")
        print("=" * 60)
        
        return config
        
    except Exception as e:
        print(f"❌ خطا در بارگذاری تنظیمات: {e}")
        raise


# بارگذاری تنظیمات
config: BotConfig = load_config()


if __name__ == "__main__":
    # تست
    print("🧪 تست تنظیمات...\n")
    
    print(f"توکن: {config.bot_token[:20]}...")
    print(f"تعداد ادمین‌ها: {len(config.admin_ids)}")
    print(f"کانال: {config.channel_id}")
    print(f"دیتابیس: {config.database_path}")
    print(f"Rate Limit: {config.max_requests_per_minute}/دقیقه")
    print(f"محدوده قیمت: {config.min_price:,} - {config.max_price:,}")
    
    print(f"\nآیا 12345 ادمین است؟ {config.is_admin(12345)}")
    print(f"آیا قیمت 500000 معتبر است؟ {config.validate_price(500000)}")
    print(f"آیا موجودی 100 معتبر است؟ {config.validate_stock(100)}")
    
    print("\n✅ تست با موفقیت انجام شد!")
