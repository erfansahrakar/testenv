"""
فایل اصلی ربات فروشگاه مانتو

این فایل مسئول راه‌اندازی و اجرای ربات است
"""

import asyncio
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
    ContextTypes
)

from config import config
from database import Database
from handlers.admin import AdminHandler
from handlers.user import UserHandler
from handlers.order import OrderHandler
from utils.logger import (
    get_logger,
    log_startup,
    log_shutdown,
    log_event,
    log_error
)
from utils.error_notifier import (
    init_error_notifier,
    notify_startup,
    notify_shutdown,
    notify_error
)
from utils.rate_limiter import RateLimiter

# Logger اصلی
logger = get_logger('main')


class ShopBot:
    """کلاس اصلی ربات فروشگاه"""
    
    def __init__(self):
        """راه‌اندازی اولیه"""
        logger.info("=" * 70)
        logger.info("🚀 شروع راه‌اندازی ربات فروشگاه مانتو...")
        logger.info("=" * 70)
        
        # بارگذاری تنظیمات
        self.config = config
        logger.info("✅ تنظیمات بارگذاری شد")
        
        # راه‌اندازی دیتابیس
        try:
            self.db = Database(self.config.database_path)
            logger.info("✅ دیتابیس آماده است")
        except Exception as e:
            logger.critical(f"❌ خطای بحرانی در دیتابیس: {e}")
            raise
        
        # راه‌اندازی rate limiter
        self.rate_limiter = RateLimiter(
            max_per_minute=self.config.max_requests_per_minute,
            max_per_hour=self.config.max_requests_per_hour
        )
        logger.info("✅ Rate Limiter راه‌اندازی شد")
        
        # راه‌اندازی error notifier
        if self.config.enable_error_notifications and self.config.admin_ids:
            try:
                init_error_notifier(self.config.bot_token, self.config.admin_ids[0])
                logger.info("✅ Error Notifier راه‌اندازی شد")
            except Exception as e:
                logger.warning(f"⚠️  Error Notifier راه‌اندازی نشد: {e}")
        
        # راه‌اندازی handlers
        self.admin_handler = AdminHandler(self.db, self.config, self.rate_limiter)
        self.user_handler = UserHandler(self.db, self.config, self.rate_limiter)
        self.order_handler = OrderHandler(self.db, self.config, self.rate_limiter)
        logger.info("✅ تمام Handler ها آماده هستند")
        
        # ساخت Application
        self.app = Application.builder().token(self.config.bot_token).build()
        logger.info("✅ Application تلگرام ساخته شد")
        
        # ثبت handler ها
        self._register_handlers()
        logger.info("✅ Handler ها ثبت شدند")
        
        logger.info("=" * 70)
        logger.info("✅ ربات با موفقیت راه‌اندازی شد و آماده دریافت پیام است!")
        logger.info("=" * 70)
    
    def _register_handlers(self):
        """ثبت تمام handler های ربات"""
        logger.info("در حال ثبت handler ها...")
        
        # Command handlers
        self.app.add_handler(CommandHandler("start", self.user_handler.start))
        self.app.add_handler(CommandHandler("help", self.user_handler.help_command))
        self.app.add_handler(CommandHandler("admin", self.admin_handler.admin_panel))
        logger.debug("✅ Command handlers ثبت شدند")
        
        # Callback query handlers - Admin
        self.app.add_handler(CallbackQueryHandler(
            self.admin_handler.add_product_start,
            pattern="^admin_add_product$"
        ))
        self.app.add_handler(CallbackQueryHandler(
            self.admin_handler.list_products,
            pattern="^admin_list_products$"
        ))
        self.app.add_handler(CallbackQueryHandler(
            self.admin_handler.list_orders,
            pattern="^admin_orders$"
        ))
        self.app.add_handler(CallbackQueryHandler(
            self.admin_handler.list_users,
            pattern="^admin_users$"
        ))
        self.app.add_handler(CallbackQueryHandler(
            self.admin_handler.full_stats,
            pattern="^admin_full_stats$"
        ))
        logger.debug("✅ Admin callback handlers ثبت شدند")
        
        # Callback query handlers - User
        self.app.add_handler(CallbackQueryHandler(
            self.user_handler.show_products,
            pattern="^user_products$"
        ))
        self.app.add_handler(CallbackQueryHandler(
            self.user_handler.view_product,
            pattern="^product_view_"
        ))
        self.app.add_handler(CallbackQueryHandler(
            self.user_handler.help_command,
            pattern="^user_help$"
        ))
        self.app.add_handler(CallbackQueryHandler(
            self.user_handler.main_menu,
            pattern="^user_main_menu$"
        ))
        logger.debug("✅ User callback handlers ثبت شدند")
        
        # Callback query handlers - Order
        self.app.add_handler(CallbackQueryHandler(
            self.order_handler.add_to_cart,
            pattern="^add_to_cart_"
        ))
        self.app.add_handler(CallbackQueryHandler(
            self.order_handler.view_cart,
            pattern="^user_cart$"
        ))
        self.app.add_handler(CallbackQueryHandler(
            self.order_handler.clear_cart,
            pattern="^clear_cart$"
        ))
        self.app.add_handler(CallbackQueryHandler(
            self.order_handler.confirm_order,
            pattern="^confirm_order$"
        ))
        self.app.add_handler(CallbackQueryHandler(
            self.order_handler.view_orders,
            pattern="^user_orders$"
        ))
        logger.debug("✅ Order callback handlers ثبت شدند")
        
        # Message handlers برای افزودن محصول (ادمین)
        self.app.add_handler(MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            self.admin_handler.handle_product_input
        ))
        self.app.add_handler(MessageHandler(
            filters.PHOTO,
            self.admin_handler.handle_product_photo
        ))
        logger.debug("✅ Message handlers ثبت شدند")
        
        # Error handler
        self.app.add_error_handler(self._error_handler)
        logger.debug("✅ Error handler ثبت شد")
    
    async def _error_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """مدیریت خطاهای غیرمنتظره"""
        logger.error("=" * 70)
        logger.error("❌ خطای غیرمنتظره رخ داد!")
        
        error = context.error
        user_id = None
        
        if update and update.effective_user:
            user_id = update.effective_user.id
            logger.error(f"کاربر: {user_id}")
        
        logger.error(f"خطا: {type(error).__name__}: {error}")
        logger.error("=" * 70)
        
        # لاگ کامل
        log_error(error, "error_handler", user_id)
        
        # ارسال نوتیفیکیشن
        if self.config.enable_error_notifications:
            try:
                await notify_error(
                    error,
                    severity="high",
                    context="error_handler",
                    user_id=user_id
                )
            except Exception as e:
                logger.error(f"خطا در ارسال نوتیفیکیشن: {e}")
        
        # پیام به کاربر
        try:
            if update and update.effective_message:
                await update.effective_message.reply_text(
                    "❌ متأسفانه خطایی رخ داد.\n"
                    "لطفاً دوباره تلاش کنید یا با پشتیبانی تماس بگیرید."
                )
        except Exception as e:
            logger.error(f"خطا در ارسال پیام خطا به کاربر: {e}")
    
    async def post_init(self, app: Application):
        """عملیات بعد از راه‌اندازی"""
        logger.info("🎯 اجرای post_init...")
        
        # ارسال نوتیفیکیشن راه‌اندازی
        if self.config.enable_error_notifications:
            try:
                await notify_startup()
                logger.info("✅ نوتیفیکیشن راه‌اندازی ارسال شد")
            except Exception as e:
                logger.warning(f"⚠️  خطا در ارسال نوتیفیکیشن راه‌اندازی: {e}")
        
        log_startup()
        log_event("ربات راه‌اندازی شد", f"PID: {asyncio.current_task().get_name()}")
    
    async def post_shutdown(self, app: Application):
        """عملیات بعد از خاموش شدن"""
        logger.info("🛑 اجرای post_shutdown...")
        
        # ارسال نوتیفیکیشن خاموش شدن
        if self.config.enable_error_notifications:
            try:
                await notify_shutdown()
                logger.info("✅ نوتیفیکیشن خاموش شدن ارسال شد")
            except Exception as e:
                logger.warning(f"⚠️  خطا در ارسال نوتیفیکیشن خاموش شدن: {e}")
        
        log_shutdown()
        log_event("ربات خاموش شد")
    
    def run(self):
        """اجرای ربات"""
        try:
            logger.info("▶️  شروع polling...")
            
            # اضافه کردن post_init و post_shutdown
            self.app.post_init = self.post_init
            self.app.post_shutdown = self.post_shutdown
            
            # اجرا
            self.app.run_polling(
                allowed_updates=Update.ALL_TYPES,
                drop_pending_updates=True
            )
            
        except KeyboardInterrupt:
            logger.info("⌨️  دریافت سیگنال توقف از کیبورد")
            log_event("ربات توسط کاربر متوقف شد", "KeyboardInterrupt")
        
        except Exception as e:
            logger.critical(f"❌ خطای بحرانی در اجرای ربات: {e}")
            log_error(e, "run")
            raise
        
        finally:
            logger.info("👋 ربات متوقف شد")


def main():
    """تابع اصلی"""
    try:
        # ساخت و اجرای ربات
        bot = ShopBot()
        bot.run()
        
    except Exception as e:
        logger.critical("=" * 70)
        logger.critical("💥 خطای بحرانی!")
        logger.critical(f"خطا: {type(e).__name__}: {e}")
        logger.critical("=" * 70)
        raise


if __name__ == "__main__":
    main()
