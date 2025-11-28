"""测试群名解析逻辑"""
import re
from datetime import datetime

def parse_order_from_title(title: str):
    """从群名解析订单信息（更新后的版本）"""
    customer = 'B'
    raw_digits = None
    order_id = None

    # Check for New Customer (A + 10 digits, 可以在任何位置)
    match_new = re.search(r'A(\d{10})', title)
    if match_new:
        customer = 'A'
        raw_digits = match_new.group(1)
        order_id = match_new.group(0)
    else:
        # Check for Old Customer (10 consecutive digits, 可以在任何位置)
        match_old = re.search(r'(?<!A)(\d{10})(?!\d)', title)
        if match_old:
            customer = 'B'
            raw_digits = match_old.group(1)
            order_id = match_old.group(1)

    if not raw_digits:
        return None

    date_part = raw_digits[:6]
    amount_part = raw_digits[8:10]

    try:
        full_date_str = f"20{date_part}"
        order_date_obj = datetime.strptime(full_date_str, "%Y%m%d").date()
    except ValueError:
        return None

    amount = int(amount_part) * 1000

    return {
        'date': order_date_obj,
        'amount': amount,
        'order_id': order_id,
        'customer': customer,
        'full_date_str': full_date_str
    }

# 测试用例
test_cases = [
    "2506060110",  # 标准格式（开头）
    "A2506060110",  # 新客户格式（开头）
    "群组 2506060110",  # 中间有内容
    "2506060110 测试",  # 后面有内容
    "测试 2506060110 其他内容",  # 前后都有内容
    "A2506060110 测试",  # 新客户，后面有内容
    "测试 A2506060110 其他",  # 新客户，前后都有内容
    "2506060110A2506060110",  # 两个订单ID（应该匹配第一个）
    "无效格式",  # 无效格式
    "123456789",  # 9位数字（无效）
    "12345678901",  # 11位数字（无效）
]

print("=" * 60)
print("群名解析测试")
print("=" * 60)

for title in test_cases:
    result = parse_order_from_title(title)
    if result:
        print(f"✅ '{title}'")
        print(f"   订单ID: {result['order_id']}")
        print(f"   客户类型: {result['customer']}")
        print(f"   日期: {result['date']}")
        print(f"   金额: {result['amount']}")
    else:
        print(f"❌ '{title}' - 无法解析")
    print()

