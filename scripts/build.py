#!/usr/bin/env python3
"""
本地构建工作流脚本 - 模拟GitHub Actions流程
用于在本地环境中完整模拟GitHub Workflow的构建、测试和打包流程
"""

import os
import subprocess
import sys
from pathlib import Path

# 获取项目根目录 (假设脚本在 scripts/ 目录下)
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent

# 切换到项目根目录
os.chdir(PROJECT_ROOT)
print(f"📂 工作目录已切换至: {PROJECT_ROOT}")


def check_required_files():
    """检查必需的文件是否存在"""
    required_files = [
        "stock_monitor/main.py",
        "requirements.txt",
        "requirements-dev.txt",
        "stock_monitor/resources/icon.ico",
    ]

    print("🔍 检查必需文件...")
    all_files_exist = True

    for file in required_files:
        if not os.path.exists(file):
            print(f"❌ 缺少必要文件: {file}")
            all_files_exist = False
        else:
            print(f"✅ 找到文件: {file}")

    return all_files_exist


def install_dependencies():
    """安装依赖项"""
    print("\n🔧 安装生产依赖...")
    try:
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", "-r", "requirements.txt"]
        )
        print("✅ 生产依赖安装完成")
    except subprocess.CalledProcessError as e:
        print(f"❌ 生产依赖安装失败: {e}")
        return False

    print("\n🔧 安装开发依赖...")
    try:
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", "-r", "requirements-dev.txt"]
        )
        print("✅ 开发依赖安装完成")
    except subprocess.CalledProcessError as e:
        print(f"❌ 开发依赖安装失败: {e}")
        return False

    return True


def run_tests():
    """运行测试套件"""
    print("\n🧪 运行测试...")
    try:
        result = subprocess.run(
            [sys.executable, "-m", "pytest", "tests/", "-v"],
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            print("✅ 所有测试通过")
            if len(result.stdout) < 2000:  # 避免输出过长
                print(result.stdout)
            else:
                print("📋 测试已完成（输出过长，已省略详细信息）")
            return True
        else:
            print("❌ 部分测试失败")
            if len(result.stdout) < 2000:
                print(result.stdout)
            if len(result.stderr) < 2000:
                print(result.stderr)
            return False
    except Exception as e:
        print(f"❌ 运行测试时出错: {e}")
        return False


def find_package_paths():
    """查找必要的包路径"""
    print("\n📂 查找依赖包路径...")

    paths = {}

    try:
        import easyquotation

        eq_path = os.path.dirname(easyquotation.__file__)
        stock_codes_path = os.path.join(eq_path, "stock_codes.conf")
        if os.path.exists(stock_codes_path):
            paths["easyquotation"] = eq_path
            print(f"✅ easyquotation路径: {eq_path}")
        else:
            print("⚠️  未找到stock_codes.conf，将创建空文件")
            with open(stock_codes_path, "w", encoding="utf-8") as f:
                f.write("# Stock codes configuration\n")
            paths["easyquotation"] = eq_path
            print(f"✅ 已创建stock_codes.conf: {stock_codes_path}")
    except ImportError:
        print("❌ 未安装easyquotation")
        return None

    try:
        import zhconv

        zhconv_path = os.path.dirname(zhconv.__file__)
        zhcdict_path = os.path.join(zhconv_path, "zhcdict.json")
        if os.path.exists(zhcdict_path):
            paths["zhconv"] = zhconv_path
            print(f"✅ zhconv路径: {zhconv_path}")
        else:
            print("❌ 未找到zhcdict.json")
            return None
    except ImportError:
        print("❌ 未安装zhconv")
        return None

    return paths


def build_executable():
    """构建可执行文件"""
    print("\n🏗️  构建可执行文件...")

    # 获取包路径
    paths = find_package_paths()
    if not paths:
        return False

    # 构建PyInstaller命令 (与GitHub Workflow保持一致)
    cmd = [
        "pyinstaller",
        # '--debug=all',          # 移除调试信息以减少噪音
        "-y",  # 覆盖输出目录
        # '-w',                   # 恢复无控制台窗口 (临时注释以查看错误输出)
        "-i",
        "stock_monitor/resources/icon.ico",  # 图标文件
        "-n",
        "stock_monitor",  # 可执行文件名
    ]
    # 添加数据文件 (与GitHub Workflow保持一致)
    cmd.extend(
        [
            "--add-data",
            f'{paths["easyquotation"]}{os.sep}stock_codes.conf;easyquotation',
        ]
    )
    cmd.extend(["--add-data", f'{paths["zhconv"]}{os.sep}zhcdict.json;zhconv'])
    cmd.extend(
        ["--add-data", "stock_monitor/resources/icon.ico;stock_monitor/resources"]
    )
    cmd.extend(
        ["--add-data", "stock_monitor/resources/stocks_base.db;stock_monitor/resources"]
    )

    # 添加updater.exe
    updater_exe_path = "dist/updater.exe"
    if os.path.exists(updater_exe_path):
        cmd.extend(["--add-data", f"{updater_exe_path};."])
        print(f"✅ 将包含updater.exe: {updater_exe_path}")
    else:
        print("⚠️  未找到updater.exe,将不包含更新程序")

    # 添加隐藏导入 (与GitHub Workflow保持一致)
    cmd.extend(["--hidden-import", "pypinyin"])
    cmd.extend(["--hidden-import", "pypinyin.style"])

    # 移除 --onefile 参数以匹配GitHub Workflow的行为
    # cmd.append('--onefile')  # 注释掉这一行以生成目录结构而不是单个exe文件

    # 添加主程序
    cmd.append("stock_monitor/main.py")

    print(f"🚀 执行命令: {' '.join(cmd)}")

    try:
        subprocess.check_call(cmd)
        print("✅ 构建成功！")

        # 检查输出文件
        exe_path = Path("dist") / "stock_monitor.exe"
        dir_path = Path("dist") / "stock_monitor"
        if exe_path.exists():
            size_mb = exe_path.stat().st_size / (1024 * 1024)
            print(f"📁 可执行文件位置: {exe_path}")
            print(f"📊 可执行文件大小: {size_mb:.1f} MB")
            return True
        elif dir_path.exists():
            print("📁 生成了目录结构 (_internal格式)")
            print(f"📁 目录位置: {dir_path}")
            return True
        else:
            print("❌ 可执行文件未生成")
            return False

    except subprocess.CalledProcessError as e:
        print(f"❌ 构建失败: {e}")
        return False
    except Exception as e:
        print(f"❌ 构建过程中发生未知错误: {e}")
        return False


def create_zip_artifact():
    """创建zip压缩包"""
    print("\n📦 创建产物压缩包...")
    try:
        import zipfile

        # 确保dist目录存在
        if not os.path.exists("dist"):
            print("❌ dist目录不存在")
            return False

        # 创建zip文件
        with zipfile.ZipFile("stock_monitor.zip", "w", zipfile.ZIP_DEFLATED) as zipf:
            # 添加可执行文件
            exe_path = "dist/stock_monitor.exe"
            if os.path.exists(exe_path):
                zipf.write(exe_path, "stock_monitor.exe")
                print("✅ 已添加可执行文件到压缩包")

            # 添加updater.exe
            updater_path = "dist/updater.exe"
            if os.path.exists(updater_path):
                zipf.write(updater_path, "updater.exe")
                print("✅ 已添加updater.exe到压缩包")

            print("✅ 产物压缩包创建完成: stock_monitor.zip")
            return True

    except Exception as e:
        print(f"❌ 创建压缩包失败: {e}")
        return False


def get_version():
    """获取应用版本号"""
    try:
        version_file = "stock_monitor/version.py"
        if os.path.exists(version_file):
            with open(version_file, encoding="utf-8") as f:
                content = f.read()
                import re

                version_match = re.search(
                    r"__version__\s*=\s*['\"]([^'\"]*)['\"]", content
                )
                if version_match:
                    return version_match.group(1)
        return "unknown"
    except Exception as e:
        print(f"⚠️  获取版本号失败: {e}")
        return "unknown"


def clean_build_artifacts():
    """清理构建产物"""
    print("\n🧹 清理构建产物...")
    try:
        # 删除构建目录
        if os.path.exists("build"):
            import shutil

            shutil.rmtree("build")
            print("✅ 已删除build目录")

        # 删除spec文件
        spec_file = "stock_monitor.spec"
        if os.path.exists(spec_file):
            os.remove(spec_file)
            print("✅ 已删除stock_monitor.spec文件")

        print("✅ 构建产物清理完成")
        return True
    except Exception as e:
        print(f"❌ 清理构建产物失败: {e}")
        return False


def main():
    """主函数 - 模拟完整的GitHub Workflow流程"""
    version = get_version()
    print(f"🚀 启动本地GitHub Workflow模拟流程 (版本: {version})")
    print("=" * 50)

    # 步骤1: 检查必需文件
    if not check_required_files():
        print("\n❌ 必需文件检查失败，终止流程")
        sys.exit(1)

    # 步骤2: 安装依赖
    if not install_dependencies():
        print("\n❌ 依赖安装失败，终止流程")
        sys.exit(1)

    # 步骤3: 运行测试
    if not run_tests():
        print("\n❌ 测试未通过，终止流程")
        sys.exit(1)

    # 步骤4: 构建可执行文件
    if not build_executable():
        print("\n❌ 构建失败，终止流程")
        sys.exit(1)

    # 步骤5: 创建产物压缩包
    if not create_zip_artifact():
        print("\n❌ 创建压缩包失败，终止流程")
        sys.exit(1)

    # 步骤6: 清理构建产物
    clean_build_artifacts()

    print("\n🎉 GitHub Workflow模拟流程完成！")
    print("📋 产物清单:")
    print("   - 可执行文件: dist/stock_monitor.exe")
    print("   - 压缩包: stock_monitor.zip")


if __name__ == "__main__":
    main()
