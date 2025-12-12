"""订单总表处理器"""
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
import db_operations
from utils.order_table_helpers import (
    generate_order_table,
    generate_completed_orders_table,
    generate_breach_end_orders_table
)
from utils.date_helpers import get_daily_period_date
from decorators import error_handler, private_chat_only
from config import ADMIN_IDS

logger = logging.getLogger(__name__)


def _is_admin(user_id: int) -> bool:
    """检查用户是否为管理员"""
    return user_id is not None and user_id in ADMIN_IDS


@error_handler
@private_chat_only
async def show_order_table(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """显示订单总表（仅管理员）"""
    user_id = update.effective_user.id if update.effective_user else None

    if not _is_admin(user_id):
        await update.message.reply_text("❌ 此功能仅限管理员使用")
        return

    try:
        # 获取所有有效订单
        valid_orders = await db_operations.get_all_valid_orders()
        
        # 获取当日利息总额
        date = get_daily_period_date()
        daily_interest = await db_operations.get_daily_interest_total(date)
        
        # 生成订单总表
        table_text = await generate_order_table(valid_orders, daily_interest)
        
        # 获取当日完成的订单
        completed_orders = await db_operations.get_completed_orders_by_date(date)
        if completed_orders:
            completed_table = await generate_completed_orders_table(completed_orders)
            table_text += completed_table
        
        # 获取当日违约完成的订单（仅当日有变动的）
        breach_end_orders = await db_operations.get_breach_end_orders_by_date(date)
        if breach_end_orders:
            breach_table = await generate_breach_end_orders_table(breach_end_orders)
            table_text += breach_table
        
        keyboard = [
            [InlineKeyboardButton(
                "📊 导出Excel", callback_data="order_table_export_excel")],
            [InlineKeyboardButton(
                "🔙 返回报表", callback_data="report_view_today_ALL")]
        ]
        
        await update.message.reply_text(
            table_text,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    except Exception as e:
        logger.error(f"显示订单总表失败: {e}", exc_info=True)
        await update.message.reply_text(f"❌ 显示订单总表失败: {e}")


@error_handler
@private_chat_only
async def export_order_table_excel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """导出订单总表为Excel（仅管理员）"""
    user_id = update.effective_user.id if update.effective_user else None

    if not _is_admin(user_id):
        await update.message.reply_text("❌ 此功能仅限管理员使用")
        return

    try:
        # 发送处理中消息
        processing_msg = await update.message.reply_text("⏳ 正在生成Excel文件，请稍候...")
        
        # 获取所有有效订单
        valid_orders = await db_operations.get_all_valid_orders()
        
        # 获取当日利息总额
        date = get_daily_period_date()
        daily_interest = await db_operations.get_daily_interest_total(date)
        
        # 获取当日完成的订单
        completed_orders = await db_operations.get_completed_orders_by_date(date)
        
        # 获取当日违约完成的订单（仅当日有变动的）
        breach_end_orders = await db_operations.get_breach_end_orders_by_date(date)
        
        # 获取日切数据
        daily_summary = await db_operations.get_daily_summary(date)
        
        # 导出Excel
        from utils.excel_export import export_orders_to_excel
        file_path = await export_orders_to_excel(
            valid_orders,
            completed_orders,
            breach_end_orders,
            daily_interest,
            daily_summary
        )
        
        # 发送Excel文件
        with open(file_path, 'rb') as f:
            await update.message.reply_document(
                document=f,
                filename=f"订单报表_{date}.xlsx",
                caption=f"📊 订单报表 Excel 文件 ({date})"
            )
        
        # 删除处理中消息
        try:
            await processing_msg.delete()
        except:
            pass
        
        # 删除临时文件
        import os
        try:
            os.remove(file_path)
        except:
            pass
            
    except Exception as e:
        logger.error(f"导出Excel失败: {e}", exc_info=True)
        await update.message.reply_text(f"❌ 导出Excel失败: {e}")

