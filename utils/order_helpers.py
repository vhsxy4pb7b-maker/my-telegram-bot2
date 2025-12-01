"""订单相关工具函数"""
import re
import logging
from datetime import date, datetime
from telegram import Update
from telegram.ext import ContextTypes
import db_operations
from constants import HISTORICAL_THRESHOLD_DATE, WEEKDAY_GROUP
from utils.stats_helpers import update_all_stats, update_liquid_capital
from utils.chat_helpers import is_group_chat, get_current_group, get_weekday_group_from_date, reply_in_group
from utils.message_builders import build_order_creation_message

logger = logging.getLogger(__name__)


def get_state_from_title(title: str) -> str:
    """从群名识别订单状态"""
    # 注意：需要先检查组合符号，再检查单个符号
    if '❌⭕️' in title:
        return 'breach_end'
    elif '⭕️' in title:
        return 'end'
    elif '❌' in title:
        return 'breach'
    elif '❗️' in title:
        return 'overdue'
    else:
        return 'normal'


def parse_order_from_title(title: str):
    """从群名解析订单信息"""
    # 规则:
    # 1. 群名必须以10个或11个连续数字开始
    # 2. 10个数字格式: YYMMDDNNKK (YYMMDD=日期, NN=序号, KK=金额千位)
    #    例如: 2501050105 -> 2015年1月5号, 第1个客户, 金额5000
    # 3. 11个数字格式: YYMMDDNNKKH (YYMMDD=日期, NN=序号, KK=金额千位, H=金额百位)
    #    例如: 25010501055 -> 2015年1月5号, 第1个客户, 金额5500
    # 4. 最后带A表示新客户，否则为老客户

    customer = 'B'  # Default
    raw_digits = None
    order_id = None
    is_11_digits = False

    # 匹配群名开头的10个或11个连续数字，后面可以跟任何内容
    # 群名必须以10或11个数字开始，后面可以跟A（表示新客户）或其他任何内容
    # 优先匹配11位数字（更具体）
    match_11 = re.match(r'^(\d{11})(A)?', title)
    if match_11:
        # 确保不是12位数字的前11位
        if len(title) > 11 and title[11].isdigit():
            # 是12位数字，不匹配
            match_11 = None
        else:
            raw_digits = match_11.group(1)
            is_11_digits = True
            if match_11.group(2) == 'A':
                customer = 'A'
                order_id = match_11.group(1) + 'A'  # 11位数字 + A
            else:
                customer = 'B'
                order_id = raw_digits  # 只有11位数字

    if not match_11:
        # 匹配10位数字，确保后面不是第11位数字
        match_10 = re.match(r'^(\d{10})(A)?', title)
        if match_10:
            # 确保不是11位数字的前10位
            if len(title) > 10 and title[10].isdigit():
                # 是11位数字，不匹配（应该匹配11位）
                match_10 = None
            else:
                raw_digits = match_10.group(1)
                is_11_digits = False
                if match_10.group(2) == 'A':
                    customer = 'A'
                    order_id = match_10.group(1) + 'A'  # 10位数字 + A
                else:
                    customer = 'B'
                    order_id = raw_digits  # 只有10位数字

    if not raw_digits:
        return None

    # 解析日期部分 (前6位: YYMMDD)
    date_part = raw_digits[:6]

    try:
        # 假设 20YY
        full_date_str = f"20{date_part}"
        order_date_obj = datetime.strptime(full_date_str, "%Y%m%d").date()
    except ValueError:
        return None

    # 解析金额部分
    if is_11_digits:
        # 11位数字: YYMMDDNNKKH
        # KK = 第9-10位 (千位)
        # H = 第11位 (百位)
        amount_thousands = int(raw_digits[8:10])  # KK
        amount_hundreds = int(raw_digits[10])     # H
        amount = amount_thousands * 1000 + amount_hundreds * 100
    else:
        # 10位数字: YYMMDDNNKK
        # KK = 第9-10位 (千位)
        amount_part = raw_digits[8:10]
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
        # Breach -> Normal/Overdue: 禁止反向变更（违约只能到违约完成）
        # Normal <-> Overdue: 仅更新状态 (都在 Valid 统计下)
        # Normal/Overdue -> End: 移动统计 (Valid -> Completed)
        # Breach -> Breach_End: 移动统计 (Breach -> Breach_End)

        is_current_valid = current_state in ['normal', 'overdue']
        is_target_valid = target_state in ['normal', 'overdue']

        is_current_breach = current_state == 'breach'
        is_target_breach = target_state == 'breach'

        is_target_end = target_state == 'end'
        is_target_breach_end = target_state == 'breach_end'

        # 禁止违约状态反向变更为正常/逾期
        if is_current_breach and is_target_valid:
            logger.info(f"订单 {order_id} 当前状态为违约，禁止反向变更为 {target_state}")
            return

        # 检查完成状态的转换规则
        if is_target_end:
            # 只能从 normal 或 overdue 转换到 end
            if not is_current_valid:
                logger.info(
                    f"订单 {order_id} 当前状态为 {current_state}，不能直接变更为 end（只能从 normal/overdue 转换）")
                return

        if is_target_breach_end:
            # 只能从 breach 转换到 breach_end
            if not is_current_breach:
                logger.info(
                    f"订单 {order_id} 当前状态为 {current_state}，不能直接变更为 breach_end（只能从 breach 转换）")
                return

        # 更新数据库状态
        if await db_operations.update_order_state(chat_id, target_state):

            # 处理统计数据迁移
            if is_current_valid and is_target_breach:
                # Valid -> Breach
                await update_all_stats('valid', -amount, -1, group_id)
                await update_all_stats('breach', amount, 1, group_id)
                await reply_in_group(update, f"🔄 State Changed: {target_state} (Auto)\nStats moved to Breach.")

            elif is_current_valid and is_target_end:
                # Valid -> End (完成订单)
                await update_all_stats('valid', -amount, -1, group_id)
                await update_all_stats('completed', amount, 1, group_id)
                # 完成订单需要增加流动资金
                from utils.stats_helpers import update_liquid_capital
                await update_liquid_capital(amount)
                await reply_in_group(update, f"✅ Order Completed: {target_state} (Auto)\nStats moved to Completed.")

            elif is_current_breach and is_target_breach_end:
                # Breach -> Breach_End (违约完成)
                await update_all_stats('breach', -amount, -1, group_id)
                await update_all_stats('breach_end', amount, 1, group_id)
                # 违约完成订单需要增加流动资金（使用订单金额）
                from utils.stats_helpers import update_liquid_capital
                await update_liquid_capital(amount)
                await reply_in_group(update, f"✅ Breach Completed: {target_state} (Auto)\nStats moved to Breach_End.")

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
                "1. Old Customer: 10 digits (e.g., 2501050105)\n"
                "   或 11 digits (e.g., 25010501055)\n"
                "2. New Customer: 10 digits + A (e.g., 2501050105A)\n"
                "   或 11 digits + A (e.g., 25010501055A)\n\n"
                "格式说明:\n"
                "- 10位: YYMMDDNNKK (日期+序号+金额千位)\n"
                "- 11位: YYMMDDNNKKH (日期+序号+金额千位+金额百位)\n"
                "- 群名必须以10或11个连续数字开始\n\n"
                f"Current title: {title}"
            )
        else:
            logger.info(
                f"Group title '{title}' does not match order pattern (must start with 10 or 11 digits).")
        return

    logger.info(
        f"Parsed order info: order_id={parsed_info['order_id']}, customer={parsed_info['customer']}, date={parsed_info['date']}, amount={parsed_info['amount']}")

    # 2. 检查是否已存在订单
    existing_order = await db_operations.get_order_by_chat_id(chat_id)
    if existing_order:
        # 如果是手动触发，提示已存在
        if manual_trigger:
            await update.message.reply_text("⚠️ Order already exists in this group.")
        else:
            # 如果是自动触发（改名），则尝试更新状态
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
    # 根据订单日期确定星期分组（历史订单和正常订单都使用订单日期）
    weekday_group = get_weekday_group_from_date(order_date)

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
    # 历史违约订单：只更新全局和分组统计，不更新日结统计
    if is_initial_breach:
        if is_historical:
            # 历史违约订单：跳过日结更新
            await update_all_stats('breach', amount, 1, group_id, skip_daily=True)
        else:
            # 非历史违约订单：正常更新（包括日结）
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
