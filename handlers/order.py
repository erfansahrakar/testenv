"""
Handler های مربوط به سفارشات و سبد خرید

شامل: افزودن به سبد، مشاهده سبد، ثبت سفارش
"""

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from typing import List, Dict, Any

from database import Database
from config import BotConfig
from utils.logger import get_logger, log_user, log_order, log_error, log_event
from utils.error_notifier import notify_error
from utils.rate_limiter import RateLimiter

# Logger این ماژول
logger = get_logger('order_handler')


class OrderHandler:
    """کلاس مدیریت handler های سفارش"""
    
    def __init__(self, db: Database, config: BotConfig, rate_limiter: RateLimiter):
        self.db = db
        self.config = config
        self.rate_limiter = rate_limiter
        
        logger.info("✅ OrderHandler راه‌اندازی شد")
    
    def _get_cart(self, context: ContextTypes.DEFAULT_TYPE) -> Dict[int, int]:
        """دریافت سبد خرید از context"""
        if 'cart' not in context.user_data:
            context.user_data['cart'] = {}
        return context.user_data['cart']
    
    def _clear_cart(self, context: ContextTypes.DEFAULT_TYPE):
        """خالی کردن سبد خرید"""
        context.user_data['cart'] = {}
    
    async def add_to_cart(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """افزودن محصول به سبد خرید"""
        query = update.callback_query
        await query.answer("✅ به سبد اضافه شد")
        
        user_id = update.effective_user.id
        username = update.effective_user.username
        
        # پارس callback_data: "add_to_cart_PRODUCT_ID_QUANTITY"
        try:
            parts = query.data.split('_')
            product_id = int(parts[3])
            quantity = int(parts[4])
        except (ValueError, IndexError):
            logger.error(f"callback_data نامعتبر: {query.data}")
            await query.answer("❌ خطا در پردازش", show_alert=True)
            return
        
        logger.info(f"افزودن به سبد: کاربر {user_id}, محصول {product_id}, تعداد {quantity}")
        
        try:
            # بررسی rate limit
            if not self.rate_limiter.check_rate_limit(user_id):
                await query.answer("⏳ لطفاً کمی صبر کنید", show_alert=True)
                return
            
            # دریافت محصول
            product = self.db.get_product(product_id)
            
            if not product:
                await query.answer("❌ محصول یافت نشد", show_alert=True)
                return
            
            if not product['is_active']:
                await query.answer("❌ این محصول غیرفعال است", show_alert=True)
                return
            
            # دریافت سبد
            cart = self._get_cart(context)
            
            # محاسبه تعداد فعلی در سبد
            current_quantity = cart.get(product_id, 0)
            new_quantity = current_quantity + quantity
            
            # بررسی موجودی
            if new_quantity > product['stock']:
                await query.answer(
                    f"❌ موجودی کافی نیست!\nموجود: {product['stock']}, در سبد: {current_quantity}",
                    show_alert=True
                )
                return
            
            # بررسی حداکثر تعداد در سبد
            total_items = sum(cart.values()) + quantity
            if total_items > self.config.max_cart_items:
                await query.answer(
                    f"❌ حداکثر {self.config.max_cart_items} محصول در سبد مجاز است",
                    show_alert=True
                )
                return
            
            # افزودن به سبد
            cart[product_id] = new_quantity
            
            # پیام تأیید
            text = (
                f"✅ <b>{product['name']}</b>\n\n"
                f"تعداد {quantity} عدد به سبد اضافه شد\n"
                f"جمع در سبد: {new_quantity} عدد"
            )
            
            keyboard = [
                [
                    InlineKeyboardButton("🛒 مشاهده سبد", callback_data="user_cart"),
                    InlineKeyboardButton("🛍 ادامه خرید", callback_data="user_products")
                ]
            ]
            
            await query.edit_message_text(
                text,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='HTML'
            )
            
            log_user(
                user_id,
                username,
                "افزودن به سبد",
                f"محصول {product_id} ({product['name']}), تعداد {quantity}"
            )
            
        except Exception as e:
            logger.error(f"خطا در افزودن به سبد: {e}", exc_info=True)
            await query.answer("❌ خطا در افزودن به سبد", show_alert=True)
            await notify_error(e, "normal", "add_to_cart", user_id)
    
    async def view_cart(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """مشاهده سبد خرید"""
        query = update.callback_query
        await query.answer()
        
        user_id = update.effective_user.id
        username = update.effective_user.username
        
        logger.info(f"مشاهده سبد خرید: کاربر {user_id}")
        
        try:
            # دریافت سبد
            cart = self._get_cart(context)
            
            if not cart:
                text = "🛒 سبد خرید شما خالی است"
                keyboard = [
                    [InlineKeyboardButton("🛍 شروع خرید", callback_data="user_products")]
                ]
                
                await query.edit_message_text(
                    text,
                    reply_markup=InlineKeyboardMarkup(keyboard)
                )
                
                log_user(user_id, username, "مشاهده سبد خالی")
                return
            
            # دریافت اطلاعات محصولات
            text = "🛒 <b>سبد خرید شما</b>\n\n"
            total_price = 0
            cart_items = []
            
            for product_id, quantity in cart.items():
                product = self.db.get_product(product_id)
                
                if not product:
                    logger.warning(f"محصول {product_id} در سبد یافت نشد")
                    continue
                
                if not product['is_active'] or product['stock'] < quantity:
                    # محصول غیرفعال یا موجودی کم
                    text += f"❌ {product['name']} (ناموجود)\n\n"
                    continue
                
                item_total = product['price'] * quantity
                total_price += item_total
                
                text += (
                    f"📦 <b>{product['name']}</b>\n"
                    f"💰 قیمت: {product['price']:,} تومان\n"
                    f"🔢 تعداد: {quantity}\n"
                    f"💵 جمع: {item_total:,} تومان\n\n"
                )
                
                cart_items.append({
                    'product_id': product_id,
                    'name': product['name'],
                    'quantity': quantity,
                    'price': product['price']
                })
            
            if not cart_items:
                text = "🛒 سبد خرید شما خالی است (محصولات غیرفعال شده‌اند)"
                keyboard = [
                    [InlineKeyboardButton("🛍 شروع خرید", callback_data="user_products")]
                ]
            else:
                text += f"💰 <b>جمع کل: {total_price:,} تومان</b>"
                
                keyboard = [
                    [
                        InlineKeyboardButton("✅ ثبت سفارش", callback_data="confirm_order"),
                        InlineKeyboardButton("🗑 خالی کردن سبد", callback_data="clear_cart")
                    ],
                    [
                        InlineKeyboardButton("🛍 ادامه خرید", callback_data="user_products"),
                        InlineKeyboardButton("🔙 منوی اصلی", callback_data="user_main_menu")
                    ]
                ]
            
            await query.edit_message_text(
                text,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='HTML'
            )
            
            log_user(
                user_id,
                username,
                "مشاهده سبد خرید",
                f"{len(cart_items)} آیتم, مبلغ {total_price:,}"
            )
            
        except Exception as e:
            logger.error(f"خطا در نمایش سبد: {e}", exc_info=True)
            await query.edit_message_text("❌ خطا در نمایش سبد خرید")
            await notify_error(e, "normal", "view_cart", user_id)
    
    async def clear_cart(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """خالی کردن سبد خرید"""
        query = update.callback_query
        await query.answer("🗑 سبد خالی شد")
        
        user_id = update.effective_user.id
        username = update.effective_user.username
        
        logger.info(f"خالی کردن سبد: کاربر {user_id}")
        
        try:
            self._clear_cart(context)
            
            text = "🗑 سبد خرید شما خالی شد"
            keyboard = [
                [InlineKeyboardButton("🛍 شروع خرید", callback_data="user_products")]
            ]
            
            await query.edit_message_text(
                text,
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            
            log_user(user_id, username, "خالی کردن سبد")
            
        except Exception as e:
            logger.error(f"خطا در خالی کردن سبد: {e}", exc_info=True)
            await notify_error(e, "low", "clear_cart", user_id)
    
    async def confirm_order(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """تأیید و ثبت سفارش"""
        query = update.callback_query
        await query.answer()
        
        user_id = update.effective_user.id
        username = update.effective_user.username
        
        logger.info(f"تأیید سفارش: کاربر {user_id}")
        
        try:
            # دریافت سبد
            cart = self._get_cart(context)
            
            if not cart:
                await query.edit_message_text("❌ سبد خرید خالی است")
                return
            
            # محاسبه مجموع و بررسی موجودی
            total_amount = 0
            items_to_order = []
            errors = []
            
            for product_id, quantity in cart.items():
                product = self.db.get_product(product_id)
                
                if not product:
                    errors.append(f"محصول {product_id} یافت نشد")
                    continue
                
                if not product['is_active']:
                    errors.append(f"{product['name']} غیرفعال شده")
                    continue
                
                if product['stock'] < quantity:
                    errors.append(
                        f"{product['name']}: موجودی کافی نیست "
                        f"(درخواست: {quantity}, موجود: {product['stock']})"
                    )
                    continue
                
                items_to_order.append({
                    'product_id': product_id,
                    'product': product,
                    'quantity': quantity
                })
                
                total_amount += product['price'] * quantity
            
            # بررسی خطاها
            if errors:
                text = "❌ <b>خطا در ثبت سفارش:</b>\n\n"
                text += "\n".join(f"• {error}" for error in errors)
                
                keyboard = [
                    [InlineKeyboardButton("🛒 بازگشت به سبد", callback_data="user_cart")]
                ]
                
                await query.edit_message_text(
                    text,
                    reply_markup=InlineKeyboardMarkup(keyboard),
                    parse_mode='HTML'
                )
                
                log_user(user_id, username, "خطا در ثبت سفارش", ", ".join(errors))
                return
            
            if not items_to_order:
                await query.edit_message_text("❌ هیچ محصول معتبری در سبد نیست")
                return
            
            # ایجاد سفارش
            order_id = self.db.create_order(user_id)
            
            # افزودن آیتم‌ها
            for item in items_to_order:
                self.db.add_order_item(
                    order_id,
                    item['product_id'],
                    item['quantity'],
                    item['product']['price']
                )
                
                # کم کردن از موجودی
                new_stock = item['product']['stock'] - item['quantity']
                self.db.update_product(item['product_id'], stock=new_stock)
            
            # به‌روزرسانی مبلغ سفارش
            self.db.update_order_status(order_id, 'pending')
            
            # خالی کردن سبد
            self._clear_cart(context)
            
            # پیام تأیید
            text = (
                f"✅ <b>سفارش شما با موفقیت ثبت شد!</b>\n\n"
                f"🆔 شماره سفارش: #{order_id}\n"
                f"💰 مبلغ کل: {total_amount:,} تومان\n"
                f"📦 تعداد اقلام: {len(items_to_order)}\n\n"
                f"📞 به زودی با شما تماس گرفته خواهد شد"
            )
            
            keyboard = [
                [
                    InlineKeyboardButton("📋 سفارشات من", callback_data="user_orders"),
                    InlineKeyboardButton("🛍 خرید جدید", callback_data="user_products")
                ]
            ]
            
            await query.edit_message_text(
                text,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='HTML'
            )
            
            # لاگ
            log_order(
                order_id,
                user_id,
                "سفارش ثبت شد",
                f"{len(items_to_order)} آیتم, مبلغ {total_amount:,}"
            )
            log_user(
                user_id,
                username,
                "ثبت سفارش",
                f"سفارش #{order_id}, مبلغ {total_amount:,}"
            )
            log_event("سفارش جدید", f"سفارش #{order_id} توسط کاربر {user_id}")
            
            # ارسال نوتیفیکیشن به ادمین (اختیاری)
            # می‌تونیم این رو بعداً اضافه کنیم
            
        except Exception as e:
            logger.error(f"خطا در ثبت سفارش: {e}", exc_info=True)
            await query.edit_message_text("❌ خطا در ثبت سفارش")
            await notify_error(e, "high", "confirm_order", user_id)
    
    async def view_orders(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """مشاهده سفارشات کاربر"""
        query = update.callback_query
        await query.answer()
        
        user_id = update.effective_user.id
        username = update.effective_user.username
        
        logger.info(f"مشاهده سفارشات: کاربر {user_id}")
        
        try:
            # دریافت سفارشات
            orders = self.db.get_user_orders(user_id)
            
            if not orders:
                text = "📋 شما هنوز سفارشی ثبت نکرده‌اید"
                keyboard = [
                    [InlineKeyboardButton("🛍 شروع خرید", callback_data="user_products")]
                ]
                
                await query.edit_message_text(
                    text,
                    reply_markup=InlineKeyboardMarkup(keyboard)
                )
                
                log_user(user_id, username, "مشاهده سفارشات", "هیچ سفارشی وجود ندارد")
                return
            
            # نمایش لیست سفارشات
            text = "📋 <b>سفارشات شما</b>\n\n"
            
            status_emoji = {
                'pending': '⏳',
                'confirmed': '✅',
                'cancelled': '❌',
                'completed': '✔️'
            }
            
            status_text = {
                'pending': 'در انتظار تأیید',
                'confirmed': 'تأیید شده',
                'cancelled': 'لغو شده',
                'completed': 'تکمیل شده'
            }
            
            for order in orders[:10]:  # حداکثر 10 سفارش
                emoji = status_emoji.get(order['status'], '❓')
                status = status_text.get(order['status'], order['status'])
                
                text += (
                    f"{emoji} سفارش #{order['order_id']}\n"
                    f"📅 {order['created_at']}\n"
                    f"💰 {order['total_amount']:,} تومان\n"
                    f"📊 وضعیت: {status}\n\n"
                )
            
            if len(orders) > 10:
                text += f"\n... و {len(orders) - 10} سفارش دیگر"
            
            keyboard = [
                [InlineKeyboardButton("🔙 منوی اصلی", callback_data="user_main_menu")]
            ]
            
            await query.edit_message_text(
                text,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='HTML'
            )
            
            log_user(user_id, username, "مشاهده سفارشات", f"{len(orders)} سفارش")
            
        except Exception as e:
            logger.error(f"خطا در نمایش سفارشات: {e}", exc_info=True)
            await query.edit_message_text("❌ خطا در نمایش سفارشات")
            await notify_error(e, "normal", "view_orders", user_id)


if __name__ == "__main__":
    print("⚠️  این ماژول باید در main.py استفاده شود")
