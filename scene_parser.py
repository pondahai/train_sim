# scene_parser.py
import os
import numpy as np
from track import StraightTrack, CurveTrack, Track

class Scene:
    """儲存場景物件"""
    def __init__(self):
        self.track = Track()
        self.buildings = [] # [ (type, x, y, z, rx, ry, rz, w, d, h, tex_id), ... ]
        self.trees = []     # [ (x, y, z, height), ... ]
        self.cylinders = [] # [ (type, x, y, z, rx, ry, rz, radius, h, tex_id), ... ]
        # 可以添加其他物件類型

    def clear(self):
        self.track.clear()
        self.buildings = []
        self.trees = []
        self.cylinders = []

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
    """解析 scene.txt 檔案 (增加坡度支持)"""
    global current_scene, texture_loader
    if texture_loader is None:
        print("錯誤：Texture Loader 尚未設定！")
        return None

    new_scene = Scene()
    current_pos = np.array([0.0, 0.0, 0.0], dtype=float)
    current_angle_rad = 3.14/2 # 指向 Z 軸正方向

    try:
        with open(filepath, 'r', encoding="utf8") as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                if not line or line.startswith('#'):
                    continue

                parts = line.split()
                command = parts[0].lower()

                try:
                    if command == "straight":
                        # straight <length> [gradient_permille]
                        length = float(parts[1])
                        gradient_permille = float(parts[2]) if len(parts) > 2 else 0.0 # 可選坡度
                        segment = StraightTrack(current_pos, current_angle_rad, length, gradient_permille)
                        new_scene.track.add_segment(segment)
                        current_pos = segment.end_pos # 更新為包含 Y 的 3D 坐標
                        current_angle_rad = segment.end_angle_rad # 水平角度不變
                    elif command == "curve":
                        # curve <radius> <angle_deg> [gradient_permille]
                        radius = float(parts[1])
                        angle_deg = float(parts[2])
                        gradient_permille = float(parts[3]) if len(parts) > 3 else 0.0 # 可選坡度
                        segment = CurveTrack(current_pos, current_angle_rad, radius, angle_deg, gradient_permille)
                        new_scene.track.add_segment(segment)
                        current_pos = segment.end_pos # 更新為包含 Y 的 3D 坐標
                        current_angle_rad = segment.end_angle_rad # 更新水平角度
                    elif command == "building":
                        # building <x> <y> <z> <rx> <ry> <rz> <w> <d> <h> [texture]
                        x, y, z = map(float, parts[1:4])
                        rx, ry, rz = map(float, parts[4:7])
                        w, d, h = map(float, parts[7:10])
                        tex_file = parts[10] if len(parts) > 10 else "building.png" # 預設紋理
                        tex_id = texture_loader.load_texture(tex_file)
                        new_scene.buildings.append(("building", x, y, z, rx, ry, rz, w, d, h, tex_id))
                    elif command == "cylinder":
                         # cylinder <x> <y> <z> <rx> <ry> <rz> <radius> <height> [texture]
                        x, y, z = map(float, parts[1:4])
                        rx, ry, rz = map(float, parts[4:7])
                        radius = float(parts[7])
                        height = float(parts[8])
                        tex_file = parts[9] if len(parts) > 9 else "metal.png" # 預設紋理
                        tex_id = texture_loader.load_texture(tex_file)
                        new_scene.cylinders.append(("cylinder", x, y, z, rx, ry, rz, radius, height, tex_id))

                    elif command == "tree":
                        # tree <x> <y> <z> <height>
                        x, y, z = map(float, parts[1:4])
                        height = float(parts[4])
                        new_scene.trees.append((x, y, z, height))
                    else:
                        print(f"警告: 第 {line_num} 行無法識別的指令 '{command}'")

                except (IndexError, ValueError) as e:
                    print(f"警告: 解析第 {line_num} 行時發生錯誤 ('{line}'): {e}")

        print(f"場景檔案 '{filepath}' 解析完成.")
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