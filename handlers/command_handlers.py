"""命令处理器"""
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
import db_operations
from utils.chat_helpers import is_group_chat
from utils.order_helpers import try_create_order_from_title
from utils.stats_helpers import update_liquid_capital, update_all_stats
from utils.date_helpers import get_daily_period_date
from utils.message_helpers import display_search_results_helper
from decorators import error_handler, admin_required, authorized_required, private_chat_only, group_chat_only

logger = logging.getLogger(__name__)


@error_handler
@private_chat_only
@authorized_required
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """发送欢迎消息"""
    financial_data = await db_operations.get_financial_data()

    await update.message.reply_text(
        "📋 订单管理系统\n\n"
        "💰 当前流动资金: {:.2f}\n\n"
        "📝 订单操作:\n"
        "/create - 读取群名创建新订单\n"
        "/order - 管理当前订单\n\n"
        "⚡ 快捷操作 (在订单群):\n"
        "+<金额>b - 减少本金\n"
        "+<金额> - 利息收入\n\n"
        "🔄 状态变更:\n"
        "/normal - 设为正常\n"
        "/overdue - 设为逾期\n"
        "/end - 标记为完成\n"
        "/breach - 标记为违约\n"
        "/breach_end - 违约完成\n\n"
        "📊 查询:\n"
        "/report [归属ID] - 查看报表\n"
        "/search <类型> <值> - 搜索订单\n"
        "  类型: order_id/group_id/customer/state/date\n\n"
        "📢 播报:\n"
        "/broadcast - 播报付款提醒（群聊）\n"
        "/schedule - 管理定时播报（最多3个）\n\n"
        "💳 支付账号:\n"
        "/accounts - 查看所有账户数据表格\n"
        "/gcash - 查看GCASH账号\n"
        "/paymaya - 查看PayMaya账号\n\n"
        "⚙️ 管理:\n"
        "/adjust <金额> [备注] - 调整资金\n"
        "/create_attribution <ID> - 创建归属ID\n"
        "/list_attributions - 列出归属ID\n"
        "/add_employee <ID> - 添加员工\n"
        "/remove_employee <ID> - 移除员工\n"
        "/list_employees - 列出员工\n\n"
        "⚠️ 部分操作需要管理员权限".format(
            financial_data['liquid_funds'])
    )


@error_handler
@authorized_required
@group_chat_only
async def create_order(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """创建新订单 (读取群名)"""
    try:
        chat = update.effective_chat
        if not chat:
            logger.error("Cannot get chat from update")
            return

        title = chat.title
        if not title:
            await update.message.reply_text("❌ Cannot get group title.")
            return

        logger.info(f"Creating order from title: {title} in chat {chat.id}")
        await try_create_order_from_title(update, context, chat, title, manual_trigger=True)
    except Exception as e:
        logger.error(f"Error in create_order: {e}", exc_info=True)
        if update.message:
            await update.message.reply_text(f"❌ Error creating order: {str(e)}")


@authorized_required
@group_chat_only
async def show_current_order(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """显示当前订单状态和操作菜单"""
    # 支持 CommandHandler 和 CallbackQueryHandler
    if update.message:
        chat_id = update.message.chat_id
        reply_func = update.message.reply_text
    elif update.callback_query:
        chat_id = update.callback_query.message.chat_id
        reply_func = update.callback_query.message.reply_text
    else:
        return

    order = await db_operations.get_order_by_chat_id(chat_id)
    if not order:
        await reply_func("❌ No active order in this group.\nUse /create to start a new order.")
        return

    # 构建订单信息
    msg = (
        f"📋 Current Order Status:\n"
        f"──────────────────\n"
        f"📝 Order ID: `{order['order_id']}`\n"
        f"🏷️ Group ID: `{order['group_id']}`\n"
        f"📅 Date: {order['date']}\n"
        f"👥 Week Group: {order['weekday_group']}\n"
        f"👤 Customer: {order['customer']}\n"
        f"💰 Amount: {order['amount']:.2f}\n"
        f"📊 State: {order['state']}\n"
        f"──────────────────"
    )

    # 构建操作按钮（群聊使用英文）
    keyboard = [
        [
            InlineKeyboardButton(
                "✅ Normal", callback_data="order_action_normal"),
            InlineKeyboardButton(
                "⚠️ Overdue", callback_data="order_action_overdue")
        ],
        [
            InlineKeyboardButton("🏁 End", callback_data="order_action_end"),
            InlineKeyboardButton(
                "🚫 Breach", callback_data="order_action_breach")
        ],
        [
            InlineKeyboardButton(
                "💸 Breach End", callback_data="order_action_breach_end")
        ],
        [
            InlineKeyboardButton(
                "💳 Send Account", callback_data="payment_select_account")
        ],
        [
            InlineKeyboardButton(
                "🔄 Change Attribution", callback_data="order_action_change_attribution")
        ]
    ]

    await reply_func(msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')


@error_handler
@admin_required
@private_chat_only
async def adjust_funds(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """调整流动资金余额命令"""
    if not context.args or len(context.args) < 1:
        await update.message.reply_text(
            "❌ 用法: /adjust <金额> [备注]\n"
            "示例: /adjust +5000 收入备注\n"
            "      /adjust -3000 支出备注"
        )
        return

    amount_str = context.args[0]
    note = " ".join(context.args[1:]) if len(context.args) > 1 else "无备注"

    # 验证金额格式
    if not (amount_str.startswith('+') or amount_str.startswith('-')):
        await update.message.reply_text("❌ 金额格式错误，请使用+100或-200格式")
        return

    amount = float(amount_str)
    if amount == 0:
        await update.message.reply_text("❌ 调整金额不能为0")
        return

    # 更新财务数据
    await update_liquid_capital(amount)

    financial_data = await db_operations.get_financial_data()
    await update.message.reply_text(
        f"✅ 资金调整成功\n"
        f"调整类型: {'增加' if amount > 0 else '减少'}\n"
        f"调整金额: {abs(amount):.2f}\n"
        f"调整后余额: {financial_data['liquid_funds']:.2f}\n"
        f"备注: {note}"
    )


@admin_required
@private_chat_only
async def create_attribution(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """创建新的归属ID"""
    if not context.args or len(context.args) < 1:
        await update.message.reply_text("❌ 用法: /create_attribution <归属ID>\n示例: /create_attribution S03")
        return

    group_id = context.args[0].upper()

    # 验证格式
    if len(group_id) != 3 or not group_id[0].isalpha() or not group_id[1:].isdigit():
        await update.message.reply_text("❌ 格式错误，正确格式：字母+两位数字（如S01）")
        return

    # 检查是否已存在
    existing_groups = await db_operations.get_all_group_ids()
    if group_id in existing_groups:
        await update.message.reply_text(f"⚠️ 归属ID {group_id} 已存在")
        return

    # 创建分组数据记录
    await db_operations.update_grouped_data(group_id, 'valid_orders', 0)
    await update.message.reply_text(f"✅ 成功创建归属ID {group_id}")


@admin_required
@private_chat_only
async def list_attributions(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """列出所有归属ID"""
    group_ids = await db_operations.get_all_group_ids()

    if not group_ids:
        await update.message.reply_text("暂无归属ID，使用 /create_attribution <ID> 创建")
        return

    message = "📋 所有归属ID:\n\n"
    for i, group_id in enumerate(sorted(group_ids), 1):
        data = await db_operations.get_grouped_data(group_id)
        message += (
            f"{i}. {group_id}\n"
            f"   有效订单: {data['valid_orders']} | "
            f"金额: {data['valid_amount']:.2f}\n"
        )

    await update.message.reply_text(message)


@admin_required
@private_chat_only
async def add_employee(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """添加员工（授权用户）"""
    if not context.args:
        await update.message.reply_text("❌ 用法: /add_employee <用户ID>")
        return

    try:
        user_id = int(context.args[0])
        if await db_operations.add_authorized_user(user_id):
            await update.message.reply_text(f"✅ 已添加员工: {user_id}")
        else:
            await update.message.reply_text("⚠️ 添加失败或用户已存在")
    except ValueError:
        await update.message.reply_text("❌ 用户ID必须是数字")


@admin_required
@private_chat_only
async def remove_employee(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """移除员工（授权用户）"""
    if not context.args:
        await update.message.reply_text("❌ 用法: /remove_employee <用户ID>")
        return

    try:
        user_id = int(context.args[0])
        if await db_operations.remove_authorized_user(user_id):
            await update.message.reply_text(f"✅ 已移除员工: {user_id}")
        else:
            await update.message.reply_text("⚠️ 移除失败或用户不存在")
    except ValueError:
        await update.message.reply_text("❌ 用户ID必须是数字")


@admin_required
@private_chat_only
async def update_weekday_groups(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """更新所有订单的星期分组（管理员命令）"""
    try:
        msg = await update.message.reply_text("🔄 开始更新所有订单的星期分组...")

        # 直接调用更新逻辑
        from datetime import datetime
        from utils.chat_helpers import get_weekday_group_from_date

        all_orders = await db_operations.search_orders_advanced_all_states({})

        if not all_orders:
            await msg.edit_text("❌ 没有找到订单")
            return

        updated_count = 0
        error_count = 0
        skipped_count = 0

        for order in all_orders:
            order_id = order['order_id']
            chat_id = order['chat_id']
            order_date_str = order.get('date', '')

            try:
                # 从订单ID解析日期
                date_from_id = None
                if order_id.startswith('A'):
                    if len(order_id) >= 7 and order_id[1:7].isdigit():
                        date_part = order_id[1:7]
                        try:
                            full_date_str = f"20{date_part}"
                            date_from_id = datetime.strptime(
                                full_date_str, "%Y%m%d").date()
                        except ValueError:
                            pass
                else:
                    if len(order_id) >= 6 and order_id[:6].isdigit():
                        date_part = order_id[:6]
                        try:
                            full_date_str = f"20{date_part}"
                            date_from_id = datetime.strptime(
                                full_date_str, "%Y%m%d").date()
                        except ValueError:
                            pass

                # 从date字段解析日期
                date_from_db = None
                if order_date_str:
                    try:
                        date_str = order_date_str.split(
                        )[0] if ' ' in order_date_str else order_date_str
                        date_from_db = datetime.strptime(
                            date_str, "%Y-%m-%d").date()
                    except ValueError:
                        pass

                order_date = date_from_id or date_from_db

                if not order_date:
                    skipped_count += 1
                    continue

                # 计算正确的星期分组
                correct_weekday_group = get_weekday_group_from_date(order_date)

                # 更新
                success = await db_operations.update_order_weekday_group(chat_id, correct_weekday_group)

                if success:
                    updated_count += 1
                else:
                    error_count += 1

            except Exception as e:
                logger.error(f"处理订单 {order_id} 时出错: {e}")
                error_count += 1

        result_msg = (
            f"✅ 更新完成！\n\n"
            f"已更新: {updated_count} 个订单\n"
            f"跳过: {skipped_count} 个订单\n"
            f"错误: {error_count} 个订单\n"
            f"总计: {len(all_orders)} 个订单"
        )

        await msg.edit_text(result_msg)

    except Exception as e:
        logger.error(f"更新星期分组时出错: {e}", exc_info=True)
        await update.message.reply_text(f"❌ 更新失败: {str(e)}")


@admin_required
@private_chat_only
async def fix_statistics(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """修复统计数据：根据实际订单数据重新计算所有统计数据（管理员命令）"""
    try:
        msg = await update.message.reply_text("🔄 开始修复统计数据...")

        # 直接在这里实现修复逻辑
        all_orders = await db_operations.search_orders_advanced_all_states({})
        all_group_ids = list(set(order.get('group_id')
                             for order in all_orders if order.get('group_id')))

        fixed_count = 0
        fixed_groups = []

        for group_id in sorted(all_group_ids):
            group_orders = [o for o in all_orders if o.get(
                'group_id') == group_id]
            valid_orders = [o for o in group_orders if o.get('state') in [
                'normal', 'overdue']]

            actual_valid_count = len(valid_orders)
            actual_valid_amount = sum(o.get('amount', 0) for o in valid_orders)

            grouped_data = await db_operations.get_grouped_data(group_id)

            valid_count_diff = actual_valid_count - \
                grouped_data['valid_orders']
            valid_amount_diff = actual_valid_amount - \
                grouped_data['valid_amount']

            if abs(valid_count_diff) > 0 or abs(valid_amount_diff) > 0.01:
                if valid_count_diff != 0:
                    await db_operations.update_grouped_data(group_id, 'valid_orders', valid_count_diff)
                if abs(valid_amount_diff) > 0.01:
                    await db_operations.update_grouped_data(group_id, 'valid_amount', valid_amount_diff)
                fixed_count += 1
                fixed_groups.append(
                    f"{group_id} (订单数: {valid_count_diff}, 金额: {valid_amount_diff:,.2f})")

        # 修复全局统计
        all_valid_orders = [o for o in all_orders if o.get('state') in [
            'normal', 'overdue']]
        global_valid_count = len(all_valid_orders)
        global_valid_amount = sum(o.get('amount', 0) for o in all_valid_orders)

        financial_data = await db_operations.get_financial_data()
        global_valid_count_diff = global_valid_count - \
            financial_data['valid_orders']
        global_valid_amount_diff = global_valid_amount - \
            financial_data['valid_amount']

        if abs(global_valid_count_diff) > 0 or abs(global_valid_amount_diff) > 0.01:
            if global_valid_count_diff != 0:
                await db_operations.update_financial_data('valid_orders', global_valid_count_diff)
            if abs(global_valid_amount_diff) > 0.01:
                await db_operations.update_financial_data('valid_amount', global_valid_amount_diff)
            fixed_count += 1

        if fixed_count > 0:
            result_msg = f"✅ 统计数据修复完成！\n\n已修复 {fixed_count} 个归属ID的统计数据。"
            if fixed_groups:
                result_msg += f"\n\n修复的归属ID:\n" + \
                    "\n".join(f"• {g}" for g in fixed_groups)
        else:
            result_msg = "✅ 统计数据一致，无需修复。"

        await msg.edit_text(result_msg)

    except Exception as e:
        logger.error(f"修复统计数据时出错: {e}", exc_info=True)
        await update.message.reply_text(f"❌ 修复失败: {str(e)}")


@admin_required
@private_chat_only
async def find_tail_orders(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """查找导致有效金额尾数的订单（管理员命令）"""
    try:
        msg = await update.message.reply_text("🔍 正在分析有效金额尾数...")

        # 获取所有有效订单（包含所有状态，用于完整分析）
        all_valid_orders = await db_operations.search_orders_advanced({})
        all_orders_all_states = await db_operations.search_orders_advanced_all_states({})

        # 计算实际有效金额（从订单表）
        actual_valid_amount = sum(order.get('amount', 0)
                                  for order in all_valid_orders)

        # 获取统计表中的有效金额
        financial_data = await db_operations.get_financial_data()
        stats_valid_amount = financial_data['valid_amount']

        # 查找所有非整千数订单
        non_thousand_orders = []
        tail_6_orders = []
        tail_distribution = {}  # 尾数分布统计

        for order in all_valid_orders:
            amount = order.get('amount', 0)
            if amount % 1000 != 0:
                tail = int(amount % 1000)
                non_thousand_orders.append((order, tail))
                if tail not in tail_distribution:
                    tail_distribution[tail] = []
                tail_distribution[tail].append(order)
                if tail == 6:
                    tail_6_orders.append(order)

        # 按归属ID分组分析
        group_analysis = {}
        all_group_ids = list(set(order.get('group_id')
                             for order in all_valid_orders if order.get('group_id')))

        for group_id in sorted(all_group_ids):
            group_orders = [o for o in all_valid_orders if o.get(
                'group_id') == group_id]
            group_amount = sum(o.get('amount', 0) for o in group_orders)
            group_tail = int(group_amount % 1000)
            group_non_thousand = [
                o for o in group_orders if o.get('amount', 0) % 1000 != 0]

            grouped_data = await db_operations.get_grouped_data(group_id)
            stats_group_amount = grouped_data.get('valid_amount', 0)
            stats_group_tail = int(stats_group_amount % 1000)

            group_analysis[group_id] = {
                'orders': group_orders,
                'actual_amount': group_amount,
                'actual_tail': group_tail,
                'stats_amount': stats_group_amount,
                'stats_tail': stats_group_tail,
                'non_thousand': group_non_thousand
            }

        # 构建结果消息
        result_msg = "🔍 有效金额尾数分析报告\n\n"
        result_msg += f"📊 总体统计：\n"
        result_msg += f"有效订单数: {len(all_valid_orders)}\n"
        result_msg += f"实际有效金额: {actual_valid_amount:,.2f}\n"
        result_msg += f"统计有效金额: {stats_valid_amount:,.2f}\n"
        result_msg += f"差异: {stats_valid_amount - actual_valid_amount:,.2f}\n\n"

        # 分析总金额尾数
        actual_tail = int(actual_valid_amount % 1000)
        stats_tail = int(stats_valid_amount % 1000)

        if actual_tail == 6:
            result_msg += f"⚠️ 实际有效金额尾数是 6\n"
        elif stats_tail == 6:
            result_msg += f"⚠️ 统计有效金额尾数是 6（但实际尾数是 {actual_tail}）\n"
            result_msg += f"   说明统计数据不一致，建议运行 /fix_statistics\n\n"
        else:
            result_msg += f"✅ 总金额尾数: 实际={actual_tail}, 统计={stats_tail}\n\n"

        # 显示尾数为6的订单
        if tail_6_orders:
            result_msg += f"⚠️ 发现 {len(tail_6_orders)} 个尾数为 6 的订单：\n\n"
            for order in tail_6_orders:
                result_msg += (
                    f"订单ID: {order.get('order_id')}\n"
                    f"金额: {order.get('amount'):,.2f}\n"
                    f"状态: {order.get('state')}\n"
                    f"归属: {order.get('group_id')}\n"
                    f"日期: {order.get('date')}\n"
                    f"客户: {order.get('customer', 'N/A')}\n\n"
                )
        else:
            result_msg += "✅ 没有找到尾数为 6 的订单\n\n"

        # 按归属ID分组显示
        result_msg += f"📋 按归属ID分组分析：\n\n"
        for group_id in sorted(all_group_ids):
            analysis = group_analysis[group_id]
            result_msg += f"{group_id}:\n"
            result_msg += f"  实际金额: {analysis['actual_amount']:,.2f} (尾数: {analysis['actual_tail']})\n"
            result_msg += f"  统计金额: {analysis['stats_amount']:,.2f} (尾数: {analysis['stats_tail']})\n"

            if analysis['actual_tail'] == 6 or analysis['stats_tail'] == 6:
                result_msg += f"  ⚠️ 该归属ID导致尾数6！\n"

            if analysis['non_thousand']:
                result_msg += f"  非整千数订单: {len(analysis['non_thousand'])} 个\n"
                for order in analysis['non_thousand'][:3]:
                    amount = order.get('amount', 0)
                    tail = int(amount % 1000)
                    result_msg += f"    - {order.get('order_id')}: {amount:,.2f} (尾数: {tail})\n"
                if len(analysis['non_thousand']) > 3:
                    result_msg += f"    ... 还有 {len(analysis['non_thousand']) - 3} 个\n"
            result_msg += "\n"

        # 尾数分布统计
        if tail_distribution:
            result_msg += f"📊 尾数分布统计：\n"
            for tail in sorted(tail_distribution.keys()):
                count = len(tail_distribution[tail])
                total = sum(o.get('amount', 0)
                            for o in tail_distribution[tail])
                result_msg += f"  尾数 {tail}: {count} 个订单, 总金额: {total:,.2f}\n"
            result_msg += "\n"

        # 可能的原因分析
        if stats_tail == 6 and actual_tail != 6:
            result_msg += "💡 原因分析：\n"
            result_msg += "统计金额尾数为6，但实际订单金额尾数不是6\n"
            result_msg += "说明统计数据与实际订单数据不一致\n"
            result_msg += "建议：运行 /fix_statistics 修复统计数据\n"
        elif actual_tail == 6:
            result_msg += "💡 原因分析：\n"
            if tail_6_orders:
                result_msg += f"找到 {len(tail_6_orders)} 个订单金额尾数为6\n"
                result_msg += "可能原因：\n"
                result_msg += "1. 订单创建时输入了非整千数金额\n"
                result_msg += "2. 执行了本金减少操作（+<金额>b），减少的金额不是整千数\n"
                result_msg += "3. 例如：订单原金额10000，执行+9994b后，剩余金额为6\n"
            else:
                result_msg += "未找到尾数为6的订单，但总金额尾数是6\n"
                result_msg += "可能是多个订单的尾数累加导致的\n"

        # 如果消息太长，分段发送
        if len(result_msg) > 4000:
            # 发送第一部分
            await msg.edit_text(result_msg[:4000])
            # 发送剩余部分
            remaining = result_msg[4000:]
            while len(remaining) > 4000:
                await update.message.reply_text(remaining[:4000])
                remaining = remaining[4000:]
            if remaining:
                await update.message.reply_text(remaining)
        else:
            await msg.edit_text(result_msg)

    except Exception as e:
        logger.error(f"查找尾数订单时出错: {e}", exc_info=True)
        await update.message.reply_text(f"❌ 查找失败: {str(e)}")


@admin_required
@private_chat_only
async def list_employees(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """列出所有员工"""
    users = await db_operations.get_authorized_users()
    if not users:
        await update.message.reply_text("📋 暂无授权员工")
        return

    message = "📋 授权员工列表:\n\n"
    for uid in users:
        message += f"👤 `{uid}`\n"

    await update.message.reply_text(message, parse_mode='Markdown')
