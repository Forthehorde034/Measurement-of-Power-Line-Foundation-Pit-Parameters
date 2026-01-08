import numpy as np
import random
import open3d as o3d
import sys

# --- 辅助函数 1：三点拟合圆 (已优化数值稳定性) ---
def fit_circle_from_3_points(p1, p2, p3):
    """
    根据三个不共线的点来计算一个圆的圆心和半径。
    - 针对三点共线和数值溢出进行了鲁棒性处理。
    """
    # 转换为浮点数，防止后续计算中出现整数溢出
    p1, p2, p3 = np.array(p1, dtype=float), np.array(p2, dtype=float), np.array(p3, dtype=float)

    # 计算行列式 (det) 所需的中间变量
    temp = p2[0]**2 + p2[1]**2
    bc = (p1[0]**2 + p1[1]**2 - temp) / 2
    cd = (temp - p3[0]**2 - p3[1]**2) / 2
    det = (p1[0] - p2[0]) * (p2[1] - p3[1]) - (p2[0] - p3[0]) * (p1[1] - p2[1])

    # 检查三点共线 (如果行列式接近零，则认为共线)
    if abs(det) < 1.0e-6: 
        return None, None # 三点共线

    # 计算圆心坐标
    center_x = (bc * (p2[1] - p3[1]) - cd * (p1[1] - p2[1])) / det
    center_y = (cd * (p1[0] - p2[0]) - bc * (p2[0] - p3[0])) / det
    
    # 计算半径
    radius_sq = (p1[0] - center_x)**2 + (p1[1] - center_y)**2
    
    # 检查半径是否在合理范围内 (防止数值溢出或得到无效结果)
    if radius_sq < 1.0e-12: 
        radius = 0.0
    elif radius_sq > 1.0e10: # 如果半径平方超过 10^10，视为无效拟合
        return None, None
    else:
        radius = np.sqrt(radius_sq)

    return (center_x, center_y), radius

# --- 辅助函数 2：RANSAC 核心算法 ---
def ransac_circle_fit(points, iterations, threshold):
    """
    RANSAC 算法：从二维点云数据中拟合圆。
    
    参数:
    points (np.array): 包含 (x, y) 坐标的 NumPy 数组 (N, 2)。
    iterations (int): RANSAC 迭代次数 (已增加)。
    threshold (float): 点到圆周的最大距离，用于判定内点 (已放宽)。
    
    返回:
    tuple: (center_x, center_y, radius) 或 None。
    """
    best_circle = None
    best_inlier_count = 0
    num_points = points.shape[0]

    if num_points < 3:
        return None

    for _ in range(iterations):
        # 随机选择 3 个点
        sample_indices = random.sample(range(num_points), 3)
        p1, p2, p3 = points[sample_indices[0]], points[sample_indices[1]], points[sample_indices[2]]

        # 尝试拟合圆
        center, radius = fit_circle_from_3_points(p1, p2, p3)

        if center is None or radius is None:
            continue

        # 计算内点数量
        current_inlier_count = 0
        
        # 批量计算点到圆心的距离
        dist_to_center = np.sqrt((points[:, 0] - center[0])**2 + (points[:, 1] - center[1])**2)
        
        # 检查点到圆周的距离是否在阈值内
        if radius == 0:
             # 如果半径为 0，则检查点是否落在圆心附近
             inlier_mask = dist_to_center < threshold 
        else:
             inlier_mask = np.abs(dist_to_center - radius) < threshold
             
        current_inlier_count = np.sum(inlier_mask)
        
        # 更新最佳模型
        if current_inlier_count > best_inlier_count:
            best_inlier_count = current_inlier_count
            best_circle = (center[0], center[1], radius)
            
    # 如果找到的内点少于一个较低的百分比，也可以认为拟合失败，这里保持宽松处理
    # 只要找到了最佳模型，就返回它
    return best_circle

# --- 核心分析函数：基坑分层计算 ---
def analyze_pit_pcd(pcd_filepath, z_interval=1.0, slice_thickness=0.30, 
                    ransac_iterations=5000, ransac_threshold=0.2):
    """
    分析 PCD 文件，计算坑深、并按深度分层计算半径。
    坐标系假设: Z轴向下为正，原点(0,0,0)为坑口圆心。
    """
    
    # 1. 数据导入与转换
    print(f"1. 正在加载文件: {pcd_filepath}")
    pcd = o3d.io.read_point_cloud(pcd_filepath)
    if not pcd.has_points():
        return None, None, "错误: PCD 文件中没有点云数据。"
    
    all_points = np.asarray(pcd.points) # 形状 (N, 3)，即 (X, Y, Z)

    # 2. 计算坑深
    z_values = all_points[:, 2]
    # 过滤掉 Z<=0 的点（在 Z 向下的坐标系中，Z=0 是坑口）
    pit_points_mask = z_values > 0.01 
    pit_z_values = z_values[pit_points_mask]

    if pit_z_values.size == 0:
        return 0, None, "错误: Z轴正值区域（基坑内部）没有有效点云。"
        
    pit_depth = np.percentile(pit_z_values, 99.5)
    print(f"2. 估计坑深 (99.5% Z值): {pit_depth:.3f} 米")

    # 3. 定义分层深度
    z_min = 0.5   # 从 0.5m 深度开始切片
    z_max = pit_depth - 0.5 # 截止到离坑底 0.5m 处
    slice_centers = np.arange(z_min, z_max, z_interval)
    
    if slice_centers.size == 0:
        return pit_depth, None, "警告: 间隔或 Z 范围太小，无法分层计算半径。"

    # 4. 循环拟合
    results = [] # 存储 (Z, Radius, Center_X, Center_Y)
    
    print(f"3. 正在按 {z_interval}m 间隔分层拟合 ({slice_centers.size} 层)...")
    
    for z_center in slice_centers:
        min_z = z_center - slice_thickness / 2
        max_z = z_center + slice_thickness / 2
        
        mask = (all_points[:, 2] >= min_z) & (all_points[:, 2] <= max_z)
        sliced_points = all_points[mask]
        
        # 极低点数限制 (只有少于 3 个点时才跳过)
        if sliced_points.shape[0] < 3: 
            print(f"警告: Z={z_center:.2f}m 处点数不足 ({sliced_points.shape[0]} < 3)，跳过拟合。")
            continue
        
        # 调试信息
        print(f"DEBUG: 正在拟合 Z={z_center:.2f}m 处，点数: {sliced_points.shape[0]}")
        
        points_2d = sliced_points[:, [0, 1]] # 投影到 X-Y 平面
        
        # RANSAC 拟合
        fitted_circle = ransac_circle_fit(
            points_2d, 
            iterations=ransac_iterations, 
            threshold=ransac_threshold
        )
        
        if fitted_circle is not None:
            center_x, center_y, radius = fitted_circle
            results.append((z_center, radius, center_x, center_y))
    
    if not results:
        # 在返回错误信息时，依然返回已计算出的深度，方便调试
        return pit_depth, None, "错误: RANSAC 拟合在所有切片上都失败了。"

    # 5. 汇总结果
    results_array = np.array(results)
    
    avg_radius = np.mean(results_array[:, 1])
    max_radius = np.max(results_array[:, 1])

    avg_center_x = np.mean(results_array[:, 2])
    avg_center_y = np.mean(results_array[:, 3])
    
    print("4. 分析完成。")
    return pit_depth, avg_radius, max_radius, avg_center_x, avg_center_y, results_array


# --- 运行示例 (请根据你的数据调整参数) ---
if __name__ == '__main__':
    # <--- 此处为修改后的代码：从命令行参数获取文件路径 --->
    if len(sys.argv) < 2:
        print("使用方法：请在命令行中提供 PCD 文件的路径。")
        print("示例：python final_radium_compute.py /path/to/your/file.pcd")
        sys.exit(1) # 退出程序，提示用户提供文件路径
        
    PCD_FILE = sys.argv[1] # 从命令行参数获取 PCD 文件路径
    # <--- 修改结束 --->
    try:
        # 参数设定: 提高鲁棒性
        # thickness=0.30m, threshold=0.2m, iterations=5000 
        return_values = analyze_pit_pcd(
            pcd_filepath=PCD_FILE,
            z_interval=1.0,           
            slice_thickness=0.30,      # 切片厚度 30cm (增加点云数量)
            ransac_iterations=5000,    # 增加迭代次数 (克服共线问题)
            ransac_threshold=0.2       # 内点阈值 20cm (容忍形状不规则性)
        )

        if len(return_values) == 6:
            pit_depth, avg_radius, max_radius, avg_center_x, avg_center_y, detailed_results = return_values
            
            print("\n================== 最终计算结果 ==================")
            print(f"**总 坑 深 (Z轴最大值): {pit_depth:.3f} 米**")
            print(f"**基坑 平均半径 (R): {avg_radius:.3f} 米**")
            print(f"**基坑 最大半径 (R_max): {max_radius:.3f} 米**")
            print("--- 校验信息 ---")
            print(f"平均圆心偏移 (X, Y): ({avg_center_x:.3f}m, {avg_center_y:.3f}m)")
            print(f"总计成功拟合切片数: {len(detailed_results)}")
            
            # 打印详细分层半径
            print("\n详细分层半径 (Z, R):")
            for z, r, cx, cy in detailed_results:
                print(f"  Z={z:.2f}m: R={r:.3f}m, 拟合圆心({cx:.3f}, {cy:.3f})")

        elif len(return_values) == 3:
            exit_depth, exit_radius, error_message = return_values
            print("\n================== 算法提前退出 ==================")
            print(f"**错误/警告信息:** {error_message}")
            if exit_depth is not None:
                print(f"已计算出的最大 Z 深度为: {exit_depth:.3f} 米")
                
        else:
            print(f"\n未知返回数量: 接收到 {len(return_values)} 个值。")

    except Exception as e:
        print(f"\n执行过程中发生异常: {e}")



#类别,要求,说明
#Python版本：3.6 或更高,建议使用 Python 3.6 ~ 3.12 版本区间。
#依赖库：numpy,用于高效的数值计算和数组操作。open3d,用于 PCD 文件的导入和点云数据的处理。random,用于 RANSAC 算法中的随机采样。
#入参：
#pcd_filepath,str,输入：要加载的 PCD 文件路径。
#z_interval,float,输入：切片间隔，单位为米。
#slice_thickness,float,输入：切片厚度，单位为米。
#ransac_iterations,int,输入：RANSAC 迭代次数。
#ransac_threshold,float,输入：点到圆周的最大距离，用于判定内点。

#文件输出：
#1. 计算结果：
#总坑深：Z轴最大值。
#基坑平均半径：R。
#基坑最大半径：R_max。
#平均圆心偏移：(X, Y)。

#使用:
#python final_radium_compute.py PCD文件路径
#备注:
#1. 请确保输入的 PCD 文件路径正确。
#2. 如果拟合失败，请检查输入参数是否合理。
#3. 如果拟合结果不理想，请尝试调整参数。
