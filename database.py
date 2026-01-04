"""
مدیریت دیتابیس ربات فروشگاه مانتو

این ماژول مسئول تمام عملیات دیتابیس است
"""

import sqlite3
from typing import List, Optional, Dict, Any, Tuple
from datetime import datetime
from contextlib import contextmanager

from utils.logger import get_logger, log_db, log_error

# Logger این ماژول
logger = get_logger('database')


class Database:
    """کلاس مدیریت دیتابیس"""
    
    def __init__(self, db_path: str):
        """
        Args:
            db_path: مسیر فایل دیتابیس
        """
        self.db_path = db_path
        logger.info(f"🗄️  در حال اتصال به دیتابیس: {db_path}")
        
        try:
            self._init_database()
            logger.info("✅ دیتابیس با موفقیت راه‌اندازی شد")
        except Exception as e:
            logger.critical(f"❌ خطای بحرانی در راه‌اندازی دیتابیس: {e}")
            raise
    
    @contextmanager
    def _get_connection(self):
        """Context manager برای مدیریت اتصال دیتابیس"""
        conn = None
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            logger.debug("اتصال به دیتابیس برقرار شد")
            yield conn
            conn.commit()
            logger.debug("تغییرات commit شد")
        except Exception as e:
            if conn:
                conn.rollback()
                logger.warning("تغییرات rollback شد")
            logger.error(f"خطا در عملیات دیتابیس: {e}")
            raise
        finally:
            if conn:
                conn.close()
                logger.debug("اتصال بسته شد")
    
    def _init_database(self):
        """ایجاد جداول دیتابیس"""
        logger.info("در حال ایجاد جداول دیتابیس...")
        
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # جدول کاربران
            logger.debug("ایجاد جدول users...")
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    username TEXT,
                    first_name TEXT,
                    last_name TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    is_blocked INTEGER DEFAULT 0
                )
            """)
            log_db("CREATE TABLE", "users")
            
            # جدول محصولات
            logger.debug("ایجاد جدول products...")
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS products (
                    product_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    description TEXT,
                    price INTEGER NOT NULL,
                    stock INTEGER DEFAULT 0,
                    image_file_id TEXT,
                    channel_message_id INTEGER,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    is_active INTEGER DEFAULT 1
                )
            """)
            log_db("CREATE TABLE", "products")
            
            # جدول سفارشات
            logger.debug("ایجاد جدول orders...")
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS orders (
                    order_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    status TEXT DEFAULT 'pending',
                    total_amount INTEGER DEFAULT 0,
                    notes TEXT,
                    FOREIGN KEY (user_id) REFERENCES users(user_id)
                )
            """)
            log_db("CREATE TABLE", "orders")
            
            # جدول آیتم‌های سفارش
            logger.debug("ایجاد جدول order_items...")
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS order_items (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    order_id INTEGER NOT NULL,
                    product_id INTEGER NOT NULL,
                    quantity INTEGER NOT NULL,
                    price_at_order INTEGER NOT NULL,
                    FOREIGN KEY (order_id) REFERENCES orders(order_id),
                    FOREIGN KEY (product_id) REFERENCES products(product_id)
                )
            """)
            log_db("CREATE TABLE", "order_items")
            
            # ایندکس‌ها برای بهبود عملکرد
            logger.debug("ایجاد ایندکس‌ها...")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_orders_user_id ON orders(user_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_orders_status ON orders(status)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_order_items_order_id ON order_items(order_id)")
            log_db("CREATE INDEX", "performance indexes")
        
        logger.info("✅ جداول با موفقیت ایجاد شدند")
    
    # ========== عملیات کاربران ==========
    
    def add_or_update_user(
        self,
        user_id: int,
        username: Optional[str] = None,
        first_name: Optional[str] = None,
        last_name: Optional[str] = None
    ):
        """افزودن یا به‌روزرسانی کاربر"""
        logger.debug(f"افزودن/به‌روزرسانی کاربر {user_id}")
        
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                
                cursor.execute("""
                    INSERT INTO users (user_id, username, first_name, last_name, last_seen)
                    VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
                    ON CONFLICT(user_id) DO UPDATE SET
                        username = ?,
                        first_name = ?,
                        last_name = ?,
                        last_seen = CURRENT_TIMESTAMP
                """, (user_id, username, first_name, last_name, username, first_name, last_name))
                
                log_db("UPSERT", f"user {user_id} (@{username})")
                logger.info(f"✅ کاربر {user_id} ثبت/به‌روزرسانی شد")
                
        except Exception as e:
            log_error(e, "add_or_update_user", user_id)
            raise
    
    def get_user(self, user_id: int) -> Optional[Dict[str, Any]]:
        """دریافت اطلاعات کاربر"""
        logger.debug(f"دریافت اطلاعات کاربر {user_id}")
        
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
                row = cursor.fetchone()
                
                if row:
                    result = dict(row)
                    log_db("SELECT", f"user {user_id} found")
                    return result
                
                log_db("SELECT", f"user {user_id} not found")
                return None
                
        except Exception as e:
            log_error(e, "get_user", user_id)
            raise
    
    def is_user_blocked(self, user_id: int) -> bool:
        """بررسی بلاک بودن کاربر"""
        logger.debug(f"بررسی بلاک کاربر {user_id}")
        
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT is_blocked FROM users WHERE user_id = ?", (user_id,))
                row = cursor.fetchone()
                
                if row:
                    is_blocked = bool(row['is_blocked'])
                    log_db("SELECT", f"user {user_id} blocked={is_blocked}")
                    return is_blocked
                
                return False
                
        except Exception as e:
            log_error(e, "is_user_blocked", user_id)
            return False
    
    def get_all_users(self) -> List[Dict[str, Any]]:
        """دریافت لیست تمام کاربران"""
        logger.debug("دریافت لیست کاربران")
        
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM users ORDER BY created_at DESC")
                rows = cursor.fetchall()
                
                result = [dict(row) for row in rows]
                log_db("SELECT", f"found {len(result)} users")
                logger.info(f"📊 تعداد کاربران: {len(result)}")
                
                return result
                
        except Exception as e:
            log_error(e, "get_all_users")
            raise
    
    # ========== عملیات محصولات ==========
    
    def add_product(
        self,
        name: str,
        price: int,
        description: Optional[str] = None,
        stock: int = 0,
        image_file_id: Optional[str] = None
    ) -> int:
        """افزودن محصول جدید"""
        logger.debug(f"افزودن محصول: {name}")
        
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                
                cursor.execute("""
                    INSERT INTO products (name, description, price, stock, image_file_id)
                    VALUES (?, ?, ?, ?, ?)
                """, (name, description, price, stock, image_file_id))
                
                product_id = cursor.lastrowid
                
                log_db("INSERT", f"product '{name}' (ID: {product_id})")
                logger.info(f"✅ محصول '{name}' با ID {product_id} اضافه شد")
                
                return product_id
                
        except Exception as e:
            log_error(e, f"add_product: {name}")
            raise
    
    def get_product(self, product_id: int) -> Optional[Dict[str, Any]]:
        """دریافت اطلاعات محصول"""
        logger.debug(f"دریافت محصول {product_id}")
        
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM products WHERE product_id = ?", (product_id,))
                row = cursor.fetchone()
                
                if row:
                    result = dict(row)
                    log_db("SELECT", f"product {product_id} found: {result['name']}")
                    return result
                
                log_db("SELECT", f"product {product_id} not found")
                return None
                
        except Exception as e:
            log_error(e, f"get_product: {product_id}")
            raise
    
    def get_all_products(self, active_only: bool = True) -> List[Dict[str, Any]]:
        """دریافت لیست محصولات"""
        logger.debug(f"دریافت محصولات (فعال فقط: {active_only})")
        
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                
                if active_only:
                    cursor.execute("""
                        SELECT * FROM products 
                        WHERE is_active = 1 
                        ORDER BY created_at DESC
                    """)
                else:
                    cursor.execute("SELECT * FROM products ORDER BY created_at DESC")
                
                rows = cursor.fetchall()
                result = [dict(row) for row in rows]
                
                log_db("SELECT", f"found {len(result)} products")
                logger.info(f"📦 تعداد محصولات: {len(result)}")
                
                return result
                
        except Exception as e:
            log_error(e, "get_all_products")
            raise
    
    def update_product(
        self,
        product_id: int,
        name: Optional[str] = None,
        price: Optional[int] = None,
        description: Optional[str] = None,
        stock: Optional[int] = None,
        image_file_id: Optional[str] = None,
        is_active: Optional[bool] = None
    ):
        """به‌روزرسانی محصول"""
        logger.debug(f"به‌روزرسانی محصول {product_id}")
        
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                
                updates = []
                values = []
                
                if name is not None:
                    updates.append("name = ?")
                    values.append(name)
                
                if price is not None:
                    updates.append("price = ?")
                    values.append(price)
                
                if description is not None:
                    updates.append("description = ?")
                    values.append(description)
                
                if stock is not None:
                    updates.append("stock = ?")
                    values.append(stock)
                
                if image_file_id is not None:
                    updates.append("image_file_id = ?")
                    values.append(image_file_id)
                
                if is_active is not None:
                    updates.append("is_active = ?")
                    values.append(1 if is_active else 0)
                
                if not updates:
                    logger.warning(f"هیچ فیلدی برای به‌روزرسانی محصول {product_id} وجود ندارد")
                    return
                
                updates.append("updated_at = CURRENT_TIMESTAMP")
                values.append(product_id)
                
                query = f"UPDATE products SET {', '.join(updates)} WHERE product_id = ?"
                cursor.execute(query, values)
                
                log_db("UPDATE", f"product {product_id} - {len(updates)} fields")
                logger.info(f"✅ محصول {product_id} به‌روزرسانی شد")
                
        except Exception as e:
            log_error(e, f"update_product: {product_id}")
            raise
    
    def update_product_channel_message(self, product_id: int, message_id: int):
        """به‌روزرسانی شناسه پیام کانال"""
        logger.debug(f"به‌روزرسانی message_id محصول {product_id}")
        
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE products 
                    SET channel_message_id = ?, updated_at = CURRENT_TIMESTAMP 
                    WHERE product_id = ?
                """, (message_id, product_id))
                
                log_db("UPDATE", f"product {product_id} channel_message_id = {message_id}")
                logger.info(f"✅ message_id محصول {product_id} به‌روزرسانی شد")
                
        except Exception as e:
            log_error(e, f"update_product_channel_message: {product_id}")
            raise
    
    def delete_product(self, product_id: int):
        """حذف محصول (غیرفعال کردن)"""
        logger.debug(f"غیرفعال کردن محصول {product_id}")
        
        try:
            self.update_product(product_id, is_active=False)
            logger.info(f"✅ محصول {product_id} غیرفعال شد")
            
        except Exception as e:
            log_error(e, f"delete_product: {product_id}")
            raise
    
    # ========== عملیات سفارشات ==========
    
    def create_order(self, user_id: int, notes: Optional[str] = None) -> int:
        """ایجاد سفارش جدید"""
        logger.debug(f"ایجاد سفارش برای کاربر {user_id}")
        
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                
                cursor.execute("""
                    INSERT INTO orders (user_id, notes)
                    VALUES (?, ?)
                """, (user_id, notes))
                
                order_id = cursor.lastrowid
                
                log_db("INSERT", f"order {order_id} for user {user_id}")
                logger.info(f"✅ سفارش {order_id} برای کاربر {user_id} ایجاد شد")
                
                return order_id
                
        except Exception as e:
            log_error(e, f"create_order for user {user_id}")
            raise
    
    def add_order_item(
        self,
        order_id: int,
        product_id: int,
        quantity: int,
        price_at_order: int
    ):
        """افزودن آیتم به سفارش"""
        logger.debug(f"افزودن آیتم به سفارش {order_id}")
        
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                
                cursor.execute("""
                    INSERT INTO order_items (order_id, product_id, quantity, price_at_order)
                    VALUES (?, ?, ?, ?)
                """, (order_id, product_id, quantity, price_at_order))
                
                log_db("INSERT", f"order_item: order={order_id}, product={product_id}, qty={quantity}")
                logger.info(f"✅ آیتم به سفارش {order_id} اضافه شد")
                
        except Exception as e:
            log_error(e, f"add_order_item: order {order_id}")
            raise
    
    def get_order(self, order_id: int) -> Optional[Dict[str, Any]]:
        """دریافت اطلاعات سفارش"""
        logger.debug(f"دریافت سفارش {order_id}")
        
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM orders WHERE order_id = ?", (order_id,))
                row = cursor.fetchone()
                
                if row:
                    result = dict(row)
                    log_db("SELECT", f"order {order_id} found")
                    return result
                
                log_db("SELECT", f"order {order_id} not found")
                return None
                
        except Exception as e:
            log_error(e, f"get_order: {order_id}")
            raise
    
    def get_order_items(self, order_id: int) -> List[Dict[str, Any]]:
        """دریافت آیتم‌های سفارش"""
        logger.debug(f"دریافت آیتم‌های سفارش {order_id}")
        
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT oi.*, p.name as product_name
                    FROM order_items oi
                    JOIN products p ON oi.product_id = p.product_id
                    WHERE oi.order_id = ?
                """, (order_id,))
                
                rows = cursor.fetchall()
                result = [dict(row) for row in rows]
                
                log_db("SELECT", f"found {len(result)} items for order {order_id}")
                return result
                
        except Exception as e:
            log_error(e, f"get_order_items: {order_id}")
            raise
    
    def update_order_status(self, order_id: int, status: str):
        """به‌روزرسانی وضعیت سفارش"""
        logger.debug(f"به‌روزرسانی وضعیت سفارش {order_id} به {status}")
        
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE orders 
                    SET status = ? 
                    WHERE order_id = ?
                """, (status, order_id))
                
                log_db("UPDATE", f"order {order_id} status = {status}")
                logger.info(f"✅ وضعیت سفارش {order_id} به {status} تغییر کرد")
                
        except Exception as e:
            log_error(e, f"update_order_status: {order_id}")
            raise
    
    def get_user_orders(self, user_id: int) -> List[Dict[str, Any]]:
        """دریافت سفارشات کاربر"""
        logger.debug(f"دریافت سفارشات کاربر {user_id}")
        
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT * FROM orders 
                    WHERE user_id = ? 
                    ORDER BY created_at DESC
                """, (user_id,))
                
                rows = cursor.fetchall()
                result = [dict(row) for row in rows]
                
                log_db("SELECT", f"found {len(result)} orders for user {user_id}")
                return result
                
        except Exception as e:
            log_error(e, f"get_user_orders: {user_id}")
            raise
    
    def get_all_orders(self, status: Optional[str] = None) -> List[Dict[str, Any]]:
        """دریافت لیست سفارشات"""
        logger.debug(f"دریافت سفارشات (وضعیت: {status or 'همه'})")
        
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                
                if status:
                    cursor.execute("""
                        SELECT * FROM orders 
                        WHERE status = ? 
                        ORDER BY created_at DESC
                    """, (status,))
                else:
                    cursor.execute("SELECT * FROM orders ORDER BY created_at DESC")
                
                rows = cursor.fetchall()
                result = [dict(row) for row in rows]
                
                log_db("SELECT", f"found {len(result)} orders")
                logger.info(f"📋 تعداد سفارشات: {len(result)}")
                
                return result
                
        except Exception as e:
            log_error(e, "get_all_orders")
            raise
    
    # ========== آمار ==========
    
    def get_stats(self) -> Dict[str, Any]:
        """دریافت آمار کلی"""
        logger.debug("دریافت آمار")
        
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                
                # تعداد کاربران
                cursor.execute("SELECT COUNT(*) as count FROM users")
                users_count = cursor.fetchone()['count']
                
                # تعداد محصولات فعال
                cursor.execute("SELECT COUNT(*) as count FROM products WHERE is_active = 1")
                products_count = cursor.fetchone()['count']
                
                # تعداد سفارشات
                cursor.execute("SELECT COUNT(*) as count FROM orders")
                orders_count = cursor.fetchone()['count']
                
                # سفارشات در انتظار
                cursor.execute("SELECT COUNT(*) as count FROM orders WHERE status = 'pending'")
                pending_orders = cursor.fetchone()['count']
                
                stats = {
                    'users_count': users_count,
                    'products_count': products_count,
                    'orders_count': orders_count,
                    'pending_orders': pending_orders
                }
                
                log_db("SELECT", f"stats retrieved")
                logger.info(f"📊 آمار: {stats}")
                
                return stats
                
        except Exception as e:
            log_error(e, "get_stats")
            raise


if __name__ == "__main__":
    # تست
    print("🧪 تست دیتابیس...\n")
    
    db = Database("data/test.db")
    
    # تست افزودن کاربر
    db.add_or_update_user(12345, "test_user", "Test", "User")
    user = db.get_user(12345)
    print(f"✅ کاربر: {user}")
    
    # تست افزودن محصول
    product_id = db.add_product("مانتو تست", 500000, "توضیحات تست", 10)
    product = db.get_product(product_id)
    print(f"✅ محصول: {product}")
    
    # تست ایجاد سفارش
    order_id = db.create_order(12345)
    db.add_order_item(order_id, product_id, 2, 500000)
    order = db.get_order(order_id)
    print(f"✅ سفارش: {order}")
    
    # آمار
    stats = db.get_stats()
    print(f"✅ آمار: {stats}")
    
    print("\n✅ تست با موفقیت انجام شد!")
