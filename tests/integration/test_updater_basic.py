"""
独立更新程序测试脚本
用于验证updater.exe的基本功能
"""
import os
import sys
import time
import subprocess
import tempfile
import zipfile
import shutil
from pathlib import Path

class UpdaterTester:
    """更新程序测试器"""
    
    def __init__(self):
        self.test_dir = Path(tempfile.mkdtemp(prefix="updater_test_"))
        self.results = []
        
    def log(self, message, status="INFO"):
        """记录测试日志"""
        timestamp = time.strftime("%H:%M:%S")
        prefix = {
            "INFO": "ℹ️",
            "SUCCESS": "✅",
            "ERROR": "❌",
            "WARNING": "⚠️"
        }.get(status, "•")
        
        log_msg = f"[{timestamp}] {prefix} {message}"
        print(log_msg)
        self.results.append((status, message))
    
    def test_updater_exists(self):
        """测试1: 检查updater.exe是否存在"""
        self.log("测试1: 检查updater.exe是否存在", "INFO")
        
        updater_path = Path("dist/updater.exe")
        if updater_path.exists():
            size_mb = updater_path.stat().st_size / (1024 * 1024)
            self.log(f"updater.exe存在, 大小: {size_mb:.1f} MB", "SUCCESS")
            return True
        else:
            self.log(f"updater.exe不存在: {updater_path}", "ERROR")
            return False
    
    def test_updater_executable(self):
        """测试2: 检查updater.exe是否可执行"""
        self.log("测试2: 检查updater.exe是否可执行", "INFO")
        
        try:
            # 尝试运行updater.exe --help
            result = subprocess.run(
                ["dist/updater.exe", "--help"],
                capture_output=True,
                text=True,
                timeout=5
            )
            
            if "Stock Monitor Updater" in result.stdout or "usage" in result.stdout.lower():
                self.log("updater.exe可以正常执行", "SUCCESS")
                return True
            else:
                self.log("updater.exe执行但输出异常", "WARNING")
                return False
                
        except subprocess.TimeoutExpired:
            self.log("updater.exe执行超时", "ERROR")
            return False
        except Exception as e:
            self.log(f"执行updater.exe失败: {e}", "ERROR")
            return False
    
    def test_create_mock_update_package(self):
        """测试3: 创建模拟更新包"""
        self.log("测试3: 创建模拟更新包", "INFO")
        
        try:
            # 创建临时目录结构
            mock_dir = self.test_dir / "mock_update"
            mock_dir.mkdir(exist_ok=True)
            
            # 创建一些模拟文件
            (mock_dir / "test_file.txt").write_text("This is a test file")
            (mock_dir / "updater.exe").write_text("Mock updater")
            
            # 创建zip包
            zip_path = self.test_dir / "test_update.zip"
            with zipfile.ZipFile(zip_path, 'w') as zipf:
                for file in mock_dir.rglob("*"):
                    if file.is_file():
                        zipf.write(file, file.relative_to(mock_dir))
            
            if zip_path.exists():
                size_kb = zip_path.stat().st_size / 1024
                self.log(f"模拟更新包创建成功: {size_kb:.1f} KB", "SUCCESS")
                return True
            else:
                self.log("模拟更新包创建失败", "ERROR")
                return False
                
        except Exception as e:
            self.log(f"创建模拟更新包失败: {e}", "ERROR")
            return False
    
    def test_extraction_logic(self):
        """测试4: 测试提取逻辑"""
        self.log("测试4: 测试updater.exe提取逻辑", "INFO")
        
        try:
            source = Path("dist/updater.exe")
            target = self.test_dir / "updater.exe"
            
            if source.exists():
                shutil.copy2(source, target)
                
                if target.exists():
                    self.log("updater.exe提取成功", "SUCCESS")
                    return True
                else:
                    self.log("updater.exe提取失败", "ERROR")
                    return False
            else:
                self.log("源文件不存在", "ERROR")
                return False
                
        except Exception as e:
            self.log(f"提取测试失败: {e}", "ERROR")
            return False
    
    def cleanup(self):
        """清理测试文件"""
        self.log("清理测试文件...", "INFO")
        try:
            if self.test_dir.exists():
                shutil.rmtree(self.test_dir)
                self.log("测试文件清理完成", "SUCCESS")
        except Exception as e:
            self.log(f"清理失败: {e}", "WARNING")
    
    def run_all_tests(self):
        """运行所有测试"""
        print("=" * 60)
        print("独立更新程序基础测试")
        print("=" * 60)
        print()
        
        tests = [
            self.test_updater_exists,
            self.test_updater_executable,
            self.test_create_mock_update_package,
            self.test_extraction_logic,
        ]
        
        passed = 0
        failed = 0
        
        for test in tests:
            try:
                if test():
                    passed += 1
                else:
                    failed += 1
            except Exception as e:
                self.log(f"测试异常: {e}", "ERROR")
                failed += 1
            print()
        
        # 清理
        self.cleanup()
        
        # 总结
        print("=" * 60)
        print("测试总结")
        print("=" * 60)
        print(f"通过: {passed}")
        print(f"失败: {failed}")
        print(f"总计: {passed + failed}")
        print()
        
        if failed == 0:
            print("✅ 所有基础测试通过!")
            print()
            print("建议下一步:")
            print("1. 进行完整的更新流程测试")
            print("2. 测试GitHub Actions编译")
            print("3. 在真实环境中验证")
        else:
            print("❌ 部分测试失败,请检查问题")
        
        print("=" * 60)

if __name__ == "__main__":
    tester = UpdaterTester()
    tester.run_all_tests()
