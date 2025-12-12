"""初始化历史数据统计脚本

此脚本用于在系统更新后，统计所有历史记录并生成历史日切数据
"""
import asyncio
import sys
import os
from datetime import datetime, timedelta

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import db_operations
from utils.daily_report_generator import calculate_daily_summary

logger = None
try:
    import logging
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    logger = logging.getLogger(__name__)
except:
    pass


def log(message):
    """日志输出"""
    if logger:
        logger.info(message)
    else:
        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {message}")


def get_all_order_dates():
    """获取所有订单的日期范围"""
    # 获取最早的订单日期
    conn = db_operations.get_connection()
    cursor = conn.cursor()
    
    cursor.execute('SELECT MIN(date) as min_date, MAX(date) as max_date FROM orders')
    row = cursor.fetchone()
    min_date = row[0][:10] if row and row[0] else None
    max_date = row[1][:10] if row and row[1] else None
    conn.close()
    
    return min_date, max_date


def get_all_income_dates():
    """获取所有收入记录的日期范围"""
    conn = db_operations.get_connection()
    cursor = conn.cursor()
    
    cursor.execute('SELECT MIN(date) as min_date, MAX(date) as max_date FROM income_records')
    row = cursor.fetchone()
    min_date = row[0][:10] if row and row[0] else None
    max_date = row[1][:10] if row and row[1] else None
    conn.close()
    
    return min_date, max_date


async def process_historical_data():
    """处理所有历史数据"""
    log("=" * 60)
    log("开始初始化历史数据统计...")
    log("=" * 60)
    
    try:
        # 获取日期范围
        order_min_date, order_max_date = get_all_order_dates()
        income_min_date, income_max_date = get_all_income_dates()
        
        if not order_min_date and not income_min_date:
            log("❌ 未找到任何历史数据")
            return
        
        # 确定统计的日期范围
        dates = []
        if order_min_date:
            dates.append(order_min_date)
        if order_max_date:
            dates.append(order_max_date)
        if income_min_date:
            dates.append(income_min_date)
        if income_max_date:
            dates.append(income_max_date)
        
        if not dates:
            log("❌ 无法确定日期范围")
            return
        
        start_date = min(dates)
        end_date = max(dates)
        
        log(f"\n📅 数据日期范围: {start_date} 至 {end_date}")
        
        # 生成日期列表
        start = datetime.strptime(start_date, "%Y-%m-%d")
        end = datetime.strptime(end_date, "%Y-%m-%d")
        current = start
        
        date_list = []
        while current <= end:
            date_list.append(current.strftime("%Y-%m-%d"))
            current += timedelta(days=1)
        
        log(f"📊 需要处理 {len(date_list)} 天的数据")
        log("\n开始处理...")
        
        # 统计每天的数据
        processed_count = 0
        skipped_count = 0
        error_count = 0
        
        for i, date in enumerate(date_list, 1):
            try:
                # 检查是否已存在日切数据
                existing = await db_operations.get_daily_summary(date)
                if existing:
                    skipped_count += 1
                    if i % 50 == 0 or i == len(date_list):
                        log(f"进度: {i}/{len(date_list)} (已跳过: {skipped_count}, 已处理: {processed_count}, 错误: {error_count})")
                    continue
                
                # 计算日切数据
                summary = await calculate_daily_summary(date)
                
                # 保存日切数据
                await db_operations.save_daily_summary(date, summary)
                
                processed_count += 1
                
                # 每处理50天或最后一天时输出进度
                if i % 50 == 0 or i == len(date_list):
                    log(f"进度: {i}/{len(date_list)} (已跳过: {skipped_count}, 已处理: {processed_count}, 错误: {error_count})")
                    
            except Exception as e:
                error_count += 1
                log(f"❌ 处理日期 {date} 时出错: {e}")
                if logger:
                    logger.error(f"处理日期 {date} 时出错", exc_info=True)
        
        log("\n" + "=" * 60)
        log("历史数据统计完成！")
        log("=" * 60)
        log(f"✅ 总计: {len(date_list)} 天")
        log(f"✅ 已处理: {processed_count} 天")
        log(f"⏭️  已跳过: {skipped_count} 天（已有数据）")
        log(f"❌ 错误: {error_count} 天")
        
        # 统计汇总
        log("\n📊 数据汇总:")
        conn = db_operations.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT 
                COUNT(*) as total_days,
                COALESCE(SUM(new_orders_count), 0) as total_new_orders,
                COALESCE(SUM(new_orders_amount), 0) as total_new_amount,
                COALESCE(SUM(completed_orders_count), 0) as total_completed,
                COALESCE(SUM(completed_orders_amount), 0) as total_completed_amount,
                COALESCE(SUM(breach_end_orders_count), 0) as total_breach_end,
                COALESCE(SUM(breach_end_orders_amount), 0) as total_breach_end_amount,
                COALESCE(SUM(daily_interest), 0) as total_interest,
                COALESCE(SUM(company_expenses), 0) as total_company_expenses,
                COALESCE(SUM(other_expenses), 0) as total_other_expenses
            FROM daily_summary
        ''')
        
        row = cursor.fetchone()
        conn.close()
        
        if row:
            log(f"  总天数: {row[0] or 0}")
            log(f"  新增订单总数: {row[1] or 0} 个")
            log(f"  新增订单总金额: {row[2] or 0:,.2f}")
            log(f"  完结订单总数: {row[3] or 0} 个")
            log(f"  完结订单总金额: {row[4] or 0:,.2f}")
            log(f"  违约完成总数: {row[5] or 0} 个")
            log(f"  违约完成总金额: {row[6] or 0:,.2f}")
            log(f"  总利息收入: {row[7] or 0:,.2f}")
            log(f"  公司总开销: {row[8] or 0:,.2f}")
            log(f"  其他总开销: {row[9] or 0:,.2f}")
            total_expenses = (row[8] or 0) + (row[9] or 0)
            log(f"  总开销: {total_expenses:,.2f}")
        
    except Exception as e:
        log(f"\n❌ 处理历史数据时发生错误: {e}")
        if logger:
            logger.error("处理历史数据时发生错误", exc_info=True)


async def main():
    """主函数"""
    try:
        await process_historical_data()
    except KeyboardInterrupt:
        log("\n\n⚠️ 用户中断操作")
    except Exception as e:
        log(f"\n❌ 发生错误: {e}")
        if logger:
            logger.error("发生错误", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())

