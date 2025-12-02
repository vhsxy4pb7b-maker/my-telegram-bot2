"""报表相关处理器"""
import logging
from datetime import datetime
from typing import Optional
import pytz
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
import db_operations
from utils.date_helpers import get_daily_period_date
from decorators import error_handler, authorized_required, private_chat_only
from config import ADMIN_IDS

logger = logging.getLogger(__name__)


async def generate_report_text(period_type: str, start_date: str, end_date: str, group_id: Optional[str] = None, show_expenses: bool = True) -> str:
    """生成报表文本"""
    # 获取当前状态数据（资金和有效订单）
    if group_id:
        current_data = await db_operations.get_grouped_data(group_id)
        report_title = f"归属ID {group_id} 的报表"
    else:
        current_data = await db_operations.get_financial_data()
        report_title = "全局报表"

    # 获取周期统计数据
    stats = await db_operations.get_stats_by_date_range(
        start_date, end_date, group_id)
    
    # 从收入明细表获取实际利息收入（确保与明细一致）
    interest_records = await db_operations.get_income_records(
        start_date, end_date, type='interest', group_id=group_id)
    actual_interest = sum(r['amount'] for r in interest_records)
    # 使用实际收入明细的利息，而不是统计表的利息
    stats['interest'] = actual_interest

    # 如果按归属ID查询，需要单独获取全局开销数据（开销是全局的，不按归属ID存储）
    if group_id:
        global_expense_stats = await db_operations.get_stats_by_date_range(
            start_date, end_date, None)
        stats['company_expenses'] = global_expense_stats['company_expenses']
        stats['other_expenses'] = global_expense_stats['other_expenses']
        # 现金余额使用全局数据
        global_financial_data = await db_operations.get_financial_data()
        current_data['liquid_funds'] = global_financial_data['liquid_funds']

    # 格式化时间
    tz = pytz.timezone('Asia/Shanghai')
    now = datetime.now(tz).strftime("%Y-%m-%d %H:%M")

    period_display = ""
    if period_type == "today":
        period_display = f"今日数据 ({start_date})"
    elif period_type == "month":
        period_display = f"本月数据 ({start_date[:-3]})"
    else:
        period_display = f"区间数据 ({start_date} 至 {end_date})"

    report = (
        f"=== {report_title} ===\n"
        f"📅 {now}\n"
        f"{'─' * 25}\n"
        f"💰 【当前状态】\n"
        f"有效订单数: {current_data['valid_orders']}\n"
        f"有效订单金额: {current_data['valid_amount']:.2f}\n"
        f"{'─' * 25}\n"
        f"📈 【{period_display}】\n"
        f"流动资金: {stats['liquid_flow']:.2f}\n"
        f"新客户数: {stats['new_clients']}\n"
        f"新客户金额: {stats['new_clients_amount']:.2f}\n"
        f"老客户数: {stats['old_clients']}\n"
        f"老客户金额: {stats['old_clients_amount']:.2f}\n"
        f"利息收入: {stats['interest']:.2f}\n"
        f"完成订单数: {stats['completed_orders']}\n"
        f"完成订单金额: {stats['completed_amount']:.2f}\n"
        f"违约订单数: {stats['breach_orders']}\n"
        f"违约订单金额: {stats['breach_amount']:.2f}\n"
        f"违约完成订单数: {stats['breach_end_orders']}\n"
        f"违约完成金额: {stats['breach_end_amount']:.2f}\n"
    )

    # 如果是归属报表，添加盈余计算
    # 盈余 = 利息收入 + 违约完成订单金额 - 违约订单金额
    if group_id:
        surplus = stats['interest'] + stats['breach_end_amount'] - stats['breach_amount']
        # 格式化显示：添加千分位分隔符和符号
        surplus_str = f"{surplus:,.2f}"
        if surplus > 0:
            report += f"盈余: +{surplus_str}\n"
        elif surplus < 0:
            report += f"盈余: {surplus_str}\n"  # 负数自带负号
        else:
            report += f"盈余: {surplus_str}\n"

    # 如果要求显示开销与余额，则添加
    if show_expenses:
        report += (
            f"{'─' * 25}\n"
            f"💸 【开销与余额】\n"
            f"公司开销: {stats['company_expenses']:.2f}\n"
            f"其他开销: {stats['other_expenses']:.2f}\n"
            f"现金余额: {current_data['liquid_funds']:.2f}\n"
        )

    return report


@error_handler
@private_chat_only
@authorized_required
async def show_report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """显示报表"""
    # 默认为今日报表
    period_type = "today"
    group_id = None

    # 处理参数
    if context.args:
        group_id = context.args[0]

    # 获取今日日期
    daily_date = get_daily_period_date()

    # 生成报表
    report_text = await generate_report_text(period_type, daily_date, daily_date, group_id)

    # 构建按钮（中文）
    keyboard = [
        [
            InlineKeyboardButton(
                "📅 月报", callback_data=f"report_view_month_{group_id if group_id else 'ALL'}"),
            InlineKeyboardButton(
                "📆 日期查询", callback_data=f"report_view_query_{group_id if group_id else 'ALL'}")
        ]
    ]

    # 检查用户权限：只有管理员或授权员工可以录入开销
    user_id = update.effective_user.id if update.effective_user else None
    if user_id:
        is_admin = user_id in ADMIN_IDS
        is_authorized = await db_operations.is_user_authorized(user_id)
        if is_admin or is_authorized:
            keyboard.append([
                InlineKeyboardButton(
                    "🏢 公司开销", callback_data="report_record_company"),
                InlineKeyboardButton(
                    "📝 其他开销", callback_data="report_record_other")
            ])

    # 如果是全局报表，显示归属查询和查找功能按钮
    if not group_id:
        keyboard.append([
            InlineKeyboardButton(
                "🔍 按归属查询", callback_data="report_menu_attribution"),
            InlineKeyboardButton(
                "🔎 查找订单", callback_data="report_search_orders")
        ])
        # 仅管理员显示收入明细按钮
        if user_id and user_id in ADMIN_IDS:
            keyboard.append([
                InlineKeyboardButton(
                    "💰 收入明细", callback_data="income_view_today")
            ])
    else:
        keyboard.append([InlineKeyboardButton(
            "🔙 返回", callback_data="report_view_today_ALL")])

    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(report_text, reply_markup=reply_markup)


@error_handler
@private_chat_only
async def show_my_report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """显示用户有权限查看的归属ID报表（仅限该归属ID）"""
    user_id = update.effective_user.id if update.effective_user else None
    if not user_id:
        await update.message.reply_text("❌ 无法获取用户信息")
        return

    # 获取用户有权限查看的归属ID
    group_id = await db_operations.get_user_group_id(user_id)
    if not group_id:
        await update.message.reply_text(
            "❌ 您没有权限查看任何归属ID的报表。\n"
            "请联系管理员为您分配归属ID权限。"
        )
        return

    # 默认为今日报表
    period_type = "today"
    daily_date = get_daily_period_date()

    # 生成报表（不显示开销与余额）
    report_text = await generate_report_text(period_type, daily_date, daily_date, group_id, show_expenses=False)

    # 构建按钮（简化版，不显示归属查询和查找功能）
    keyboard = [
        [
            InlineKeyboardButton(
                "📅 月报", callback_data=f"report_view_month_{group_id}"),
            InlineKeyboardButton(
                "📆 日期查询", callback_data=f"report_view_query_{group_id}")
        ]
    ]

    # 检查用户权限：只有管理员或授权员工可以录入开销
    user_id = update.effective_user.id if update.effective_user else None
    if user_id:
        is_admin = user_id in ADMIN_IDS
        is_authorized = await db_operations.is_user_authorized(user_id)
        if is_admin or is_authorized:
            keyboard.append([
                InlineKeyboardButton(
                    "🏢 公司开销", callback_data="report_record_company"),
                InlineKeyboardButton(
                    "📝 其他开销", callback_data="report_record_other")
            ])

    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(report_text, reply_markup=reply_markup)
