"""
Handler های مربوط به کاربران عادی

شامل: start، help، مشاهده محصولات
"""

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from typing import List, Dict, Any

from database import Database
from config import BotConfig
from utils.logger import get_logger, log_user, log_error, log_event
from utils.error_notifier import notify_error
from utils.rate_limiter import RateLimiter

# Logger این ماژول
logger = get_logger('user_handler')


class UserHandler:
    """کلاس مدیریت handler های کاربران"""
    
    def __init__(self, db: Database, config: BotConfig, rate_limiter: RateLimiter):
        self.db = db
        self.config = config
        self.rate_limiter = rate_limiter
        
        logger.info("✅ UserHandler راه‌اندازی شد")
    
    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """پیام خوش‌آمدگویی"""
        user = update.effective_user
        user_id = user.id
        username = user.username
        first_name = user.first_name
        last_name = user.last_name
        
        logger.info(f"کاربر جدید/بازگشته: {user_id} (@{username})")
        
        try:
            # بررسی rate limit
            if not self.rate_limiter.check_rate_limit(user_id):
                logger.warning(f"Rate limit برای کاربر {user_id}")
                await update.message.reply_text(
                    "⏳ لطفاً کمی صبر کنید و دوباره تلاش کنید."
                )
                return
            
            # ثبت/به‌روزرسانی کاربر
            self.db.add_or_update_user(user_id, username, first_name, last_name)
            
            # بررسی بلاک
            if self.db.is_user_blocked(user_id):
                logger.warning(f"کاربر بلاک شده تلاش به استفاده: {user_id}")
                await update.message.reply_text("⛔️ دسترسی شما محدود شده است.")
                log_user(user_id, username, "تلاش استفاده با اکانت بلاک شده")
                return
            
            # پیام خوش‌آمدگویی
            text = (
                f"👋 سلام {first_name} عزیز!\n\n"
                "به فروشگاه مانتو ما خوش آمدید 🛍\n\n"
                "برای مشاهده محصولات از دکمه‌های زیر استفاده کنید:"
            )
            
            keyboard = [
                [
                    InlineKeyboardButton("🛍 محصولات", callback_data="user_products"),
                    InlineKeyboardButton("🛒 سبد خرید", callback_data="user_cart")
                ],
                [
                    InlineKeyboardButton("📋 سفارشات من", callback_data="user_orders"),
                    InlineKeyboardButton("ℹ️ راهنما", callback_data="user_help")
                ]
            ]
            
            await update.message.reply_text(
                text,
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            
            log_user(user_id, username, "استفاده از /start")
            
        except Exception as e:
            logger.error(f"خطا در start handler: {e}", exc_info=True)
            await update.message.reply_text("❌ خطا در پردازش درخواست")
            await notify_error(e, "normal", "start", user_id)
    
    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """راهنمای استفاده"""
        user_id = update.effective_user.id
        username = update.effective_user.username
        
        logger.info(f"درخواست راهنما از {user_id}")
        
        try:
            # بررسی rate limit
            if not self.rate_limiter.check_rate_limit(user_id):
                return
            
            text = (
                "ℹ️ <b>راهنمای استفاده</b>\n\n"
                "🛍 <b>مشاهده محصولات:</b>\n"
                "از منوی اصلی گزینه «محصولات» را انتخاب کنید\n\n"
                "🛒 <b>خرید:</b>\n"
                "روی هر محصول کلیک کنید و تعداد دلخواه را انتخاب کنید\n\n"
                "📋 <b>سفارشات:</b>\n"
                "از منوی اصلی می‌توانید سفارشات خود را مشاهده کنید\n\n"
                "❓ <b>پشتیبانی:</b>\n"
                "در صورت نیاز با پشتیبانی تماس بگیرید"
            )
            
            keyboard = [
                [InlineKeyboardButton("🔙 منوی اصلی", callback_data="user_main_menu")]
            ]
            
            if update.callback_query:
                await update.callback_query.edit_message_text(
                    text,
                    reply_markup=InlineKeyboardMarkup(keyboard),
                    parse_mode='HTML'
                )
                await update.callback_query.answer()
            else:
                await update.message.reply_text(
                    text,
                    reply_markup=InlineKeyboardMarkup(keyboard),
                    parse_mode='HTML'
                )
            
            log_user(user_id, username, "مشاهده راهنما")
            
        except Exception as e:
            logger.error(f"خطا در help: {e}", exc_info=True)
            await notify_error(e, "low", "help", user_id)
    
    async def show_products(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """نمایش لیست محصولات"""
        query = update.callback_query
        await query.answer()
        
        user_id = update.effective_user.id
        username = update.effective_user.username
        
        logger.info(f"درخواست محصولات از {user_id}")
        
        try:
            # بررسی rate limit
            if not self.rate_limiter.check_rate_limit(user_id):
                await query.edit_message_text("⏳ لطفاً کمی صبر کنید")
                return
            
            # دریافت محصولات فعال
            products = self.db.get_all_products(active_only=True)
            
            if not products:
                await query.edit_message_text(
                    "📦 در حال حاضر محصولی موجود نیست.\n"
                    "لطفاً بعداً مراجعه کنید."
                )
                log_user(user_id, username, "مشاهده محصولات", "هیچ محصولی موجود نیست")
                return
            
            # فیلتر محصولات موجود
            available_products = [p for p in products if p['stock'] > 0]
            
            if not available_products:
                await query.edit_message_text(
                    "📦 متأسفانه تمام محصولات تمام شده است.\n"
                    "به زودی موجودی جدید اضافه می‌شود."
                )
                log_user(user_id, username, "مشاهده محصولات", "همه تمام شده")
                return
            
            # ساخت لیست محصولات
            text = "🛍 <b>محصولات موجود</b>\n\n"
            keyboard = []
            
            for product in available_products[:20]:  # حداکثر 20 محصول
                text += (
                    f"📦 <b>{product['name']}</b>\n"
                    f"💰 قیمت: {product['price']:,} تومان\n"
                    f"📊 موجودی: {product['stock']} عدد\n\n"
                )
                
                # دکمه مشاهده جزئیات
                keyboard.append([
                    InlineKeyboardButton(
                        f"👁 {product['name']}",
                        callback_data=f"product_view_{product['product_id']}"
                    )
                ])
            
            # دکمه بازگشت
            keyboard.append([
                InlineKeyboardButton("🔙 منوی اصلی", callback_data="user_main_menu")
            ])
            
            await query.edit_message_text(
                text,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='HTML'
            )
            
            log_user(user_id, username, "مشاهده لیست محصولات", f"{len(available_products)} محصول")
            
        except Exception as e:
            logger.error(f"خطا در نمایش محصولات: {e}", exc_info=True)
            await query.edit_message_text("❌ خطا در نمایش محصولات")
            await notify_error(e, "normal", "show_products", user_id)
    
    async def view_product(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """نمایش جزئیات محصول"""
        query = update.callback_query
        await query.answer()
        
        user_id = update.effective_user.id
        username = update.effective_user.username
        
        # دریافت product_id از callback_data
        try:
            product_id = int(query.data.split('_')[-1])
        except (ValueError, IndexError):
            logger.error(f"callback_data نامعتبر: {query.data}")
            await query.edit_message_text("❌ خطا در پردازش")
            return
        
        logger.info(f"درخواست مشاهده محصول {product_id} از {user_id}")
        
        try:
            # دریافت محصول
            product = self.db.get_product(product_id)
            
            if not product:
                await query.edit_message_text("❌ محصول یافت نشد")
                return
            
            if not product['is_active']:
                await query.edit_message_text("❌ این محصول غیرفعال است")
                return
            
            # ساخت پیام
            text = (
                f"📦 <b>{product['name']}</b>\n\n"
                f"💰 قیمت: {product['price']:,} تومان\n"
                f"📊 موجودی: {product['stock']} عدد\n"
            )
            
            if product['description']:
                text += f"\n📝 {product['description']}\n"
            
            text += f"\n🆔 کد محصول: {product_id}"
            
            # دکمه‌های خرید
            keyboard = []
            
            if product['stock'] > 0:
                # دکمه‌های تعداد
                quantities = [1, 2, 3, 5]
                quantity_buttons = []
                
                for qty in quantities:
                    if qty <= product['stock']:
                        quantity_buttons.append(
                            InlineKeyboardButton(
                                f"🛒 {qty}",
                                callback_data=f"add_to_cart_{product_id}_{qty}"
                            )
                        )
                
                if quantity_buttons:
                    # تقسیم به ردیف‌های 2 تایی
                    for i in range(0, len(quantity_buttons), 2):
                        keyboard.append(quantity_buttons[i:i+2])
            
            else:
                text += "\n\n❌ <b>ناموجود</b>"
            
            # دکمه بازگشت
            keyboard.append([
                InlineKeyboardButton("🔙 بازگشت", callback_data="user_products")
            ])
            
            # ارسال با یا بدون عکس
            if product['image_file_id']:
                await query.message.reply_photo(
                    photo=product['image_file_id'],
                    caption=text,
                    reply_markup=InlineKeyboardMarkup(keyboard),
                    parse_mode='HTML'
                )
                await query.message.delete()
            else:
                await query.edit_message_text(
                    text,
                    reply_markup=InlineKeyboardMarkup(keyboard),
                    parse_mode='HTML'
                )
            
            log_user(user_id, username, "مشاهده محصول", f"ID {product_id}: {product['name']}")
            
        except Exception as e:
            logger.error(f"خطا در نمایش محصول: {e}", exc_info=True)
            await query.edit_message_text("❌ خطا در نمایش محصول")
            await notify_error(e, "normal", "view_product", user_id)
    
    async def main_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """بازگشت به منوی اصلی"""
        query = update.callback_query
        await query.answer()
        
        user_id = update.effective_user.id
        username = update.effective_user.username
        first_name = update.effective_user.first_name
        
        logger.debug(f"بازگشت به منوی اصلی: {user_id}")
        
        try:
            text = (
                f"👋 {first_name} عزیز\n\n"
                "منوی اصلی:"
            )
            
            keyboard = [
                [
                    InlineKeyboardButton("🛍 محصولات", callback_data="user_products"),
                    InlineKeyboardButton("🛒 سبد خرید", callback_data="user_cart")
                ],
                [
                    InlineKeyboardButton("📋 سفارشات من", callback_data="user_orders"),
                    InlineKeyboardButton("ℹ️ راهنما", callback_data="user_help")
                ]
            ]
            
            await query.edit_message_text(
                text,
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            
            log_user(user_id, username, "بازگشت به منوی اصلی")
            
        except Exception as e:
            logger.error(f"خطا در منوی اصلی: {e}", exc_info=True)
            await notify_error(e, "low", "main_menu", user_id)


if __name__ == "__main__":
    print("⚠️  این ماژول باید در main.py استفاده شود")
