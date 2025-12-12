import sqlite3
import os
import asyncio
import json
from datetime import datetime
import pytz
from typing import Optional, Dict, List, Tuple, Any
from functools import wraps

# 数据库文件路径
DATA_DIR = os.getenv('DATA_DIR', os.path.dirname(os.path.abspath(__file__)))
os.makedirs(DATA_DIR, exist_ok=True)
DB_NAME = os.path.join(DATA_DIR, 'loan_bot.db')


def get_connection():
    """获取数据库连接"""
    conn = sqlite3.connect(DB_NAME, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def db_transaction(func):
    """数据库事务装饰器"""
    @wraps(func)
    async def wrapper(*args, **kwargs):
        loop = asyncio.get_running_loop()

        def sync_work():
            conn = get_connection()
            cursor = conn.cursor()
            try:
                result = func(conn, cursor, *args, **kwargs)
                if result is not False:
                    conn.commit()
                return result
            except Exception as e:
                conn.rollback()
                print(f"Database error in {func.__name__}: {e}")
                return False
            finally:
                conn.close()

        return await loop.run_in_executor(None, sync_work)
    return wrapper


def db_query(func):
    """数据库查询装饰器"""
    @wraps(func)
    async def wrapper(*args, **kwargs):
        loop = asyncio.get_running_loop()

        def sync_work():
            conn = get_connection()
            cursor = conn.cursor()
            try:
                return func(conn, cursor, *args, **kwargs)
            except Exception as e:
                print(f"Database query error in {func.__name__}: {e}")
                raise e
            finally:
                conn.close()

        return await loop.run_in_executor(None, sync_work)
    return wrapper

# ========== 订单操作 ==========


@db_transaction
def create_order(conn, cursor, order_data: Dict) -> bool:
    """创建新订单"""
    try:
        cursor.execute('''
        INSERT INTO orders (
            order_id, group_id, chat_id, date, weekday_group,
            customer, amount, state
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            order_data['order_id'],
            order_data['group_id'],
            order_data['chat_id'],
            order_data['date'],
            order_data['group'],
            order_data['customer'],
            order_data['amount'],
            order_data['state']
        ))
        return True
    except sqlite3.IntegrityError as e:
        print(f"订单创建失败（重复）: {e}")
        return False


@db_query
def get_order_by_chat_id(conn, cursor, chat_id: int) -> Optional[Dict]:
    """根据chat_id获取订单"""
    cursor.execute('SELECT * FROM orders WHERE chat_id = ? AND state NOT IN (?, ?)',
                   (chat_id, 'end', 'breach_end'))
    row = cursor.fetchone()
    return dict(row) if row else None


@db_query
def get_order_by_order_id(conn, cursor, order_id: str) -> Optional[Dict]:
    """根据order_id获取订单"""
    cursor.execute('SELECT * FROM orders WHERE order_id = ?', (order_id,))
    row = cursor.fetchone()
    return dict(row) if row else None


@db_transaction
def update_order_amount(conn, cursor, chat_id: int, new_amount: float) -> bool:
    """更新订单金额"""
    cursor.execute('''
    UPDATE orders 
    SET amount = ?, updated_at = CURRENT_TIMESTAMP
    WHERE chat_id = ? AND state NOT IN (?, ?)
    ''', (new_amount, chat_id, 'end', 'breach_end'))
    return cursor.rowcount > 0


@db_transaction
def update_order_state(conn, cursor, chat_id: int, new_state: str) -> bool:
    """更新订单状态"""
    cursor.execute('''
    UPDATE orders 
    SET state = ?, updated_at = CURRENT_TIMESTAMP
    WHERE chat_id = ? AND state NOT IN (?, ?)
    ''', (new_state, chat_id, 'end', 'breach_end'))
    return cursor.rowcount > 0


@db_transaction
def update_order_group_id(conn, cursor, chat_id: int, new_group_id: str) -> bool:
    """更新订单归属ID"""
    cursor.execute('''
    UPDATE orders 
    SET group_id = ?, updated_at = CURRENT_TIMESTAMP
    WHERE chat_id = ?
    ''', (new_group_id, chat_id))
    return cursor.rowcount > 0


@db_transaction
def update_order_weekday_group(conn, cursor, chat_id: int, new_weekday_group: str) -> bool:
    """更新订单星期分组"""
    cursor.execute('''
    UPDATE orders 
    SET weekday_group = ?, updated_at = CURRENT_TIMESTAMP
    WHERE chat_id = ?
    ''', (new_weekday_group, chat_id))
    return cursor.rowcount > 0


@db_transaction
def delete_order_by_chat_id(conn, cursor, chat_id: int) -> bool:
    """删除订单（用于撤销订单创建）"""
    cursor.execute('DELETE FROM orders WHERE chat_id = ?', (chat_id,))
    return cursor.rowcount > 0


@db_transaction
def delete_order_by_order_id(conn, cursor, order_id: str) -> bool:
    """根据订单ID删除订单"""
    cursor.execute('DELETE FROM orders WHERE order_id = ?', (order_id,))
    return cursor.rowcount > 0

# ========== 查找功能 ==========


@db_query
def search_orders_by_group_id(conn, cursor, group_id: str, state: Optional[str] = None) -> List[Dict]:
    """根据归属ID查找订单"""
    if state:
        cursor.execute('SELECT * FROM orders WHERE group_id = ? AND state = ? ORDER BY date DESC',
                       (group_id, state))
    else:
        # 默认排除完成和违约完成的订单
        cursor.execute(
            "SELECT * FROM orders WHERE group_id = ? AND state NOT IN ('end', 'breach_end') ORDER BY date DESC", (group_id,))
    rows = cursor.fetchall()
    return [dict(row) for row in rows]


@db_query
def search_orders_by_date_range(conn, cursor, start_date: str, end_date: str) -> List[Dict]:
    """根据日期范围查找订单"""
    cursor.execute('''
    SELECT * FROM orders 
    WHERE date >= ? AND date <= ?
    ORDER BY date DESC
    ''', (start_date, end_date))
    rows = cursor.fetchall()
    return [dict(row) for row in rows]


@db_query
def search_orders_by_customer(conn, cursor, customer: str) -> List[Dict]:
    """根据客户类型查找订单"""
    cursor.execute(
        'SELECT * FROM orders WHERE customer = ? ORDER BY date DESC', (customer.upper(),))
    rows = cursor.fetchall()
    return [dict(row) for row in rows]


@db_query
def search_orders_by_state(conn, cursor, state: str) -> List[Dict]:
    """根据状态查找订单"""
    cursor.execute(
        'SELECT * FROM orders WHERE state = ? ORDER BY date DESC', (state,))
    rows = cursor.fetchall()
    return [dict(row) for row in rows]


@db_query
def search_orders_all(conn, cursor) -> List[Dict]:
    """查找所有订单"""
    cursor.execute('SELECT * FROM orders ORDER BY date DESC')
    rows = cursor.fetchall()
    return [dict(row) for row in rows]


@db_query
def search_orders_advanced(conn, cursor, criteria: Dict) -> List[Dict]:
    """
    高级查找订单（支持混合条件）
    """
    query = "SELECT * FROM orders WHERE 1=1"
    params = []

    if 'group_id' in criteria and criteria['group_id']:
        query += " AND group_id = ?"
        params.append(criteria['group_id'])

    if 'state' in criteria and criteria['state']:
        query += " AND state = ?"
        params.append(criteria['state'])
    else:
        # 默认只查找有效订单（normal和overdue状态）
        query += " AND state IN ('normal', 'overdue')"

    if 'customer' in criteria and criteria['customer']:
        query += " AND customer = ?"
        params.append(criteria['customer'])

    if 'order_id' in criteria and criteria['order_id']:
        query += " AND order_id = ?"
        params.append(criteria['order_id'])

    if 'date_range' in criteria and criteria['date_range']:
        start_date, end_date = criteria['date_range']
        query += " AND date >= ? AND date <= ?"
        params.extend([start_date, end_date])

    if 'weekday_group' in criteria and criteria['weekday_group']:
        query += " AND weekday_group = ?"
        params.append(criteria['weekday_group'])

    query += " ORDER BY date DESC"

    cursor.execute(query, params)
    rows = cursor.fetchall()
    return [dict(row) for row in rows]


@db_query
def search_orders_advanced_all_states(conn, cursor, criteria: Dict) -> List[Dict]:
    """
    高级查找订单（支持混合条件，包含所有状态的订单）
    用于报表查找功能
    """
    query = "SELECT * FROM orders WHERE 1=1"
    params = []

    if 'group_id' in criteria and criteria['group_id']:
        query += " AND group_id = ?"
        params.append(criteria['group_id'])

    if 'state' in criteria and criteria['state']:
        query += " AND state = ?"
        params.append(criteria['state'])

    if 'customer' in criteria and criteria['customer']:
        query += " AND customer = ?"
        params.append(criteria['customer'])

    if 'order_id' in criteria and criteria['order_id']:
        query += " AND order_id = ?"
        params.append(criteria['order_id'])

    if 'date_range' in criteria and criteria['date_range']:
        start_date, end_date = criteria['date_range']
        query += " AND date >= ? AND date <= ?"
        params.extend([start_date, end_date])

    if 'weekday_group' in criteria and criteria['weekday_group']:
        query += " AND weekday_group = ?"
        params.append(criteria['weekday_group'])

    query += " ORDER BY date DESC"

    cursor.execute(query, params)
    rows = cursor.fetchall()
    return [dict(row) for row in rows]

# ========== 财务数据操作 ==========


@db_query
def get_financial_data(conn, cursor) -> Dict:
    """获取全局财务数据"""
    cursor.execute('SELECT * FROM financial_data ORDER BY id DESC LIMIT 1')
    row = cursor.fetchone()
    if row:
        return dict(row)
    return {
        'valid_orders': 0,
        'valid_amount': 0,
        'liquid_funds': 0,
        'new_clients': 0,
        'new_clients_amount': 0,
        'old_clients': 0,
        'old_clients_amount': 0,
        'interest': 0,
        'completed_orders': 0,
        'completed_amount': 0,
        'breach_orders': 0,
        'breach_amount': 0,
        'breach_end_orders': 0,
        'breach_end_amount': 0
    }


@db_transaction
def update_financial_data(conn, cursor, field: str, amount: float) -> bool:
    """更新财务数据字段"""
    cursor.execute('SELECT * FROM financial_data ORDER BY id DESC LIMIT 1')
    row = cursor.fetchone()
    if not row:
        cursor.execute('''
        INSERT INTO financial_data (
            valid_orders, valid_amount, liquid_funds,
            new_clients, new_clients_amount,
            old_clients, old_clients_amount,
            interest, completed_orders, completed_amount,
            breach_orders, breach_amount,
            breach_end_orders, breach_end_amount
        ) VALUES (0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0)
        ''')
        current_value = 0
    else:
        row_dict = dict(row)
        current_value = row_dict.get(field, 0)

    new_value = current_value + amount
    cursor.execute(f'''
    UPDATE financial_data 
    SET "{field}" = ?, updated_at = CURRENT_TIMESTAMP
    WHERE id = (SELECT id FROM financial_data ORDER BY id DESC LIMIT 1)
    ''', (new_value,))
    return True

# ========== 分组数据操作 ==========


@db_query
def get_grouped_data(conn, cursor, group_id: Optional[str] = None) -> Dict:
    """获取分组数据"""
    if group_id:
        cursor.execute(
            'SELECT * FROM grouped_data WHERE group_id = ?', (group_id,))
        row = cursor.fetchone()
        if row:
            return dict(row)
        return {
            'group_id': group_id,
            'valid_orders': 0,
            'valid_amount': 0,
            'liquid_funds': 0,
            'new_clients': 0,
            'new_clients_amount': 0,
            'old_clients': 0,
            'old_clients_amount': 0,
            'interest': 0,
            'completed_orders': 0,
            'completed_amount': 0,
            'breach_orders': 0,
            'breach_amount': 0,
            'breach_end_orders': 0,
            'breach_end_amount': 0
        }
    else:
        # 获取所有分组数据
        cursor.execute('SELECT * FROM grouped_data')
        rows = cursor.fetchall()
        result = {}
        for row in rows:
            result[row['group_id']] = dict(row)
        return result


@db_transaction
def update_grouped_data(conn, cursor, group_id: str, field: str, amount: float) -> bool:
    """更新分组数据字段"""
    cursor.execute(
        'SELECT * FROM grouped_data WHERE group_id = ?', (group_id,))
    row = cursor.fetchone()

    if not row:
        cursor.execute('''
        INSERT INTO grouped_data (
            group_id, valid_orders, valid_amount, liquid_funds,
            new_clients, new_clients_amount,
            old_clients, old_clients_amount,
            interest, completed_orders, completed_amount,
            breach_orders, breach_amount,
            breach_end_orders, breach_end_amount
        ) VALUES (?, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0)
        ''', (group_id,))
        current_value = 0
    else:
        row_dict = dict(row)
        current_value = row_dict.get(field, 0)

    new_value = current_value + amount
    cursor.execute(f'''
    UPDATE grouped_data 
    SET "{field}" = ?, updated_at = CURRENT_TIMESTAMP
    WHERE group_id = ?
    ''', (new_value, group_id))
    return True


@db_query
def get_all_group_ids(conn, cursor) -> List[str]:
    """获取所有归属ID列表"""
    cursor.execute(
        'SELECT DISTINCT group_id FROM grouped_data ORDER BY group_id')
    rows = cursor.fetchall()
    return [row[0] for row in rows]

# ========== 日结数据操作 ==========


@db_query
def get_daily_data(conn, cursor, date: str, group_id: Optional[str] = None) -> Dict:
    """获取日结数据"""
    if group_id:
        cursor.execute(
            'SELECT * FROM daily_data WHERE date = ? AND group_id = ?', (date, group_id))
    else:
        # 全局日结数据（group_id为NULL）
        cursor.execute(
            'SELECT * FROM daily_data WHERE date = ? AND group_id IS NULL', (date,))

    row = cursor.fetchone()
    if row:
        return dict(row)

    return {
        'new_clients': 0,
        'new_clients_amount': 0,
        'old_clients': 0,
        'old_clients_amount': 0,
        'interest': 0,
        'completed_orders': 0,
        'completed_amount': 0,
        'breach_orders': 0,
        'breach_amount': 0,
        'breach_end_orders': 0,
        'breach_end_amount': 0,
        'liquid_flow': 0,
        'company_expenses': 0,
        'other_expenses': 0
    }


@db_transaction
def update_daily_data(conn, cursor, date: str, field: str, amount: float, group_id: Optional[str] = None) -> bool:
    """更新日结数据字段"""
    if group_id:
        cursor.execute(
            'SELECT * FROM daily_data WHERE date = ? AND group_id = ?', (date, group_id))
    else:
        cursor.execute(
            'SELECT * FROM daily_data WHERE date = ? AND group_id IS NULL', (date,))

    row = cursor.fetchone()

    if not row:
        cursor.execute('''
        INSERT INTO daily_data (
            date, group_id, new_clients, new_clients_amount,
            old_clients, old_clients_amount,
            interest, completed_orders, completed_amount,
            breach_orders, breach_amount,
            breach_end_orders, breach_end_amount,
            liquid_flow, company_expenses, other_expenses
        ) VALUES (?, ?, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0)
        ''', (date, group_id))
        current_value = 0
    else:
        row_dict = dict(row)
        current_value = row_dict.get(field, 0)

    new_value = current_value + amount
    if group_id:
        cursor.execute(f'''
        UPDATE daily_data 
        SET "{field}" = ?, updated_at = CURRENT_TIMESTAMP
        WHERE date = ? AND group_id = ?
        ''', (new_value, date, group_id))
    else:
        cursor.execute(f'''
        UPDATE daily_data 
        SET "{field}" = ?, updated_at = CURRENT_TIMESTAMP
        WHERE date = ? AND group_id IS NULL
        ''', (new_value, date))

    return True


@db_query
def get_stats_by_date_range(conn, cursor, start_date: str, end_date: str, group_id: Optional[str] = None) -> Dict:
    """根据日期范围聚合统计数据"""
    where_clause = "date >= ? AND date <= ?"
    params = [start_date, end_date]

    if group_id:
        where_clause += " AND group_id = ?"
        params.append(group_id)
    else:
        where_clause += " AND group_id IS NULL"

    cursor.execute(f'''
    SELECT 
        SUM(new_clients) as new_clients,
        SUM(new_clients_amount) as new_clients_amount,
        SUM(old_clients) as old_clients,
        SUM(old_clients_amount) as old_clients_amount,
        SUM(interest) as interest,
        SUM(completed_orders) as completed_orders,
        SUM(completed_amount) as completed_amount,
        SUM(breach_orders) as breach_orders,
        SUM(breach_amount) as breach_amount,
        SUM(breach_end_orders) as breach_end_orders,
        SUM(breach_end_amount) as breach_end_amount,
        SUM(liquid_flow) as liquid_flow,
        SUM(company_expenses) as company_expenses,
        SUM(other_expenses) as other_expenses
    FROM daily_data 
    WHERE {where_clause}
    ''', params)

    row = cursor.fetchone()

    result = {}
    keys = [
        'new_clients', 'new_clients_amount',
        'old_clients', 'old_clients_amount',
        'interest',
        'completed_orders', 'completed_amount',
        'breach_orders', 'breach_amount',
        'breach_end_orders', 'breach_end_amount',
        'liquid_flow', 'company_expenses', 'other_expenses'
    ]

    for i, key in enumerate(keys):
        result[key] = row[i] if row[i] is not None else 0

    return result

# ========== 授权用户操作 ==========


@db_transaction
def add_authorized_user(conn, cursor, user_id: int) -> bool:
    """添加授权用户"""
    cursor.execute(
        'INSERT OR IGNORE INTO authorized_users (user_id) VALUES (?)', (user_id,))
    return True


@db_transaction
def remove_authorized_user(conn, cursor, user_id: int) -> bool:
    """移除授权用户"""
    cursor.execute(
        'DELETE FROM authorized_users WHERE user_id = ?', (user_id,))
    return True


@db_query
def get_authorized_users(conn, cursor) -> List[int]:
    """获取所有授权用户ID"""
    cursor.execute('SELECT user_id FROM authorized_users')
    rows = cursor.fetchall()
    return [row[0] for row in rows]


@db_query
def is_user_authorized(conn, cursor, user_id: int) -> bool:
    """检查用户是否授权"""
    cursor.execute(
        'SELECT 1 FROM authorized_users WHERE user_id = ?', (user_id,))
    return cursor.fetchone() is not None

# ========== 用户归属ID映射操作 ==========


@db_query
def get_user_group_id(conn, cursor, user_id: int) -> Optional[str]:
    """获取用户有权限查看的归属ID"""
    cursor.execute(
        'SELECT group_id FROM user_group_mapping WHERE user_id = ?', (user_id,))
    row = cursor.fetchone()
    return row[0] if row else None


@db_transaction
def set_user_group_id(conn, cursor, user_id: int, group_id: str) -> bool:
    """设置用户有权限查看的归属ID"""
    cursor.execute('''
    INSERT OR REPLACE INTO user_group_mapping (user_id, group_id, updated_at)
    VALUES (?, ?, CURRENT_TIMESTAMP)
    ''', (user_id, group_id))
    return True


@db_transaction
def remove_user_group_id(conn, cursor, user_id: int) -> bool:
    """移除用户的归属ID映射"""
    cursor.execute(
        'DELETE FROM user_group_mapping WHERE user_id = ?', (user_id,))
    return cursor.rowcount > 0


@db_query
def get_all_user_group_mappings(conn, cursor) -> List[Dict]:
    """获取所有用户归属ID映射"""
    cursor.execute('''
    SELECT user_id, group_id, created_at, updated_at
    FROM user_group_mapping
    ORDER BY user_id
    ''')
    rows = cursor.fetchall()
    return [dict(row) for row in rows]

# ========== 支付账号操作 ==========


@db_query
def get_payment_account(conn, cursor, account_type: str) -> Optional[Dict]:
    """获取支付账号信息"""
    cursor.execute(
        'SELECT * FROM payment_accounts WHERE account_type = ?', (account_type,))
    row = cursor.fetchone()
    if row:
        return dict(row)
    return None


@db_query
def get_all_payment_accounts(conn, cursor) -> List[Dict]:
    """获取所有支付账号信息"""
    cursor.execute(
        'SELECT * FROM payment_accounts ORDER BY account_type, account_name')
    rows = cursor.fetchall()
    return [dict(row) for row in rows]


@db_query
def get_payment_accounts_by_type(conn, cursor, account_type: str) -> List[Dict]:
    """获取指定类型的所有支付账号信息"""
    cursor.execute(
        'SELECT * FROM payment_accounts WHERE account_type = ? ORDER BY account_name',
        (account_type,))
    rows = cursor.fetchall()
    return [dict(row) for row in rows]


@db_query
def get_payment_account_by_id(conn, cursor, account_id: int) -> Optional[Dict]:
    """根据ID获取支付账号信息"""
    cursor.execute(
        'SELECT * FROM payment_accounts WHERE id = ?', (account_id,))
    row = cursor.fetchone()
    if row:
        return dict(row)
    return None


@db_transaction
def create_payment_account(conn, cursor, account_type: str, account_number: str,
                           account_name: str = '', balance: float = 0) -> int:
    """创建新的支付账号，返回账户ID"""
    cursor.execute('''
    INSERT INTO payment_accounts (account_type, account_number, account_name, balance)
    VALUES (?, ?, ?, ?)
    ''', (account_type, account_number, account_name or '', balance or 0))
    return cursor.lastrowid


@db_transaction
def update_payment_account_by_id(conn, cursor, account_id: int, account_number: str = None,
                                 account_name: str = None, balance: float = None) -> bool:
    """根据ID更新支付账号信息"""
    updates = []
    params = []

    if account_number is not None:
        updates.append('account_number = ?')
        params.append(account_number)

    if account_name is not None:
        updates.append('account_name = ?')
        params.append(account_name)

    if balance is not None:
        updates.append('balance = ?')
        params.append(balance)

    if not updates:
        return False

    updates.append('updated_at = CURRENT_TIMESTAMP')
    params.append(account_id)

    set_clause = ", ".join(updates)
    query = f'UPDATE payment_accounts SET {set_clause} WHERE id = ?'
    try:
        cursor.execute(query, params)
        # 事务的commit由@db_transaction装饰器处理
        return cursor.rowcount > 0
    except Exception as e:
        print(f"更新支付账号时出错: {e}")
        return False


@db_transaction
def delete_payment_account(conn, cursor, account_id: int) -> bool:
    """删除支付账号"""
    cursor.execute('DELETE FROM payment_accounts WHERE id = ?', (account_id,))
    return cursor.rowcount > 0


@db_transaction
def update_payment_account(conn, cursor, account_type: str, account_number: str = None,
                           account_name: str = None, balance: float = None) -> bool:
    """更新支付账号信息（兼容旧代码，更新该类型的第一个账户）"""
    cursor.execute(
        'SELECT * FROM payment_accounts WHERE account_type = ? LIMIT 1', (account_type,))
    row = cursor.fetchone()

    if row:
        # 更新现有记录
        account_id = row['id']
        return update_payment_account_by_id(conn, cursor, account_id,
                                            account_number, account_name, balance)
    else:
        # 创建新记录
        if account_number:
            create_payment_account(conn, cursor, account_type, account_number,
                                   account_name or '', balance or 0)
            return True
        return False


@db_transaction
def record_expense(conn, cursor, date: str, type: str, amount: float, note: str) -> int:
    """记录开销，返回开销记录ID"""
    cursor.execute('''
    INSERT INTO expense_records (date, type, amount, note)
    VALUES (?, ?, ?, ?)
    ''', (date, type, amount, note))
    expense_id = cursor.lastrowid

    field = 'company_expenses' if type == 'company' else 'other_expenses'

    cursor.execute(
        'SELECT * FROM daily_data WHERE date = ? AND group_id IS NULL', (date,))
    row = cursor.fetchone()

    if not row:
        cursor.execute('''
        INSERT INTO daily_data (
            date, group_id, new_clients, new_clients_amount,
            old_clients, old_clients_amount,
            interest, completed_orders, completed_amount,
            breach_orders, breach_amount,
            breach_end_orders, breach_end_amount,
            liquid_flow, company_expenses, other_expenses
        ) VALUES (?, NULL, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, ?, ?)
        ''', (date, amount if field == 'company_expenses' else 0, amount if field == 'other_expenses' else 0))
    else:
        cursor.execute(f'''
        UPDATE daily_data 
        SET "{field}" = "{field}" + ?, updated_at = CURRENT_TIMESTAMP
        WHERE date = ? AND group_id IS NULL
        ''', (amount, date))

    cursor.execute('SELECT * FROM financial_data ORDER BY id DESC LIMIT 1')
    row = cursor.fetchone()
    if not row:
        cursor.execute('''
        INSERT INTO financial_data (
            valid_orders, valid_amount, liquid_funds,
            new_clients, new_clients_amount,
            old_clients, old_clients_amount,
            interest, completed_orders, completed_amount,
            breach_orders, breach_amount,
            breach_end_orders, breach_end_amount
        ) VALUES (0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0)
        ''')
        current_value = 0
    else:
        row_dict = dict(row)
        current_value = row_dict.get('liquid_funds', 0)

    new_value = current_value - amount

    cursor.execute('''
    UPDATE financial_data 
    SET "liquid_funds" = ?, updated_at = CURRENT_TIMESTAMP
    WHERE id = (SELECT id FROM financial_data ORDER BY id DESC LIMIT 1)
    ''', (new_value,))

    cursor.execute(
        'SELECT * FROM daily_data WHERE date = ? AND group_id IS NULL', (date,))
    daily_row = cursor.fetchone()

    if not daily_row:
        cursor.execute('''
        INSERT INTO daily_data (
            date, group_id, new_clients, new_clients_amount,
            old_clients, old_clients_amount,
            interest, completed_orders, completed_amount,
            breach_orders, breach_amount,
            breach_end_orders, breach_end_amount,
            liquid_flow, company_expenses, other_expenses
        ) VALUES (?, NULL, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, ?, ?, ?)
        ''', (date, -amount, amount if field == 'company_expenses' else 0, amount if field == 'other_expenses' else 0))
    else:
        cursor.execute('''
        UPDATE daily_data 
        SET "liquid_flow" = "liquid_flow" - ?, updated_at = CURRENT_TIMESTAMP
        WHERE date = ? AND group_id IS NULL
        ''', (amount, date))

    return expense_id


@db_query
def get_expense_records(conn, cursor, start_date: str, end_date: str = None, type: Optional[str] = None) -> List[Dict]:
    """获取开销记录（支持日期范围）"""
    query = "SELECT * FROM expense_records WHERE date >= ?"
    params = [start_date]

    if end_date:
        query += " AND date <= ?"
        params.append(end_date)
    else:
        query += " AND date <= ?"
        params.append(start_date)

    if type:
        query += " AND type = ?"
        params.append(type)

    query += " ORDER BY date DESC, created_at ASC"

    cursor.execute(query, params)
    rows = cursor.fetchall()
    return [dict(row) for row in rows]


@db_transaction
def delete_expense_record(conn, cursor, expense_id: int) -> bool:
    """删除开销记录"""
    cursor.execute('DELETE FROM expense_records WHERE id = ?', (expense_id,))
    return cursor.rowcount > 0

# ========== 定时播报操作 ==========


@db_query
def get_scheduled_broadcast(conn, cursor, slot: int) -> Optional[Dict]:
    """获取指定槽位的定时播报"""
    cursor.execute(
        'SELECT * FROM scheduled_broadcasts WHERE slot = ?', (slot,))
    row = cursor.fetchone()
    return dict(row) if row else None


@db_query
def get_all_scheduled_broadcasts(conn, cursor) -> List[Dict]:
    """获取所有定时播报"""
    cursor.execute('SELECT * FROM scheduled_broadcasts ORDER BY slot')
    rows = cursor.fetchall()
    return [dict(row) for row in rows]


@db_query
def get_active_scheduled_broadcasts(conn, cursor) -> List[Dict]:
    """获取所有激活的定时播报"""
    cursor.execute(
        'SELECT * FROM scheduled_broadcasts WHERE is_active = 1 ORDER BY slot')
    rows = cursor.fetchall()
    return [dict(row) for row in rows]


@db_transaction
def create_or_update_scheduled_broadcast(conn, cursor, slot: int, time: str,
                                         chat_id: Optional[int], chat_title: Optional[str],
                                         message: str, is_active: int = 1) -> bool:
    """创建或更新定时播报"""
    cursor.execute(
        'SELECT * FROM scheduled_broadcasts WHERE slot = ?', (slot,))
    row = cursor.fetchone()

    if row:
        # 更新现有记录
        cursor.execute('''
        UPDATE scheduled_broadcasts 
        SET time = ?, chat_id = ?, chat_title = ?, message = ?, 
            is_active = ?, updated_at = CURRENT_TIMESTAMP
        WHERE slot = ?
        ''', (time, chat_id, chat_title, message, is_active, slot))
    else:
        # 创建新记录
        cursor.execute('''
        INSERT INTO scheduled_broadcasts (slot, time, chat_id, chat_title, message, is_active)
        VALUES (?, ?, ?, ?, ?, ?)
        ''', (slot, time, chat_id, chat_title, message, is_active))

    return True


@db_transaction
def delete_scheduled_broadcast(conn, cursor, slot: int) -> bool:
    """删除定时播报"""
    cursor.execute('DELETE FROM scheduled_broadcasts WHERE slot = ?', (slot,))
    return cursor.rowcount > 0


@db_transaction
def toggle_scheduled_broadcast(conn, cursor, slot: int, is_active: int) -> bool:
    """切换定时播报的激活状态"""
    cursor.execute('''
    UPDATE scheduled_broadcasts 
    SET is_active = ?, updated_at = CURRENT_TIMESTAMP
    WHERE slot = ?
    ''', (is_active, slot))
    return cursor.rowcount > 0

# ========== 收入明细操作 ==========


@db_transaction
def record_income(conn, cursor, date: str, type: str, amount: float,
                  group_id: Optional[str] = None, order_id: Optional[str] = None,
                  order_date: Optional[str] = None, customer: Optional[str] = None,
                  weekday_group: Optional[str] = None, note: Optional[str] = None,
                  created_by: Optional[int] = None) -> bool:
    """记录收入明细"""
    # 使用北京时间作为 created_at
    tz_beijing = pytz.timezone('Asia/Shanghai')
    created_at = datetime.now(tz_beijing).strftime('%Y-%m-%d %H:%M:%S')

    cursor.execute('''
    INSERT INTO income_records (
        date, type, amount, group_id, order_id, order_date,
        customer, weekday_group, note, created_by, created_at
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (date, type, amount, group_id, order_id, order_date, customer, weekday_group, note, created_by, created_at))
    return True


@db_query
def get_income_records(conn, cursor, start_date: str, end_date: str = None,
                       type: Optional[str] = None, customer: Optional[str] = None,
                       group_id: Optional[str] = None, order_id: Optional[str] = None) -> List[Dict]:
    """获取收入明细（支持多维度过滤）"""
    query = "SELECT * FROM income_records WHERE date >= ?"
    params = [start_date]

    if end_date:
        query += " AND date <= ?"
        params.append(end_date)
    else:
        query += " AND date <= ?"
        params.append(start_date)

    if type:
        query += " AND type = ?"
        params.append(type)

    if customer:
        query += " AND customer = ?"
        params.append(customer)

    if group_id:
        query += " AND group_id = ?"
        params.append(group_id)

    if order_id:
        query += " AND order_id = ?"
        params.append(order_id)

    query += " ORDER BY date DESC, created_at DESC"

    cursor.execute(query, params)
    rows = cursor.fetchall()
    return [dict(row) for row in rows]


@db_query
def get_interest_by_order_id(conn, cursor, order_id: str) -> Dict:
    """获取指定订单的所有利息收入汇总"""
    cursor.execute('''
    SELECT 
        COUNT(*) as count,
        SUM(amount) as total_amount,
        MIN(date) as first_date,
        MAX(date) as last_date
    FROM income_records 
    WHERE order_id = ? AND type = 'interest'
    ''', (order_id,))

    row = cursor.fetchone()
    if row and row[0] > 0:
        return {
            'count': row[0],
            'total_amount': row[1] or 0.0,
            'first_date': row[2],
            'last_date': row[3]
        }
    return {
        'count': 0,
        'total_amount': 0.0,
        'first_date': None,
        'last_date': None
    }


@db_query
def get_all_interest_by_order_id(conn, cursor, order_id: str) -> List[Dict]:
    """获取指定订单的所有利息收入明细"""
    cursor.execute('''
    SELECT * FROM income_records 
    WHERE order_id = ? AND type = 'interest'
    ORDER BY date ASC, created_at ASC
    ''', (order_id,))

    rows = cursor.fetchall()
    return [dict(row) for row in rows]


@db_query
def get_all_valid_orders(conn, cursor) -> List[Dict]:
    """获取所有有效订单（normal和overdue状态）"""
    cursor.execute('''
    SELECT * FROM orders 
    WHERE state IN ('normal', 'overdue')
    ORDER BY date DESC, order_id DESC
    ''')
    rows = cursor.fetchall()
    return [dict(row) for row in rows]


@db_query
def get_completed_orders_by_date(conn, cursor, date: str) -> List[Dict]:
    """获取指定日期完成的订单（通过updated_at判断）"""
    cursor.execute('''
    SELECT * FROM orders 
    WHERE state = 'end' 
    AND updated_at >= ? AND updated_at < ?
    ORDER BY updated_at DESC
    ''', (f"{date} 00:00:00", f"{date} 23:59:59"))
    rows = cursor.fetchall()
    return [dict(row) for row in rows]


@db_query
def get_breach_end_orders_by_date(conn, cursor, date: str) -> List[Dict]:
    """获取指定日期违约完成且有变动的订单（通过updated_at判断）"""
    cursor.execute('''
    SELECT * FROM orders 
    WHERE state = 'breach_end' 
    AND updated_at >= ? AND updated_at < ?
    ORDER BY updated_at DESC
    ''', (f"{date} 00:00:00", f"{date} 23:59:59"))
    rows = cursor.fetchall()
    return [dict(row) for row in rows]


@db_query
def get_new_orders_by_date(conn, cursor, date: str) -> List[Dict]:
    """获取指定日期新增的订单（通过created_at判断）"""
    cursor.execute('''
    SELECT * FROM orders 
    WHERE created_at >= ? AND created_at < ?
    ORDER BY created_at DESC
    ''', (f"{date} 00:00:00", f"{date} 23:59:59"))
    rows = cursor.fetchall()
    return [dict(row) for row in rows]


@db_query
def get_daily_interest_total(conn, cursor, date: str) -> float:
    """获取指定日期的利息收入总额"""
    cursor.execute('''
    SELECT COALESCE(SUM(amount), 0) as total
    FROM income_records 
    WHERE date = ? AND type = 'interest'
    ''', (date,))
    row = cursor.fetchone()
    return float(row[0]) if row and row[0] else 0.0


@db_query
def get_daily_expenses(conn, cursor, date: str) -> Dict:
    """获取指定日期的开销（公司开销+其他开销）"""
    cursor.execute('''
    SELECT 
        type,
        COALESCE(SUM(amount), 0) as total
    FROM expense_records 
    WHERE date = ?
    GROUP BY type
    ''', (date,))
    rows = cursor.fetchall()
    
    result = {
        'company_expenses': 0.0,
        'other_expenses': 0.0,
        'total': 0.0
    }
    
    for row in rows:
        expense_type = row[0]
        amount = float(row[1]) if row[1] else 0.0
        if expense_type == 'company':
            result['company_expenses'] = amount
        elif expense_type == 'other':
            result['other_expenses'] = amount
        result['total'] += amount
    
    return result


@db_query
def get_daily_summary(conn, cursor, date: str) -> Optional[Dict]:
    """获取指定日期的日切数据"""
    cursor.execute('''
    SELECT * FROM daily_summary 
    WHERE date = ?
    ''', (date,))
    row = cursor.fetchone()
    if row:
        return dict(row)
    return None


@db_transaction
def save_daily_summary(conn, cursor, date: str, data: Dict) -> bool:
    """保存日切数据"""
    try:
        cursor.execute('''
        INSERT OR REPLACE INTO daily_summary (
            date, new_orders_count, new_orders_amount,
            completed_orders_count, completed_orders_amount,
            breach_end_orders_count, breach_end_orders_amount,
            daily_interest, company_expenses, other_expenses,
            created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            date,
            data.get('new_orders_count', 0),
            data.get('new_orders_amount', 0.0),
            data.get('completed_orders_count', 0),
            data.get('completed_orders_amount', 0.0),
            data.get('breach_end_orders_count', 0),
            data.get('breach_end_orders_amount', 0.0),
            data.get('daily_interest', 0.0),
            data.get('company_expenses', 0.0),
            data.get('other_expenses', 0.0),
            datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        ))
        conn.commit()
        return True
    except Exception as e:
        conn.rollback()
        raise e


@db_query
def get_customer_total_contribution(conn, cursor, customer: str, start_date: str = None, end_date: str = None) -> Dict:
    """获取指定客户的总贡献（跨所有订单周期）

    参数:
        customer: 客户类型（'A'=新客户，'B'=老客户）
        start_date: 起始日期（可选，如果提供则只统计该日期之后的数据）
        end_date: 结束日期（可选，如果提供则只统计该日期之前的数据）

    返回:
        {
            'total_interest': 总利息收入,
            'total_completed': 总完成订单金额,
            'total_breach_end': 总违约完成金额,
            'total_principal_reduction': 总本金减少,
            'total_amount': 总贡献金额,
            'order_count': 订单数量,
            'interest_count': 利息收取次数,
            'first_order_date': 首次订单日期,
            'last_order_date': 最后订单日期
        }
    """
    # 构建基础查询条件
    income_conditions = ["customer = ?"]
    income_params = [customer.upper()]

    order_conditions = ["customer = ?"]
    order_params = [customer.upper()]

    if start_date:
        income_conditions.append("date >= ?")
        income_params.append(start_date)
        order_conditions.append("date >= ?")
        order_params.append(start_date)

    if end_date:
        income_conditions.append("date <= ?")
        income_params.append(end_date)
        order_conditions.append("date <= ?")
        order_params.append(end_date)

    income_where = " AND ".join(income_conditions)
    order_where = " AND ".join(order_conditions)

    # 查询收入汇总
    cursor.execute(f'''
    SELECT 
        type,
        COUNT(*) as count,
        SUM(amount) as total_amount
    FROM income_records 
    WHERE {income_where}
    GROUP BY type
    ''', income_params)

    income_rows = cursor.fetchall()

    # 初始化结果
    result = {
        'total_interest': 0.0,
        'total_completed': 0.0,
        'total_breach_end': 0.0,
        'total_principal_reduction': 0.0,
        'total_amount': 0.0,
        'interest_count': 0,
        'order_count': 0,
        'first_order_date': None,
        'last_order_date': None
    }

    # 处理收入数据
    for row in income_rows:
        income_type = row[0]
        count = row[1]
        amount = row[2] or 0.0

        if income_type == 'interest':
            result['total_interest'] = amount
            result['interest_count'] = count
        elif income_type == 'completed':
            result['total_completed'] = amount
        elif income_type == 'breach_end':
            result['total_breach_end'] = amount
        elif income_type == 'principal_reduction':
            result['total_principal_reduction'] = amount

        result['total_amount'] += amount

    # 查询订单统计
    cursor.execute(f'''
    SELECT 
        COUNT(*) as order_count,
        MIN(date) as first_date,
        MAX(date) as last_date
    FROM orders 
    WHERE {order_where}
    ''', order_params)

    order_row = cursor.fetchone()
    if order_row:
        result['order_count'] = order_row[0] or 0
        result['first_order_date'] = order_row[1]
        result['last_order_date'] = order_row[2]

    return result


@db_query
def get_customer_orders_summary(conn, cursor, customer: str, start_date: str = None, end_date: str = None) -> List[Dict]:
    """获取指定客户的所有订单及每笔订单的贡献汇总

    返回每个订单的详细信息，包括：
    - 订单基本信息
    - 该订单的利息总额
    - 该订单的完成金额
    - 该订单的总贡献
    """
    # 构建查询条件
    conditions = ["customer = ?"]
    params = [customer.upper()]

    if start_date:
        conditions.append("date >= ?")
        params.append(start_date)

    if end_date:
        conditions.append("date <= ?")
        params.append(end_date)

    where_clause = " AND ".join(conditions)

    # 查询所有订单
    cursor.execute(f'''
    SELECT * FROM orders 
    WHERE {where_clause}
    ORDER BY date DESC
    ''', params)

    order_rows = cursor.fetchall()
    orders = [dict(row) for row in order_rows]

    # 为每个订单查询收入汇总
    result = []
    for order in orders:
        order_id = order['order_id']

        # 查询该订单的收入汇总
        cursor.execute('''
        SELECT 
            type,
            COUNT(*) as count,
            SUM(amount) as total_amount
        FROM income_records 
        WHERE order_id = ?
        GROUP BY type
        ''', (order_id,))

        income_rows = cursor.fetchall()

        order_interest = 0.0
        order_completed = 0.0
        order_breach_end = 0.0
        order_principal_reduction = 0.0
        order_total = 0.0

        for row in income_rows:
            income_type = row[0]
            amount = row[2] or 0.0

            if income_type == 'interest':
                order_interest = amount
            elif income_type == 'completed':
                order_completed = amount
            elif income_type == 'breach_end':
                order_breach_end = amount
            elif income_type == 'principal_reduction':
                order_principal_reduction = amount

            order_total += amount

        result.append({
            'order': order,
            'interest': order_interest,
            'completed': order_completed,
            'breach_end': order_breach_end,
            'principal_reduction': order_principal_reduction,
            'total_contribution': order_total
        })

    return result


@db_query
def get_income_summary_by_type(conn, cursor, start_date: str, end_date: str = None,
                               group_id: Optional[str] = None) -> Dict:
    """按收入类型和客户类型汇总"""
    query = """
    SELECT 
        type,
        customer,
        COUNT(*) as count,
        SUM(amount) as total_amount
    FROM income_records 
    WHERE date >= ? AND date <= ?
    """
    params = [start_date, end_date or start_date]

    if group_id:
        query += " AND group_id = ?"
        params.append(group_id)

    query += " GROUP BY type, customer ORDER BY type, customer"

    cursor.execute(query, params)
    rows = cursor.fetchall()

    # 构建汇总字典
    summary = {}
    for row in rows:
        type_name = row[0]
        customer_type = row[1] or 'None'
        count = row[2]
        total = row[3]

        if type_name not in summary:
            summary[type_name] = {}
        summary[type_name][customer_type] = {
            'count': count,
            'total': total
        }

    return summary


@db_query
def get_income_summary_by_group(conn, cursor, start_date: str, end_date: str = None) -> Dict:
    """按归属ID汇总收入"""
    query = """
    SELECT 
        group_id,
        COUNT(*) as count,
        SUM(amount) as total_amount
    FROM income_records 
    WHERE date >= ? AND date <= ?
    GROUP BY group_id
    ORDER BY total_amount DESC
    """
    params = [start_date, end_date or start_date]

    cursor.execute(query, params)
    rows = cursor.fetchall()

    summary = {}
    for row in rows:
        group_id = row[0] or 'NULL'
        count = row[1]
        total = row[2]
        summary[group_id] = {
            'count': count,
            'total': total
        }

    return summary

# ========== 操作历史（撤销功能） ==========


@db_transaction
def record_operation(conn, cursor, user_id: int, operation_type: str, operation_data: Dict, chat_id: int) -> int:
    """记录操作历史，返回操作ID"""
    cursor.execute('''
    INSERT INTO operation_history (user_id, chat_id, operation_type, operation_data, is_undone)
    VALUES (?, ?, ?, ?, 0)
    ''', (user_id, chat_id, operation_type, json.dumps(operation_data, ensure_ascii=False)))
    return cursor.lastrowid


@db_query
def get_last_operation(conn, cursor, user_id: int, chat_id: int) -> Optional[Dict]:
    """获取用户在指定聊天环境中的最后一个未撤销的操作"""
    cursor.execute('''
    SELECT * FROM operation_history 
    WHERE user_id = ? AND chat_id = ? AND is_undone = 0
    ORDER BY created_at DESC, id DESC
    LIMIT 1
    ''', (user_id, chat_id))
    row = cursor.fetchone()
    if row:
        result = dict(row)
        result['operation_data'] = json.loads(result['operation_data'])
        return result
    return None


@db_transaction
def mark_operation_undone(conn, cursor, operation_id: int) -> bool:
    """标记操作为已撤销"""
    cursor.execute('''
    UPDATE operation_history 
    SET is_undone = 1
    WHERE id = ?
    ''', (operation_id,))
    return cursor.rowcount > 0


@db_query
def get_operation_by_id(conn, cursor, operation_id: int) -> Optional[Dict]:
    """根据ID获取操作记录"""
    cursor.execute(
        'SELECT * FROM operation_history WHERE id = ?', (operation_id,))
    row = cursor.fetchone()
    if row:
        result = dict(row)
        result['operation_data'] = json.loads(result['operation_data'])
        return result
    return None


@db_query
def get_recent_operations(conn, cursor, user_id: int, limit: int = 10) -> List[Dict]:
    """获取用户最近的操作历史"""
    cursor.execute('''
    SELECT * FROM operation_history 
    WHERE user_id = ?
    ORDER BY created_at DESC, id DESC
    LIMIT ?
    ''', (user_id, limit))
    rows = cursor.fetchall()
    result = []
    for row in rows:
        op = dict(row)
        op['operation_data'] = json.loads(op['operation_data'])
        result.append(op)
    return result
