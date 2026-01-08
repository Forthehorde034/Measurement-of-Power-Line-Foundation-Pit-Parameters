import numpy as np
import random
import open3d as o3d
import os
import sys  
from collections import namedtuple

# --- 1. 定义返回结构：新增 Min_Diameter ---
PitMetrics = namedtuple('PitMetrics', ['depth', 'avg_diameter', 'min_diameter', 'verticality_deg'])

# --- Part 1: RANSAC 辅助函数 (保持不变) ---
def fit_circle_from_3_points(p1, p2, p3):
    p1, p2, p3 = np.array(p1, dtype=float), np.array(p2, dtype=float), np.array(p3, dtype=float)
    temp = p2[0]**2 + p2[1]**2
    bc = (p1[0]**2 + p1[1]**2 - temp) / 2
    cd = (temp - p3[0]**2 - p3[1]**2) / 2
    det = (p1[0] - p2[0]) * (p2[1] - p3[1]) - (p2[0] - p3[0]) * (p1[1] - p2[1])
    if abs(det) < 1.0e-6: 
        return None, None
    center_x = (bc * (p2[1] - p3[1]) - cd * (p1[1] - p2[1])) / det
    center_y = (cd * (p1[0] - p2[0]) - bc * (p2[0] - p3[0])) / det
    radius_sq = (p1[0] - center_x)**2 + (p1[1] - center_y)**2
    if radius_sq < 1.0e-12 or radius_sq > 1.0e10: 
        return None, None
    else:
        radius = np.sqrt(radius_sq)
    return (center_x, center_y), radius

def ransac_circle_fit(points, iterations, threshold):
    best_circle = None
    best_inlier_count = 0
    num_points = points.shape[0]
    if num_points < 3:
        return None
    for _ in range(iterations):
        sample_indices = random.sample(range(num_points), 3)
        p1, p2, p3 = points[sample_indices[0]], points[sample_indices[1]], points[sample_indices[2]]
        center, radius = fit_circle_from_3_points(p1, p2, p3)
        if center is None or radius is None:
            continue
        dist_to_center = np.sqrt((points[:, 0] - center[0])**2 + (points[:, 1] - center[1])**2)
        inlier_mask = np.abs(dist_to_center - radius) < threshold
        current_inlier_count = np.sum(inlier_mask)
        if current_inlier_count > best_inlier_count:
            best_inlier_count = current_inlier_count
            best_circle = (center[0], center[1], radius)
    return best_circle

# --- Part 2: 边界框裁剪函数 (保持不变) ---
def crop_pcd_by_bbox(pcd_object, x_min, x_max, y_min, y_max, z_min, z_max):
    if not pcd_object.has_points():
        return None
    min_bound = np.array([x_min, y_min, z_min]) 
    max_bound = np.array([x_max, y_max, z_max])
    bbox = o3d.geometry.AxisAlignedBoundingBox(min_bound, max_bound)
    pcd_cropped = pcd_object.crop(bbox)
    print(f"裁剪完成。原始点数: {len(pcd_object.points)}, 裁剪后点数: {len(pcd_cropped.points)}")
    if not pcd_cropped.has_points():
        return None
    return pcd_cropped

# --- Part 3: 核心功能函数 (新增最小直径计算) ---
def analyze_and_calculate_metrics(pcd_object, analysis_params):
    z_interval = analysis_params['z_interval']
    slice_thickness = analysis_params['slice_thickness']
    ransac_iterations = analysis_params['ransac_iterations']
    ransac_threshold = analysis_params['ransac_threshold']

    if pcd_object is None or not pcd_object.has_points():
        raise ValueError("错误: 传入的点云对象为空或不含点。")
        
    all_points = np.asarray(pcd_object.points)

    # 1. 计算总坑深 (Depth)
    z_values = all_points[:, 2]
    pit_points_mask = z_values > 0.01 
    pit_z_values = z_values[pit_points_mask]
    if pit_z_values.size == 0:
        raise ValueError("错误: Z轴正值区域（基坑内部）没有有效点云，无法计算深度。")
        
    depth = np.percentile(pit_z_values, 99.5)
    print(f"1. 估计总坑深 (Depth): {depth:.3f} 米")

    # 2. 深度分层和拟合
    z_min = 0.5   
    z_max = depth - 0.5 
    slice_centers = np.arange(z_min, z_max, z_interval)
    
    if slice_centers.size == 0:
        print("警告: 间隔或 Z 范围太小，无法分层计算半径。")
        return PitMetrics(depth, None, None, None) 

    results = [] 
    
    for z_center in slice_centers:
        min_z = z_center - slice_thickness / 2
        max_z = z_center + slice_thickness / 2
        mask = (all_points[:, 2] >= min_z) & (all_points[:, 2] <= max_z)
        sliced_points = all_points[mask]
        
        if sliced_points.shape[0] < 3: 
            continue
        
        points_2d = sliced_points[:, [0, 1]] 
        
        fitted_circle = ransac_circle_fit(
            points_2d, iterations=ransac_iterations, threshold=ransac_threshold
        )
        
        if fitted_circle is not None:
            center_x, center_y, radius = fitted_circle
            results.append((z_center, radius, center_x, center_y))
    
    if not results:
        raise ValueError("错误: RANSAC 拟合在所有切片上都失败了，无法计算直径和垂直度。")

    results_array = np.array(results) # (Z, Radius, Center_X, Center_Y)

    # 3. 计算平均直径和最小直径
    all_radii = results_array[:, 1]
    
    avg_d = np.mean(all_radii) * 2
    min_d = np.min(all_radii) * 2
    
    print("2. 直径计算完成。")

    # 4. 计算垂直度 (Verticality)
    center_points = results_array[:, [2, 3, 0]] # (X, Y, Z)
    center_mean = np.mean(center_points, axis=0)
    center_points_centered = center_points - center_mean
    U, S, V = np.linalg.svd(center_points_centered)
    axis_vector = V[0] 
    if axis_vector[2] < 0:
        axis_vector = -axis_vector
    z_axis = np.array([0.0, 0.0, 1.0])
    dot_product = np.dot(axis_vector, z_axis)
    angle_rad = np.arccos(np.clip(dot_product, -1.0, 1.0))
    verticality_deg = np.degrees(angle_rad)
    
    print(f"3. 垂直度计算完成。拟合中心轴与Z轴夹角: {verticality_deg:.3f} 度")

    return PitMetrics(
        depth=depth,
        avg_diameter=avg_d,
        min_diameter=min_d,
        verticality_deg=verticality_deg
    )


# --- Part 4: 主执行逻辑 (保持不变) ---
def calculate_pit_pipeline(pcd_filepath, crop_params, analysis_params):
    try:
        print(f"1. 尝试加载原始文件: {pcd_filepath}")
        pcd_original = o3d.io.read_point_cloud(pcd_filepath)
        if not pcd_original.has_points():
            raise FileNotFoundError("错误: PCD 文件加载失败或不含点。")
            
        print("--- 裁剪预处理 ---")
        pcd_cropped = crop_pcd_by_bbox(pcd_original, **crop_params)
        
        if pcd_cropped is None:
            raise ValueError("流程中止：裁剪后点云为空。请检查 CROP_PARAMS。")

        print("\n================== 开始基坑分析 ==================")
        metrics = analyze_and_calculate_metrics(pcd_cropped, analysis_params)
        
        return metrics

    except FileNotFoundError as e:
        print(e)
        return None
    except ValueError as e:
        print(e)
        return None
    except Exception as e:
        print(f"\n执行过程中发生异常: {e}")
        return None


# --- Part 5: 新的包装函数 (内置 30m 规模参数) ---
def quick_analyze_pit(pcd_filepath):
    """
    快速执行基坑点云分析，使用内置的默认参数 (适应 30m 规模)。
    """
    # --- 裁剪参数 (适应 30m 规模) ---
    CROP_PARAMS = {
        'x_min': -5.0, 'x_max': 5.0,      
        'y_min': -5.0, 'y_max': 5.0,      
        'z_min': -1.0, 'z_max': 40.0      # 调整 Z 轴范围以适应 30m 深度
    }
    
    # --- 分析参数 ---
    ANALYSIS_PARAMS = {
        'z_interval': 1.0,           
        'slice_thickness': 0.30,     
        'ransac_iterations': 5000,
        'ransac_threshold': 0.2
    }
    
    print("--- 正在使用内置参数进行分析 ---")
    
    return calculate_pit_pipeline(pcd_filepath, CROP_PARAMS, ANALYSIS_PARAMS)

def calculate_pit_pipeline_pcd_data(pcd: o3d.geometry.PointCloud, crop_params, analysis_params):
    """
    整个基坑分析流程的入口函数。
    返回: (metrics, cropped_pcd) 元组，如果失败则返回 (None, None)
    """
    # --- 裁剪参数 (默认值，您可以根据实际需求调整) ---
    CROP_PARAMS = {
        'x_min': -4.0, 'x_max': 4.0,
        'y_min': -4.0, 'y_max': 4.0,
        'z_min': -1.0, 'z_max': 15.0  # Z轴向下为正
    }

    # --- 分析参数 (默认值，您可以根据实际需求调整) ---
    ANALYSIS_PARAMS = {
        'z_interval': 1.0,
        'slice_thickness': 0.30,
        'ransac_iterations': 5000,
        'ransac_threshold': 0.2
    }

    # 使用三目运算符选择裁剪参数
    crop_params = crop_params if crop_params is not None else CROP_PARAMS
    analysis_params = analysis_params if analysis_params is not None else ANALYSIS_PARAMS

    print("--- 正在使用内置参数进行分析 ---")

    try:
        print(f"1. 尝试加载原始数据")
        pcd_original = pcd
        if not pcd_original.has_points():
            raise FileNotFoundError("错误: PCD 文件加载失败或不含点。")

        # 步骤 A: 裁剪
        print("--- 裁剪预处理 ---")
        pcd_cropped = crop_pcd_by_bbox(pcd_original, **crop_params)

        if pcd_cropped is None:
            raise ValueError("流程中止：裁剪后点云为空。请检查 CROP_PARAMS。")

        # 步骤 B: 分析
        print("\n================== 开始基坑分析 ==================")
        metrics = analyze_and_calculate_metrics(pcd_cropped, analysis_params)

        # 返回 metrics 和裁剪后的点云
        return metrics, pcd_cropped

    except FileNotFoundError as e:
        print(e)
        return None, None
    except ValueError as e:
        print(e)
        return None, None
    except Exception as e:
        print(f"\n执行过程中发生异常: {e}")
        return None, None


# --- 运行示例 (新增垂直度合格性判断) ---

if __name__ == '__main__':
    # 从命令行参数获取文件路径
    if len(sys.argv) < 2:
        print("使用方法：请在命令行中提供 PCD 文件的路径。")
        print("示例：python pit_pipeline_analyze.py /path/to/your/file.pcd")
        sys.exit(1)
        
    PCD_FILE = sys.argv[1] 

    final_metrics = quick_analyze_pit(PCD_FILE)

    if final_metrics:
        # --- 垂直度合格性判断逻辑 ---
        # 允许的最大角度：tan(theta) = 0.01 (1% 偏差)
        # 转换为度：theta_max = degrees(arctan(0.01)) ≈ 0.573 度
        MAX_VERTICALITY_DEG = np.degrees(np.arctan(0.01))
        
        verticality_status = "合格 (Conforming)"
        if final_metrics.verticality_deg > MAX_VERTICALITY_DEG:
            verticality_status = "不合格 (Non-conforming)"
        
        print("\n================== 最终计算结果 ==================")
        print(f"**总 坑 深 (Depth): {final_metrics.depth:.3f} 米**")
        print(f"**基坑 平均直径 (Avg. D): {final_metrics.avg_diameter:.3f} 米**")
        print(f"**基坑 最小直径 (Min. D): {final_metrics.min_diameter:.3f} 米**")
        print("--- 垂直度校验 ---")
        print(f"**基坑 垂直度误差: {final_metrics.verticality_deg:.3f} 度**")
        print(f"**规范要求 (Q/GDW 10115-2022): 偏差 ≤ 桩长 1% (即 ≤ {MAX_VERTICALITY_DEG:.3f} 度)**")
        print(f"**垂直度判断结果: {verticality_status}**")


#类别,要求,说明
#Python 版本,3.6 或更高,由于使用了 open3d 和现代 Python 语法，建议使用 Python 3.6 ~ 3.12 版本区间。
#依赖库,numpy,用于高效的数值计算和数组操作。open3d,用于 PCD 文件的导入、点云对象操作（裁剪）和点云处理。random,用于 RANSAC 算法中的随机采样。os,用于操作系统路径处理。


#算法总览与执行流程
#主程序 (if __name__ == '__main__':) 遵循以下流水线步骤：

#加载文件：读取 PCD_FILE 指定的点云文件。

#裁剪预处理：调用 crop_pcd_by_bbox 函数，使用 CROP_PARAMS 中定义的边界框裁剪点云。

#核心分析：将裁剪后的点云对象传递给 analyze_pit_pcd_object 函数，使用 ANALYSIS_PARAMS 进行深度分层和圆拟合。

#结果输出：打印坑深、平均半径、最大半径和详细的分层拟合结果。

#CROP_PARAMS中参数名,所在位置,类型,示例值,说明
#"x_min, x_max",CROP_PARAMS,float,"-4.0, 4.0",裁剪区域的 X 轴最小/最大坐标。
#"y_min, y_max",CROP_PARAMS,float,"-4.0, 4.0",裁剪区域的 Y 轴最小/最大坐标。
#"z_min, z_max",CROP_PARAMS,float,"-1.0, 15.0",裁剪区域的 Z 轴最小/最大坐标。请注意 Z 轴向下为正。

#ANALYSIS_PARAMS中参数名,所在位置,类型,示例值,说明
#"z_interval",ANALYSIS_PARAMS,float,"1.0",切片间隔，单位为米。
#"slice_thickness",ANALYSIS_PARAMS,float,"0.30",切片厚度，单位为米。
#"ransac_iterations",ANALYSIS_PARAMS,int,"5000",RANSAC 迭代次数。
#"ransac_threshold",ANALYSIS_PARAMS,float,"0.2",点到圆周的最大距离，用于判定内点。

#返回值,类型,说明
#1,float,pit_depth (总坑深)：点云中 Z 坐标的第 99.5 百分位值，代表基坑的最大有效深度。
#2,float,avg_radius (平均半径)：所有成功拟合的切片半径的平均值。
#3,float,max_radius (最大半径)：所有成功拟合的切片半径中的最大值。
#4,float,avg_center_x (平均圆心 X)：所有切片拟合圆心 X 坐标的平均值（用于校验原点定位）。
#5,float,avg_center_y (平均圆心 Y)：所有切片拟合圆心 Y 坐标的平均值。
#6,np.array,"detailed_results (详细结果)：一个 N×4 的数组，每行包含 (Z, Radius, Center_X, Center_Y)，记录了每个有效切片的详细拟合数据。