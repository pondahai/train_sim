# scene_parser.py
import os
import numpy as np
import numpy as math # Keep consistent
# import math # Original import removed
from track import StraightTrack, CurveTrack, Track, TrackSegment

# --- Texture loading dependency ---
texture_loader = None
# --- REMOVED: Renderer module dependency ---

def set_texture_loader(loader):
    """Sets the texture loader instance to be used by the parser."""
    global texture_loader
    texture_loader = loader

# --- REMOVED: set_renderer_module function ---

# --- Command Hints Dictionary (Update) ---
# Used by the editor to display parameter names
COMMAND_HINTS = {
    "map": ["    cmd    ", "file", "cx", "cz", "scale"],
    "start": ["    cmd    ", "x", "y", "z", "angle°"],
    "skybox": ["    cmd    ", "base_name"], # <--- NEW: Skybox (expects base name for 6 textures)
    "skydome": ["    cmd    ", "texture_file"], # <--- NEW: Skydome (expects single texture file)
    "straight": ["    cmd    ", "length", "grad‰"],
    "curve": ["    cmd    ", "radius", "angle°", "grad‰"],
    "building": ["    cmd    ", "rel_x", "rel_y", "rel_z", "rx°", "rel_ry°", "rz°", "w", "d", "h", "tex?", "uOf?", "vOf?", "tAng°?", "uvMd?", "uSc?", "vSc?"],
    "cylinder": ["    cmd    ", "rel_x", "rel_y", "rel_z", "rx°", "rel_ry°", "rz°", "rad", "h", "tex?", "uOf?", "vOf?", "tAng°?", "uvMd?", "uSc?", "vSc?"],
    "tree": ["    cmd    ", "rel_x", "rel_y", "rel_z", "height"]
    # Add other commands if they exist
}

class Scene:
    """儲存場景物件"""
    def __init__(self):
        self.track = Track()
        # Store ABSOLUTE world coordinates and rotations
        # Updated tuple structure for buildings:
        # (type, world_x, world_y, world_z, rx, abs_ry, rz, w, d, h, tex_id,
        #  u_offset, v_offset, tex_angle_deg, uv_mode, uscale, vscale, tex_file) <-- Added tex_file
        self.buildings = []
        self.trees = []     # [ (world_x, world_y, world_z, height), ... ]
        # Updated tuple structure for cylinders:
        # (type, world_x, world_y, world_z, rx, rz, abs_ry, radius, h, tex_id, # Note rx, rz, abs_ry order
        #  u_offset, v_offset, tex_angle_deg, uv_mode, uscale, vscale, tex_file) <-- Added tex_file
        self.cylinders = []
        # Store the explicit start position/angle if provided
        self.start_position = np.array([0.0, 0.0, 0.0], dtype=float)
        self.start_angle_deg = 0.0 # Store in degrees for potential reference

        # --- Minimap Background Info (Keep) ---
        self.map_filename = None          # Filename of the map image
        self.map_world_center_x = 0.0     # World X coordinate corresponding to the image center
        self.map_world_center_z = 0.0     # World Z coordinate corresponding to the image center
        self.map_world_scale = 1.0        # World units per pixel of the map image (positive value)

        # --- NEW: Background (Skybox/Skydome) Info ---
        # Stores the info dictionary defined by the *first* skybox/skydome command
        self.initial_background_info = None
        # Stores tuples of (trigger_distance, background_info_dict)
        # background_info_dict will be {'type': 'skybox', 'base_name': ...}
        # or {'type': 'skydome', 'file': ..., 'id': texture_id}
        # Let's include the texture ID for skydome here if loaded.
        self.background_triggers = []


    def clear(self):
        self.track.clear()
        self.buildings = []
        self.trees = []
        self.cylinders = []
        self.start_position = np.array([0.0, 0.0, 0.0], dtype=float)
        self.start_angle_deg = 0.0
        # --- Reset Minimap Info ---
        self.map_filename = None
        self.map_world_center_x = 0.0
        self.map_world_center_z = 0.0
        self.map_world_scale = 1.0
        # --- Reset Background Info ---
        self.initial_background_info = None
        self.background_triggers = []

# --- Global state for scene parsing ---
scene_file_path = "scene.txt"
last_modified_time = 0
current_scene = Scene()

def _parse_scene_content(lines_list, load_textures=True):
    """
    Internal function to parse scene commands from a list of strings.
    Returns a new Scene object or None on failure.
    Requires texture_loader to be set (for object textures if load_textures is True).
    Does NOT perform rendering or FBO baking.
    """
    global texture_loader # Ensure texture_loader is accessible

    # Texture loader is only strictly required if load_textures is True for objects
    if load_textures and texture_loader is None:
        print("警告：Texture Loader 尚未設定！物件和 Skydome 紋理將不會被載入。")

    new_scene = Scene()

    # State for track building (Keep)
    current_pos = np.array([0.0, 0.0, 0.0], dtype=float)
    current_angle_rad = 0.0

    # State for relative object placement origin (Keep)
    relative_origin_pos = np.array([0.0, 0.0, 0.0], dtype=float)
    relative_origin_angle_rad = 0.5 * math.pi

    # --- NEW: State for background triggers ---
    last_background_info = None # Stores the info dict for the next track segment

    start_cmd_found = False
    map_cmd_found = False

    for line_num, line in enumerate(lines_list, 1):
        line = line.strip()
        if not line or line.startswith('#'):
            continue

        parts = line.split()
        if not parts: continue
        command = parts[0].lower()

        try:
            # --- Map Command ---
            if command == "map":
                # (Logic unchanged)
                if len(parts) < 5: print(f"警告: 第 {line_num} 行 'map' 指令參數不足。"); continue
                filename = parts[1]
                try: center_x, center_z, scale_val = map(float, parts[2:5])
                except ValueError: print(f"警告: 第 {line_num} 行 'map' 指令的中心點或比例無效。"); continue
                if scale_val <= 0: print(f"警告: 第 {line_num} 行 'map' 縮放比例 ({scale_val}) 必須為正數。"); scale_val = 1.0
                new_scene.map_filename = filename
                new_scene.map_world_center_x = center_x
                new_scene.map_world_center_z = center_z
                new_scene.map_world_scale = scale_val
                map_cmd_found = True
                # print(f"場景地圖資訊已設定: 檔案='{filename}', 中心=({center_x:.1f}, {center_z:.1f}), 比例={scale_val:.2f} 世界單位/像素")

            # --- Start Command ---
            elif command == "start":
                # (Logic unchanged)
                if len(parts) < 5: print(f"警告: 第 {line_num} 行 'start' 指令參數不足。"); continue
                try: x, y, z = map(float, parts[1:4]); angle_deg = float(parts[4])
                except ValueError: print(f"警告: 第 {line_num} 行 'start' 指令的座標或角度無效。"); continue
                angle_rad = math.radians(angle_deg)
                current_pos[:] = [x, y, z]
                current_angle_rad = angle_rad
                relative_origin_pos[:] = current_pos
                relative_origin_angle_rad = current_angle_rad
                new_scene.start_position[:] = current_pos
                new_scene.start_angle_deg = angle_deg
                start_cmd_found = True

            # --- NEW: Skybox Command ---
            elif command == "skybox":
                if len(parts) < 2: print(f"警告: 第 {line_num} 行 'skybox' 指令需要 base_name 參數。"); continue
                base_name = parts[1]
                # Store info, assuming renderer/loader will handle loading the 6 textures based on this name later.
                # We don't load textures here.
                current_info = {'type': 'skybox', 'base_name': base_name}
                if new_scene.initial_background_info is None:
                    new_scene.initial_background_info = current_info
                last_background_info = current_info # Remember for the next track segment
                print(f"解析 Skybox: base_name='{base_name}' (等待軌道觸發)")

            # --- NEW: Skydome Command ---
            elif command == "skydome":
                if len(parts) < 2: print(f"警告: 第 {line_num} 行 'skydome' 指令需要 texture_file 參數。"); continue
                texture_file = parts[1]
                tex_id = None
                # Try to load the 2D texture for the skydome here if requested
                if load_textures and texture_loader:
                    tex_id = texture_loader.load_texture(texture_file)
                    if tex_id is None:
                        print(f"提示: 第 {line_num} 行 'skydome' 無法載入紋理 '{texture_file}'。")
                elif load_textures:
                     print(f"提示: 第 {line_num} 行 'skydome' 無法載入紋理 '{texture_file}' (loader未設定)。")

                current_info = {'type': 'skydome', 'file': texture_file, 'id': tex_id}
                if new_scene.initial_background_info is None:
                    new_scene.initial_background_info = current_info
                last_background_info = current_info # Remember for the next track segment
                print(f"解析 Skydome: file='{texture_file}', ID={tex_id} (等待軌道觸發)")

            # --- Track Commands (Straight/Curve - Update) ---
            elif command == "straight" or command == "curve":
                if not start_cmd_found and not new_scene.track.segments:
                    print(f"提示: 第 {line_num} 行軌道指令前未找到 'start'，將從 ({current_pos[0]:.1f},{current_pos[1]:.1f},{current_pos[2]:.1f}) 角度 {math.degrees(current_angle_rad):.1f}° 開始。")

                # --- Check for pending background trigger ---
                current_track_distance = new_scene.track.total_length
                if last_background_info is not None:
                    # Add the trigger *before* adding the new segment length
                    new_scene.background_triggers.append((current_track_distance, last_background_info))
                    print(f"  -> 設定背景觸發器於里程 {current_track_distance:.2f} ({last_background_info['type']})")
                    last_background_info = None # Reset after associating with a track start

                # --- Track segment parsing (logic mostly unchanged) ---
                relative_origin_pos[:] = current_pos # Update relative origin for subsequent objects
                relative_origin_angle_rad = current_angle_rad
                segment = None
                try:
                    if command == "straight":
                        if len(parts) < 2: print(f"警告: 第 {line_num} 行 'straight' 指令參數不足。"); continue
                        length = float(parts[1])
                        gradient = float(parts[2]) if len(parts) > 2 else 0.0
                        segment = StraightTrack(current_pos, current_angle_rad, length, gradient)
                        segment.source_line_number = line_num
                    elif command == "curve":
                        if len(parts) < 3: print(f"警告: 第 {line_num} 行 'curve' 指令參數不足。"); continue
                        radius = float(parts[1])
                        angle_deg = float(parts[2])
                        gradient = float(parts[3]) if len(parts) > 3 else 0.0
                        segment = CurveTrack(current_pos, current_angle_rad, radius, angle_deg, gradient)
                        segment.source_line_number = line_num
                except ValueError:
                     print(f"警告: 第 {line_num} 行 '{command}' 指令的參數無效。"); continue

                if segment:
                    new_scene.track.add_segment(segment)
                    current_pos = segment.end_pos
                    current_angle_rad = segment.end_angle_rad

            # --- Object Placement Commands (building, cylinder, tree - logic unchanged) ---
            elif command == "building":
                # (Logic unchanged)
                base_param_count = 9; min_parts = 1 + base_param_count
                if len(parts) < min_parts: print(f"警告: 第 {line_num} 行 'building' 指令參數不足。"); continue
                try: rel_x, rel_y, rel_z = map(float, parts[1:4]); rx_deg, rel_ry_deg, rz_deg = map(float, parts[4:7]); w, d, h = map(float, parts[7:10])
                except ValueError: print(f"警告: 第 {line_num} 行 'building' 指令的基本參數無效。"); continue
                tex_file = parts[10] if len(parts) > 10 else "building.png"
                try: u_offset = float(parts[11]) if len(parts) > 11 else 0.0; v_offset = float(parts[12]) if len(parts) > 12 else 0.0; tex_angle_deg = float(parts[13]) if len(parts) > 13 else 0.0; uv_mode = int(parts[14]) if len(parts) > 14 else 1; uscale = float(parts[15]) if len(parts) > 15 and uv_mode == 0 else 1.0; vscale = float(parts[16]) if len(parts) > 16 and uv_mode == 0 else 1.0
                except ValueError: print(f"警告: 第 {line_num} 行 'building' 紋理參數無效。"); tex_file = "building.png"; u_offset=0.0; v_offset=0.0; tex_angle_deg=0.0; uv_mode=1; uscale=1.0; vscale=1.0
                if uv_mode == 0 and (uscale <= 0 or vscale <= 0): print(f"警告: 第 {line_num} 行 'building' uv_mode=0 uscale/vscale 需為正。"); uscale = vscale = 1.0
                if uv_mode not in [0, 1]: print(f"警告: 第 {line_num} 行 'building' uv_mode 無效。"); uv_mode = 1
                tex_id = texture_loader.load_texture(tex_file) if load_textures and texture_loader else None
                origin_angle = relative_origin_angle_rad; cos_a = math.cos(origin_angle); sin_a = math.sin(origin_angle)
                world_offset_x = rel_z * cos_a + rel_x * sin_a; world_offset_z = rel_z * sin_a - rel_x * cos_a
                world_x = relative_origin_pos[0] + world_offset_x; world_y = relative_origin_pos[1] + rel_y; world_z = relative_origin_pos[2] + world_offset_z
                absolute_ry_deg = math.degrees(-origin_angle) + rel_ry_deg - 90
                obj_data_tuple = ("building", world_x, world_y, world_z, rx_deg, absolute_ry_deg, rz_deg, w, d, h, tex_id, u_offset, v_offset, tex_angle_deg, uv_mode, uscale, vscale, tex_file)
                new_scene.buildings.append((line_num, obj_data_tuple))
                
            elif command == "cylinder":
                # (Logic unchanged)
                base_param_count = 8; min_parts = 1 + base_param_count
                if len(parts) < min_parts: print(f"警告: 第 {line_num} 行 'cylinder' 指令參數不足。"); continue
                try: rel_x, rel_y, rel_z = map(float, parts[1:4]); rx_deg, rel_ry_deg, rz_deg = map(float, parts[4:7]); radius = float(parts[7]); height = float(parts[8])
                except ValueError: print(f"警告: 第 {line_num} 行 'cylinder' 指令的基本參數無效。"); continue
                tex_file = parts[9] if len(parts) > 9 else "metal.png"
                try: u_offset = float(parts[10]) if len(parts) > 10 else 0.0; v_offset = float(parts[11]) if len(parts) > 11 else 0.0; tex_angle_deg = float(parts[12]) if len(parts) > 12 else 0.0; uv_mode = int(parts[13]) if len(parts) > 13 else 1; uscale = float(parts[14]) if len(parts) > 14 and uv_mode == 0 else 1.0; vscale = float(parts[15]) if len(parts) > 15 and uv_mode == 0 else 1.0
                except ValueError: print(f"警告: 第 {line_num} 行 'cylinder' 紋理參數無效。"); tex_file = "metal.png"; u_offset=0.0; v_offset=0.0; tex_angle_deg=0.0; uv_mode=1; uscale=1.0; vscale=1.0
                if uv_mode == 0 and (uscale <= 0 or vscale <= 0): print(f"警告: 第 {line_num} 行 'cylinder' uv_mode=0 uscale/vscale 需為正。"); uscale = vscale = 1.0
                if uv_mode not in [0, 1]: print(f"警告: 第 {line_num} 行 'cylinder' uv_mode 無效。"); uv_mode = 1
                tex_id = texture_loader.load_texture(tex_file) if load_textures and texture_loader else None
                origin_angle = relative_origin_angle_rad; cos_a = math.cos(origin_angle); sin_a = math.sin(origin_angle)
                world_offset_x = rel_z * cos_a + rel_x * sin_a; world_offset_z = rel_z * sin_a - rel_x * cos_a
                world_x = relative_origin_pos[0] + world_offset_x; world_y = relative_origin_pos[1] + rel_y; world_z = relative_origin_pos[2] + world_offset_z
                absolute_ry_deg = math.degrees(-origin_angle) + rel_ry_deg - 90
                obj_data_tuple = ("cylinder", world_x, world_y, world_z, rx_deg, absolute_ry_deg, rz_deg, radius, height, tex_id, u_offset, v_offset, tex_angle_deg, uv_mode, uscale, vscale, tex_file)
                new_scene.cylinders.append((line_num, obj_data_tuple))
                
            elif command == "tree":
                 # (Logic unchanged)
                if len(parts) < 5: print(f"警告: 第 {line_num} 行 'tree' 指令參數不足。"); continue
                try: rel_x, rel_y, rel_z = map(float, parts[1:4]); height = float(parts[4])
                except ValueError: print(f"警告: 第 {line_num} 行 'tree' 指令的參數無效。"); continue
                origin_angle = relative_origin_angle_rad; cos_a = math.cos(origin_angle); sin_a = math.sin(origin_angle)
                world_offset_x = rel_z * cos_a + rel_x * sin_a; world_offset_z = rel_z * sin_a - rel_x * cos_a
                world_x = relative_origin_pos[0] + world_offset_x; world_y = relative_origin_pos[1] + rel_y; world_z = relative_origin_pos[2] + world_offset_z
                obj_data_tuple = (world_x, world_y, world_z, height)
                new_scene.trees.append((line_num, obj_data_tuple))

            else:
                print(f"警告: 第 {line_num} 行無法識別的指令 '{command}'")

        except Exception as e: # Catch potential errors
             print(f"警告: 處理第 {line_num} 行時發生內部錯誤 ('{line}'): {e}")
             # Optionally re-raise or log traceback for debugging
             # import traceback
             # traceback.print_exc()

    # If no start command was found, set default scene start info (Keep)
    if not start_cmd_found:
        new_scene.start_position = np.array([0.0, 0.0, 0.0], dtype=float)
        new_scene.start_angle_deg = 0.0

    # --- Sort triggers by distance ---
    new_scene.background_triggers.sort(key=lambda item: item[0])

    return new_scene

# --- parse_scene_from_lines (wrapper - unchanged) ---
def parse_scene_from_lines(lines_list, load_textures=True):
    """
    Parses scene definition from a list of strings (e.g., from a table editor).
    Requires texture_loader to be set beforehand for object textures.

    Args:
        lines_list: A list of strings, where each string is one line from the scene definition.
        load_textures: If True, attempts to load textures for objects like buildings/cylinders.

    Returns:
        A Scene object populated with the parsed data, or None if parsing fails critically.
    """
    # print(f"從 {len(lines_list)} 行文字開始解析場景...")
    parsed_scene = _parse_scene_content(lines_list, load_textures)
    if parsed_scene:
        # print("場景內容解析完成。")
        pass
    else:
        # _parse_scene_content should return a Scene object even on non-critical errors
        print("場景內容解析期間出現警告或錯誤 (詳見上方日誌)。")
        # Return the partially parsed scene or an empty scene if needed
        if parsed_scene is None: parsed_scene = Scene() # Ensure we return a Scene object
    return parsed_scene

# --- parse_scene_file (wrapper - unchanged) ---
def parse_scene_file(filepath, load_textures=True):
    """
    Parses the scene definition from a file.
    Requires texture_loader to be set beforehand for object textures.

    Args:
        filepath: Path to the scene definition file.
        load_textures: If True, attempts to load textures for objects.

    Returns:
        A Scene object populated with the parsed data, or None if file not found.
    """
    print(f"從檔案 '{filepath}' 開始解析場景...")
    try:
        with open(filepath, 'r', encoding="utf-8") as f:
            lines = f.readlines() # Read all lines into a list
        parsed_scene = _parse_scene_content(lines, load_textures)
        if parsed_scene:
            # print(f"場景檔案 '{filepath}' 解析完成。")
            pass
        else:
            print(f"場景檔案 '{filepath}' 解析期間出現警告或錯誤。")
            if parsed_scene is None: parsed_scene = Scene() # Ensure return Scene object
        return parsed_scene
    except FileNotFoundError:
        print(f"錯誤: 場景檔案 '{filepath}' 不存在。")
        return None # Return None if file not found
    except Exception as e:
        print(f"讀取或解析場景檔案 '{filepath}' 時發生未知錯誤: {e}")
        return Scene() # Return empty scene on other errors? Or None? Let's return empty.

# --- load_scene (logic unchanged, relies on parse_scene_file) ---
def load_scene(force_reload=False):
    """
    Loads or reloads the scene file if modified.
    Clears old resources (track buffers, texture cache) before reloading.
    Does NOT trigger minimap baking; that's done externally after this returns True.
    """
    global last_modified_time, current_scene, scene_file_path

    try:
        # Texture loader check is done inside parse functions if load_textures=True
        if not os.path.exists(scene_file_path): # Handle file not found earlier
            raise FileNotFoundError

        current_mod_time = os.path.getmtime(scene_file_path)
        needs_reload = force_reload or current_mod_time != last_modified_time

        if needs_reload:
            print(f"偵測到場景檔案變更或強制重新載入 '{scene_file_path}'...")

            # --- 1. Cleanup OLD scene resources ---
            if current_scene and current_scene.track:
                 # print("清理舊軌道緩衝區...")
                 current_scene.track.clear() # Cleans up track VBOs/VAOs

            if texture_loader:
                # print("清理物件紋理快取...")
                texture_loader.clear_texture_cache() # Includes skydome textures loaded here

            # --- 2. Parse NEW scene data ---
            new_scene_data = parse_scene_file(scene_file_path, load_textures=True)

            if new_scene_data:
                current_scene = new_scene_data # Replace scene object
                last_modified_time = current_mod_time
                print("場景已成功載入/重新載入 (等待外部處理緩衝區和烘焙)。")
                return True # Indicate successful reload, external steps needed
            else:
                print("場景載入失敗，保留舊場景 (或變為空場景)。")
                if current_scene: current_scene.clear()
                return False # Indicate failure

        return False # No reload needed

    except FileNotFoundError:
        print(f"錯誤: 場景檔案 '{scene_file_path}' 在檢查更新時未找到。")
        if current_scene and (current_scene.track.segments or current_scene.map_filename or current_scene.initial_background_info): # Check if scene has content
            print("清理當前場景...")
            if current_scene.track: current_scene.track.clear()
            if texture_loader: texture_loader.clear_texture_cache()
            current_scene.clear() # Clear the Scene object itself
        last_modified_time = 0 # Reset timestamp
        return True # Indicate scene changed (disappeared), external cleanup might be needed

    except Exception as e:
        print(f"檢查場景檔案更新時發生錯誤: {e}")
        import traceback
        traceback.print_exc() # Print stack trace for debugging
        return False

# --- get_current_scene (unchanged) ---
def get_current_scene():
    """獲取當前載入的場景"""
    global current_scene
    return current_scene