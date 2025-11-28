"""测试群名解析: 2511210110（5）❗"""
import re
from datetime import datetime

def parse_order_from_title(title: str):
    """从群名解析订单信息"""
    customer = 'B'
    raw_digits = None
    order_id = None

    print(f"解析群名: '{title}'")
    print(f"群名长度: {len(title)}")
    print()

    # Check for New Customer (A + 10 digits)
    match_new = re.search(r'A(\d{10})', title)
    if match_new:
        print("匹配到新客户格式")
        customer = 'A'
        raw_digits = match_new.group(1)
        order_id = match_new.group(0)
    else:
        print("未匹配到新客户格式，检查老客户格式")
        # Check for Old Customer (10 consecutive digits)
        match_old = re.search(r'(?<!A)(\d{10})(?!\d)', title)
        if match_old:
            print(f"匹配到老客户格式: {match_old.group(1)}")
            customer = 'B'
            raw_digits = match_old.group(1)
            order_id = match_old.group(1)
        else:
            print("未匹配到老客户格式")
            # 调试：检查所有数字
            all_digits = re.findall(r'\d+', title)
            print(f"群名中的所有数字段: {all_digits}")
            for i, d in enumerate(all_digits):
                print(f"  段 {i+1}: '{d}' (长度: {len(d)})")
                if len(d) == 10:
                    print(f"    -> 这是10位数字，应该能匹配")
                elif len(d) > 10:
                    print(f"    -> 超过10位，需要检查")
                else:
                    print(f"    -> 少于10位")

    if not raw_digits:
        return None

    date_part = raw_digits[:6]
    amount_part = raw_digits[8:10]

    print()
    print(f"提取的10位数字: {raw_digits}")
    print(f"日期部分 (前6位): {date_part}")
    print(f"金额部分 (后2位): {amount_part}")

    try:
        full_date_str = f"20{date_part}"
        print(f"完整日期字符串: {full_date_str}")
        order_date_obj = datetime.strptime(full_date_str, "%Y%m%d").date()
        print(f"解析的日期: {order_date_obj}")
    except ValueError as e:
        print(f"日期解析失败: {e}")
        return None

    amount = int(amount_part) * 1000

    return {
        'date': order_date_obj,
        'amount': amount,
        'order_id': order_id,
        'customer': customer,
        'full_date_str': full_date_str
    }

# 测试群名
test_title = "2511210110（5）❗"

print("=" * 60)
print("测试群名解析")
print("=" * 60)
print()

result = parse_order_from_title(test_title)

print()
print("=" * 60)
if result:
    print("解析成功!")
    print(f"订单ID: {result['order_id']}")
    print(f"客户类型: {result['customer']}")
    print(f"订单日期: {result['date']}")
    print(f"订单金额: {result['amount']:,}")
else:
    print("解析失败!")
    print()
    print("可能的原因:")
    print("1. 正则表达式无法匹配10位数字")
    print("2. 日期解析失败（日期无效）")
    print("3. 其他格式问题")
print("=" * 60)

