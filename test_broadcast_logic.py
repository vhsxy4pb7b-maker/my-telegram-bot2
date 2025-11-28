"""测试新的播报逻辑"""
from datetime import datetime, date
from utils.broadcast_helpers import calculate_next_payment_date, format_broadcast_message

# 测试场景：订单是周二，现在是周五
print("=" * 60)
print("测试场景：订单是周二，现在是周五")
print("=" * 60)

# 订单日期：2025-07-22 (周二)
order_date_str = "2025-07-22 12:00:00"
order_date = datetime.strptime("2025-07-22", "%Y-%m-%d").date()

print(f"订单日期: {order_date} ({order_date.strftime('%A')})")
print(f"当前日期: {datetime.now().date()} ({datetime.now().strftime('%A')})")

# 计算下个付款日期
next_date, date_str, weekday_str = calculate_next_payment_date(order_date_str)

print(f"下个付款日期: {date_str} ({weekday_str})")
print(f"计算逻辑: 从当前日期找到下一个周二")

# 生成播报消息
principal = 8000
principal_12 = principal * 0.12
outstanding_interest = 0

message = format_broadcast_message(
    principal=principal,
    principal_12=principal_12,
    outstanding_interest=outstanding_interest,
    date_str=date_str,
    weekday_str=weekday_str
)

print("\n" + "=" * 60)
print("播报消息")
print("=" * 60)
print(message)
print("=" * 60)

# 测试另一个场景：订单是周二，现在也是周二
print("\n" + "=" * 60)
print("测试场景：订单是周二，现在也是周二")
print("=" * 60)

# 模拟当前日期是周二
from datetime import timedelta
today_tuesday = date(2025, 11, 25)  # 假设今天是周二
print(f"订单日期: {order_date} ({order_date.strftime('%A')})")
print(f"当前日期: {today_tuesday} ({today_tuesday.strftime('%A')})")

# 手动计算：如果今天是目标星期几，下个付款日期是7天后
if today_tuesday.weekday() == order_date.weekday():
    next_payment = today_tuesday + timedelta(days=7)
    print(f"下个付款日期: {next_payment} ({next_payment.strftime('%A')})")
    print("计算逻辑: 如果今天是目标星期几，下个付款日期是7天后")

