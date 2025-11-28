"""测试示例：订单是周二，现在是周五"""
from datetime import datetime, date
from utils.broadcast_helpers import calculate_next_payment_date, format_broadcast_message

print("=" * 60)
print("示例：订单是周二，现在是周五")
print("=" * 60)

# 订单日期：2025-07-22 (周二)
order_date_str = "2025-07-22 12:00:00"
order_date = datetime.strptime("2025-07-22", "%Y-%m-%d").date()

print(f"订单日期: {order_date} ({order_date.strftime('%A')})")
print(f"当前日期: {datetime.now().date()} ({datetime.now().strftime('%A')})")

# 计算下个付款日期
next_date, date_str, weekday_str = calculate_next_payment_date(order_date_str)

print(f"\n下个付款日期: {date_str} ({weekday_str})")
print(f"验证: 从当前日期找到下一个周二")

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

