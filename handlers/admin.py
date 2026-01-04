"""
Handler های مربوط به پنل ادمین

شامل: مدیریت محصولات، سفارشات، کاربران و آمار
"""

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from typing import Optional
import asyncio

from database import Database
from config import BotConfig
from utils.logger import get_logger, log_admin, log_error, log_event
from utils.error_notifier import notify_error
from utils.validation import Validator
from utils.rate_limiter import RateLimiter

# Logger این ماژول
logger = get_logger('admin_handler')


class AdminHandler:
    """کلاس مدیریت handler های ادمین"""
    
    def __init__(self, db: Database, config: BotConfig, rate_limiter: RateLimiter):
        self.db = db
        self.config = config
        self.rate_limiter = rate_limiter
        self.validator = Validator(config)
        
        logger.info("✅ AdminHandler راه‌اندازی شد")
    
    def is_admin(self, user_id: int) -> bool:
        """بررسی دسترسی ادمین"""
        is_admin_user = self.config.is_admin(user_id)
        
        if not is_admin_user:
            logger.warning(f"تلاش برای دسترسی غیرمجاز: کاربر {user_id}")
        
        return is_admin_user
    
    async def admin_panel(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """نمایش پنل ادمین"""
        user_id = update.effective_user.id
        username = update.effective_user.username
        
        logger.info(f"درخواست پنل ادمین از {user_id} (@{username})")
        
        # بررسی دسترسی
        if not self.is_admin(user_id):
            await update.message.reply_text("⛔️ شما دسترسی ندارید.")
            log_admin(user_id, username, "تلاش دسترسی غیرمجاز", "پنل ادمین")
            return
        
        # دریافت آمار
        try:
            stats = self.db.get_stats()
            
            text = (
                "🔐 <b>پنل مدیریت</b>\n\n"
                f"👥 تعداد کاربران: {stats['users_count']}\n"
                f"📦 تعداد محصولات: {stats['products_count']}\n"
                f"📋 تعداد سفارشات: {stats['orders_count']}\n"
                f"⏳ سفارشات در انتظار: {stats['pending_orders']}\n"
            )
            
            keyboard = [
                [
                    InlineKeyboardButton("➕ افزودن محصول", callback_data="admin_add_product"),
                    InlineKeyboardButton("📦 لیست محصولات", callback_data="admin_list_products")
                ],
                [
                    InlineKeyboardButton("📋 سفارشات", callback_data="admin_orders"),
                    InlineKeyboardButton("👥 کاربران", callback_data="admin_users")
                ],
                [
                    InlineKeyboardButton("📊 آمار کامل", callback_data="admin_full_stats")
                ]
            ]
            
            await update.message.reply_text(
                text,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='HTML'
            )
            
            log_admin(user_id, username, "باز کردن پنل ادمین", f"آمار: {stats}")
            
        except Exception as e:
            logger.error(f"خطا در نمایش پنل ادمین: {e}", exc_info=True)
            await update.message.reply_text("❌ خطا در نمایش پنل")
            await notify_error(e, "high", "admin_panel", user_id)
    
    async def add_product_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """شروع فرآیند افزودن محصول"""
        query = update.callback_query
        await query.answer()
        
        user_id = update.effective_user.id
        username = update.effective_user.username
        
        logger.info(f"شروع افزودن محصول توسط {user_id}")
        
        if not self.is_admin(user_id):
            await query.edit_message_text("⛔️ شما دسترسی ندارید.")
            return
        
        # ذخیره state
        context.user_data['adding_product'] = True
        context.user_data['product_data'] = {}
        
        await query.edit_message_text(
            "➕ <b>افزودن محصول جدید</b>\n\n"
            "لطفاً نام محصول را ارسال کنید:",
            parse_mode='HTML'
        )
        
        log_admin(user_id, username, "شروع افزودن محصول")
    
    async def handle_product_input(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """مدیریت ورودی‌های افزودن محصول"""
        user_id = update.effective_user.id
        username = update.effective_user.username
        
        if not context.user_data.get('adding_product'):
            return
        
        logger.debug(f"دریافت ورودی محصول از {user_id}")
        
        product_data = context.user_data['product_data']
        message_text = update.message.text
        
        try:
            # مرحله 1: نام
            if 'name' not in product_data:
                if not self.validator.validate_text(message_text, 3, 100):
                    await update.message.reply_text("❌ نام باید بین 3 تا 100 کاراکتر باشد.")
                    return
                
                product_data['name'] = message_text
                await update.message.reply_text(
                    f"✅ نام: {message_text}\n\n"
                    "حالا قیمت را به تومان ارسال کنید:"
                )
                log_admin(user_id, username, "وارد کردن نام محصول", message_text)
                return
            
            # مرحله 2: قیمت
            if 'price' not in product_data:
                try:
                    price = int(message_text.replace(',', ''))
                    
                    if not self.config.validate_price(price):
                        await update.message.reply_text(
                            f"❌ قیمت باید بین {self.config.min_price:,} تا {self.config.max_price:,} تومان باشد."
                        )
                        return
                    
                    product_data['price'] = price
                    await update.message.reply_text(
                        f"✅ قیمت: {price:,} تومان\n\n"
                        "حالا تعداد موجودی را ارسال کنید:"
                    )
                    log_admin(user_id, username, "وارد کردن قیمت", f"{price:,} تومان")
                    return
                    
                except ValueError:
                    await update.message.reply_text("❌ لطفاً یک عدد معتبر وارد کنید.")
                    return
            
            # مرحله 3: موجودی
            if 'stock' not in product_data:
                try:
                    stock = int(message_text)
                    
                    if not self.config.validate_stock(stock):
                        await update.message.reply_text(
                            f"❌ موجودی باید بین {self.config.min_stock} تا {self.config.max_stock} باشد."
                        )
                        return
                    
                    product_data['stock'] = stock
                    await update.message.reply_text(
                        f"✅ موجودی: {stock}\n\n"
                        "حالا توضیحات محصول را ارسال کنید (یا /skip برای رد کردن):"
                    )
                    log_admin(user_id, username, "وارد کردن موجودی", str(stock))
                    return
                    
                except ValueError:
                    await update.message.reply_text("❌ لطفاً یک عدد معتبر وارد کنید.")
                    return
            
            # مرحله 4: توضیحات
            if 'description' not in product_data:
                if message_text == '/skip':
                    product_data['description'] = None
                else:
                    if not self.validator.validate_text(message_text, 0, 500):
                        await update.message.reply_text("❌ توضیحات نباید بیشتر از 500 کاراکتر باشد.")
                        return
                    product_data['description'] = message_text
                
                await update.message.reply_text(
                    "حالا عکس محصول را ارسال کنید (یا /skip):"
                )
                log_admin(user_id, username, "وارد کردن توضیحات")
                return
            
        except Exception as e:
            logger.error(f"خطا در مدیریت ورودی محصول: {e}", exc_info=True)
            await update.message.reply_text("❌ خطا در پردازش")
            await notify_error(e, "normal", "handle_product_input", user_id)
    
    async def handle_product_photo(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """مدیریت عکس محصول"""
        user_id = update.effective_user.id
        username = update.effective_user.username
        
        if not context.user_data.get('adding_product'):
            return
        
        logger.debug(f"دریافت عکس محصول از {user_id}")
        
        product_data = context.user_data['product_data']
        
        try:
            # دریافت file_id عکس
            photo = update.message.photo[-1]  # بزرگترین سایز
            product_data['image_file_id'] = photo.file_id
            
            # ذخیره در دیتابیس
            product_id = self.db.add_product(
                name=product_data['name'],
                price=product_data['price'],
                stock=product_data['stock'],
                description=product_data.get('description'),
                image_file_id=product_data['image_file_id']
            )
            
            # ارسال به کانال
            caption = (
                f"🆕 <b>{product_data['name']}</b>\n\n"
                f"💰 قیمت: {product_data['price']:,} تومان\n"
                f"📦 موجودی: {product_data['stock']} عدد\n"
            )
            
            if product_data.get('description'):
                caption += f"\n📝 {product_data['description']}\n"
            
            caption += f"\n🆔 کد محصول: {product_id}"
            
            # ارسال به کانال
            channel_msg = await context.bot.send_photo(
                chat_id=self.config.channel_id,
                photo=product_data['image_file_id'],
                caption=caption,
                parse_mode='HTML'
            )
            
            # به‌روزرسانی message_id
            self.db.update_product_channel_message(product_id, channel_msg.message_id)
            
            # پیام تأیید
            await update.message.reply_text(
                f"✅ محصول با موفقیت اضافه شد!\n\n"
                f"🆔 کد محصول: {product_id}\n"
                f"📢 پست در کانال منتشر شد"
            )
            
            # پاک کردن state
            context.user_data.pop('adding_product', None)
            context.user_data.pop('product_data', None)
            
            log_admin(
                user_id, 
                username, 
                "افزودن محصول کامل شد",
                f"ID: {product_id}, نام: {product_data['name']}"
            )
            log_event("محصول جدید", f"ID {product_id} توسط ادمین {user_id}")
            
        except Exception as e:
            logger.error(f"خطا در ذخیره محصول: {e}", exc_info=True)
            await update.message.reply_text("❌ خطا در ذخیره محصول")
            await notify_error(e, "high", "handle_product_photo", user_id, f"product: {product_data.get('name')}")
    
    async def list_products(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """نمایش لیست محصولات"""
        query = update.callback_query
        await query.answer()
        
        user_id = update.effective_user.id
        username = update.effective_user.username
        
        logger.info(f"درخواست لیست محصولات از {user_id}")
        
        if not self.is_admin(user_id):
            await query.edit_message_text("⛔️ شما دسترسی ندارید.")
            return
        
        try:
            products = self.db.get_all_products(active_only=False)
            
            if not products:
                await query.edit_message_text("📦 هیچ محصولی وجود ندارد.")
                return
            
            text = "📦 <b>لیست محصولات</b>\n\n"
            
            for product in products[:20]:  # حداکثر 20 محصول
                status = "✅" if product['is_active'] else "❌"
                text += (
                    f"{status} <b>{product['name']}</b>\n"
                    f"🆔 کد: {product['product_id']}\n"
                    f"💰 قیمت: {product['price']:,} تومان\n"
                    f"📦 موجودی: {product['stock']}\n\n"
                )
            
            if len(products) > 20:
                text += f"\n... و {len(products) - 20} محصول دیگر"
            
            keyboard = [
                [InlineKeyboardButton("🔙 بازگشت", callback_data="admin_panel")]
            ]
            
            await query.edit_message_text(
                text,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='HTML'
            )
            
            log_admin(user_id, username, "مشاهده لیست محصولات", f"{len(products)} محصول")
            
        except Exception as e:
            logger.error(f"خطا در نمایش لیست: {e}", exc_info=True)
            await query.edit_message_text("❌ خطا در نمایش لیست")
            await notify_error(e, "normal", "list_products", user_id)
    
    async def list_orders(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """نمایش لیست سفارشات"""
        query = update.callback_query
        await query.answer()
        
        user_id = update.effective_user.id
        username = update.effective_user.username
        
        logger.info(f"درخواست لیست سفارشات از {user_id}")
        
        if not self.is_admin(user_id):
            await query.edit_message_text("⛔️ شما دسترسی ندارید.")
            return
        
        try:
            orders = self.db.get_all_orders()
            
            if not orders:
                await query.edit_message_text("📋 هیچ سفارشی وجود ندارد.")
                return
            
            text = "📋 <b>لیست سفارشات</b>\n\n"
            
            status_emoji = {
                'pending': '⏳',
                'confirmed': '✅',
                'cancelled': '❌',
                'completed': '✔️'
            }
            
            for order in orders[:15]:  # حداکثر 15 سفارش
                emoji = status_emoji.get(order['status'], '❓')
                text += (
                    f"{emoji} سفارش #{order['order_id']}\n"
                    f"👤 کاربر: {order['user_id']}\n"
                    f"💰 مبلغ: {order['total_amount']:,} تومان\n"
                    f"📅 {order['created_at']}\n\n"
                )
            
            if len(orders) > 15:
                text += f"\n... و {len(orders) - 15} سفارش دیگر"
            
            keyboard = [
                [InlineKeyboardButton("🔙 بازگشت", callback_data="admin_panel")]
            ]
            
            await query.edit_message_text(
                text,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='HTML'
            )
            
            log_admin(user_id, username, "مشاهده لیست سفارشات", f"{len(orders)} سفارش")
            
        except Exception as e:
            logger.error(f"خطا در نمایش سفارشات: {e}", exc_info=True)
            await query.edit_message_text("❌ خطا در نمایش سفارشات")
            await notify_error(e, "normal", "list_orders", user_id)
    
    async def list_users(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """نمایش لیست کاربران"""
        query = update.callback_query
        await query.answer()
        
        user_id = update.effective_user.id
        username = update.effective_user.username
        
        logger.info(f"درخواست لیست کاربران از {user_id}")
        
        if not self.is_admin(user_id):
            await query.edit_message_text("⛔️ شما دسترسی ندارید.")
            return
        
        try:
            users = self.db.get_all_users()
            
            if not users:
                await query.edit_message_text("👥 هیچ کاربری وجود ندارد.")
                return
            
            text = "👥 <b>لیست کاربران</b>\n\n"
            text += f"🔢 تعداد کل: {len(users)}\n\n"
            
            for user in users[:20]:  # حداکثر 20 کاربر
                username_str = f"@{user['username']}" if user['username'] else "بدون نام کاربری"
                text += (
                    f"👤 {user['first_name']} ({username_str})\n"
                    f"🆔 {user['user_id']}\n"
                    f"📅 {user['created_at']}\n\n"
                )
            
            if len(users) > 20:
                text += f"\n... و {len(users) - 20} کاربر دیگر"
            
            keyboard = [
                [InlineKeyboardButton("🔙 بازگشت", callback_data="admin_panel")]
            ]
            
            await query.edit_message_text(
                text,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='HTML'
            )
            
            log_admin(user_id, username, "مشاهده لیست کاربران", f"{len(users)} کاربر")
            
        except Exception as e:
            logger.error(f"خطا در نمایش کاربران: {e}", exc_info=True)
            await query.edit_message_text("❌ خطا در نمایش کاربران")
            await notify_error(e, "normal", "list_users", user_id)
    
    async def full_stats(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """نمایش آمار کامل"""
        query = update.callback_query
        await query.answer()
        
        user_id = update.effective_user.id
        username = update.effective_user.username
        
        logger.info(f"درخواست آمار کامل از {user_id}")
        
        if not self.is_admin(user_id):
            await query.edit_message_text("⛔️ شما دسترسی ندارید.")
            return
        
        try:
            stats = self.db.get_stats()
            orders = self.db.get_all_orders()
            
            # محاسبه آمار سفارشات
            total_revenue = sum(o['total_amount'] for o in orders if o['status'] == 'completed')
            
            text = (
                "📊 <b>آمار کامل سیستم</b>\n\n"
                f"👥 کاربران: {stats['users_count']}\n"
                f"📦 محصولات فعال: {stats['products_count']}\n"
                f"📋 کل سفارشات: {stats['orders_count']}\n"
                f"⏳ در انتظار: {stats['pending_orders']}\n"
                f"💰 درآمد کل: {total_revenue:,} تومان\n"
            )
            
            keyboard = [
                [InlineKeyboardButton("🔙 بازگشت", callback_data="admin_panel")]
            ]
            
            await query.edit_message_text(
                text,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='HTML'
            )
            
            log_admin(user_id, username, "مشاهده آمار کامل", str(stats))
            
        except Exception as e:
            logger.error(f"خطا در نمایش آمار: {e}", exc_info=True)
            await query.edit_message_text("❌ خطا در نمایش آمار")
            await notify_error(e, "normal", "full_stats", user_id)


if __name__ == "__main__":
    print("⚠️  این ماژول باید در main.py استفاده شود")
