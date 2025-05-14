# scene_parser.py
import os
import numpy as np
import numpy as math # Keep consistent
# import math # Original import removed
from track import StraightTrack, CurveTrack, Track, TrackSegment, INTERPOLATION_STEPS 

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
    # --- START OF MODIFICATION ---
    "vbranch": ["    cmd    ", "type(straight/curve)", "p1(angle°/radius)", "p2(length/angle°)", "grad‰?", "dir(fwd/bwd)?"], 
    # --- END OF MODIFICATION ---
    "building": ["    cmd    ", "rel_x", "rel_y", "rel_z", "rx°", "rel_ry°", "rz°", "w", "d", "h", "tex?", "uOf?", "vOf?", "tAng°?", "uvMd?", "uSc?", "vSc?"],
    "cylinder": ["    cmd    ", "rel_x", "rel_y", "rel_z", "rx°", "rel_ry°", "rz°", "rad", "h", "tex?", "uOf?", "vOf?", "tAng°?", "uvMd?", "uSc?", "vSc?"],
    "tree": ["    cmd    ", "rel_x", "rel_y", "rel_z", "height", "tex?"],
    "sphere": ["    cmd    ", "rel_x", "rel_y", "rel_z", "rx°", "rel_ry°", "rz°", "radius", "tex?", "uOf?", "vOf?", "tAng°?", "uvMd?", "uSc?", "vSc?"],
    "hill": ["    cmd    ", "cx", "height", "cz", "radius", "tex?", "uSc?", "vSc?"], # <--- 新增這一行
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
        self.spheres = []
        self.hills = [] # [(line_num, (center_x, peak_height, center_z, base_radius, tex_id, uscale, vscale, tex_file)), ...]
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

        self.is_render_ready = False # 新增標誌

    def clear(self):
        self.track.clear()
        self.buildings = []
        self.trees = []
        self.cylinders = []
        self.spheres = [] # Ensure spheres are cleared
        self.hills = []
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

    def clear_content(self): # 用於清空場景內容，但不一定釋放 OpenGL 資源
        self.track = Track() # 創建一個新的空軌道
        self.buildings = []
        # ... (清空其他列表) ...
        self.map_filename = None
        # ...
        self.initial_background_info = None
        self.background_triggers = []
        self.is_render_ready = False

    def cleanup_resources(self):
        """清理與此場景相關的 OpenGL 資源，主要是軌道緩衝區。"""
        if self.track:
            self.track.clear() # Track.clear() 應負責清理其 VBOs/VAOs
        # 如果 Scene 還管理其他 OpenGL 資源（例如，直接的紋理ID列表），也在此清理
        self.is_render_ready = False
        print(f"Scene resources cleaned up.")

    def populate_from_lines(self, lines_list, load_textures=True):
        """用解析器填充此 Scene 實例的內容。會先清空現有內容。"""
        self.clear_content() # 先清空當前 Scene 的數據
        # _parse_scene_content 應該被修改或有一個輔助函數
        # 它不再創建新的 Scene，而是填充傳入的 Scene 實例
        # 或者，_parse_scene_content 仍然返回一個新 Scene，然後我們手動複製其內容
        # 為了簡單起見，我們先假設 _parse_scene_content 返回一個新 Scene
        
        temp_parsed_scene = _parse_scene_content(lines_list, load_textures) # 假設這個函數依然返回新的 Scene
        if temp_parsed_scene:
            # 將 temp_parsed_scene 的屬性複製到 self
            self.track = temp_parsed_scene.track
            self.buildings = temp_parsed_scene.buildings
            self.trees = temp_parsed_scene.trees
            self.cylinders = temp_parsed_scene.cylinders
            self.spheres = temp_parsed_scene.spheres
            self.hills = temp_parsed_scene.hills
            self.start_position = temp_parsed_scene.start_position
            self.start_angle_deg = temp_parsed_scene.start_angle_deg
            self.map_filename = temp_parsed_scene.map_filename
            self.map_world_center_x = temp_parsed_scene.map_world_center_x
            self.map_world_center_z = temp_parsed_scene.map_world_center_z
            self.map_world_scale = temp_parsed_scene.map_world_scale
            self.initial_background_info = temp_parsed_scene.initial_background_info
            self.background_triggers = temp_parsed_scene.background_triggers
            return True
        return False

    def prepare_for_render(self):
        """準備場景用於渲染，例如創建軌道緩衝區。"""
        if self.track:
            print(f"Scene: Preparing track for render (creating buffers)...")
            self.track.create_all_segment_buffers() # Track 內部應處理好 VBO/VAO
            # 這裡可以檢查 segment.is_buffer_ready
            all_segments_ready = all(s.is_buffer_ready for s in self.track.segments if hasattr(s, 'is_buffer_ready'))
            if all_segments_ready and self.track.segments: # 確保有軌道段且都準備好了
                self.is_render_ready = True
                print("Scene: Track is render ready.")
            elif not self.track.segments:
                self.is_render_ready = True # 空軌道也算準備好了（沒東西渲染）
                print("Scene: Track is empty, render ready.")
            else:
                self.is_render_ready = False
                print("Scene: Track not fully render ready.")
        else:
            self.is_render_ready = True # 沒有軌道也算準備好了
            print("Scene: No track, render ready.")
        
        # 如果還有其他需要在渲染前準備的資源，可以在這裡處理
        # 例如，預載入一些一次性的紋理或模型到 GPU

        # 小地圖烘焙也可以考慮作為 prepare_for_render 的一部分，或者由外部調用
        # minimap_renderer.bake_static_map_elements(self)
        
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

            # --- START OF MODIFICATION ---
            elif command == "vbranch":
                if not new_scene.track.segments:
                    print(f"警告: 第 {line_num} 行 'vbranch' 指令之前沒有任何常規軌道段。將忽略此指令。")
                    continue
                
                parent_segment = new_scene.track.segments[-1]
                
                if len(parts) < 2:
                    print(f"警告: 第 {line_num} 行 'vbranch' 指令需要類型 ('straight' 或 'curve')。")
                    continue

                branch_type = parts[1].lower()
                branch_data = {
                    "type": branch_type,
                    "points": [],
                    "orientations": [],
                    # Add keys for VBOs/VAOs which will be populated in track.py
                    'ballast_vertices': [], 'rail_left_vertices': [], 'rail_right_vertices': [],
                    'ballast_vao': None, 'rail_left_vao': None, 'rail_right_vao': None,
                    'ballast_vbo': None, 'rail_left_vbo': None, 'rail_right_vbo': None
                    } # Initialize points/orientations

                # 視覺分岔的起點是父軌道段的末端
                branch_start_pos = np.copy(parent_segment.end_pos) # Use a copy
                branch_parent_end_angle_rad = parent_segment.end_angle_rad

                if branch_type == "straight":
                    # vbranch straight <angle_deg> <length> [gradient_permille]
                    if len(parts) < 4:
                        print(f"警告: 第 {line_num} 行 'vbranch straight' 需要 <angle_deg> 和 <length> 參數。")
                        continue
                    try:
                        angle_offset_deg = float(parts[2])
                        branch_length = float(parts[3])
                        gradient_permille = float(parts[4]) if len(parts) > 4 else 0.0
                        if branch_length <= 0:
                            print(f"警告: 第 {line_num} 行 'vbranch straight' 長度 ({branch_length}) 必須為正。"); continue

                        branch_data["angle_deg_offset"] = angle_offset_deg # Store original offset for reference
                        branch_data["length"] = branch_length
                        branch_data["gradient"] = gradient_permille
                        
                        # 計算此直線視覺分岔的 points 和 orientations
                        branch_actual_start_angle_rad = branch_parent_end_angle_rad + math.radians(angle_offset_deg)
                        branch_gradient_factor = gradient_permille / 1000.0
                        
                        # 水平方向向量
                        b_fwd_xz_tuple = (math.cos(branch_actual_start_angle_rad), math.sin(branch_actual_start_angle_rad))
                        b_fwd_xz_arr = np.array(b_fwd_xz_tuple)
                        b_fwd_horiz_3d = np.array([b_fwd_xz_arr[0], 0, b_fwd_xz_arr[1]])
                        
                        b_horizontal_length_for_grad_calc = branch_length
                        b_vertical_change = b_horizontal_length_for_grad_calc * branch_gradient_factor
                        # Note: For vbranch straight, 'branch_length' is its horizontal_length
                        
                        num_steps_b = max(2, int(branch_length * INTERPOLATION_STEPS / 5))
                        if num_steps_b < 2: num_steps_b = 2
                        
                        for i_b in range(num_steps_b):
                            t_b = i_b / (num_steps_b - 1)
                            current_horizontal_dist_b = t_b * branch_length # horizontal length for straight
                            current_vertical_change_b = current_horizontal_dist_b * branch_gradient_factor
                            point_pos_b = branch_start_pos + b_fwd_horiz_3d * current_horizontal_dist_b \
                                       + np.array([0, current_vertical_change_b, 0])
                            branch_data["points"].append(point_pos_b)
                            branch_data["orientations"].append(b_fwd_xz_tuple)
                            
                    except ValueError:
                        print(f"警告: 第 {line_num} 行 'vbranch straight' 參數無效。")
                        continue

                elif branch_type == "curve":
                    # vbranch curve <radius> <angle_deg> [gradient_permille]
                    if len(parts) < 4:
                        print(f"警告: 第 {line_num} 行 'vbranch curve' 需要 <radius> 和 <angle_deg> 參數。")
                        continue
                    try:
                        branch_radius = float(parts[2])
                        branch_sweep_angle_deg = float(parts[3])
                        
                        gradient_permille = 0.0
                        branch_direction_mode = "forward" # Default
                        
                        # Check for optional gradient and direction_modifier
                        # gradient is parts[4], direction is parts[5]
                        if len(parts) > 4: # At least one optional arg exists
                            # Try to parse parts[4] as gradient
                            try:
                                gradient_permille = float(parts[4])
                                # If successful, check if parts[5] is direction_modifier
                                if len(parts) > 5:
                                    modifier_candidate = parts[5].lower()
                                    if modifier_candidate in ["forward", "backward"]:
                                        branch_direction_mode = modifier_candidate
                                    elif modifier_candidate: # Not empty and not a valid direction
                                        print(f"警告: 第 {line_num} 行 'vbranch curve' 無效的方向修飾符 '{parts[5]}'")
                                        # continue # Optionally skip if invalid modifier
                            except ValueError:
                                # parts[4] was not a float (gradient), so it must be the direction_modifier
                                modifier_candidate = parts[4].lower()
                                if modifier_candidate in ["forward", "backward"]:
                                    branch_direction_mode = modifier_candidate
                                    if len(parts) > 5: # Too many args if direction was in parts[4]
                                        print(f"警告: 第 {line_num} 行 'vbranch curve' 在方向修飾符 '{parts[4]}' 後有過多參數。")
                                        # continue
                                elif modifier_candidate: # Not empty and not a valid direction
                                    print(f"警告: 第 {line_num} 行 'vbranch curve' 無效的可選參數 '{parts[4]}'")
                                    # continue 
                        
                        # Parameter validation
                        if abs(branch_radius) < 1e-3 : 
                             print(f"警告: 第 {line_num} 行 'vbranch curve' 半徑過小。"); continue
                        if branch_radius <=0: 
                            print(f"警告: 第 {line_num} 行 'vbranch curve' 半徑 ({branch_radius}) 必須為正。"); continue
                        if abs(branch_sweep_angle_deg) < 1e-3 and branch_sweep_angle_deg != 0.0 : # Allow 0 angle for potential future use?
                             print(f"警告: 第 {line_num} 行 'vbranch curve' 掃過角度過小。"); continue


                        branch_data["radius"] = branch_radius
                        branch_data["angle_deg"] = branch_sweep_angle_deg
                        branch_data["gradient"] = gradient_permille
                        branch_data["direction_mode"] = branch_direction_mode # Store for reference/debugging
                        
                        # 計算此曲線視覺分岔的 points 和 orientations
                        branch_angle_rad = math.radians(branch_sweep_angle_deg)
                        branch_gradient_factor = gradient_permille / 1000.0
                        b_horizontal_length = abs(branch_radius * branch_angle_rad)
                        
                        b_turn_dir = 1.0 if branch_angle_rad > 0 else -1.0
                        
                        # Determine the initial tangent direction for the curve
                        b_initial_tangent_rad = branch_parent_end_angle_rad
                        if branch_direction_mode == "backward":
                            b_initial_tangent_rad += math.pi # Add 180 degrees for backward

                        # Calculate center of the curve based on the new initial tangent
                        b_perp_angle_to_tangent = b_initial_tangent_rad + b_turn_dir * math.pi / 2.0
                        b_center_offset_xz = np.array([math.cos(b_perp_angle_to_tangent), math.sin(b_perp_angle_to_tangent)]) * branch_radius
                        b_center_xz = np.array([branch_start_pos[0], branch_start_pos[2]]) + b_center_offset_xz
                        
                        # Calculate the starting angle on the circle for interpolation
                        b_start_angle_on_circle = b_initial_tangent_rad - b_turn_dir * math.pi / 2.0
                        
                        num_steps_b = max(2, int(abs(branch_sweep_angle_deg) * INTERPOLATION_STEPS / 5))
                        if num_steps_b < 2: num_steps_b = 2
                                                
                        for i_b in range(num_steps_b):
                            t_b = i_b / (num_steps_b - 1)
                            current_angle_on_circle_b = b_start_angle_on_circle + t_b * branch_angle_rad
                            
                            point_offset_xz_b = np.array([math.cos(current_angle_on_circle_b), math.sin(current_angle_on_circle_b)]) * branch_radius
                            current_pos_xz_b = b_center_xz + point_offset_xz_b
                            
                            current_horizontal_arc_len_b = t_b * b_horizontal_length
                            current_vertical_change_b = current_horizontal_arc_len_b * branch_gradient_factor
                            current_pos_y_b = branch_start_pos[1] + current_vertical_change_b
                            
                            branch_data["points"].append(np.array([current_pos_xz_b[0], current_pos_y_b, current_pos_xz_b[1]]))
                            
                            tangent_angle_b = current_angle_on_circle_b + b_turn_dir * math.pi / 2.0
                            orientation_vec_xz_b_tuple = (math.cos(tangent_angle_b), math.sin(tangent_angle_b))
                            branch_data["orientations"].append(orientation_vec_xz_b_tuple)

                    except ValueError:
                        print(f"警告: 第 {line_num} 行 'vbranch curve' 參數無效。")
                        continue
                else:
                    print(f"警告: 第 {line_num} 行無法識別的 'vbranch' 類型: '{branch_type}'。")
                    continue
                
                # 如果成功解析並計算了點，則添加到父軌道段
                if branch_data["points"]:
                    parent_segment.visual_branches.append(branch_data)
                else:
                    print(f"警告: 第 {line_num} 行 'vbranch {branch_type}' 未能生成任何點。")

            # --- END OF MODIFICATION ---

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
                if len(parts) < 5:
                    print(f"警告: 第 {line_num} 行 'tree' 指令參數不足。");
                    continue
                try:
                    rel_x, rel_y, rel_z = map(float, parts[1:4]);
                    height = float(parts[4])
                    if height <= 0:
                        print(f"警告: 第 {line_num} 行 'tree' 高度 ({height}) 必須為正數。");
                        continue
                except ValueError:
                    print(f"警告: 第 {line_num} 行 'tree' 指令的基本參數無效。");
                    continue
                # --- 新增：解析可選的紋理檔名 ---
                # 假設第 5 個參數 (索引 5) 是紋理檔名
                tex_file = parts[5] if len(parts) > 5 else "tree_leaves.png" # 可以用預設的樹葉紋理或新的 "tree_billboard.png"

                # --- 新增：載入紋理 (如果需要) ---
                tex_id = None
                if load_textures and texture_loader:
                    tex_id = texture_loader.load_texture(tex_file)
                    if tex_id is None: # 載入失敗
                        # print(f"提示: 第 {line_num} 行 'tree' 無法載入紋理 '{tex_file}'。將不使用紋理。")
                        pass # 改為靜默處理，draw_tree 會處理 tex_id is None 的情況
                # --- 座標轉換 (保持不變) ---
                origin_angle = relative_origin_angle_rad;
                cos_a = math.cos(origin_angle);
                sin_a = math.sin(origin_angle)
                world_offset_x = rel_z * cos_a + rel_x * sin_a;
                world_offset_z = rel_z * sin_a - rel_x * cos_a
                world_x = relative_origin_pos[0] + world_offset_x;
                world_y = relative_origin_pos[1] + rel_y;
                world_z = relative_origin_pos[2] + world_offset_z
                obj_data_tuple = (world_x, world_y, world_z, height, tex_id, tex_file)
                new_scene.trees.append((line_num, obj_data_tuple))
                
            elif command == "sphere":
                # Sphere 參數：rel_x, rel_y, rel_z, rx°, rel_ry°, rz°, radius, [tex_file], [u_off], [v_off], [tex_angle], [uv_mode], [u_scale], [v_scale]
                base_param_count = 7 # x, y, z, rx, ry, rz, radius
                min_parts = 1 + base_param_count
                if len(parts) < min_parts:
                    print(f"警告: 第 {line_num} 行 'sphere' 指令參數不足 (需要至少 {min_parts} 個)。"); continue

                try:
                    # 解析基本參數 (位置, 旋轉, 半徑)
                    rel_x, rel_y, rel_z = map(float, parts[1:4])
                    rx_deg, rel_ry_deg, rz_deg = map(float, parts[4:7])
                    radius = float(parts[7])
                    if radius <= 0:
                        print(f"警告: 第 {line_num} 行 'sphere' 半徑 ({radius}) 必須為正數。"); continue
                except ValueError:
                    print(f"警告: 第 {line_num} 行 'sphere' 指令的基本參數無效。"); continue

                # --- 開始解析可選紋理參數 (重用 building/cylinder 的邏輯) ---
                # 假設第 8 個參數 (索引 8) 開始是可選紋理參數
                tex_param_start_index = 8
                tex_file = parts[tex_param_start_index] if len(parts) > tex_param_start_index else "default_sphere.png" # 可以設定一個預設球體紋理
                try:
                    u_offset = float(parts[tex_param_start_index + 1]) if len(parts) > tex_param_start_index + 1 else 0.0
                    v_offset = float(parts[tex_param_start_index + 2]) if len(parts) > tex_param_start_index + 2 else 0.0
                    tex_angle_deg = float(parts[tex_param_start_index + 3]) if len(parts) > tex_param_start_index + 3 else 0.0
                    uv_mode = int(parts[tex_param_start_index + 4]) if len(parts) > tex_param_start_index + 4 else 1 # 預設模式 1 (物件比例)
                    uscale = float(parts[tex_param_start_index + 5]) if len(parts) > tex_param_start_index + 5 and uv_mode == 0 else 1.0
                    vscale = float(parts[tex_param_start_index + 6]) if len(parts) > tex_param_start_index + 6 and uv_mode == 0 else 1.0
                except ValueError:
                    print(f"警告: 第 {line_num} 行 'sphere' 紋理參數無效。將使用預設值。")
                    tex_file = "default_sphere.png" # 確保重置
                    u_offset, v_offset, tex_angle_deg = 0.0, 0.0, 0.0
                    uv_mode, uscale, vscale = 1, 1.0, 1.0
                # 驗證 uv_mode 和 scale (重用 building/cylinder 的邏輯)
                if uv_mode == 0 and (uscale <= 0 or vscale <= 0):
                    print(f"警告: 第 {line_num} 行 'sphere' uv_mode=0 時 uscale/vscale ({uscale}/{vscale}) 需為正數。已重設為 1.0。")
                    uscale = vscale = 1.0
                if uv_mode not in [0, 1]:
                    print(f"警告: 第 {line_num} 行 'sphere' uv_mode ({uv_mode}) 無效。已重設為 1。")
                    uv_mode = 1
                # --- 結束解析可選紋理參數 ---

                # 載入紋理 (如果需要)
                tex_id = None
                if load_textures and texture_loader:
                    tex_id = texture_loader.load_texture(tex_file)
                    # 可以選擇性地添加 tex_id 為 None 時的警告

                # --- 轉換座標和旋轉 (重用 building/cylinder 的邏輯) ---
                origin_angle = relative_origin_angle_rad
                cos_a = math.cos(origin_angle)
                sin_a = math.sin(origin_angle)
                # 計算世界偏移
                world_offset_x = rel_z * cos_a + rel_x * sin_a
                world_offset_z = rel_z * sin_a - rel_x * cos_a
                # 計算絕對世界座標
                world_x = relative_origin_pos[0] + world_offset_x
                world_y = relative_origin_pos[1] + rel_y
                world_z = relative_origin_pos[2] + world_offset_z
                # 計算絕對世界 Y 軸旋轉角度
                absolute_ry_deg = math.degrees(-origin_angle) + rel_ry_deg - 90 # 保持與 building/cylinder 一致
                # --- 結束轉換 ---

                # 打包數據元組 (類型, 世界座標, 世界旋轉, 半徑, 紋理資訊, 原始檔名)
                obj_data_tuple = (
                    "sphere", world_x, world_y, world_z,
                    rx_deg, absolute_ry_deg, rz_deg, # 使用絕對旋轉
                    radius, tex_id,
                    u_offset, v_offset, tex_angle_deg, uv_mode, uscale, vscale,
                    tex_file # 儲存原始檔名以備後用
                )
                # 添加到場景列表
                new_scene.spheres.append((line_num, obj_data_tuple))

            elif command == "hill":
                # Hill 參數: center_x center_z peak_height base_radius [texture_file] [tex_u_scale] [tex_v_scale]
                base_param_count = 4 # cx, height, cz, radius
                min_parts = 1 + base_param_count
                if len(parts) < min_parts:
                    print(f"警告: 第 {line_num} 行 'hill' 指令參數不足 (需要至少 {min_parts} 個)。"); continue

                try:
                    center_x = float(parts[1])
                    peak_height = float(parts[2])
                    center_z = float(parts[3])
                    base_radius = float(parts[4])
                    if peak_height <= 0 or base_radius <= 0:
                        print(f"警告: 第 {line_num} 行 'hill' 高度 ({peak_height}) 和半徑 ({base_radius}) 必須為正數。"); continue
                except ValueError:
                    print(f"警告: 第 {line_num} 行 'hill' 指令的基本參數無效。"); continue

                # 解析可選紋理和縮放參數
                tex_param_start_index = 5
                tex_file = parts[tex_param_start_index] if len(parts) > tex_param_start_index else "grass.png" # 預設山丘紋理
                try:
                    # 注意索引：第6個參數是 uscale，第7個是 vscale
                    uscale = float(parts[tex_param_start_index + 1]) if len(parts) > tex_param_start_index + 1 else 10.0 # 預設紋理重複 10x10 次
                    vscale = float(parts[tex_param_start_index + 2]) if len(parts) > tex_param_start_index + 2 else 10.0
                except ValueError:
                    print(f"警告: 第 {line_num} 行 'hill' 紋理縮放參數無效。將使用預設值。")
                    uscale, vscale = 10.0, 10.0 # 重設為預設值

                # 驗證 scale (必須為正)
                if uscale <= 0: print(f"警告: 第 {line_num} 行 'hill' uscale ({uscale}) 必須為正數。已重設為 10.0。"); uscale = 10.0
                if vscale <= 0: print(f"警告: 第 {line_num} 行 'hill' vscale ({vscale}) 必須為正數。已重設為 10.0。"); vscale = 10.0

                # 載入紋理 (如果需要)
                tex_id = None
                if load_textures and texture_loader:
                    tex_id = texture_loader.load_texture(tex_file)
                    # 可以選擇性地添加 tex_id 為 None 時的警告

                # 打包數據元組 (中心座標, 高度, 半徑, 紋理資訊, 原始檔名)
                hill_data = (
                    center_x, peak_height, center_z, base_radius,
                    tex_id, uscale, vscale, tex_file # 包含檔名
                )
                # 添加到場景列表
                new_scene.hills.append((line_num, hill_data))

            else:
                # ... (原有的未知指令警告) ...
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
def load_scene(force_reload=False, filepath=None):
    """
    Loads or reloads the scene file if modified.
    Clears old resources (track buffers, texture cache) before reloading.
    Does NOT trigger minimap baking; that's done externally after this returns True.
    """
    global last_modified_time, current_scene, scene_file_path

    # --- 決定實際要載入的路徑 ---
    path_to_use = filepath if filepath is not None else scene_file_path
    # -------------------------

    try:
        # Texture loader check is done inside parse functions if load_textures=True
        if not os.path.exists(path_to_use): # Handle file not found earlier
            # 如果指定了檔案路徑但不存在，這是一個明確的錯誤
            if filepath is not None:
                print(f"錯誤: 指定的場景檔案 '{filepath}' 不存在。")
                # 這種情況下，我們可能不應該繼續清理或修改 current_scene
                # 可以選擇返回 False，或者如果希望清空場景則繼續
                # 為了安全，如果指定檔案不存在，直接返回 False，不改變當前狀態
                return False
            # 如果是預設路徑不存在，則按原來的 FileNotFoundError 處理
            raise FileNotFoundError(f"預設場景檔案 '{path_to_use}' 未找到。")

        current_mod_time = os.path.getmtime(path_to_use)
        needs_reload = (filepath is not None) or \
                       force_reload or \
                       (filepath is None and current_mod_time != last_modified_time)
        
        if needs_reload:
            print(f"偵測到場景檔案變更或強制重新載入 '{scene_file_path}'...")

            # --- 1. Cleanup OLD scene resources ---
            if current_scene: # 確保 current_scene 不是 None
                if hasattr(current_scene, 'cleanup_resources') and callable(current_scene.cleanup_resources):
                    # print("清理舊場景資源 (via Scene.cleanup_resources)...") # 可選調試
                    current_scene.cleanup_resources() # 調用 Scene 自己的清理方法
                elif current_scene.track: # 後備：如果沒有 cleanup_resources，但有 track
                    # print("清理舊軌道緩衝區 (直接)...") # 可選調試
                    current_scene.track.clear()

            if texture_loader:
                # print("清理物件紋理快取...") # 可選調試
                texture_loader.clear_texture_cache()

            # --- 2. Parse NEW scene data ---
            new_scene_data = parse_scene_file(path_to_use, load_textures=True)

            if new_scene_data:
                current_scene = new_scene_data # 更新全域的 current_scene
                
                # 更新檔案修改時間 (僅當我們載入的是預設的 scene_file_path 且沒有強制指定 filepath 時)
                if filepath is None: # 只有當載入的是預設的全域 scene_file_path 時，才更新 last_modified_time
                    last_modified_time = current_mod_time
                
                # --- 新增：在 current_scene 被賦值後，調用 prepare_for_render ---
                if hasattr(current_scene, 'prepare_for_render') and callable(current_scene.prepare_for_render):
                    print(f"為新載入的場景 '{path_to_use}' 準備渲染資源...")
                    current_scene.prepare_for_render()
                # ------------------------------------------------------------
                
                print(f"場景 '{path_to_use}' 已成功載入/重新載入。")
                return True # 指示成功重載
            else:
                print(f"場景檔案 '{path_to_use}' 載入失敗，但解析返回 None。可能保留舊場景或變為空。")
                # 這裡可以選擇是否要清空 current_scene
                # current_scene.clear_content() # 或者 current_scene.cleanup_resources() 然後 current_scene = Scene()
                # current_scene.prepare_for_render() # 即使是空場景，也調用一下
                return False # 指示失敗

        return False # 不需要重載

    except FileNotFoundError:
        # 這個 FileNotFoundError 主要對應預設 scene_file_path 找不到的情況
        print(f"錯誤: 場景檔案 '{path_to_use}' (在 load_scene 中) 未找到。")
        if current_scene and (current_scene.track.segments or current_scene.map_filename or current_scene.initial_background_info):
            print("清理當前場景...")
            if hasattr(current_scene, 'cleanup_resources') and callable(current_scene.cleanup_resources):
                current_scene.cleanup_resources()
            elif current_scene.track: current_scene.track.clear()
            if texture_loader: texture_loader.clear_texture_cache()
            current_scene.clear_content() # 清空內容，但不一定是新 Scene()
            # current_scene = Scene() # 或者直接賦值一個新的空場景
        
        # 為空場景也調用 prepare_for_render (是安全的)
        if hasattr(current_scene, 'prepare_for_render') and callable(current_scene.prepare_for_render):
            current_scene.prepare_for_render()

        if filepath is None: # 只有當檢查的是預設路徑時才重置時間戳
            last_modified_time = 0
        return True # 指示場景已更改（變為空或已清理），外部可能需要更新

    except Exception as e:
        print(f"檢查或載入場景檔案 '{path_to_use}' 更新時發生錯誤: {e}")
        import traceback
        traceback.print_exc()
        return False

# --- get_current_scene (unchanged) ---
def get_current_scene():
    """獲取當前載入的場景"""
    global current_scene
    return current_scene