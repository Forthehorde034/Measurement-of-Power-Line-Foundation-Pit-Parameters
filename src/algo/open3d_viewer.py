import open3d as o3d
import sys
import os
import numpy as np

def crop_pcd_by_bbox(file_path):
    """
    使用预定义的轴对齐边界框 (AABB) 裁剪点云。
    """
    if not os.path.exists(file_path):
        print(f"错误：文件未找到：{file_path}")
        return

    print(f"尝试加载点云文件：{file_path}...")
    pcd = o3d.io.read_point_cloud(file_path)
    if not pcd.has_points():
        print("错误：点云加载失败或不含点。")
        return
        
    print(f"原始点数：{len(pcd.points)}")
    
    # --- 裁剪参数设置（请根据您的基坑位置进行修改！） ---
    # 假设基坑在 (0, 0, 0) 附近，且范围是 10m x 10m x 5m
    
    # 最小坐标 (x_min, y_min, z_min)
    min_bound = np.array([-3.0, -3.0, -10.0]) 
    
    # 最大坐标 (x_max, y_max, z_max)
    max_bound = np.array([3.0, 3.0, 10.0])
    
    # 提示：您可以通过打印原始点云的边界来辅助确定范围：
    # print(f"原始点云最小边界: {pcd.get_min_bound()}")
    # print(f"原始点云最大边界: {pcd.get_max_bound()}")

    # --- 执行裁剪 ---
    # 1. 创建轴对齐边界框 (Axis Aligned Bounding Box)
    bbox = o3d.geometry.AxisAlignedBoundingBox(min_bound, max_bound)
    
    # 2. 裁剪点云
    pcd_cropped = pcd.crop(bbox)
    
    print(f"裁剪完成。裁剪后点数：{len(pcd_cropped.points)}")

    # --- 可视化 ---
    
    # 原始点云（灰色）
    pcd.paint_uniform_color([0.5, 0.5, 0.5]) 
    
    # 裁剪后的点云（绿色）
    pcd_cropped.paint_uniform_color([0.0, 1.0, 0.0]) 
    
    # 可视化裁剪后的点云和边界框
    print("正在打开可视化窗口... 绿色点为裁剪区域。")
    o3d.visualization.draw_geometries(
        [pcd_cropped, bbox],
        window_name="基于边界框的裁剪结果"
    )
    
    # --- 保存裁剪后的点云 ---
    output_file = file_path.replace(".pcd", "_cropped.pcd")
    o3d.io.write_point_cloud(output_file, pcd_cropped)
    print(f"裁剪后的点云已保存到: {output_file}")

def crop_pcd_interactively(file_path):
    """
    通过在可视化窗口中交互式选择点来裁剪点云。
    """
    if not os.path.exists(file_path):
        print(f"错误：文件未找到：{file_path}")
        return

    print(f"尝试加载点云文件：{file_path}...")
    pcd = o3d.io.read_point_cloud(file_path)
    if not pcd.has_points():
        print("错误：点云加载失败或不含点。")
        return
        
    print(f"原始点数：{len(pcd.points)}")
    
    print("\n--- 交互式裁剪说明 ---")
    print("1. 窗口弹出后，按 'P' 键进入拾取模式 (Picking)。")
    print("2. 使用鼠标左键或 Ctrl + 左键选择点云中的区域（如基坑）。")
    print("3. 按 'Shift + Q' 完成拾取并关闭窗口。")

    o3d.visualization.draw_geometries_with_editing([pcd])
    
# --- 主程序入口 ---
if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("使用方法：请在命令行中提供 PCD 文件的路径。")
    else:
        pcd_file_path = sys.argv[1]
        
        # 推荐使用边界框裁剪，因为它更稳定且可重复
        crop_pcd_by_bbox(pcd_file_path)


# 使用说明:
# python open3d_viewer.py pcd文件路径

#Python 版本3.6 或更高,建议使用 Python 3.6 ~ 3.12 版本区间。
#依赖库,open3d,用于点云加载、裁剪和可视化。numpy,用于定义边界框数组。sys, os用于命令行参数获取和文件路径操作。
#入参：
#file_path,str,输入：要加载的 PCD 文件路径。
#min_bound,np.array,"[-3.0, -3.0, -10.0]","代码中硬编码的轴对齐边界框 (AABB) 的最小坐标（Xmin, Ymin, Zmin）。"
#max_bound,np.array,"[3.0, 3.0, 10.0]","代码中硬编码的 AABB 的最大坐标（Xmax, Ymax, Zmax）。

#文件输出,裁剪后的点云将以原文件名 + _cropped.pcd 的格式保存（例如：input.pcd 保存为 input_cropped.pcd）。
#可视化,打开 Open3D 可视化窗口：原始点云显示为灰色，裁剪后的点云显示为绿色，并显示裁剪边界框（bbox）。
#程序功能,crop_pcd_interactively 函数提供了交互式裁剪的说明，但实际主要通过 crop_pcd_by_bbox 执行预设边界框裁剪。