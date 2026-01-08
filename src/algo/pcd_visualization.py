import open3d as o3d
import sys
import os
import numpy as np

def view_pcd_file_with_axis(file_path, frame_size=1.0):
    """
    使用 Open3D 库加载并可视化 PCD (Point Cloud Data) 文件，并显示笛卡尔坐标系。

    :param file_path: PCD 文件的路径。
    :param frame_size: 坐标系轴的长度。
    """
    if not os.path.exists(file_path):
        print(f"错误：文件未找到。请检查路径是否正确：{file_path}")
        return

    print(f"尝试加载点云文件：{file_path}...")
    
    try:
        # 1. 读取 PCD 文件
        pcd = o3d.io.read_point_cloud(file_path)
        
        if not pcd.has_points():
            print("错误：点云加载成功，但其中不包含任何点。")
            return
            
        print(f"点云加载成功！点数：{len(pcd.points)}")
        
        # 2. 创建坐标系
        # Open3D 提供了一个工厂函数来创建表示坐标系的 TriangleMesh。
        # 红色 = X 轴，绿色 = Y 轴，蓝色 = Z 轴。
        # frame_origin 设置坐标系的原点，这里默认是 (0, 0, 0)。
        mesh_frame = o3d.geometry.TriangleMesh.create_coordinate_frame(
            size=frame_size, 
            origin=[0.0, 0.0, 0.0]
        )
        
        # 提示：如果你的点云中心离原点很远，你可以将坐标系平移到点云的中心：
        # pcd_center = pcd.get_center()
        # mesh_frame.translate(pcd_center)
        
        # 3. 可视化
        # 将点云和坐标系（两种不同的几何体）一起放入 draw_geometries 的列表中。
        print(f"正在打开可视化窗口... 坐标系轴长：{frame_size}")
        print("按 'Q' 键关闭窗口。")
        
        o3d.visualization.draw_geometries(
            [pcd, mesh_frame],  # 将所有要显示的几何体放入列表中
            window_name="PCD 点云和坐标系",
            width=800,
            height=600
        )
        
        print("可视化完成。")
        
    except Exception as e:
        print(f"加载或可视化点云时发生错误：{e}")

# --- 主程序入口 ---
if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("使用方法：")
        print("  请在命令行中提供 PCD 文件的路径。")
        print("  示例：python view_pcd_with_axis.py /path/to/your/file.pcd")
        print("  （可选）您可以修改脚本中的 frame_size 变量来调整坐标系的大小。")
    else:
        pcd_file_path = sys.argv[1]
        # 默认坐标系轴长设为 1.0，你可以根据点云的尺寸调整这个值
        DEFAULT_FRAME_SIZE = 1.0 
        view_pcd_file_with_axis(pcd_file_path, DEFAULT_FRAME_SIZE)