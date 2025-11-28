"""测试播报功能 - 使用数据库中的订单日期"""
from datetime import datetime, date, timedelta
from utils.broadcast_helpers import calculate_next_payment_date, format_broadcast_message

# 测试订单ID: 2505200104
order_id = '2505200104'

# 解析订单信息
date_part = order_id[:6]  # 250520
amount_part = int(order_id[8:10])  # 04
amount = amount_part * 1000  # 4000

# 解析日期
full_date_str = f'20{date_part}'  # 20250520
order_date_from_id = datetime.strptime(full_date_str, '%Y%m%d').date()

print("=" * 60)
print("从订单ID解析")
print("=" * 60)
print(f"订单ID: {order_id}")
print(f"解析的订单日期: {order_date_from_id} ({order_date_from_id.strftime('%A')})")
print(f"订单金额: {amount:,.0f}")

# 如果应该是12月2日周二，反推订单日期
target_payment_date = date(2025, 12, 2)
expected_order_date = target_payment_date - timedelta(days=7)

print("\n" + "=" * 60)
print("如果下个付款日期是12月2日周二")
print("=" * 60)
print(f"目标付款日期: {target_payment_date} ({target_payment_date.strftime('%A')})")
print(f"应该的订单日期: {expected_order_date} ({expected_order_date.strftime('%A')})")

# 使用应该的订单日期计算
next_date, date_str, weekday_str = calculate_next_payment_date(expected_order_date)

print("\n" + "=" * 60)
print("使用应该的订单日期计算")
print("=" * 60)
print(f"订单日期: {expected_order_date} ({expected_order_date.strftime('%A')})")
print(f"下个付款日期: {date_str} ({weekday_str})")
print(f"验证: {expected_order_date} + 7天 = {next_date.date()}")

# 生成播报消息
principal = amount
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

