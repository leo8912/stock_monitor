"""
基础数据库生成脚本
生成包含主要股票的基础数据库，用于打包到程序中
"""

import sys
import os
import shutil
import tempfile

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from stock_monitor.data.fetcher import stock_fetcher
from stock_monitor.data.stock.stock_db import StockDatabase
from pypinyin import lazy_pinyin, Style

def create_base_database():
    """创建基础数据库（主要股票）"""
    print("=" * 80)
    print("开始创建基础数据库...")
    print("=" * 80)
    
    # 获取所有股票
    print("\n1. 获取所有股票数据...")
    all_stocks = stock_fetcher.fetch_all_stocks()
    print(f"   获取到 {len(all_stocks)} 只股票")
    
    # 筛选主要股票
    print("\n2. 筛选主要股票...")
    major_stocks = []
    
    # 计数器
    sh600_count = 0
    sz000_count = 0
    sh688_count = 0
    sz300_count = 0
    
    for stock in all_stocks:
        code = stock['code']
        
        # 所有指数
        if code.startswith(('sh000', 'sz399')):
            major_stocks.append(stock)
        # 主板股票（sh600前300只，sz000前300只）
        elif code.startswith('sh600'):
            if sh600_count < 300:
                major_stocks.append(stock)
                sh600_count += 1
        elif code.startswith('sz000'):
            if sz000_count < 300:
                major_stocks.append(stock)
                sz000_count += 1
        # 科创板前50
        elif code.startswith('sh688'):
            if sh688_count < 50:
                major_stocks.append(stock)
                sh688_count += 1
        # 创业板前50
        elif code.startswith('sz300'):
            if sz300_count < 50:
                major_stocks.append(stock)
                sz300_count += 1
    
    print(f"   筛选出 {len(major_stocks)} 只主要股票")
    print(f"   - 指数: {len([s for s in major_stocks if s['code'].startswith(('sh000', 'sz399'))])} 只")
    print(f"   - 主板(sh600): {sh600_count} 只")
    print(f"   - 主板(sz000): {sz000_count} 只")
    print(f"   - 科创板: {sh688_count} 只")
    print(f"   - 创业板: {sz300_count} 只")
    
    # 添加拼音
    print("\n3. 添加拼音信息...")
    for stock in major_stocks:
        name = stock['name']
        base = name.replace('*', '').replace('ST', '').replace(' ', '')
        stock['pinyin'] = ''.join(lazy_pinyin(base)).lower()
        stock['abbr'] = ''.join(lazy_pinyin(base, style=Style.FIRST_LETTER)).lower()
    print("   拼音信息添加完成")
    
    # 创建临时数据库
    print("\n4. 创建数据库...")
    temp_dir = tempfile.mkdtemp()
    
    # 临时修改配置目录
    import stock_monitor.config.manager as config_module
    original_get_config_dir = config_module.get_config_dir
    
    def temp_get_config_dir():
        return temp_dir
    
    # 替换函数
    config_module.get_config_dir = temp_get_config_dir
    import stock_monitor.data.stock.stock_db as db_module
    db_module.get_config_dir = temp_get_config_dir
    
    # 创建数据库实例
    db = StockDatabase()
    count = db.insert_stocks(major_stocks)
    print(f"   成功插入 {count} 条记录")
    
    # 复制到resources
    print("\n5. 保存基础数据库...")
    target_path = "stock_monitor/resources/stocks_base.db"
    os.makedirs(os.path.dirname(target_path), exist_ok=True)
    shutil.copy2(db.db_path, target_path)
    
    file_size = os.path.getsize(target_path)
    print(f"   基础数据库已创建: {target_path}")
    print(f"   文件大小: {file_size / 1024:.2f} KB ({file_size / 1024 / 1024:.2f} MB)")
    
    # 恢复原始函数
    config_module.get_config_dir = original_get_config_dir
    db_module.get_config_dir = original_get_config_dir
    
    # 清理临时目录
    print("\n6. 清理临时文件...")
    shutil.rmtree(temp_dir)
    print("   清理完成")
    
    print("\n" + "=" * 80)
    print("基础数据库创建成功！")
    print("=" * 80)
    
    # 验证数据库
    print("\n验证数据库...")
    verify_db = StockDatabase()
    # 临时修改路径
    verify_db.db_path = target_path
    
    import sqlite3
    with sqlite3.connect(target_path) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM stocks")
        count = cursor.fetchone()[0]
        print(f"✓ 数据库包含 {count} 只股票")
        
        cursor.execute("SELECT COUNT(*) FROM stocks WHERE market_type='INDEX'")
        index_count = cursor.fetchone()[0]
        print(f"✓ 其中指数 {index_count} 只")
        
        cursor.execute("SELECT COUNT(*) FROM stocks WHERE market_type='A'")
        a_count = cursor.fetchone()[0]
        print(f"✓ 其中A股 {a_count} 只")

if __name__ == '__main__':
    try:
        create_base_database()
    except Exception as e:
        print(f"\n错误: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
