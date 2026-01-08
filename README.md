# 1. 克隆项目
git clone https://github.com/you/pcdviewer.git
cd pcdviewer

# 2. 创建虚拟环境
python -m venv .venv310
.venv310\Scripts\activate

# 3. 安装开发依赖
pip install -e ".[dev,build]"

# 4. 验证关键依赖
python -c "import PySide6, open3d; print('Ready!')"

# 5. 开发
pyside6-designer resources/main.ui  
python src/main.py                  

# 6. 测试
pytest tests/

# 7. 打包（命令方式）
pyside6-deploy build                 
 或
pyinstaller --name=PCDViewer --onefile --windowed --icon=resources/icons/app.ico --add-data="resources;resources" src/main.py


# 8.打包（代码方式）

## 使用 pyside6-deploy（推荐新项目）
python tools/build.py --deploy

## 使用 PyInstaller（含 numpy/pandas 等）
python tools/build.py --pyinstaller

## 清理临时文件
python tools/build.py --clea
