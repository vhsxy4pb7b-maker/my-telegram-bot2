"""收入明细查询处理器（仅管理员权限）"""
import logging
from datetime import datetime
from typing import Optional
import pytz
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
import db_operations
from utils.date_helpers import get_daily_period_date
from decorators import error_handler, private_chat_only
from config import ADMIN_IDS
from constants import INCOME_TYPES, CUSTOMER_TYPES

logger = logging.getLogger(__name__)


def _is_admin(user_id: Optional[int]) -> bool:
    """检查用户是否为管理员"""
    return user_id is not None and user_id in ADMIN_IDS


async def format_income_detail(record: dict) -> str:
    """格式化单条收入明细 - 格式：金额、订单号、时间"""
    # 格式化金额
    amount_str = f"{record['amount']:,.2f}"
    
    # 获取订单号
    order_id = record.get('order_id') or '无'
    
    # 获取时间（转换为北京时间显示）
    time_str = ""
    if record.get('created_at'):
        try:
            created_at_str = record['created_at']
            
            # 修复日期阈值：2024-12-02（修复代码部署日期）
            # 在此日期之后创建的记录，已经是北京时间，直接显示
            # 在此日期之前创建的记录，是UTC时间，需要转换
            FIX_DEPLOY_DATE = datetime(2024, 12, 2).date()
            
            # 解析时间字符串
            if 'T' in created_at_str:
                # ISO格式
                try:
                    dt = datetime.fromisoformat(created_at_str.replace('Z', '+00:00'))
                except:
                    created_at_str_clean = created_at_str.split('.')[0].split('+')[0].split('Z')[0]
                    dt = datetime.strptime(created_at_str_clean, "%Y-%m-%dT%H:%M:%S")
            else:
                # SQLite格式 (2024-12-02 15:00:00)
                if '.' in created_at_str:
                    dt = datetime.strptime(created_at_str.split('.')[0], "%Y-%m-%d %H:%M:%S")
                else:
                    dt = datetime.strptime(created_at_str, "%Y-%m-%d %H:%M:%S")
            
            # 判断是新数据（北京时间）还是旧数据（UTC）
            record_date = dt.date()
            
            if record_date >= FIX_DEPLOY_DATE:
                # 新数据：已经是北京时间，直接显示
                time_str = dt.strftime("%H:%M:%S")
            else:
                # 旧数据：是UTC时间，需要转换为北京时间
                if dt.tzinfo is None:
                    dt = pytz.utc.localize(dt)
                tz_beijing = pytz.timezone('Asia/Shanghai')
                dt_beijing = dt.astimezone(tz_beijing)
                time_str = dt_beijing.strftime("%H:%M:%S")
        except Exception as e:
            logger.warning(f"解析时间失败: {record.get('created_at')}, 错误: {e}")
            pass
    
    # 格式：金额 订单号 时间
    detail = f"{amount_str} | {order_id} | {time_str if time_str else '无时间'}"
    
    return detail


async def generate_income_report(records: list, start_date: str, end_date: str,
                                  title: str = "收入明细", page: int = 1, 
                                  items_per_page: int = 20, income_type: Optional[str] = None) -> tuple:
    """
    生成收入明细报表（支持分页）
    
    返回: (report_text, has_more_pages, total_pages, current_type)
    """
    if not records:
        return (f"💰 {title}\n\n{start_date} 至 {end_date}\n\n❌ 无记录", False, 0, None)
    
    # 如果指定了类型，只显示该类型的记录
    if income_type:
        records = [r for r in records if r['type'] == income_type]
    
    # 按类型分组
    by_type = {}
    for record in records:
        type_name = record['type']
        if type_name not in by_type:
            by_type[type_name] = []
        by_type[type_name].append(record)
    
    # 计算总计
    total_amount = sum(r['amount'] for r in records)
    
    # 生成报表文本
    report = f"💰 {title}\n"
    report += f"{'═' * 30}\n"
    report += f"📅 {start_date} 至 {end_date}\n"
    report += f"{'═' * 30}\n\n"
    
    # 按类型显示
    type_order = ['completed', 'breach_end', 'interest', 'principal_reduction', 'adjustment']
    
    # 如果指定了类型，只显示该类型
    if income_type:
        type_order = [income_type] if income_type in type_order else []
    
    has_more_pages = False
    total_pages = 1
    current_type = None
    
    # 如果指定了类型，只显示该类型并支持分页
    if income_type and income_type in by_type:
        type_key = income_type
        type_name = INCOME_TYPES.get(type_key, type_key)
        type_records = by_type[type_key]
        
        # 按时间倒序排序（最新的在前）
        type_records.sort(key=lambda x: x.get('created_at', ''), reverse=True)
        
        type_total = sum(r['amount'] for r in type_records)
        type_count = len(type_records)
        
        report += f"【{type_name}】总计: {type_total:,.2f} ({type_count}笔)\n"
        report += f"{'─' * 30}\n"
        
        # 分页处理
        if type_count > items_per_page:
            total_pages = (type_count + items_per_page - 1) // items_per_page
            start_idx = (page - 1) * items_per_page
            end_idx = start_idx + items_per_page
            display_records = type_records[start_idx:end_idx]
            has_more_pages = end_idx < type_count
            
            report += f"📄 第 {page}/{total_pages} 页 (显示 {start_idx + 1}-{min(end_idx, type_count)}/{type_count} 条)\n"
            report += f"{'─' * 30}\n"
        else:
            display_records = type_records
            has_more_pages = False
        
        # 显示明细（全部显示）
        for i, record in enumerate(display_records, 1):
            detail = await format_income_detail(record)
            global_idx = (page - 1) * items_per_page + i if type_count > items_per_page else i
            report += f"{global_idx}. {detail}\n"
        
        current_type = type_key
        report += "\n"
    else:
        # 显示所有类型，每个类型如果记录太多，只显示第一页并提供分页按钮
        for type_key in type_order:
            if type_key not in by_type:
                continue
            
            type_name = INCOME_TYPES.get(type_key, type_key)
            type_records = by_type[type_key]
            
            # 按时间倒序排序（最新的在前）
            type_records.sort(key=lambda x: x.get('created_at', ''), reverse=True)
            
            type_total = sum(r['amount'] for r in type_records)
            type_count = len(type_records)
            
            report += f"【{type_name}】总计: {type_total:,.2f} ({type_count}笔)\n"
            report += f"{'─' * 30}\n"
            
            # 如果记录太多，只显示第一页
            if type_count > items_per_page:
                display_records = type_records[:items_per_page]
                report += f"📄 显示前 {items_per_page}/{type_count} 条\n"
                report += f"{'─' * 30}\n"
            else:
                display_records = type_records
            
            # 显示明细（全部显示）
            for i, record in enumerate(display_records, 1):
                detail = await format_income_detail(record)
                report += f"{i}. {detail}\n"
            
            report += "\n"
            
            # 如果当前类型记录最多，设置为当前类型（用于分页）
            if not current_type or type_count > len(by_type.get(current_type, [])):
                current_type = type_key
    
    report += f"{'═' * 30}\n"
    report += f"💰 总收入: {total_amount:,.2f}\n"
    
    return (report, has_more_pages, total_pages, current_type)


@error_handler
@private_chat_only
async def show_income_detail(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """显示今日收入明细（仅管理员）"""
    user_id = update.effective_user.id if update.effective_user else None
    
    if not _is_admin(user_id):
        await update.message.reply_text("❌ 此功能仅限管理员使用")
        return
    
    date = get_daily_period_date()
    records = await db_operations.get_income_records(date, date)
    
    report, has_more, total_pages, current_type = await generate_income_report(
        records, date, date, f"今日收入明细 ({date})", page=1
    )
    
    keyboard = []
    
    # 如果有分页，添加分页按钮
    if has_more and total_pages > 1:
        page_buttons = []
        if total_pages > 1:
            # 使用 | 作为分隔符，避免日期中的连字符干扰
            date = get_daily_period_date()
            page_buttons.append(InlineKeyboardButton("下一页 ▶️", callback_data=f"income_page_{current_type}|2|{date}|{date}"))
        keyboard.append(page_buttons)
    
    keyboard.extend([
        [
            InlineKeyboardButton("📅 本月收入", callback_data="income_view_month"),
            InlineKeyboardButton("📆 日期查询", callback_data="income_view_query")
        ],
        [
            InlineKeyboardButton("🔍 分类查询", callback_data="income_view_by_type")
        ],
        [
            InlineKeyboardButton("🔙 返回报表", callback_data="report_view_today_ALL")
        ]
    ])
    
    try:
        if update.callback_query:
            await update.callback_query.edit_message_text(report, reply_markup=InlineKeyboardMarkup(keyboard))
        else:
            await update.message.reply_text(report, reply_markup=InlineKeyboardMarkup(keyboard))
    except Exception as e:
        logger.error(f"显示收入明细失败: {e}", exc_info=True)
        if update.callback_query:
            await update.callback_query.message.reply_text(report, reply_markup=InlineKeyboardMarkup(keyboard))
        else:
            await update.message.reply_text(report, reply_markup=InlineKeyboardMarkup(keyboard))


async def handle_income_query_input(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str):
    """处理收入明细查询输入"""
    user_id = update.effective_user.id if update.effective_user else None
    
    if not _is_admin(user_id):
        await update.message.reply_text("❌ 此功能仅限管理员使用")
        context.user_data['state'] = None
        return
    
    try:
        dates = text.split()
        if len(dates) == 1:
            start_date = end_date = dates[0]
        elif len(dates) == 2:
            start_date = dates[0]
            end_date = dates[1]
        else:
            await update.message.reply_text("❌ 格式错误。请使用：\n格式1 (单日): 2024-01-01\n格式2 (范围): 2024-01-01 2024-01-31")
            return
        
        # 验证日期格式
        datetime.strptime(start_date, "%Y-%m-%d")
        datetime.strptime(end_date, "%Y-%m-%d")
        
        records = await db_operations.get_income_records(start_date, end_date)
        
        report, has_more, total_pages, current_type = await generate_income_report(
            records, start_date, end_date, 
            f"收入明细 ({start_date} 至 {end_date})", page=1
        )
        
        keyboard = []
        
        # 如果有分页，添加分页按钮
        if has_more and total_pages > 1:
            keyboard.append([InlineKeyboardButton("下一页 ▶️", callback_data=f"income_page_{current_type}|2|{start_date}|{end_date}")])
        
        keyboard.append([InlineKeyboardButton("🔙 返回", callback_data="income_view_today")])
        await update.message.reply_text(report, reply_markup=InlineKeyboardMarkup(keyboard))
        context.user_data['state'] = None
        
    except ValueError:
        await update.message.reply_text("❌ 日期格式错误。请使用 YYYY-MM-DD 格式")
    except Exception as e:
        logger.error(f"查询收入明细出错: {e}", exc_info=True)
        await update.message.reply_text(f"⚠️ 错误: {e}")
        context.user_data['state'] = None

