"""
سیستم Validation برای ربات

اعتبارسنجی ورودی‌های کاربران و ادمین‌ها
"""

import re
from typing import Optional
from config import BotConfig
from utils.logger import get_logger, log_security

logger = get_logger('validation')


class Validator:
    """کلاس اعتبارسنجی ورودی‌ها"""
    
    def __init__(self, config: BotConfig):
        self.config = config
        logger.info("✅ Validator راه‌اندازی شد")
    
    def validate_text(self, text: str, min_length: int = 1, max_length: int = 1000) -> bool:
        """اعتبارسنجی متن"""
        if not text or not isinstance(text, str):
            logger.warning("متن نامعتبر: None یا غیر string")
            return False
        
        text = text.strip()
        
        if len(text) < min_length:
            logger.warning(f"متن کوتاه‌تر از حد مجاز: {len(text)} < {min_length}")
            return False
        
        if len(text) > max_length:
            logger.warning(f"متن بلندتر از حد مجاز: {len(text)} > {max_length}")
            return False
        
        return True
    
    def validate_price(self, price: int) -> bool:
        """اعتبارسنجی قیمت"""
        if not isinstance(price, int):
            logger.warning(f"قیمت باید عدد باشد: {type(price)}")
            return False
        
        return self.config.validate_price(price)
    
    def validate_stock(self, stock: int) -> bool:
        """اعتبارسنجی موجودی"""
        if not isinstance(stock, int):
            logger.warning(f"موجودی باید عدد باشد: {type(stock)}")
            return False
        
        return self.config.validate_stock(stock)
    
    def validate_quantity(self, quantity: int, max_quantity: Optional[int] = None) -> bool:
        """اعتبارسنجی تعداد"""
        if not isinstance(quantity, int):
            logger.warning(f"تعداد باید عدد باشد: {type(quantity)}")
            return False
        
        if quantity < 1:
            logger.warning(f"تعداد باید حداقل 1 باشد: {quantity}")
            return False
        
        if max_quantity and quantity > max_quantity:
            logger.warning(f"تعداد بیش از حد مجاز: {quantity} > {max_quantity}")
            return False
        
        return True
    
    def sanitize_text(self, text: str) -> str:
        """پاکسازی متن از کاراکترهای مخرب"""
        if not text:
            return ""
        
        # حذف تگ‌های HTML
        text = re.sub(r'<[^>]+>', '', text)
        
        # حذف کاراکترهای کنترلی
        text = ''.join(char for char in text if ord(char) >= 32 or char == '\n')
        
        return text.strip()
    
    def detect_spam(self, text: str) -> bool:
        """تشخیص اسپم"""
        if not text:
            return False
        
        # تکرار زیاد کاراکتر
        if re.search(r'(.)\1{10,}', text):
            log_security("تشخیص اسپم", details="تکرار زیاد کاراکتر")
            return True
        
        # لینک مشکوک
        if re.search(r'(bit\.ly|t\.me|telegram\.me)', text, re.IGNORECASE):
            log_security("تشخیص اسپم", details="لینک مشکوک")
            return True
        
        return False


if __name__ == "__main__":
    print("⚠️  این ماژول باید در سایر handler ها استفاده شود")
