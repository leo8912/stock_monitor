"""
详细测试 market_snapshot 接口
查看返回的数据结构和字段
"""

import easyquotation
from pprint import pprint
import json

def test_market_snapshot_detail():
    """详细测试 market_snapshot 接口"""
    print("=" * 80)
    print("测试 market_snapshot(prefix=True) 接口")
    print("=" * 80)
    
    try:
        quotation = easyquotation.use('sina')
        snapshot = quotation.market_snapshot(prefix=True)
        
        if not snapshot:
            print("✗ 未获取到数据")
            return
        
        print(f"\n✓ 成功获取数据")
        print(f"✓ 数据类型: {type(snapshot)}")
        print(f"✓ 股票数量: {len(snapshot)}")
        
        # 查看前3只股票的完整数据结构
        print("\n" + "=" * 80)
        print("示例数据（前3只股票的完整字段）")
        print("=" * 80)
        
        count = 0
        for code, info in snapshot.items():
            if count >= 3:
                break
            
            print(f"\n股票代码: {code}")
            print(f"数据类型: {type(info)}")
            
            if isinstance(info, dict):
                print(f"字段数量: {len(info)}")
                print("所有字段:")
                for key, value in info.items():
                    print(f"  {key}: {value} ({type(value).__name__})")
            else:
                print(f"数据内容: {info}")
            
            count += 1
        
        # 统计分析
        print("\n" + "=" * 80)
        print("数据统计分析")
        print("=" * 80)
        
        up_count = 0
        down_count = 0
        flat_count = 0
        error_count = 0
        index_count = 0
        
        for code, info in snapshot.items():
            if not isinstance(info, dict):
                error_count += 1
                continue
            
            name = info.get('name', '')
            
            # 统计指数数量
            if '指数' in name or 'Ａ股' in name:
                index_count += 1
                continue
            
            try:
                close = float(info.get('close', 0))
                now = float(info.get('now', 0))
                
                if close == 0:
                    flat_count += 1
                elif now > close:
                    up_count += 1
                elif now < close:
                    down_count += 1
                else:
                    flat_count += 1
            except (ValueError, TypeError) as e:
                error_count += 1
                continue
        
        total = up_count + down_count + flat_count
        
        print(f"总股票数: {len(snapshot)}")
        print(f"指数数量: {index_count}")
        print(f"有效股票: {total}")
        print(f"数据错误: {error_count}")
        print(f"\n涨跌统计:")
        print(f"  上涨: {up_count} ({up_count/total*100:.2f}%)")
        print(f"  下跌: {down_count} ({down_count/total*100:.2f}%)")
        print(f"  平盘: {flat_count} ({flat_count/total*100:.2f}%)")
        
        # 查看一些特殊股票
        print("\n" + "=" * 80)
        print("特殊股票示例")
        print("=" * 80)
        
        # 查找指数
        print("\n指数示例:")
        count = 0
        for code, info in snapshot.items():
            if isinstance(info, dict):
                name = info.get('name', '')
                if '指数' in name and count < 3:
                    print(f"  {code}: {name}")
                    count += 1
        
        # 查找涨停股票
        print("\n涨停股票示例:")
        count = 0
        for code, info in snapshot.items():
            if isinstance(info, dict):
                try:
                    changepercent = float(info.get('changepercent', 0))
                    if changepercent >= 9.9 and count < 3:
                        name = info.get('name', '')
                        print(f"  {code}: {name} (+{changepercent}%)")
                        count += 1
                except:
                    pass
        
        # 查找跌停股票
        print("\n跌停股票示例:")
        count = 0
        for code, info in snapshot.items():
            if isinstance(info, dict):
                try:
                    changepercent = float(info.get('changepercent', 0))
                    if changepercent <= -9.9 and count < 3:
                        name = info.get('name', '')
                        print(f"  {code}: {name} ({changepercent}%)")
                        count += 1
                except:
                    pass
        
        # 保存完整数据到文件（前10只）
        print("\n" + "=" * 80)
        print("保存示例数据到文件")
        print("=" * 80)
        
        sample_data = {}
        count = 0
        for code, info in snapshot.items():
            if count >= 10:
                break
            sample_data[code] = info
            count += 1
        
        with open('market_snapshot_sample.json', 'w', encoding='utf-8') as f:
            json.dump(sample_data, f, ensure_ascii=False, indent=2)
        
        print("✓ 已保存前10只股票数据到 market_snapshot_sample.json")
        
    except Exception as e:
        print(f"✗ 错误: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    test_market_snapshot_detail()
