"""订单相关工具函数"""
import re
import logging
from datetime import date, datetime
from telegram import Update
from telegram.ext import ContextTypes
import db_operations
from constants import HISTORICAL_THRESHOLD_DATE, WEEKDAY_GROUP
from utils.stats_helpers import update_all_stats, update_liquid_capital
from utils.chat_helpers import is_group_chat, get_current_group, reply_in_group
from utils.message_builders import build_order_creation_message

logger = logging.getLogger(__name__)


def get_state_from_title(title: str) -> str:
    """从群名识别订单状态"""
    if '❌' in title:
        return 'breach'
    elif '❗️' in title:
        return 'overdue'
    else:
        return 'normal'


def parse_order_from_title(title: str):
    """从群名解析订单信息"""
    # 规则:
    # 1. 群名中包含10位连续数字 -> 老客户 (B)
    # 2. 群名中包含 A + 10位连续数字 -> 新客户 (A)
    # 注意: 10位数字或A+10位数字可以在群名的任何位置，不一定是开头

    customer = 'B'  # Default
    raw_digits = None
    order_id = None

    # Check for New Customer (A + 10 digits, 可以在任何位置)
    # 匹配 A 后面紧跟10位数字的模式
    match_new = re.search(r'A(\d{10})', title)
    if match_new:
        customer = 'A'
        raw_digits = match_new.group(1)
        order_id = match_new.group(0)  # A + digits as ID
    else:
        # Check for Old Customer (10 consecutive digits, 可以在任何位置)
        # 匹配10位连续数字，但确保不是A后面的（避免重复匹配）
        # 使用负向前瞻确保前面不是A
        match_old = re.search(r'(?<!A)(\d{10})(?!\d)', title)
        if match_old:
            customer = 'B'
            raw_digits = match_old.group(1)
            order_id = match_old.group(1)  # 只有10位数字作为ID

    if not raw_digits:
        return None

    # Parse Date and Amount from the 10 digits
    # Digits: YYMMDDNNKK
    # YYMMDD: Date
    # NN: Seq
    # KK: Amount (k)

    date_part = raw_digits[:6]
    amount_part = raw_digits[8:10]

    try:
        # 假设 20YY
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


async def update_order_state_from_title(update: Update, context: ContextTypes.DEFAULT_TYPE, order: dict, title: str):
    """根据群名变更自动更新订单状态"""
    current_state = order['state']

    # 1. 完成状态不再更改
    if current_state in ['end', 'breach_end']:
        return

    target_state = get_state_from_title(title)

    # 2. 状态一致无需更改
    if current_state == target_state:
        return

    chat_id = order['chat_id']
    group_id = order['group_id']
    amount = order['amount']
    order_id = order['order_id']

    try:
        # 3. 执行状态变更逻辑
        # 逻辑矩阵:
        # Normal/Overdue -> Breach: 移动统计 (Valid -> Breach)
        # Breach -> Normal/Overdue: 移动统计 (Breach -> Valid)
        # Normal <-> Overdue: 仅更新状态 (都在 Valid 统计下)

        is_current_valid = current_state in ['normal', 'overdue']
        is_target_valid = target_state in ['normal', 'overdue']

        is_current_breach = current_state == 'breach'
        is_target_breach = target_state == 'breach'

        # 更新数据库状态
        if await db_operations.update_order_state(chat_id, target_state):

            # 处理统计数据迁移
            if is_current_valid and is_target_breach:
                # Valid -> Breach
                await update_all_stats('valid', -amount, -1, group_id)
                await update_all_stats('breach', amount, 1, group_id)
                await reply_in_group(update, f"🔄 State Changed: {target_state} (Auto)\nStats moved to Breach.")

            elif is_current_breach and is_target_valid:
                # Breach -> Valid
                await update_all_stats('breach', -amount, -1, group_id)
                await update_all_stats('valid', amount, 1, group_id)
                await reply_in_group(update, f"🔄 State Changed: {target_state} (Auto)\nStats moved to Valid.")

            else:
                # Normal <-> Overdue (都在 Valid 池中，仅状态变更)
                await reply_in_group(update, f"🔄 State Changed: {target_state} (Auto)")

    except Exception as e:
        logger.error(f"Auto update state failed: {e}", exc_info=True)


async def try_create_order_from_title(update: Update, context: ContextTypes.DEFAULT_TYPE, chat, title: str, manual_trigger: bool = False):
    """尝试从群标题创建订单（通用逻辑）"""
    chat_id = chat.id

    logger.info(
        f"Attempting to create order from title: '{title}' (chat_id: {chat_id}, manual_trigger: {manual_trigger})")

    # 1. 解析群名 (ID, Customer, Date, Amount)
    parsed_info = parse_order_from_title(title)
    if not parsed_info:
        if manual_trigger:
            await update.message.reply_text(
                "❌ Invalid Group Title Format.\n"
                "Expected:\n"
                "1. Old Customer: 10 digits (e.g., 2401150105)\n"
                "2. New Customer: A + 10 digits (e.g., A2401150105)\n\n"
                f"Current title: {title}"
            )
        else:
            logger.info(
                f"Group title '{title}' does not match order pattern (no 10 digits or A+10 digits found).")
        return

    logger.info(
        f"Parsed order info: order_id={parsed_info['order_id']}, customer={parsed_info['customer']}, date={parsed_info['date']}, amount={parsed_info['amount']}")

    # 2. 检查是否已存在订单
    existing_order = await db_operations.get_order_by_chat_id(chat_id)
    if existing_order:
        # 如果是手动触发，提示已存在
        if manual_trigger:
            await update.message.reply_text("⚠️ Order already exists in this group.")
        # 如果是自动触发（改名），则尝试更新状态
        elif not manual_trigger:
            await update_order_state_from_title(update, context, existing_order, title)
        return

    # 3. 提取信息
    order_date = parsed_info['date']
    amount = parsed_info['amount']
    order_id = parsed_info['order_id']
    customer = parsed_info['customer']  # 'A' or 'B'

    # 4. 初始状态识别 (根据群名标志)
    initial_state = get_state_from_title(title)

    # 5. 检查日期阈值 (2025-11-28)
    # 规则: 2025-11-28之前的订单作为历史数据导入，不扣款，不播报
    threshold_date = date(*HISTORICAL_THRESHOLD_DATE)
    is_historical = order_date < threshold_date

    # 检查余额 (仅当非历史订单时检查)
    if not is_historical:
        financial_data = await db_operations.get_financial_data()
        if financial_data['liquid_funds'] < amount:
            msg = (
                f"❌ Insufficient Liquid Funds\n"
                f"Current Balance: {financial_data['liquid_funds']:.2f}\n"
                f"Required: {amount:.2f}\n"
                f"Missing: {amount - financial_data['liquid_funds']:.2f}"
            )
            if manual_trigger or is_group_chat(update):
                await update.message.reply_text(msg)
            return

    group_id = 'S01'  # 默认归属
    weekday_group = get_current_group()

    # 构造创建时间
    created_at = f"{order_date.strftime('%Y-%m-%d')} 12:00:00"

    new_order = {
        'order_id': order_id,
        'group_id': group_id,
        'chat_id': chat_id,
        'date': created_at,
        'group': weekday_group,
        'customer': customer,
        'amount': amount,
        'state': initial_state
    }

    # 6. 创建订单
    if not await db_operations.create_order(new_order):
        if manual_trigger:
            await update.message.reply_text("❌ Failed to create order. Order ID might duplicate.")
        return

    # 7. 更新统计
    # 根据初始状态决定计入 Valid 还是 Breach
    is_initial_breach = (initial_state == 'breach')

    # 更新订单统计
    if is_initial_breach:
        await update_all_stats('breach', amount, 1, group_id)
    else:
        await update_all_stats('valid', amount, 1, group_id)

    # 非历史订单才扣款和更新客户统计
    if not is_historical:
        # 扣除流动资金
        await update_liquid_capital(-amount)

        # 客户统计
        client_field = 'new_clients' if customer == 'A' else 'old_clients'
        await update_all_stats(client_field, amount, 1, group_id)

        # 自动播报下一期还款（基于订单日期计算下个周期）
        await send_auto_broadcast(update, context, chat_id, amount, created_at)
    else:
        # 历史订单不播报
        logger.info(f"Historical order {order_id} created, skipping broadcast")

    # 构建并发送确认消息
    msg = build_order_creation_message(
        order_id=order_id,
        group_id=group_id,
        created_at=created_at,
        weekday_group=weekday_group,
        customer=customer,
        amount=amount,
        initial_state=initial_state,
        is_historical=is_historical
    )
    await update.message.reply_text(msg)


async def send_auto_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE, chat_id: int, amount: float, order_date: str = None):
    """订单创建后自动播报下一期还款"""
    try:
        # 计算本金和本金12%
        principal = amount
        principal_12 = principal * 0.12

        # 获取未付利息（新订单默认为0）
        outstanding_interest = 0

        # 使用统一的播报模板函数，基于订单日期计算下个周期
        from utils.broadcast_helpers import format_broadcast_message, calculate_next_payment_date
        _, date_str, weekday_str = calculate_next_payment_date(order_date)
        message = format_broadcast_message(
            principal=principal,
            principal_12=principal_12,
            outstanding_interest=outstanding_interest,
            date_str=date_str,
            weekday_str=weekday_str
        )

        await context.bot.send_message(chat_id=chat_id, text=message)
        logger.info(f"自动播报已发送到群组 {chat_id}")
    except Exception as e:
        logger.error(f"自动播报失败: {e}", exc_info=True)
        # 不显示错误给用户，静默失败
