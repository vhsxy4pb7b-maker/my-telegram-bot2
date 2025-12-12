"""日切数据处理器"""
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
import db_operations
from utils.date_helpers import get_daily_period_date
from decorators import error_handler, private_chat_only
from config import ADMIN_IDS

logger = logging.getLogger(__name__)


def _is_admin(user_id: int) -> bool:
    """检查用户是否为管理员"""
    return user_id is not None and user_id in ADMIN_IDS


@error_handler
@private_chat_only
async def show_daily_summary(update: Update, context: ContextTypes.DEFAULT_TYPE, date: str = None):
    """显示日切数据表（仅管理员）"""
    user_id = update.effective_user.id if update.effective_user else None

    if not _is_admin(user_id):
        await update.message.reply_text("❌ 此功能仅限管理员使用")
        return

    try:
        # 如果没有指定日期，使用当前日切日期
        if not date:
            date = get_daily_period_date()
        
        # 获取日切数据
        summary = await db_operations.get_daily_summary(date)
        
        if not summary:
            await update.message.reply_text(f"📊 日切数据 ({date})\n\n暂无数据")
            return
        
        # 生成报表文本
        report = f"📊 日切数据 ({date})\n"
        report += "═══════════════════════════════════════\n"
        report += f"新增订单: {summary.get('new_orders_count', 0)} 个\n"
        report += f"新增订单金额: {summary.get('new_orders_amount', 0.0):,.2f}\n"
        report += f"完结订单: {summary.get('completed_orders_count', 0)} 个\n"
        report += f"完结订单金额: {summary.get('completed_orders_amount', 0.0):,.2f}\n"
        report += f"违约完成: {summary.get('breach_end_orders_count', 0)} 个\n"
        report += f"违约完成金额: {summary.get('breach_end_orders_amount', 0.0):,.2f}\n"
        report += f"当日利息: {summary.get('daily_interest', 0.0):,.2f}\n"
        report += f"公司开销: {summary.get('company_expenses', 0.0):,.2f}\n"
        report += f"其他开销: {summary.get('other_expenses', 0.0):,.2f}\n"
        total_expenses = summary.get('company_expenses', 0.0) + summary.get('other_expenses', 0.0)
        report += f"总开销: {total_expenses:,.2f}\n"
        report += "═══════════════════════════════════════\n"
        
        keyboard = [
            [InlineKeyboardButton(
                "🔙 返回报表", callback_data="report_view_today_ALL")]
        ]
        
        await update.message.reply_text(
            report,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    except Exception as e:
        logger.error(f"显示日切数据失败: {e}", exc_info=True)
        await update.message.reply_text(f"❌ 显示日切数据失败: {e}")

