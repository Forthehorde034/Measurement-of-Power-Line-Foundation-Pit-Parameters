#!/usr/bin/env python3
"""
PySide6 项目打包工具
支持:
  - pyside6-deploy（原生轻量，推荐新项目）
  - PyInstaller（兼容复杂依赖）

用法:
  python tools/build.py --deploy          # 使用 pyside6-deploy
  python tools/build.py --pyinstaller     # 使用 PyInstaller
  python tools/build.py --help            # 显示帮助
"""

import argparse
import subprocess
import sys
import os


import platform
import shutil
from pathlib import Path

# 从 pyproject.toml 读取版本
import tomli


# ==============================
# 配置区 —— 按项目需求修改
# ==============================
PROJECT_ROOT = Path(__file__).parent.parent  # 项目根目录

# 更好的错误处理方式
with open(PROJECT_ROOT/"pyproject.toml", "rb") as f:
    config = tomli.load(f)

SRC_DIR = PROJECT_ROOT / "src"
MAIN_SCRIPT = SRC_DIR / "main.py"
RESOURCES_DIR = PROJECT_ROOT / "resources"
BUILD_DIR = PROJECT_ROOT / "build"
DIST_DIR = PROJECT_ROOT / "dist"

# 应用元数据（与 pyproject.toml 保持一致）
APP_NAME = config["project"]["name"]
VERSION = config["project"]["version"]
ICON_PATH = RESOURCES_DIR / "icons" / "app.png"  # 通用 icon（.png），自动转格式

# 平台特定配置
IS_WINDOWS = platform.system() == "Windows"
IS_MACOS = platform.system() == "Darwin"
IS_LINUX = platform.system() == "Linux"


# ==============================
# 工具函数
# ==============================
def log_info(msg: str):
    print(f"\033[1;34m[INFO]\033[0m {msg}")

def log_success(msg: str):
    print(f"\033[1;32m[SUCCESS]\033[0m {msg}")

def log_error(msg: str):
    print(f"\033[1;31m[ERROR]\033[0m {msg}", file=sys.stderr)

def run_command(cmd: list, cwd=None):
    """执行 shell 命令，带实时输出"""
    log_info(f"Running: {' '.join(cmd)}")
    try:
        result = subprocess.run(
            cmd,
            cwd=cwd,
            check=True,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT
        )
        print(result.stdout)
        return result
    except subprocess.CalledProcessError as e:
        log_error(f"Command failed with exit code {e.returncode}")
        print(e.output)
        sys.exit(1)


def ensure_directories():
    """确保输出目录存在"""
    BUILD_DIR.mkdir(exist_ok=True)
    DIST_DIR.mkdir(exist_ok=True)


def get_icon_for_platform():
    """根据平台返回图标路径（自动转换）"""
    if IS_WINDOWS:
        icon = RESOURCES_DIR / "icons" / "app.ico"
        if not icon.exists():
            # 尝试用 png 生成 ico（需 Pillow）
            try:
                from PIL import Image
                img = Image.open(ICON_PATH)
                img.save(icon, format="ICO", sizes=[(256, 256)])
                log_info(f"Generated {icon} from {ICON_PATH}")
            except Exception as e:
                log_error(f"Failed to generate .ico: {e}. Using default icon.")
                return None
        return str(icon)
    elif IS_MACOS:
        icon = RESOURCES_DIR / "icons" / "app.icns"
        if not icon.exists():
            log_error(f"macOS icon missing: {icon}. Please provide .icns file.")
            return None
        return str(icon)
    else:  # Linux
        return str(ICON_PATH)  # .png 通常可直接用


# ==============================
# 打包方法
# ==============================
def build_with_pyside6_deploy():
    """使用 pyside6-deploy 打包"""
    log_info("📦 Starting pyside6-deploy build...")

    # 检查 pyproject.toml 是否存在
    pyproject = PROJECT_ROOT / "pysidedeploy.spec"
    if not pyproject.exists():
        log_error("pysidedeploy.spec not found! Required for pyside6-deploy.")
        sys.exit(1)

    # 构建命令
    cmd = [
        "pyside6-deploy",
        "--config", str(pyproject)
    ]


    try:
        run_command(cmd, cwd=PROJECT_ROOT)
        log_success("✅ pyside6-deploy build completed!")

        # 复制输出到 dist/
        build_output = BUILD_DIR
        if IS_WINDOWS:
            src_exe = build_output / f"{APP_NAME}.exe"
            dst_exe = DIST_DIR / f"{APP_NAME}-{VERSION}-win64.exe"
        elif IS_MACOS:
            src_exe = build_output / f"{APP_NAME}.app"
            dst_exe = DIST_DIR / f"{APP_NAME}-{VERSION}-mac.dmg"  # 实际需 dmgutil，此处简化
            # 注意：pyside6-deploy 6.8+ 支持 --dmg 生成 .dmg
        else:  # Linux
            src_exe = build_output /  APP_NAME
            dst_exe = DIST_DIR / f"{APP_NAME}-{VERSION}-linux.AppImage"

        if src_exe.exists():
            if IS_MACOS and src_exe.suffix == ".app":
                # macOS: 打包为 .dmg（需 hdiutil，此处仅复制 .app）
                shutil.copytree(src_exe, DIST_DIR / src_exe.name, dirs_exist_ok=True)
                log_info(f"Copied {src_exe.name} to {DIST_DIR}")
            else:
                shutil.copy2(src_exe, dst_exe)
                log_success(f"→ Output: {dst_exe}")
        else:
            log_error(f"Build output not found: {src_exe}")

    except Exception as e:
        log_error(f"pyside6-deploy failed: {e}")
        sys.exit(1)


def build_with_pyinstaller():
    """使用 PyInstaller 打包"""
    log_info("📦 Starting PyInstaller build...")

    # 检查主脚本
    if not MAIN_SCRIPT.exists():
        log_error(f"Main script not found: {MAIN_SCRIPT}")
        sys.exit(1)

    # 构建命令基础
    cmd = [
        "pyinstaller",
        "--name", APP_NAME,
        "--clean",
        "--noconfirm"
    ]

    # 平台特定参数
    if IS_WINDOWS:
        cmd.extend(["--windowed"])
        # cmd.extend(["--onefile"])
        icon = get_icon_for_platform()
        if icon:
            cmd.extend(["--icon", icon])
        # 资源路径: "resources;resources"
        cmd.extend(["--add-data", f"{RESOURCES_DIR};resources"])
        cmd.extend(["--collect-data=open3d"])
    elif IS_MACOS:
        cmd.extend(["--windowed"])
        # cmd.extend(["--onefile"])
        icon = get_icon_for_platform()
        if icon:
            cmd.extend(["--icon", icon])
        # 资源路径: "resources:resources"
        cmd.extend(["--add-data", f"{RESOURCES_DIR}:resources"])
        cmd.extend(["--collect-data=open3d"])
    else:  # Linux
        cmd.extend(["--windowed"])
        # cmd.extend(["--onefile"])
        cmd.extend(["--collect-data=open3d"])

    # 添加主脚本
    cmd.append(str(MAIN_SCRIPT))

    try:
        # 清理旧 build
        if (PROJECT_ROOT / "build").exists():
            shutil.rmtree(PROJECT_ROOT / "build")
        if (PROJECT_ROOT / "dist").exists():
            shutil.rmtree(PROJECT_ROOT / "dist")

        run_command(cmd, cwd=PROJECT_ROOT)

        # 移动输出到项目 dist/
        pyi_dist = PROJECT_ROOT / "dist"
        if IS_WINDOWS:
            src_exe = pyi_dist / f"{APP_NAME}.exe"
            dst_exe = DIST_DIR / f"{APP_NAME}-{VERSION}-win64.exe"
        elif IS_MACOS:
            src_exe = pyi_dist / f"{APP_NAME}.app"
            dst_exe = DIST_DIR / f"{APP_NAME}-{VERSION}-mac.app"
        else:
            src_exe = pyi_dist / APP_NAME
            dst_exe = DIST_DIR / f"{APP_NAME}-{VERSION}-linux"

        if src_exe.exists():
            if src_exe.is_dir():  # macOS .app 是目录
                shutil.copytree(src_exe, dst_exe, dirs_exist_ok=True)
            else:
                shutil.copy2(src_exe, dst_exe)
            log_success(f"✅ PyInstaller build completed! → {dst_exe}")
        else:
            log_error(f"PyInstaller output not found: {src_exe}")

    except Exception as e:
        log_error(f"PyInstaller failed: {e}")
        sys.exit(1)


# ==============================
# 主程序
# ==============================
def main():
    parser = argparse.ArgumentParser(description="PySide6 打包工具")
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "--deploy",
        action="store_true",
        help="使用 pyside6-deploy 打包（原生轻量）"
    )
    group.add_argument(
        "--pyinstaller",
        action="store_true",
        help="使用 PyInstaller 打包（兼容复杂依赖）"
    )
    parser.add_argument(
        "--clean",
        action="store_true",
        help="清理 build/ 和 dist/ 目录"
    )

    args = parser.parse_args()

    # 清理模式
    if args.clean:
        log_info("🧹 Cleaning build and dist directories...")
        for d in [BUILD_DIR, DIST_DIR, PROJECT_ROOT / "build", PROJECT_ROOT / "dist"]:
            if d.exists():
                shutil.rmtree(d)
                log_info(f"Removed {d}")
        return

    # 确保目录
    ensure_directories()

    # 执行打包
    if args.deploy:
        build_with_pyside6_deploy()
    elif args.pyinstaller:
        build_with_pyinstaller()


if __name__ == "__main__":
    main()