# scene_parser.py
import os
import numpy as np
import math # <-- Add math import for radians conversion and degrees
from track import StraightTrack, CurveTrack, Track

class Scene:
    """儲存場景物件"""
    def __init__(self):
        self.track = Track()
        # Store ABSOLUTE world coordinates and rotations
        self.buildings = [] # [ (type, world_x, world_y, world_z, rx, abs_ry, rz, w, d, h, tex_id), ... ]
        self.trees = []     # [ (world_x, world_y, world_z, height), ... ]
        self.cylinders = [] # [ (type, world_x, world_y, world_z, rx, abs_ry, rz, radius, h, tex_id), ... ]
        # Store the explicit start position/angle if provided
        self.start_position = np.array([0.0, 0.0, 0.0], dtype=float)
        self.start_angle_deg = 0.0 # Store in degrees for potential reference

    def clear(self):
        self.track.clear()
        self.buildings = []
        self.trees = []
        self.cylinders = []
        self.start_position = np.array([0.0, 0.0, 0.0], dtype=float)
        self.start_angle_deg = 0.0

# --- Global state for scene parsing ---
scene_file_path = "scene.txt"
last_modified_time = 0
current_scene = Scene()
# --- Texture loading dependency ---
texture_loader = None # Will be set by main.py

def set_texture_loader(loader):
    global texture_loader
    texture_loader = loader

def parse_scene_file(filepath):
    """
    解析 scene.txt 檔案。
    - 物件 (building, cylinder, tree) 的 x,y,z 是相對於其前面軌道段起點的偏移。
    - 物件 (building, cylinder) 的 ry 是相對於其前面軌道段起始角度的相對旋轉。
    - 若物件定義在任何軌道段之前，則相對於世界原點 (0,0,0) 和 0 度角。
    """
    global current_scene, texture_loader
    if texture_loader is None:
        print("錯誤：Texture Loader 尚未設定！")
        return None

    new_scene = Scene()

    # --- State for track building ---
    # current_pos/angle track the END of the last segment, ready for the NEXT segment
    current_pos = np.array([0.0, 0.0, 0.0], dtype=float)
    current_angle_rad = 0 # Default angle is 0 (along +X axis) as per common convention

    # --- State for relative object placement ---
    # relative_origin_pos/angle track the START of the segment PRECEDING the object
    relative_origin_pos = np.array([0.0, 0.0, 0.0], dtype=float)
    relative_origin_angle_rad = 0.5*math.pi # Default 0 angle

    start_cmd_found = False # Flag to store if start was explicitly set

    try:
        with open(filepath, 'r', encoding="utf8") as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                if not line or line.startswith('#'):
                    continue

                parts = line.split()
                command = parts[0].lower()

                try:
                    # --- Track and Start Commands (Update BOTH current state and relative origin) ---
                    if command == "start":
                        if len(parts) < 5:
                             print(f"警告: 第 {line_num} 行 'start' 指令參數不足。格式: start x y z angle_deg")
                             continue
                        x, y, z = map(float, parts[1:4])
                        angle_deg = float(parts[4])
                        angle_rad = math.radians(angle_deg)

                        # Update track building state
                        current_pos[:] = [x, y, z]
                        current_angle_rad = angle_rad

                        # Update relative origin state for subsequent objects
                        relative_origin_pos[:] = current_pos
                        relative_origin_angle_rad = current_angle_rad

                        # Record scene start info
                        new_scene.start_position[:] = [x, y, z]
                        new_scene.start_angle_deg = angle_deg
                        start_cmd_found = True
                        print(f"場景起始點設定: pos=({x:.2f}, {y:.2f}, {z:.2f}), angle={angle_deg:.2f}°")

                    elif command == "straight" or command == "curve":
                        if not start_cmd_found and not new_scene.track.segments:
                             print(f"提示: 未找到 'start' 指令，軌道將從預設位置 (0,0,0) 角度 0 開始。")

                        # --- Set relative origin BEFORE creating segment ---
                        # The start of this segment becomes the relative origin for objects FOLLOWING it
                        relative_origin_pos[:] = current_pos # Use the current start position
                        relative_origin_angle_rad = current_angle_rad # Use the current start angle

                        # --- Create the track segment ---
                        segment = None
                        if command == "straight":
                            # straight <length> [gradient_permille]
                            length = float(parts[1])
                            gradient_permille = float(parts[2]) if len(parts) > 2 else 0.0
                            segment = StraightTrack(current_pos, current_angle_rad, length, gradient_permille)
                        elif command == "curve":
                            # curve <radius> <angle_deg> [gradient_permille]
                            radius = float(parts[1])
                            angle_deg = float(parts[2])
                            gradient_permille = float(parts[3]) if len(parts) > 3 else 0.0
                            segment = CurveTrack(current_pos, current_angle_rad, radius, angle_deg, gradient_permille)

                        if segment:
                            new_scene.track.add_segment(segment)
                            # --- Update track building state for the NEXT segment ---
                            current_pos = segment.end_pos # Update to the end of the created segment
                            current_angle_rad = segment.end_angle_rad # Update angle as well

                    # --- Object Placement Commands (Use relative origin) ---
                    elif command == "building":
                        # building <rel_x> <rel_y> <rel_z> <rx> <rel_ry> <rz> <w> <d> <h> [texture]
                        rel_x, rel_y, rel_z = map(float, parts[1:4])
                        rx_deg, rel_ry_deg, rz_deg = map(float, parts[4:7])
                        w, d, h = map(float, parts[7:10])
                        tex_file = parts[10] if len(parts) > 10 else "building.png"
                        tex_id = texture_loader.load_texture(tex_file)

                        # --- *** 核心修改：計算旋轉後的偏移量 *** ---
                        origin_angle = relative_origin_angle_rad
                        cos_a = math.cos(origin_angle)
                        sin_a = math.sin(origin_angle)

                        # 假設 rel_x 是軌道右側，rel_z 是軌道前方
                        # 計算世界坐標系中的偏移向量
                        world_offset_x = rel_z * cos_a + rel_x * sin_a # 旋轉 rel_x, rel_z
                        world_offset_y = rel_y # Y 軸通常直接對應世界 Y
                        world_offset_z = rel_z * sin_a - rel_x * cos_a # 旋轉 rel_x, rel_z

                        # 計算最終的絕對世界位置
                        world_x = relative_origin_pos[0] + world_offset_x
                        world_y = relative_origin_pos[1] + world_offset_y
                        world_z = relative_origin_pos[2] + world_offset_z
                        # --- *** 修改結束 *** ---
                        
                        # Calculate absolute world Y rotation
                        absolute_ry_deg = math.degrees(-relative_origin_angle_rad) + rel_ry_deg - 90

                        new_scene.buildings.append(
                            ("building", world_x, world_y, world_z,
                             rx_deg, absolute_ry_deg, rz_deg, # Use absolute ry
                             w, d, h, tex_id)
                        )

                    elif command == "cylinder":
                        # cylinder <rel_x> <rel_y> <rel_z> <rx> <rel_ry> <rz> <radius> <height> [texture]
                        rel_x, rel_y, rel_z = map(float, parts[1:4])
                        rx_deg, rel_ry_deg, rz_deg = map(float, parts[4:7])
                        radius = float(parts[7])
                        height = float(parts[8])
                        tex_file = parts[9] if len(parts) > 9 else "metal.png"
                        tex_id = texture_loader.load_texture(tex_file)

                        # --- *** 核心修改：計算旋轉後的偏移量 *** ---
                        origin_angle = relative_origin_angle_rad
                        cos_a = math.cos(origin_angle)
                        sin_a = math.sin(origin_angle)
                        world_offset_x = rel_z * cos_a + rel_x * sin_a
                        world_offset_y = rel_y
                        world_offset_z = rel_z * sin_a - rel_x * cos_a
                        world_x = relative_origin_pos[0] + world_offset_x
                        world_y = relative_origin_pos[1] + world_offset_y
                        world_z = relative_origin_pos[2] + world_offset_z
                        # --- *** 修改結束 *** ---
                        
                        # Calculate absolute world Y rotation
                        absolute_ry_deg = math.degrees(-relative_origin_angle_rad) + rel_ry_deg - 90
#                         absolute_rz_deg = math.degrees(-relative_origin_angle_rad) + rel_rz_deg

                        new_scene.cylinders.append(
                            ("cylinder", world_x, world_y, world_z,
                             rx_deg, rz_deg, absolute_ry_deg, # Use absolute ry
                             radius, height, tex_id)
                        )

                    elif command == "tree":
                        # tree <rel_x> <rel_y> <rel_z> <height>
                        rel_x, rel_y, rel_z = map(float, parts[1:4])
                        height = float(parts[4])

                        # --- *** 核心修改：計算旋轉後的偏移量 *** ---
                        origin_angle = relative_origin_angle_rad
                        cos_a = math.cos(origin_angle)
                        sin_a = math.sin(origin_angle)
                        world_offset_x = rel_z * cos_a + rel_x * sin_a
                        world_offset_y = rel_y
                        world_offset_z = rel_z * sin_a - rel_x * cos_a
                        world_x = relative_origin_pos[0] + world_offset_x
                        world_y = relative_origin_pos[1] + world_offset_y
                        world_z = relative_origin_pos[2] + world_offset_z
                        # --- *** 修改結束 *** ---
                        
                        new_scene.trees.append((world_x, world_y, world_z, height))

                    else:
                        print(f"警告: 第 {line_num} 行無法識別的指令 '{command}'")

                except (IndexError, ValueError) as e:
                    print(f"警告: 解析第 {line_num} 行時發生錯誤 ('{line}'): {e}")

        # If no start command was found, set default scene start info
        if not start_cmd_found:
            new_scene.start_position = np.array([0.0, 0.0, 0.0], dtype=float)
            new_scene.start_angle_deg = 0.0
            # Hint was already printed if needed

        print(f"場景檔案 '{filepath}' 解析完成 (使用相對坐標系).")
        return new_scene

    except FileNotFoundError:
        print(f"錯誤: 場景檔案 '{filepath}' 不存在.")
        return None
    except Exception as e:
        print(f"讀取或解析場景檔案 '{filepath}' 時發生未知錯誤: {e}")
        return None

def load_scene(force_reload=False):
    """載入或重新載入場景檔案"""
    global last_modified_time, current_scene, scene_file_path
    try:
        current_mod_time = os.path.getmtime(scene_file_path)
        if force_reload or current_mod_time != last_modified_time:
            print(f"偵測到場景檔案變更或強制重新載入 '{scene_file_path}'...")
            # 清除舊資源 (尤其是紋理)
            if texture_loader:
                texture_loader.clear_texture_cache()

            new_scene_data = parse_scene_file(scene_file_path)
            if new_scene_data:
                current_scene = new_scene_data # 替換場景
                last_modified_time = current_mod_time
                print("場景已成功載入/重新載入.")
                return True # 表示已重新載入
            else:
                print("場景載入失敗，保留舊場景.")
                # 如果解析失敗，保留舊場景，但不更新時間戳，以便下次嘗試
                return False
        return False # 表示未重新載入
    except FileNotFoundError:
        print(f"錯誤: 場景檔案 '{scene_file_path}' 在檢查更新時未找到。")
        if not current_scene.track.segments: # 如果連初始場景都沒有，則清空
             current_scene.clear()
        last_modified_time = 0 # 重置時間戳
        return True # 表示需要處理變化（場景消失）
    except Exception as e:
        print(f"檢查場景檔案更新時發生錯誤: {e}")
        return False

def get_current_scene():
    """獲取當前載入的場景"""
    global current_scene
    return current_scene