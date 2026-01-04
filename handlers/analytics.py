"""
سیستم گزارش‌های گرافیکی و تحلیلی
"""
import io
import json
from datetime import datetime, timedelta
from telegram import Update
from telegram.ext import ContextTypes
from config import ADMIN_ID
import matplotlib
matplotlib.use('Agg')  # برای استفاده در محیط بدون GUI
import matplotlib.pyplot as plt
from matplotlib import font_manager
import matplotlib.dates as mdates
from collections import defaultdict, Counter

# تنظیم فونت فارسی
plt.rcParams['font.family'] = 'DejaVu Sans'
plt.rcParams['axes.unicode_minus'] = False


class Analytics:
    """کلاس تحلیل و گزارش‌گیری"""
    
    def __init__(self, db):
        self.db = db
    
    def get_sales_data(self, days=30):
        """دریافت داده‌های فروش"""
        query = """
            SELECT DATE(created_at) as date, 
                   COUNT(*) as order_count,
                   SUM(final_price) as total_sales
            FROM orders 
            WHERE status IN ('confirmed', 'payment_confirmed')
              AND created_at >= DATE('now', '-{} days')
            GROUP BY DATE(created_at)
            ORDER BY date
        """.format(days)
        
        self.db.cursor.execute(query)
        return self.db.cursor.fetchall()
    
    def get_popular_products(self, limit=10):
        """محبوب‌ترین محصولات"""
        query = """
            SELECT items FROM orders 
            WHERE status IN ('confirmed', 'payment_confirmed')
        """
        
        self.db.cursor.execute(query)
        orders = self.db.cursor.fetchall()
        
        product_counter = Counter()
        
        for order in orders:
            items = json.loads(order[0])
            for item in items:
                product_name = item.get('product', 'Unknown')
                quantity = item.get('quantity', 0)
                product_counter[product_name] += quantity
        
        return product_counter.most_common(limit)
    
    def get_hourly_orders(self):
        """ساعات شلوغی سفارش"""
        query = """
            SELECT strftime('%H', created_at) as hour,
                   COUNT(*) as count
            FROM orders
            WHERE created_at >= DATE('now', '-30 days')
            GROUP BY hour
            ORDER BY hour
        """
        
        self.db.cursor.execute(query)
        return self.db.cursor.fetchall()
    
    def get_conversion_rate(self):
        """نرخ تبدیل"""
        # تعداد کل کاربران
        self.db.cursor.execute("SELECT COUNT(*) FROM users")
        total_users = self.db.cursor.fetchone()[0]
        
        # تعداد کاربران خریدار
        self.db.cursor.execute("""
            SELECT COUNT(DISTINCT user_id) FROM orders
            WHERE status IN ('confirmed', 'payment_confirmed')
        """)
        buyers = self.db.cursor.fetchone()[0]
        
        # تعداد سفارشات
        self.db.cursor.execute("""
            SELECT COUNT(*) FROM orders
            WHERE status IN ('confirmed', 'payment_confirmed')
        """)
        orders = self.db.cursor.fetchone()[0]
        
        conversion_rate = (buyers / total_users * 100) if total_users > 0 else 0
        repeat_rate = (orders / buyers) if buyers > 0 else 0
        
        return {
            'total_users': total_users,
            'buyers': buyers,
            'non_buyers': total_users - buyers,
            'conversion_rate': conversion_rate,
            'total_orders': orders,
            'repeat_rate': repeat_rate
        }
    
    def get_revenue_data(self, days=30):
        """داده‌های درآمد"""
        query = """
            SELECT DATE(created_at) as date,
                   SUM(total_price) as gross_revenue,
                   SUM(discount_amount) as total_discount,
                   SUM(final_price) as net_revenue
            FROM orders
            WHERE status IN ('confirmed', 'payment_confirmed')
              AND created_at >= DATE('now', '-{} days')
            GROUP BY DATE(created_at)
            ORDER BY date
        """.format(days)
        
        self.db.cursor.execute(query)
        return self.db.cursor.fetchall()


def create_sales_chart(analytics, period='weekly'):
    """نمودار فروش"""
    days_map = {'daily': 7, 'weekly': 30, 'monthly': 90}
    days = days_map.get(period, 30)
    
    data = analytics.get_sales_data(days)
    
    if not data:
        return None
    
    dates = [datetime.strptime(row[0], '%Y-%m-%d') for row in data]
    order_counts = [row[1] for row in data]
    sales = [row[2]/1000000 for row in data]  # تبدیل به میلیون تومان
    
    fig, ax1 = plt.subplots(figsize=(12, 6))
    
    # نمودار تعداد سفارشات
    color1 = '#3498db'
    ax1.set_xlabel('Date', fontsize=12)
    ax1.set_ylabel('Order Count', color=color1, fontsize=12)
    ax1.plot(dates, order_counts, color=color1, marker='o', linewidth=2, label='Orders')
    ax1.tick_params(axis='y', labelcolor=color1)
    ax1.grid(True, alpha=0.3)
    
    # نمودار فروش
    ax2 = ax1.twinx()
    color2 = '#2ecc71'
    ax2.set_ylabel('Sales (Million Toman)', color=color2, fontsize=12)
    ax2.plot(dates, sales, color=color2, marker='s', linewidth=2, label='Sales')
    ax2.tick_params(axis='y', labelcolor=color2)
    
    # فرمت تاریخ
    if period == 'daily':
        ax1.xaxis.set_major_formatter(mdates.DateFormatter('%m/%d'))
    else:
        ax1.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'))
    
    plt.setp(ax1.xaxis.get_majorticklabels(), rotation=45, ha='right')
    
    # عنوان
    period_title = {'daily': 'Daily', 'weekly': 'Weekly', 'monthly': 'Monthly'}
    plt.title(f'{period_title[period]} Sales Report', fontsize=16, fontweight='bold', pad=20)
    
    fig.tight_layout()
    
    # ذخیره در بافر
    buf = io.BytesIO()
    plt.savefig(buf, format='png', dpi=150, bbox_inches='tight')
    buf.seek(0)
    plt.close()
    
    return buf


def create_popular_products_chart(analytics):
    """نمودار محبوب‌ترین محصولات"""
    products = analytics.get_popular_products(10)
    
    if not products:
        return None
    
    names = [p[0][:20] + '...' if len(p[0]) > 20 else p[0] for p in products]
    counts = [p[1] for p in products]
    
    fig, ax = plt.subplots(figsize=(12, 8))
    
    colors = plt.cm.viridis([i/len(names) for i in range(len(names))])
    bars = ax.barh(names, counts, color=colors, edgecolor='black', linewidth=1.5)
    
    ax.set_xlabel('Quantity Sold', fontsize=12, fontweight='bold')
    ax.set_title('Top 10 Popular Products', fontsize=16, fontweight='bold', pad=20)
    ax.grid(axis='x', alpha=0.3, linestyle='--')
    
    # اضافه کردن مقادیر روی میله‌ها
    for i, (bar, count) in enumerate(zip(bars, counts)):
        ax.text(count + max(counts)*0.01, bar.get_y() + bar.get_height()/2, 
                f'{count}', va='center', fontsize=10, fontweight='bold')
    
    plt.tight_layout()
    
    buf = io.BytesIO()
    plt.savefig(buf, format='png', dpi=150, bbox_inches='tight')
    buf.seek(0)
    plt.close()
    
    return buf


def create_hourly_orders_chart(analytics):
    """نمودار ساعات شلوغی"""
    data = analytics.get_hourly_orders()
    
    if not data:
        return None
    
    # ایجاد لیست کامل 24 ساعته
    hours_dict = {str(i).zfill(2): 0 for i in range(24)}
    for hour, count in data:
        hours_dict[hour] = count
    
    hours = list(range(24))
    counts = [hours_dict[str(h).zfill(2)] for h in hours]
    
    fig, ax = plt.subplots(figsize=(14, 6))
    
    colors = ['#e74c3c' if c == max(counts) else '#3498db' for c in counts]
    bars = ax.bar(hours, counts, color=colors, edgecolor='black', linewidth=1.5, alpha=0.8)
    
    ax.set_xlabel('Hour of Day', fontsize=12, fontweight='bold')
    ax.set_ylabel('Number of Orders', fontsize=12, fontweight='bold')
    ax.set_title('Peak Hours for Orders (Last 30 Days)', fontsize=16, fontweight='bold', pad=20)
    ax.set_xticks(hours)
    ax.set_xticklabels([f'{h:02d}:00' for h in hours], rotation=45, ha='right')
    ax.grid(axis='y', alpha=0.3, linestyle='--')
    
    # خط میانگین
    avg = sum(counts) / len(counts)
    ax.axhline(y=avg, color='orange', linestyle='--', linewidth=2, label=f'Average: {avg:.1f}')
    ax.legend()
    
    # اضافه کردن مقادیر روی میله‌ها
    for bar, count in zip(bars, counts):
        if count > 0:
            ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + max(counts)*0.01,
                   f'{int(count)}', ha='center', va='bottom', fontsize=9, fontweight='bold')
    
    plt.tight_layout()
    
    buf = io.BytesIO()
    plt.savefig(buf, format='png', dpi=150, bbox_inches='tight')
    buf.seek(0)
    plt.close()
    
    return buf


def create_revenue_chart(analytics, period='monthly'):
    """نمودار درآمد"""
    days_map = {'weekly': 30, 'monthly': 90}
    days = days_map.get(period, 30)
    
    data = analytics.get_revenue_data(days)
    
    if not data:
        return None
    
    dates = [datetime.strptime(row[0], '%Y-%m-%d') for row in data]
    gross = [row[1]/1000000 for row in data]
    discounts = [row[2]/1000000 for row in data]
    net = [row[3]/1000000 for row in data]
    
    fig, ax = plt.subplots(figsize=(14, 7))
    
    ax.plot(dates, gross, marker='o', linewidth=2, label='Gross Revenue', color='#3498db')
    ax.plot(dates, net, marker='s', linewidth=2, label='Net Revenue', color='#2ecc71')
    ax.fill_between(dates, gross, net, alpha=0.2, color='#e74c3c', label='Discounts')
    
    ax.set_xlabel('Date', fontsize=12, fontweight='bold')
    ax.set_ylabel('Revenue (Million Toman)', fontsize=12, fontweight='bold')
    ax.set_title('Revenue Analysis', fontsize=16, fontweight='bold', pad=20)
    ax.legend(loc='upper left', fontsize=11)
    ax.grid(True, alpha=0.3, linestyle='--')
    
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'))
    plt.setp(ax.xaxis.get_majorticklabels(), rotation=45, ha='right')
    
    plt.tight_layout()
    
    buf = io.BytesIO()
    plt.savefig(buf, format='png', dpi=150, bbox_inches='tight')
    buf.seek(0)
    plt.close()
    
    return buf


def create_conversion_chart(analytics):
    """نمودار نرخ تبدیل"""
    data = analytics.get_conversion_rate()
    
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6))
    
    # نمودار دایره‌ای - کاربران
    labels1 = ['Buyers', 'Non-Buyers']
    sizes1 = [data['buyers'], data['non_buyers']]
    colors1 = ['#2ecc71', '#e74c3c']
    explode1 = (0.1, 0)
    
    ax1.pie(sizes1, explode=explode1, labels=labels1, colors=colors1,
            autopct='%1.1f%%', shadow=True, startangle=90, textprops={'fontsize': 12, 'fontweight': 'bold'})
    ax1.set_title(f'User Conversion Rate\n{data["conversion_rate"]:.1f}% converted', 
                  fontsize=14, fontweight='bold', pad=20)
    
    # نمودار میله‌ای - آمار
    categories = ['Total\nUsers', 'Buyers', 'Total\nOrders']
    values = [data['total_users'], data['buyers'], data['total_orders']]
    colors2 = ['#3498db', '#2ecc71', '#f39c12']
    
    bars = ax2.bar(categories, values, color=colors2, edgecolor='black', linewidth=2, alpha=0.8)
    ax2.set_ylabel('Count', fontsize=12, fontweight='bold')
    ax2.set_title(f'Statistics Overview\nRepeat Rate: {data["repeat_rate"]:.2f} orders/buyer', 
                  fontsize=14, fontweight='bold', pad=20)
    ax2.grid(axis='y', alpha=0.3, linestyle='--')
    
    # اضافه کردن مقادیر
    for bar, value in zip(bars, values):
        ax2.text(bar.get_x() + bar.get_width()/2, bar.get_height() + max(values)*0.02,
                f'{int(value)}', ha='center', va='bottom', fontsize=12, fontweight='bold')
    
    plt.tight_layout()
    
    buf = io.BytesIO()
    plt.savefig(buf, format='png', dpi=150, bbox_inches='tight')
    buf.seek(0)
    plt.close()
    
    return buf


async def send_analytics_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """منوی گزارش‌های تحلیلی"""
    if update.effective_user.id != ADMIN_ID:
        return
    
    from keyboards import analytics_menu_keyboard
    
    await update.message.reply_text(
        "📊 **گزارش‌های تحلیلی**\n\n"
        "کدام گزارش را می‌خواهید مشاهده کنید؟",
        parse_mode='Markdown',
        reply_markup=analytics_menu_keyboard()
    )


async def handle_analytics_report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """مدیریت درخواست گزارش"""
    query = update.callback_query
    await query.answer()
    
    if update.effective_user.id != ADMIN_ID:
        return
    
    report_type = query.data.split(":")[1]
    
    await query.message.reply_text("⏳ در حال تولید گزارش...\nلطفاً صبر کنید...")
    
    db = context.bot_data['db']
    analytics = Analytics(db)
    
    try:
        if report_type == 'sales_daily':
            chart = create_sales_chart(analytics, 'daily')
            caption = "📊 **گزارش فروش روزانه** (7 روز اخیر)"
        
        elif report_type == 'sales_weekly':
            chart = create_sales_chart(analytics, 'weekly')
            caption = "📊 **گزارش فروش هفتگی** (30 روز اخیر)"
        
        elif report_type == 'sales_monthly':
            chart = create_sales_chart(analytics, 'monthly')
            caption = "📊 **گزارش فروش ماهانه** (90 روز اخیر)"
        
        elif report_type == 'popular':
            chart = create_popular_products_chart(analytics)
            caption = "🏆 **محبوب‌ترین محصولات** (بر اساس تعداد فروش)"
        
        elif report_type == 'hourly':
            chart = create_hourly_orders_chart(analytics)
            caption = "⏰ **ساعات شلوغی سفارش‌گذاری** (30 روز اخیر)"
        
        elif report_type == 'revenue':
            chart = create_revenue_chart(analytics, 'monthly')
            caption = "💰 **تحلیل درآمد** (90 روز اخیر)\n\n" \
                     "🔵 درآمد ناخالص | 🟢 درآمد خالص | 🔴 تخفیفات"
        
        elif report_type == 'conversion':
            chart = create_conversion_chart(analytics)
            caption = "📈 **نرخ تبدیل و آمار کاربران**"
        
        else:
            await query.message.reply_text("❌ نوع گزارش نامعتبر است!")
            return
        
        if chart:
            await query.message.reply_photo(
                photo=chart,
                caption=caption,
                parse_mode='Markdown'
            )
        else:
            await query.message.reply_text("❌ داده‌ای برای نمایش وجود ندارد!")
    
    except Exception as e:
        await query.message.reply_text(f"❌ خطا در تولید گزارش:\n`{str(e)}`", parse_mode='Markdown')