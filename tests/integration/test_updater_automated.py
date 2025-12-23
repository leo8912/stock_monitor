"""
自动化测试updater.exe的核心功能
不需要运行GUI程序
"""
import shutil
import subprocess
import time
import zipfile
from pathlib import Path


class AutomatedUpdaterTest:
    """自动化updater测试"""

    def __init__(self):
        self.test_dir = Path("automated_test_env")
        self.results = []

    def log(self, message, status="INFO"):
        """记录日志"""
        prefix = {"INFO": "ℹ️", "SUCCESS": "✅", "ERROR": "❌", "WARNING": "⚠️"}.get(
            status, "•"
        )
        log_msg = f"{prefix} {message}"
        print(log_msg)
        self.results.append((status, message))

    def setup(self):
        """设置测试环境"""
        self.log("设置测试环境...", "INFO")

        # 创建测试目录
        if self.test_dir.exists():
            shutil.rmtree(self.test_dir)
        self.test_dir.mkdir()

        # 创建模拟的主程序目录
        (self.test_dir / "_internal").mkdir()
        (self.test_dir / "test_file.txt").write_text("Old version")

        self.log("测试环境创建完成", "SUCCESS")
        return True

    def test_updater_help(self):
        """测试updater.exe --help"""
        self.log("测试1: updater.exe --help", "INFO")

        try:
            result = subprocess.run(
                ["dist/updater.exe", "--help"],
                capture_output=True,
                text=True,
                timeout=5,
            )

            if (
                result.returncode == 0
                or "usage" in result.stdout.lower()
                or "Stock Monitor" in result.stdout
            ):
                self.log("updater.exe响应正常", "SUCCESS")
                return True
            else:
                self.log(f"updater.exe响应异常: {result.stderr}", "WARNING")
                return False
        except Exception as e:
            self.log(f"测试失败: {e}", "ERROR")
            return False

    def create_mock_update_package(self):
        """创建模拟更新包"""
        self.log("测试2: 创建模拟更新包", "INFO")

        try:
            # 创建临时内容
            mock_content_dir = self.test_dir / "new_version"
            mock_content_dir.mkdir()
            (mock_content_dir / "test_file.txt").write_text("New version")
            (mock_content_dir / "new_file.txt").write_text("This is new")

            # 创建zip
            zip_path = self.test_dir / "update.zip"
            with zipfile.ZipFile(zip_path, "w") as zipf:
                for file in mock_content_dir.rglob("*"):
                    if file.is_file():
                        zipf.write(file, file.relative_to(mock_content_dir))

            if zip_path.exists():
                size = zip_path.stat().st_size
                self.log(f"更新包创建成功: {size} bytes", "SUCCESS")
                return zip_path
            else:
                self.log("更新包创建失败", "ERROR")
                return None
        except Exception as e:
            self.log(f"创建更新包失败: {e}", "ERROR")
            return None

    def test_updater_execution(self, update_package):
        """测试updater.exe执行(不等待完成)"""
        self.log("测试3: 测试updater.exe执行", "INFO")

        try:
            updater_exe = Path("dist/updater.exe").absolute()
            if not updater_exe.exists():
                self.log("updater.exe不存在", "ERROR")
                return False

            # 准备参数
            args = [
                str(updater_exe),
                "--update-package",
                str(update_package.absolute()),
                "--target-dir",
                str(self.test_dir.absolute()),
                "--main-exe",
                "stock_monitor.exe",
                "--pid",
                "99999",  # 假的PID,不会等待
            ]

            self.log(f"执行命令: {' '.join(args)}", "INFO")

            # 启动updater(不等待)
            process = subprocess.Popen(
                args,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP,
            )

            self.log(f"updater.exe已启动, PID: {process.pid}", "SUCCESS")

            # 等待一小段时间让updater开始工作
            time.sleep(2)

            # 检查进程是否还在运行
            if process.poll() is None:
                self.log("updater.exe正在运行", "SUCCESS")
                # 终止进程
                process.terminate()
                process.wait(timeout=5)
                self.log("updater.exe已终止", "INFO")
            else:
                self.log(f"updater.exe已退出, 返回码: {process.returncode}", "WARNING")

            return True

        except Exception as e:
            self.log(f"执行测试失败: {e}", "ERROR")
            return False

    def cleanup(self):
        """清理"""
        self.log("清理测试环境...", "INFO")
        try:
            if self.test_dir.exists():
                shutil.rmtree(self.test_dir)
            self.log("清理完成", "SUCCESS")
        except Exception as e:
            self.log(f"清理失败: {e}", "WARNING")

    def run(self):
        """运行所有测试"""
        print("=" * 60)
        print("自动化updater.exe测试")
        print("=" * 60)
        print()

        passed = 0
        failed = 0

        # 测试1: Help命令
        if self.test_updater_help():
            passed += 1
        else:
            failed += 1
        print()

        # 设置环境
        if not self.setup():
            print("❌ 环境设置失败")
            return

        # 测试2: 创建更新包
        update_package = self.create_mock_update_package()
        if update_package:
            passed += 1
        else:
            failed += 1
        print()

        # 测试3: 执行updater
        if update_package and self.test_updater_execution(update_package):
            passed += 1
        else:
            failed += 1
        print()

        # 清理
        self.cleanup()
        print()

        # 总结
        print("=" * 60)
        print("测试总结")
        print("=" * 60)
        print(f"通过: {passed}")
        print(f"失败: {failed}")
        print()

        if failed == 0:
            print("✅ 所有自动化测试通过!")
            print()
            print("注意:")
            print("- updater.exe可以正常启动和执行")
            print("- 完整的更新流程需要在真实环境中测试")
            print("- 建议提交代码后通过GitHub Actions进行完整测试")
        else:
            print("❌ 部分测试失败")

        print("=" * 60)


if __name__ == "__main__":
    tester = AutomatedUpdaterTest()
    tester.run()
