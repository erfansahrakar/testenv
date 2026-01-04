"""
سیستم Rate Limiting برای جلوگیری از سوء استفاده

محدودسازی تعداد درخواست‌های کاربران
"""

from collections import defaultdict
from datetime import datetime, timedelta
from typing import Dict, Tuple
from utils.logger import get_logger, log_security

logger = get_logger('rate_limiter')


class RateLimiter:
    """کلاس محدودسازی نرخ درخواست"""
    
    def __init__(self, max_per_minute: int = 20, max_per_hour: int = 100):
        """
        Args:
            max_per_minute: حداکثر درخواست در دقیقه
            max_per_hour: حداکثر درخواست در ساعت
        """
        self.max_per_minute = max_per_minute
        self.max_per_hour = max_per_hour
        
        # ذخیره زمان درخواست‌ها
        self.requests: Dict[int, list] = defaultdict(list)
        
        logger.info(f"✅ Rate Limiter: {max_per_minute}/min, {max_per_hour}/hour")
    
    def check_rate_limit(self, user_id: int) -> bool:
        """
        بررسی محدودیت نرخ درخواست
        
        Returns:
            True: اجازه درخواست
            False: محدودیت فعال
        """
        now = datetime.now()
        
        # دریافت لیست درخواست‌های کاربر
        user_requests = self.requests[user_id]
        
        # پاکسازی درخواست‌های قدیمی (بیش از 1 ساعت)
        cutoff_time = now - timedelta(hours=1)
        user_requests[:] = [req_time for req_time in user_requests if req_time > cutoff_time]
        
        # شمارش درخواست‌های اخیر
        minute_ago = now - timedelta(minutes=1)
        requests_last_minute = sum(1 for req_time in user_requests if req_time > minute_ago)
        requests_last_hour = len(user_requests)
        
        # بررسی محدودیت دقیقه
        if requests_last_minute >= self.max_per_minute:
            logger.warning(
                f"Rate limit (minute) برای کاربر {user_id}: "
                f"{requests_last_minute}/{self.max_per_minute}"
            )
            log_security(
                "Rate limit hit (minute)",
                user_id,
                f"{requests_last_minute} requests"
            )
            return False
        
        # بررسی محدودیت ساعت
        if requests_last_hour >= self.max_per_hour:
            logger.warning(
                f"Rate limit (hour) برای کاربر {user_id}: "
                f"{requests_last_hour}/{self.max_per_hour}"
            )
            log_security(
                "Rate limit hit (hour)",
                user_id,
                f"{requests_last_hour} requests"
            )
            return False
        
        # ثبت درخواست جدید
        user_requests.append(now)
        
        logger.debug(f"Request allowed for user {user_id}: {requests_last_minute}/min, {requests_last_hour}/hour")
        
        return True
    
    def get_user_stats(self, user_id: int) -> Tuple[int, int]:
        """
        دریافت آمار درخواست‌های کاربر
        
        Returns:
            (تعداد در دقیقه گذشته, تعداد در ساعت گذشته)
        """
        now = datetime.now()
        user_requests = self.requests[user_id]
        
        minute_ago = now - timedelta(minutes=1)
        requests_last_minute = sum(1 for req_time in user_requests if req_time > minute_ago)
        requests_last_hour = len(user_requests)
        
        return requests_last_minute, requests_last_hour
    
    def reset_user(self, user_id: int):
        """ریست کردن محدودیت کاربر (برای ادمین)"""
        if user_id in self.requests:
            self.requests.pop(user_id)
            logger.info(f"Rate limit reset for user {user_id}")
            log_security("Rate limit reset", user_id, "توسط ادمین")


if __name__ == "__main__":
    print("⚠️  این ماژول باید در سایر handler ها استفاده شود")
