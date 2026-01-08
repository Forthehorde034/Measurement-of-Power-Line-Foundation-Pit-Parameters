
import sys

import open3d as o3d
import win32gui
from PySide6.QtCore import Qt
from PySide6.QtGui import QSurfaceFormat, QAction
from PySide6.QtWidgets import (
    QMainWindow, QFileDialog, QVBoxLayout,
    QWidget, QMessageBox, QLabel
)
from open3d.visualization import gui
from core.log_manager import LogManager as logger

class PointCloudWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setLayout(QVBoxLayout())
        self.layout().setContentsMargins(0, 0, 0, 0)

        self.vis = None

        # 尝试创建嵌入式可视化器
        try:
            self._create_embedded_visualizer()
        except Exception as e:
            self.close()

    def _create_embedded_visualizer(self):

        # 创建 O3DVisualizer
        self.vis = o3d.visualization.O3DVisualizer()
        self.vis.show(False)
        self.vis.show_settings = True
        self.vis.show_menu( True)


        # 添加初始几何体
        self.vis.add_geometry("Coordinate", o3d.geometry.TriangleMesh.create_coordinate_frame(size=0.5))
        self.vis.reset_camera_to_default()

        # 添加窗口到Application
        app = gui.Application.instance
        if app:
            app.add_window(self.vis)


        if sys.platform == "win32":
            from PySide6.QtGui import QWindow
            # 注意：PySide6 6.8 中 QWindow.fromWinId 仍然可用，但需确保是整数句柄
            # 获取原生窗口句柄（仅 Windows 可靠）
            self.win_id = win32gui.FindWindow('GLFW30', None)
            logger.info(f"获取窗口句柄成功：{self.win_id}")
            if isinstance(self.win_id, int):
                window = QWindow.fromWinId(self.win_id)
                self.window = window
            else:
                raise RuntimeError("native_window 不是有效的窗口句柄 (int)")
        else:
            # macOS/Linux: 不支持可靠嵌入，抛出异常触发 fallback
            raise RuntimeError("macOS/Linux 不支持嵌入 Open3D 窗口")

        # 嵌入到 QWidget
        container = QWidget.createWindowContainer(window, self)
        self.layout().addWidget(container)

    def load_point_cloud(self, file_path):
        try:
            pcd = o3d.io.read_point_cloud(file_path)
            if pcd.is_empty():
                raise ValueError("点云文件为空")

            if self.vis:
                # 嵌入模式：更新可视化器
                if self.vis.scene.has_geometry("PointCloud"):
                    self.vis.remove_geometry("PointCloud")
                self.vis.add_geometry("PointCloud", pcd)
                self.vis.reset_camera_to_default()
        except Exception as e:
            raise e

    def closeEvent(self, event):
        """修复：正确的资源清理和进程退出"""
        if self.vis:
            try:
                self.window.destroy()
                # 销毁可视化器窗口
                logger.info("销毁可视化器窗口")
                self.vis.close()
                self.vis = None
            except Exception as e:
                logger.error(f"销毁可视化器失败: {e}")
                pass
        # 退出Open3D应用
        try:
            app = gui.Application.instance
            if app:
                logger.info("退出 app")
                app.quit()
        except:
            pass

        # 接受关闭事件
        event.accept()
    def __del__(self):
        # 安全销毁可视化器
        if hasattr(self, 'vis') and self.vis:
            try:
                logger.info("销毁vis")
                self.vis.destroy_window()
            except:
                pass

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        # 设置 OpenGL（提升兼容性）
        fmt = QSurfaceFormat()
        fmt.setVersion(3, 3)
        fmt.setProfile(QSurfaceFormat.OpenGLContextProfile.CoreProfile)
        fmt.setDepthBufferSize(24)
        QSurfaceFormat.setDefaultFormat(fmt)
        self.setWindowTitle("PcdViewer")
        self.resize(1920, 1080)

        self.point_cloud_widget = PointCloudWidget()
        self.setCentralWidget(self.point_cloud_widget)
        # self.create_menu()

    def create_menu(self):
        menubar = self.menuBar()
        file_menu = menubar.addMenu("文件")

        open_action = QAction("打开", self)
        open_action.setShortcut("Ctrl+O")
        open_action.triggered.connect(self.open_file)
        file_menu.addAction(open_action)

        exit_action = QAction("退出", self)
        exit_action.setShortcut("Ctrl+Q")
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

    def open_file(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "打开点云文件",
            "",
            "点云文件 (*.ply *.pcd);;所有文件 (*)"
        )
        if not file_path:
            return

        try:
            self.point_cloud_widget.load_point_cloud(file_path)
        except Exception as e:
            QMessageBox.critical(self, "错误", f"无法加载点云:\n{str(e)}")

    def closeEvent(self, event):
        """主窗口关闭事件"""
        # 可以在这里添加其他清理逻辑
        logger.info("关闭主窗")

        # 关闭点云widget
        if hasattr(self, 'point_cloud_widget'):
            self.point_cloud_widget.close()

        event.accept()
