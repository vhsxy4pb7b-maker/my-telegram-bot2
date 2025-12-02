"""报表相关回调处理器"""
from datetime import datetime
import pytz
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
import db_operations
from utils.date_helpers import get_daily_period_date
from handlers.report_handlers import generate_report_text
from config import ADMIN_IDS

logger = logging.getLogger(__name__)


async def _check_expense_permission(user_id: int) -> bool:
    """检查用户是否有权限录入开销（异步版本）"""
    if not user_id:
        return False
    if user_id in ADMIN_IDS:
        return True
    return await db_operations.is_user_authorized(user_id)


async def handle_report_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """处理报表相关的回调"""
    query = update.callback_query
    if not query:
        logger.error("handle_report_callback: query is None")
        return

    data = query.data
    if not data:
        logger.error("handle_report_callback: data is None")
        return

    logger.info(f"handle_report_callback: processing callback data={data}")

    # 获取用户ID
    user_id = update.effective_user.id if update.effective_user else None
    if not user_id:
        logger.error("handle_report_callback: user_id is None")
        try:
            await query.answer("❌ 无法获取用户信息", show_alert=True)
        except Exception as e:
            logger.error(
                f"handle_report_callback: failed to answer query: {e}")
        return

    # 检查用户是否有权限查看特定归属ID的报表
    # 如果用户有映射的归属ID，只能查看该归属ID的报表
    user_group_id = await db_operations.get_user_group_id(user_id)
    if user_group_id:
        # 用户有权限限制，检查回调中的归属ID
        if data.startswith("report_view_"):
            # 提取归属ID
            parts = data.split("_")
            if len(parts) >= 4:
                callback_group_id = parts[3] if parts[3] != 'ALL' else None
                if callback_group_id and callback_group_id != user_group_id:
                    await query.answer("❌ 您没有权限查看该归属ID的报表", show_alert=True)
                    return
        elif data.startswith("report_menu_attribution") or data.startswith("report_search_orders"):
            # 限制用户不能使用归属查询和查找功能
            await query.answer("❌ 您没有权限使用此功能", show_alert=True)
            return

    if data == "report_record_company":
        logger.info(
            f"handle_report_callback: processing report_record_company for user {user_id}")
        try:
            await query.answer()
        except Exception as e:
            logger.warning(
                f"handle_report_callback: query.answer() failed: {e}")

        try:
            date = get_daily_period_date()
            records = await db_operations.get_expense_records(date, date, 'company')
        except Exception as e:
            logger.error(
                f"handle_report_callback: failed to get expense records: {e}", exc_info=True)
            try:
                await query.answer("❌ 获取开销记录失败", show_alert=True)
            except Exception:
                pass
            return

        msg = f"🏢 公司开销今日 ({date}):\n\n"
        if not records:
            msg += "无记录\n"
        else:
            total = 0
            for i, r in enumerate(records, 1):
                msg += f"{i}. {r['amount']:.2f} - {r['note'] or '无备注'}\n"
                total += r['amount']
            msg += f"\n总计: {total:.2f}\n"

        keyboard = []

        # 只有有权限的用户才显示添加开销按钮
        if await _check_expense_permission(user_id):
            keyboard.append([InlineKeyboardButton(
                "➕ 添加开销", callback_data="report_add_expense_company")])

        keyboard.extend([
            [
                InlineKeyboardButton(
                    "📅 本月", callback_data="report_expense_month_company"),
                InlineKeyboardButton(
                    "📆 查询", callback_data="report_expense_query_company")
            ],
            [InlineKeyboardButton(
                "🔙 返回", callback_data="report_view_today_ALL")]
        ])
        try:
            await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(keyboard))
            logger.info(
                f"handle_report_callback: successfully edited message for report_record_company")
        except Exception as e:
            logger.error(f"编辑公司开销消息失败: {e}", exc_info=True)
            try:
                await query.message.reply_text(msg, reply_markup=InlineKeyboardMarkup(keyboard))
                logger.info(
                    f"handle_report_callback: successfully sent new message for report_record_company")
            except Exception as e2:
                logger.error(f"发送公司开销消息失败: {e2}", exc_info=True)
                try:
                    await query.answer("❌ 显示开销记录失败", show_alert=True)
                except Exception:
                    pass
        return

    if data == "report_expense_month_company":
        await query.answer()
        tz = pytz.timezone('Asia/Shanghai')
        now = datetime.now(tz)
        start_date = now.replace(day=1).strftime("%Y-%m-%d")
        end_date = get_daily_period_date()

        records = await db_operations.get_expense_records(
            start_date, end_date, 'company')

        msg = f"🏢 公司开销本月 ({start_date} 至 {end_date}):\n\n"
        if not records:
            msg += "无记录\n"
        else:
            # 限制显示数量，防止消息过长
            display_records = records[-20:] if len(records) > 20 else records

            for r in display_records:
                msg += f"[{r['date']}] {r['amount']:.2f} - {r['note'] or '无备注'}\n"

            # 计算总额（所有记录）
            real_total = sum(r['amount'] for r in records)
            if len(records) > 20:
                msg += f"\n... (共 {len(records)} 条记录，显示最后20条)\n"
            msg += f"\n总计: {real_total:.2f}\n"

        keyboard = [
            [InlineKeyboardButton(
                "🔙 返回", callback_data="report_record_company")]
        ]
        try:
            await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(keyboard))
        except Exception as e:
            logger.error(f"编辑消息失败: {e}", exc_info=True)
            try:
                await query.message.reply_text(msg, reply_markup=InlineKeyboardMarkup(keyboard))
            except Exception:
                pass
        return

    if data == "report_expense_query_company":
        await query.answer()
        await query.message.reply_text(
            "🏢 请输入日期范围：\n"
            "格式1 (单日): 2024-01-01\n"
            "格式2 (范围): 2024-01-01 2024-01-31\n"
            "输入 'cancel' 取消"
        )
        context.user_data['state'] = 'QUERY_EXPENSE_COMPANY'
        return

    if data == "report_add_expense_company":
        await query.answer()
        # 检查权限：只有管理员或授权员工可以录入开销
        if not user_id:
            await query.answer("❌ 无法获取用户信息", show_alert=True)
            return

        if not await _check_expense_permission(user_id):
            await query.answer("❌ 您没有权限录入开销（仅限员工和管理员）", show_alert=True)
            return

        await query.message.reply_text(
            "🏢 请输入金额和备注：\n"
            "格式: 金额 备注\n"
            "示例: 100 服务器费用"
        )
        context.user_data['state'] = 'WAITING_EXPENSE_COMPANY'
        return

    if data == "report_record_other":
        logger.info(
            f"handle_report_callback: processing report_record_other for user {user_id}")
        try:
            await query.answer()
        except Exception as e:
            logger.warning(
                f"handle_report_callback: query.answer() failed: {e}")

        try:
            date = get_daily_period_date()
            records = await db_operations.get_expense_records(date, date, 'other')
        except Exception as e:
            logger.error(
                f"handle_report_callback: failed to get expense records: {e}", exc_info=True)
            try:
                await query.answer("❌ 获取开销记录失败", show_alert=True)
            except Exception:
                pass
            return

        msg = f"📝 其他开销今日 ({date}):\n\n"
        if not records:
            msg += "无记录\n"
        else:
            total = 0
            for i, r in enumerate(records, 1):
                msg += f"{i}. {r['amount']:.2f} - {r['note'] or '无备注'}\n"
                total += r['amount']
            msg += f"\n总计: {total:.2f}\n"

        keyboard = []

        # 只有有权限的用户才显示添加开销按钮
        if await _check_expense_permission(user_id):
            keyboard.append([InlineKeyboardButton(
                "➕ 添加开销", callback_data="report_add_expense_other")])

        keyboard.extend([
            [
                InlineKeyboardButton(
                    "📅 本月", callback_data="report_expense_month_other"),
                InlineKeyboardButton(
                    "📆 查询", callback_data="report_expense_query_other")
            ],
            [InlineKeyboardButton(
                "🔙 返回", callback_data="report_view_today_ALL")]
        ])
        try:
            await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(keyboard))
            logger.info(
                f"handle_report_callback: successfully edited message for report_record_other")
        except Exception as e:
            logger.error(f"编辑其他开销消息失败: {e}", exc_info=True)
            try:
                await query.message.reply_text(msg, reply_markup=InlineKeyboardMarkup(keyboard))
                logger.info(
                    f"handle_report_callback: successfully sent new message for report_record_other")
            except Exception as e2:
                logger.error(f"发送其他开销消息失败: {e2}", exc_info=True)
                try:
                    await query.answer("❌ 显示开销记录失败", show_alert=True)
                except Exception:
                    pass
        return

    if data == "report_expense_month_other":
        await query.answer()
        tz = pytz.timezone('Asia/Shanghai')
        now = datetime.now(tz)
        start_date = now.replace(day=1).strftime("%Y-%m-%d")
        end_date = get_daily_period_date()

        records = await db_operations.get_expense_records(
            start_date, end_date, 'other')

        msg = f"📝 其他开销本月 ({start_date} 至 {end_date}):\n\n"
        if not records:
            msg += "无记录\n"
        else:
            display_records = records[-20:] if len(records) > 20 else records
            for r in display_records:
                msg += f"[{r['date']}] {r['amount']:.2f} - {r['note'] or '无备注'}\n"

            real_total = sum(r['amount'] for r in records)
            if len(records) > 20:
                msg += f"\n... (共 {len(records)} 条记录，显示最后20条)\n"
            msg += f"\n总计: {real_total:.2f}\n"

        keyboard = [
            [InlineKeyboardButton(
                "🔙 返回", callback_data="report_record_other")]
        ]
        try:
            await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(keyboard))
        except Exception as e:
            logger.error(f"编辑消息失败: {e}", exc_info=True)
            try:
                await query.message.reply_text(msg, reply_markup=InlineKeyboardMarkup(keyboard))
            except Exception:
                pass
        return

    if data == "report_expense_query_other":
        await query.answer()
        await query.message.reply_text(
            "📝 请输入日期范围：\n"
            "格式1 (单日): 2024-01-01\n"
            "格式2 (范围): 2024-01-01 2024-01-31\n"
            "输入 'cancel' 取消"
        )
        context.user_data['state'] = 'QUERY_EXPENSE_OTHER'
        return

    if data == "report_add_expense_other":
        await query.answer()
        # 检查权限：只有管理员或授权员工可以录入开销
        if not user_id:
            await query.answer("❌ 无法获取用户信息", show_alert=True)
            return

        if not await _check_expense_permission(user_id):
            await query.answer("❌ 您没有权限录入开销（仅限员工和管理员）", show_alert=True)
            return

        await query.message.reply_text(
            "📝 请输入金额和备注：\n"
            "格式: 金额 备注\n"
            "示例: 50 办公用品"
        )
        context.user_data['state'] = 'WAITING_EXPENSE_OTHER'
        return

    if data == "report_menu_attribution":
        # 直接显示归属ID列表供选择查看报表
        group_ids = await db_operations.get_all_group_ids()
        if not group_ids:
            await query.edit_message_text(
                "⚠️ 无归属数据",
                reply_markup=InlineKeyboardMarkup(
                    [[InlineKeyboardButton("🔙 返回", callback_data="report_view_today_ALL")]])
            )
            return

        keyboard = []
        row = []
        for gid in sorted(group_ids):
            row.append(InlineKeyboardButton(
                gid, callback_data=f"report_view_today_{gid}"))
            if len(row) == 4:
                keyboard.append(row)
                row = []
        if row:
            keyboard.append(row)
        keyboard.append([InlineKeyboardButton(
            "🔙 返回", callback_data="report_view_today_ALL")])
        await query.edit_message_text("请选择归属ID查看报表:", reply_markup=InlineKeyboardMarkup(keyboard))
        return

    if data == "report_search_orders":
        await query.message.reply_text(
            "🔍 查找订单\n\n"
            "输入查询条件：\n\n"
            "单一查询：\n"
            "• S01（按归属查询）\n"
            "• 三（按星期分组查询）\n"
            "• 正常（按状态查询）\n\n"
            "综合查询：\n"
            "• 三 正常（周三的正常订单）\n"
            "• S01 正常（S01的正常订单）\n\n"
            "请输入:（输入 'cancel' 取消）"
        )
        context.user_data['state'] = 'REPORT_SEARCHING'
        return

    # ========== 收入明细查询回调（仅管理员） ==========
    if data == "income_view_today":
        if not user_id or user_id not in ADMIN_IDS:
            await query.answer("❌ 此功能仅限管理员使用", show_alert=True)
            return

        await query.answer()
        date = get_daily_period_date()
        records = await db_operations.get_income_records(date, date)
        from handlers.income_handlers import generate_income_report
        report, has_more, total_pages, current_type = await generate_income_report(
            records, date, date, f"今日收入明细 ({date})", page=1
        )

        keyboard = []

        # 如果有分页，添加分页按钮
        if total_pages > 1:
            page_buttons = []
            # 第一页只显示"下一页"
            if 1 < total_pages:
                page_buttons.append(InlineKeyboardButton(
                    "下一页 ▶️", callback_data=f"income_page_{current_type}|2|{date}|{date}"))
            if page_buttons:
                keyboard.append(page_buttons)

        keyboard.extend([
            [
                InlineKeyboardButton(
                    "📅 本月收入", callback_data="income_view_month"),
                InlineKeyboardButton(
                    "📆 日期查询", callback_data="income_view_query")
            ],
            [
                InlineKeyboardButton(
                    "🔍 分类查询", callback_data="income_view_by_type")
            ],
            [
                InlineKeyboardButton(
                    "🔙 返回报表", callback_data="report_view_today_ALL")
            ]
        ])

        try:
            await query.edit_message_text(report, reply_markup=InlineKeyboardMarkup(keyboard))
        except Exception as e:
            logger.error(f"编辑收入明细消息失败: {e}", exc_info=True)
            await query.message.reply_text(report, reply_markup=InlineKeyboardMarkup(keyboard))
        return

    if data == "income_view_month":
        if not user_id or user_id not in ADMIN_IDS:
            await query.answer("❌ 此功能仅限管理员使用", show_alert=True)
            return

        await query.answer()
        tz = pytz.timezone('Asia/Shanghai')
        now = datetime.now(tz)
        start_date = now.replace(day=1).strftime("%Y-%m-%d")
        end_date = get_daily_period_date()

        records = await db_operations.get_income_records(start_date, end_date)
        from handlers.income_handlers import generate_income_report
        report, has_more, total_pages, current_type = await generate_income_report(
            records, start_date, end_date, f"本月收入明细 ({start_date} 至 {end_date})", page=1
        )

        keyboard = []

        # 如果有分页，添加分页按钮
        if total_pages > 1:
            page_buttons = []
            # 第一页只显示"下一页"
            if 1 < total_pages:
                page_buttons.append(InlineKeyboardButton(
                    "下一页 ▶️", callback_data=f"income_page_{current_type}|2|{start_date}|{end_date}"))
            if page_buttons:
                keyboard.append(page_buttons)

        keyboard.extend([
            [
                InlineKeyboardButton(
                    "📄 今日收入", callback_data="income_view_today"),
                InlineKeyboardButton(
                    "📆 日期查询", callback_data="income_view_query")
            ],
            [InlineKeyboardButton(
                "🔙 返回报表", callback_data="report_view_today_ALL")]
        ])

        try:
            await query.edit_message_text(report, reply_markup=InlineKeyboardMarkup(keyboard))
        except Exception as e:
            logger.error(f"编辑收入明细消息失败: {e}", exc_info=True)
            await query.message.reply_text(report, reply_markup=InlineKeyboardMarkup(keyboard))
        return

    if data == "income_view_query":
        if not user_id or user_id not in ADMIN_IDS:
            await query.answer("❌ 此功能仅限管理员使用", show_alert=True)
            return

        await query.answer()
        await query.message.reply_text(
            "📆 请输入查询日期范围：\n"
            "格式1 (单日): 2024-01-01\n"
            "格式2 (范围): 2024-01-01 2024-01-31\n"
            "输入 'cancel' 取消"
        )
        context.user_data['state'] = 'QUERY_INCOME'
        return

    if data == "income_view_by_type":
        if not user_id or user_id not in ADMIN_IDS:
            await query.answer("❌ 此功能仅限管理员使用", show_alert=True)
            return

        await query.answer()
        keyboard = [
            [
                InlineKeyboardButton(
                    "订单完成", callback_data="income_type_completed"),
                InlineKeyboardButton(
                    "违约完成", callback_data="income_type_breach_end")
            ],
            [
                InlineKeyboardButton(
                    "利息收入", callback_data="income_type_interest"),
                InlineKeyboardButton(
                    "本金减少", callback_data="income_type_principal_reduction")
            ],
            [
                InlineKeyboardButton(
                    "🔍 高级查询", callback_data="income_advanced_query")
            ],
            [InlineKeyboardButton("🔙 返回", callback_data="income_view_today")]
        ]

        await query.edit_message_text(
            "🔍 请选择要查询的收入类型：\n\n或者使用高级查询进行多条件筛选",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return

    if data == "income_advanced_query":
        if not user_id or user_id not in ADMIN_IDS:
            await query.answer("❌ 此功能仅限管理员使用", show_alert=True)
            return

        await query.answer()
        # 初始化查询条件
        context.user_data['income_query'] = {
            'date': None,
            'type': None,
            'group_id': None
        }

        keyboard = [
            [InlineKeyboardButton(
                "📅 选择日期", callback_data="income_query_step_date")],
            [InlineKeyboardButton("🔙 返回", callback_data="income_view_by_type")]
        ]

        await query.edit_message_text(
            "🔍 高级查询\n\n"
            "请逐步选择查询条件：\n"
            "1️⃣ 日期（必选）\n"
            "2️⃣ 收入类型（可选）\n"
            "3️⃣ 归属ID/群名（可选）\n\n"
            "当前状态：未设置",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return

    if data == "income_query_step_date":
        if not user_id or user_id not in ADMIN_IDS:
            await query.answer("❌ 此功能仅限管理员使用", show_alert=True)
            return

        await query.answer()
        await query.message.reply_text(
            "📅 请输入查询日期：\n"
            "格式: YYYY-MM-DD\n"
            "示例: 2025-12-02\n"
            "输入 'cancel' 取消\n\n"
            "或输入日期范围（用空格分隔）：\n"
            "示例: 2025-12-01 2025-12-31"
        )
        context.user_data['state'] = 'INCOME_QUERY_DATE'
        return

    if data.startswith("income_query_step_type_"):
        if not user_id or user_id not in ADMIN_IDS:
            await query.answer("❌ 此功能仅限管理员使用", show_alert=True)
            return

        await query.answer()
        # 保存日期
        date_str = data.replace("income_query_step_type_", "")
        context.user_data['income_query']['date'] = date_str

        # 选择类型
        keyboard = [
            [
                InlineKeyboardButton(
                    "订单完成", callback_data=f"income_query_type_completed_{date_str}"),
                InlineKeyboardButton(
                    "违约完成", callback_data=f"income_query_type_breach_end_{date_str}")
            ],
            [
                InlineKeyboardButton(
                    "利息收入", callback_data=f"income_query_type_interest_{date_str}"),
                InlineKeyboardButton(
                    "本金减少", callback_data=f"income_query_type_principal_reduction_{date_str}")
            ],
            [
                InlineKeyboardButton(
                    "全部类型", callback_data=f"income_query_type_all_{date_str}")
            ],
            [InlineKeyboardButton(
                "🔙 返回", callback_data="income_advanced_query")]
        ]

        await query.edit_message_text(
            f"📅 已选择日期: {date_str}\n\n"
            "🔍 请选择收入类型：",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return

    if data.startswith("income_query_type_"):
        if not user_id or user_id not in ADMIN_IDS:
            await query.answer("❌ 此功能仅限管理员使用", show_alert=True)
            return

        await query.answer()
        # 解析参数: income_query_type_{type}_{date}
        parts = data.replace("income_query_type_", "").split("_", 1)
        income_type = parts[0]
        date_str = parts[1] if len(parts) > 1 else context.user_data.get(
            'income_query', {}).get('date')

        # 保存类型（如果是 all，设为 None）
        if income_type == 'all':
            context.user_data['income_query']['type'] = None
            income_type = None
        else:
            context.user_data['income_query']['type'] = income_type

        # 获取所有归属ID
        all_group_ids = await db_operations.get_all_group_ids()

        keyboard = []
        row = []
        for gid in sorted(all_group_ids):
            row.append(InlineKeyboardButton(
                gid,
                callback_data=f"income_query_group_{gid}_{income_type or 'all'}_{date_str}"
            ))
            if len(row) == 4:
                keyboard.append(row)
                row = []
        if row:
            keyboard.append(row)

        # 添加"全部"和"全局"选项
        keyboard.append([
            InlineKeyboardButton(
                "全部归属ID", callback_data=f"income_query_group_all_{income_type or 'all'}_{date_str}"),
            InlineKeyboardButton(
                "全局", callback_data=f"income_query_group_null_{income_type or 'all'}_{date_str}")
        ])

        keyboard.append([InlineKeyboardButton(
            "🔙 返回", callback_data=f"income_query_step_type_{date_str}")])

        type_display = {
            'completed': '订单完成',
            'breach_end': '违约完成',
            'interest': '利息收入',
            'principal_reduction': '本金减少'
        }.get(income_type, '全部类型') if income_type else '全部类型'

        await query.edit_message_text(
            f"📅 日期: {date_str}\n"
            f"🔍 类型: {type_display}\n\n"
            "📋 请选择归属ID/群名：",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return

    if data.startswith("income_query_group_"):
        if not user_id or user_id not in ADMIN_IDS:
            await query.answer("❌ 此功能仅限管理员使用", show_alert=True)
            return

        await query.answer()
        # 解析参数: income_query_group_{group_id}_{type}_{date}
        parts = data.replace("income_query_group_", "").split("_")
        group_id = parts[0]
        income_type = parts[1] if len(parts) > 1 else 'all'
        date_str = parts[2] if len(parts) > 2 else context.user_data.get(
            'income_query', {}).get('date')

        # 处理 group_id
        # 'all' 表示所有归属ID（包括NULL），查询时不过滤group_id
        # 'null' 表示只查询全局（group_id IS NULL）
        # 其他值表示查询特定归属ID

        if group_id == 'all':
            final_group = None  # 不过滤，查询所有
        elif group_id == 'null':
            final_group = 'NULL_SPECIAL'  # 特殊标记，稍后处理为 IS NULL
        else:
            final_group = group_id  # 具体归属ID

        # 保存并执行查询
        final_type = None if income_type == 'all' else income_type

        # 解析日期范围
        dates = date_str.split()
        if len(dates) == 1:
            start_date = end_date = dates[0]
        elif len(dates) == 2:
            start_date = dates[0]
            end_date = dates[1]
        else:
            start_date = end_date = get_daily_period_date()

        # 查询记录
        # 如果 final_group 是 'NULL_SPECIAL'，需要特殊处理（查询 group_id IS NULL）
        if final_group == 'NULL_SPECIAL':
            # 查询所有记录，然后过滤出 group_id 为 NULL 的
            all_records = await db_operations.get_income_records(
                start_date, end_date,
                type=final_type,
                group_id=None  # 先不过滤 group_id
            )
            records = [r for r in all_records if r.get('group_id') is None]
        else:
            records = await db_operations.get_income_records(
                start_date, end_date,
                type=final_type,
                group_id=final_group
            )

        from handlers.income_handlers import generate_income_report
        INCOME_TYPES = {"completed": "订单完成", "breach_end": "违约完成",
                        "interest": "利息收入", "principal_reduction": "本金减少"}

        type_name = INCOME_TYPES.get(
            final_type, "全部类型") if final_type else "全部类型"
        if final_group == 'NULL_SPECIAL':
            group_name = "全局"
        elif final_group:
            group_name = final_group
        else:
            group_name = "全部"

        title = f"收入明细查询"
        if start_date == end_date:
            title += f" ({start_date})"
        else:
            title += f" ({start_date} 至 {end_date})"
        title += f"\n类型: {type_name} | 归属ID: {group_name}"

        report, has_more, total_pages, current_type = await generate_income_report(
            records, start_date, end_date, title, page=1, income_type=final_type
        )

        keyboard = []

        # 如果有分页，添加分页按钮
        if total_pages > 1:
            page_data = f"{final_type or 'all'}|{final_group or 'all' if final_group else 'all'}|{start_date}|{end_date}"
            keyboard.append([InlineKeyboardButton(
                "下一页 ▶️", callback_data=f"income_adv_page_{page_data}|2")])

        keyboard.append([InlineKeyboardButton(
            "🔙 返回高级查询", callback_data="income_advanced_query")])

        try:
            await query.edit_message_text(report, reply_markup=InlineKeyboardMarkup(keyboard))
        except Exception as e:
            logger.error(f"编辑收入明细消息失败: {e}", exc_info=True)
            await query.message.reply_text(report, reply_markup=InlineKeyboardMarkup(keyboard))
        return

    # 处理高级查询分页
    if data.startswith("income_adv_page_"):
        if not user_id or user_id not in ADMIN_IDS:
            await query.answer("❌ 此功能仅限管理员使用", show_alert=True)
            return

        await query.answer()
        # 解析: income_adv_page_{type}|{group}|{start_date}|{end_date}|{page}
        # 使用 | 作为分隔符，避免日期中的连字符干扰
        param_str = data.replace("income_adv_page_", "")
        if "|" in param_str:
            # 新格式：使用 | 分隔
            parts = param_str.split("|")
            if len(parts) >= 5:
                type_key = parts[0]
                group_key = parts[1]
                start_date = parts[2]
                end_date = parts[3]
                page = int(parts[4])
            else:
                await query.answer("❌ 分页参数错误", show_alert=True)
                return
        else:
            # 兼容旧格式（使用 _ 分隔）
            parts = param_str.split("_")
            if len(parts) >= 6:
                page = int(parts[-1])
                end_date = parts[-2]
                start_date = parts[-3]
                group_key = parts[-4]
                type_key = parts[-5]
            else:
                await query.answer("❌ 分页参数错误", show_alert=True)
                return

        final_type = None if type_key == 'all' else type_key

        # 处理 group_id
        if group_key == 'all':
            final_group = None  # 不过滤
        elif group_key == 'NULL':
            final_group = 'NULL_SPECIAL'  # 特殊标记
        else:
            final_group = group_key

            # 查询记录
            if final_group == 'NULL_SPECIAL':
                all_records = await db_operations.get_income_records(
                    start_date, end_date,
                    type=final_type,
                    group_id=None
                )
                records = [r for r in all_records if r.get('group_id') is None]
            else:
                records = await db_operations.get_income_records(
                    start_date, end_date,
                    type=final_type,
                    group_id=final_group
                )

            from handlers.income_handlers import generate_income_report
            INCOME_TYPES = {"completed": "订单完成", "breach_end": "违约完成",
                            "interest": "利息收入", "principal_reduction": "本金减少"}

            type_name = INCOME_TYPES.get(
                final_type, "全部类型") if final_type else "全部类型"
            if final_group == 'NULL_SPECIAL':
                group_name = "全局"
            elif final_group:
                group_name = final_group
            else:
                group_name = "全部"

            title = f"收入明细查询"
            if start_date == end_date:
                title += f" ({start_date})"
            else:
                title += f" ({start_date} 至 {end_date})"
            title += f"\n类型: {type_name} | 归属ID: {group_name}"

            report, has_more_pages, total_pages, current_type = await generate_income_report(
                records, start_date, end_date, title, page=page, income_type=final_type
            )

            keyboard = []
            page_buttons = []

            if page > 1:
                page_data = f"{final_type or 'all'}|{final_group or 'all' if final_group else 'all'}|{start_date}|{end_date}"
                page_buttons.append(InlineKeyboardButton(
                    "◀️ 上一页", callback_data=f"income_adv_page_{page_data}|{page - 1}"))

            if page < total_pages:
                page_data = f"{final_type or 'all'}|{final_group or 'all' if final_group else 'all'}|{start_date}|{end_date}"
                page_buttons.append(InlineKeyboardButton(
                    "下一页 ▶️", callback_data=f"income_adv_page_{page_data}|{page + 1}"))

            if page_buttons:
                keyboard.append(page_buttons)

            keyboard.append([InlineKeyboardButton(
                "🔙 返回高级查询", callback_data="income_advanced_query")])

            try:
                await query.edit_message_text(report, reply_markup=InlineKeyboardMarkup(keyboard))
            except Exception as e:
                logger.error(f"编辑收入明细消息失败: {e}", exc_info=True)
                await query.message.reply_text(report, reply_markup=InlineKeyboardMarkup(keyboard))
        return

    if data.startswith("income_type_"):
        if not user_id or user_id not in ADMIN_IDS:
            await query.answer("❌ 此功能仅限管理员使用", show_alert=True)
            return

        await query.answer()
        income_type = data.replace("income_type_", "")
        date = get_daily_period_date()
        records = await db_operations.get_income_records(date, date, type=income_type)

        from handlers.income_handlers import generate_income_report
        type_name = {"completed": "订单完成", "breach_end": "违约完成",
                     "interest": "利息收入", "principal_reduction": "本金减少"}.get(income_type, income_type)
        report, has_more, total_pages, current_type = await generate_income_report(
            records, date, date, f"今日{type_name}收入 ({date})", page=1, income_type=income_type
        )

        keyboard = []

        # 如果有分页，添加分页按钮
        if total_pages > 1:
            page_buttons = []
            # 第一页只显示"下一页"
            if 1 < total_pages:
                page_buttons.append(InlineKeyboardButton(
                    "下一页 ▶️", callback_data=f"income_page_{income_type}|2|{date}|{date}"))
            if page_buttons:
                keyboard.append(page_buttons)

        keyboard.append([InlineKeyboardButton(
            "🔙 返回", callback_data="income_view_today")])
        try:
            await query.edit_message_text(report, reply_markup=InlineKeyboardMarkup(keyboard))
        except Exception as e:
            logger.error(f"编辑收入明细消息失败: {e}", exc_info=True)
            await query.message.reply_text(report, reply_markup=InlineKeyboardMarkup(keyboard))
        return

    # 处理收入明细分页
    if data.startswith("income_page_"):
        if not user_id or user_id not in ADMIN_IDS:
            await query.answer("❌ 此功能仅限管理员使用", show_alert=True)
            return

        await query.answer()

        # 解析分页参数: income_page_{type}|{page}|{start_date}|{end_date}
        # 使用 | 作为分隔符，避免日期中的连字符干扰
        param_str = data.replace("income_page_", "")

        # 兼容旧格式（使用 _ 分隔）和新格式（使用 | 分隔）
        if "|" in param_str:
            # 新格式：使用 | 分隔
            parts = param_str.split("|")
            if len(parts) < 2:
                await query.answer("❌ 分页参数错误", show_alert=True)
                return

            income_type = parts[0]
            page = int(parts[1])

            # 解析日期
            if len(parts) >= 4:
                start_date = parts[2]
                end_date = parts[3]
            else:
                # 如果没有日期，使用今日
                start_date = end_date = get_daily_period_date()
        else:
            # 旧格式兼容：尝试用 _ 分隔（可能日期会被分割）
            parts = param_str.split("_")
            if len(parts) < 2:
                await query.answer("❌ 分页参数错误", show_alert=True)
                return

            income_type = parts[0]
            try:
                page = int(parts[1])
            except (ValueError, IndexError):
                await query.answer("❌ 分页参数错误", show_alert=True)
                return

            # 尝试解析日期（旧格式日期可能被分割）
            if len(parts) >= 8:
                # 格式可能是: type_page_year_month_day_year_month_day
                try:
                    start_date = f"{parts[2]}-{parts[3].zfill(2)}-{parts[4].zfill(2)}"
                    end_date = f"{parts[5]}-{parts[6].zfill(2)}-{parts[7].zfill(2)}"
                except (ValueError, IndexError):
                    start_date = end_date = get_daily_period_date()
            elif len(parts) >= 4:
                # 尝试简单解析
                try:
                    start_date = parts[2] if len(
                        parts[2]) == 10 else get_daily_period_date()
                    end_date = parts[3] if len(parts[3]) == 10 else start_date
                except IndexError:
                    start_date = end_date = get_daily_period_date()
            else:
                # 没有日期，使用今日
                start_date = end_date = get_daily_period_date()

        # 获取记录
        records = await db_operations.get_income_records(start_date, end_date, type=income_type if income_type != 'None' else None)

        from handlers.income_handlers import generate_income_report, INCOME_TYPES
        type_name = INCOME_TYPES.get(
            income_type, income_type) if income_type != 'None' else "全部"

        # 生成标题
        if start_date == end_date:
            title = f"今日{type_name}收入 ({start_date})"
        else:
            title = f"{type_name}收入 ({start_date} 至 {end_date})"

        report, has_more, total_pages, current_type = await generate_income_report(
            records, start_date, end_date, title, page=page, income_type=income_type if income_type != 'None' else None
        )

        # 构建分页按钮
        keyboard = []
        page_buttons = []

        if page > 1:
            page_buttons.append(InlineKeyboardButton(
                "◀️ 上一页", callback_data=f"income_page_{income_type}|{page - 1}|{start_date}|{end_date}"))

        if page < total_pages:
            page_buttons.append(InlineKeyboardButton(
                "下一页 ▶️", callback_data=f"income_page_{income_type}|{page + 1}|{start_date}|{end_date}"))

        if page_buttons:
            keyboard.append(page_buttons)

        # 添加返回按钮
        if start_date == end_date and start_date == get_daily_period_date():
            keyboard.append([InlineKeyboardButton(
                "🔙 返回", callback_data="income_view_today")])
        else:
            keyboard.append([InlineKeyboardButton(
                "🔙 返回", callback_data="income_view_today")])

        try:
            await query.edit_message_text(report, reply_markup=InlineKeyboardMarkup(keyboard))
        except Exception as e:
            logger.error(f"编辑收入明细分页消息失败: {e}", exc_info=True)
            await query.message.reply_text(report, reply_markup=InlineKeyboardMarkup(keyboard))
        return

    if data == "report_change_attribution":
        # 获取查找结果
        orders = context.user_data.get('report_search_orders', [])
        if not orders:
            await query.answer("❌ 没有找到订单，请先使用查找功能")
            return

        # 获取所有归属ID列表
        all_group_ids = await db_operations.get_all_group_ids()
        if not all_group_ids:
            await query.answer("❌ 没有可用的归属ID")
            return

        # 显示归属ID选择界面
        keyboard = []
        row = []
        for gid in sorted(all_group_ids):
            row.append(InlineKeyboardButton(
                gid, callback_data=f"report_change_to_{gid}"))
            if len(row) == 4:
                keyboard.append(row)
                row = []
        if row:
            keyboard.append(row)
        keyboard.append([InlineKeyboardButton(
            "🔙 取消", callback_data="report_view_today_ALL")])

        order_count = len(orders)
        total_amount = sum(order.get('amount', 0) for order in orders)

        await query.edit_message_text(
            f"🔄 修改归属\n\n"
            f"找到订单: {order_count} 个\n"
            f"订单金额: {total_amount:,.2f}\n\n"
            f"请选择新的归属ID:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return

    if data.startswith("report_change_to_"):
        # 处理归属变更
        new_group_id = data[17:]  # 提取新的归属ID

        orders = context.user_data.get('report_search_orders', [])
        if not orders:
            await query.answer("❌ 没有找到订单")
            return

        # 执行归属变更
        from handlers.attribution_handlers import change_orders_attribution
        success_count, fail_count = await change_orders_attribution(
            update, context, orders, new_group_id
        )

        result_msg = (
            f"✅ 归属变更完成\n\n"
            f"成功: {success_count} 个订单\n"
            f"失败: {fail_count} 个订单"
        )

        await query.edit_message_text(result_msg)
        await query.answer("✅ 归属变更完成")

        # 清除查找结果
        context.user_data.pop('report_search_orders', None)
        return

    # 提取视图类型和参数
    # 格式: report_view_{type}_{group_id}
    # 或者旧格式: report_{group_id}

    if data.startswith("report_") and not data.startswith("report_view_"):
        # 兼容旧格式，转为 today 视图
        group_id = data[7:]
        view_type = 'today'
    else:
        parts = data.split('_')
        # report, view, type, group_id...
        if len(parts) < 4:
            return
        view_type = parts[2]
        group_id = parts[3]

    group_id = None if group_id == 'ALL' else group_id

    # 如果用户有权限限制，确保使用用户的归属ID
    if user_group_id:
        group_id = user_group_id

    if view_type == 'today':
        date = get_daily_period_date()
        # 如果用户有权限限制，不显示开销与余额
        show_expenses = not user_group_id
        report_text = await generate_report_text("today", date, date, group_id, show_expenses=show_expenses)

        keyboard = [
            [
                InlineKeyboardButton(
                    "📅 月报", callback_data=f"report_view_month_{group_id if group_id else 'ALL'}"),
                InlineKeyboardButton(
                    "📆 日期查询", callback_data=f"report_view_query_{group_id if group_id else 'ALL'}")
            ]
        ]

        # 只有有权限的用户才显示开销按钮
        if await _check_expense_permission(user_id):
            keyboard.append([
                InlineKeyboardButton(
                    "🏢 公司开销", callback_data="report_record_company"),
                InlineKeyboardButton(
                    "📝 其他开销", callback_data="report_record_other")
            ])

        # 全局视图添加通用按钮（但用户有权限限制时不显示）
        if not group_id and not user_group_id:
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
        elif group_id:
            # 如果用户有权限限制，不显示返回按钮（因为不能返回全局视图）
            if not user_group_id:
                keyboard.append([InlineKeyboardButton(
                    "🔙 返回", callback_data="report_view_today_ALL")])

        await query.edit_message_text(report_text, reply_markup=InlineKeyboardMarkup(keyboard))

    elif view_type == 'month':
        # 如果用户有权限限制，确保使用用户的归属ID
        if user_group_id:
            group_id = user_group_id

        tz = pytz.timezone('Asia/Shanghai')
        now = datetime.now(tz)
        start_date = now.replace(day=1).strftime("%Y-%m-%d")
        end_date = get_daily_period_date()

        # 如果用户有权限限制，不显示开销与余额
        show_expenses = not user_group_id
        report_text = await generate_report_text("month", start_date, end_date, group_id, show_expenses=show_expenses)

        keyboard = [
            [
                InlineKeyboardButton(
                    "📄 今日报表", callback_data=f"report_view_today_{group_id if group_id else 'ALL'}"),
                InlineKeyboardButton(
                    "📆 日期查询", callback_data=f"report_view_query_{group_id if group_id else 'ALL'}")
            ]
        ]

        # 只有有权限的用户才显示开销按钮
        if await _check_expense_permission(user_id):
            keyboard.append([
                InlineKeyboardButton(
                    "🏢 公司开销", callback_data="report_record_company"),
                InlineKeyboardButton(
                    "📝 其他开销", callback_data="report_record_other")
            ])
        await query.edit_message_text(report_text, reply_markup=InlineKeyboardMarkup(keyboard))

    elif view_type == 'query':
        # 如果用户有权限限制，确保使用用户的归属ID
        if user_group_id:
            group_id = user_group_id

        await query.message.reply_text(
            "📆 请输入查询日期范围：\n"
            "格式1 (单日): 2024-01-01\n"
            "格式2 (范围): 2024-01-01 2024-01-31\n"
            "输入 'cancel' 取消"
        )
        context.user_data['state'] = 'REPORT_QUERY'
        context.user_data['report_group_id'] = group_id
