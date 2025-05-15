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
    "hill": ["    cmd    ", "cx", "base_y", "cz", "radius", "peak_h_off", "tex?", "uSc?", "vSc?"], # <--- 新增這一行
    "import": ["    cmd    ", "filepath"], # <--- 新增 IMPORT 指令提示
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
        self.start_angle_deg = 90.0 # Store in degrees for potential reference

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

        # --- 新增：用於解析過程的狀態 ---
        self.current_parse_pos = np.copy(self.start_position)
        self.current_parse_angle_rad = math.radians(self.start_angle_deg)
        #相對原點的預設值應該是一個不會輕易與實際場景混淆的值，或者在第一次`start`或軌道指令時設定
        self.current_relative_origin_pos = np.copy(self.current_parse_pos)
        self.current_relative_origin_angle_rad = self.current_parse_angle_rad # 保持與 parse_pos 一致
        self.last_background_info = None # 初始化為 None
        # ----------------------------------
        
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

        # --- 重置解析狀態 ---
        self.current_parse_pos = np.copy(self.start_position)
        self.current_parse_angle_rad = math.radians(self.start_angle_deg)
        self.current_relative_origin_pos = np.copy(self.current_parse_pos)
        self.current_relative_origin_angle_rad = self.current_parse_angle_rad
        self.last_background_info = None
        # ---------------------
        
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

def _parse_scene_content(lines_list, scene_to_populate: Scene,
                         current_file_directory: str, current_filename_for_display: str,
                         imported_files: set,
                         is_parsing_imported_file: bool, load_textures=True):
    """
    Internal function to parse scene commands from a list of strings and populate a Scene object.
    Args:
        lines_list: List of strings (lines from the current file being parsed).
        scene_to_populate: The Scene object to add parsed elements to.
        current_file_directory: The directory of the file from which 'lines_list' was read.
                                Used to resolve relative paths for 'import'.
        imported_files: A set of absolute filepaths already imported in the current chain, to prevent cycles.
        load_textures: Whether to load textures.
    Returns:
        The populated Scene object (same as scene_to_populate).
    """
    global texture_loader 

    if load_textures and texture_loader is None:
        print("警告：Texture Loader 尚未設定！物件和 Skydome 紋理將不會被載入。")

    # new_scene = Scene() # 不再創建新的，而是填充傳入的 scene_to_populate

    # State for track building (這些狀態應該屬於 scene_to_populate 的一部分，或者在解析時動態維護)
    # 為了簡化，我們假設這些狀態在遞迴調用中能被正確共享和更新，
    # 或者，對於 import 的內容，它們應該是相對於 import 點的狀態。
    # 這裡我們需要謹慎處理 current_pos, current_angle_rad, relative_origin_pos, relative_origin_angle_rad
    # 一個簡單的策略是，import 進來的內容，其 track 和 object 的相對原點是基於 import 指令被解析時的狀態。

    # 從 scene_to_populate 獲取或初始化解析狀態 (這部分需要仔細考慮如何傳遞和更新)
    # 暫時我們假設這些是全域的（雖然不好），或者它們是 Scene 的屬性
    # 為了讓 import 的內容能正確銜接，這些狀態變數不能在每次遞迴時重置
    # 這暗示著它們可能需要作為參數傳遞，或者 Scene 物件本身需要追蹤它們。

    # --- 讓我們假設這些狀態是跟隨 scene_to_populate 的 ---
    # 如果 scene_to_populate 是第一次被傳入（頂層調用），這些值可能是初始值。
    # 如果是遞迴調用（由 import 觸發），它們應該是 import 點的狀態。
    # 這部分有點棘手，因為原始的 _parse_scene_content 設計中，這些是局部變數。
    # 最好的方法可能是將 track building state 封裝到 Scene 物件中。
    # 為了快速實現，我們先假設一個簡化的共享狀態（這在嚴格遞迴下可能不完美，但可以先嘗試）

    # 我們需要一個方法來獲取和更新這些狀態，而不僅僅是局部變數。
    # 暫時，我們讓這些狀態在 `scene_to_populate` 首次創建時初始化，
    # 並且在處理 "start", "straight", "curve" 時更新 `scene_to_populate` 內部對應的狀態。
    # `_parse_scene_content` 應該從 `scene_to_populate` 讀取當前解析的起點。

    # 獲取當前的解析起點和角度 (如果 Scene 物件有追蹤的話)
    # 這裡需要 scene_to_populate 有類似 self.current_parse_pos, self.current_parse_angle_rad 等屬性
    # 假設 Scene 類別已經擴展了這些:
    # scene_to_populate.current_parse_pos (np.array)
    # scene_to_populate.current_parse_angle_rad (float)
    # scene_to_populate.current_relative_origin_pos (np.array)
    # scene_to_populate.current_relative_origin_angle_rad (float)
    # scene_to_populate.last_background_info (dict)

    # (這些狀態的正確管理對於 import 嵌套和相對定位至關重要)
    # --- END 狀態管理思考 ---


    for line_num_in_file, line_content in enumerate(lines_list, 1): # line_num_in_file 是相對於當前檔案的行號
        line = line_content.strip()
        if not line or line.startswith('#'):
            continue

        parts = line.split()
        if not parts: continue
        command = parts[0].lower()

        # --- 決定儲存的行號/索引 ---
        line_identifier_for_object = ""
        if is_parsing_imported_file:
            line_identifier_for_object = f"{current_filename_for_display}:{line_num_in_file}"
        else:
            # 對於根檔案，我們需要一個能與編輯器表格行號對應的值。
            # 如果 scene_parser 只處理單個檔案（或遞迴地將所有 import 內容視為一個流），
            # 那麼 line_num_in_file (對於根檔案) 或一個累加的行號是合適的。
            # 既然我們放棄了全域連續行號追蹤器，對於根檔案，就用它在該檔案內的行號。
            # 這意味著 highlight_line_nums 傳入 minimap 時，如果它來自表格，
            # 而表格是合併視圖，這裡可能需要一個從表格合併行號到 (檔名,檔案內行號) 的映射。
            # 但根據你的折衷方案，高亮只處理根場景，所以根場景用簡單整數行號是OK的。
            line_identifier_for_object = line_num_in_file # 根檔案的物件，使用其在檔案內的行號
        # --------------------------
        
        try:
            if command == "import":
                if len(parts) < 2:
                    print(f"警告: (文件: {current_filename_for_display} 行 {line_num_in_file}) 'import' 指令需要檔名參數。")
                    continue
                
                import_filename_param  = parts[1]
                # --- 解析相對路徑 ---
                # 假設 import_filename 是相對於 current_file_directory 的
                imported_filepath_abs = os.path.abspath(os.path.join(current_file_directory, import_filename_param))
                
                if imported_filepath_abs in imported_files:
                    print(f"警告: ({current_filename_for_display} 行 {line_num_in_file}) 循环导入 '{import_filename_param}'。跳过。")
                    continue

                if not os.path.exists(imported_filepath_abs):
                    print(f"警告: ({current_filename_for_display} 行 {line_num_in_file}) Import 文件 '{import_filename_param}' (at '{imported_filepath_abs}') 不存在。")
                    continue

                imported_files.add(imported_filepath_abs)
                print(f"信息: ({current_filename_for_display} 行 {line_num_in_file}) 导入 '{import_filename_param}'...")
                
                try:
                    with open(imported_filepath_abs, 'r', encoding='utf-8') as f_import:
                        imported_lines = f_import.readlines()
                    
                    # 遞迴解析導入的檔案內容，傳遞相同的 scene_to_populate 和 updated imported_files
                    # current_pos 等狀態會由 scene_to_populate 內部維護和更新
                    _parse_scene_content(imported_lines, scene_to_populate, 
                                         os.path.dirname(imported_filepath_abs), 
                        os.path.basename(imported_filepath_abs), imported_files, load_textures)
                    print(f"信息: 完成导入 '{import_filename_param}'。")

                except Exception as e_import:
                    print(f"錯誤: (文件: {os.path.basename(current_filename_for_display)} 行 {line_num_in_file}) 导入文件 '{import_filename_param}' 时发生错误: {e_import}")
                
                # 從集合中移除，允許其他分支再次導入同一個檔案（如果不是循環的一部分）
                # 或者，如果一個檔案只應被導入一次，則不移除
                imported_files.remove(imported_filepath_abs) # 允許非循環的重複導入 (例如 A import C, B import C)

            # --- 其他指令的處理邏輯 (需要調整以使用 scene_to_populate 中的狀態) ---
            # 例如，對於 "start" 指令:
            elif command == "start":
                if len(parts) < 5: print(f"警告: (文件: {os.path.basename(current_file_directory)} 行 {line_num_in_file}) 'start' 參數不足。"); continue
                try: x, y, z = map(float, parts[1:4]); angle_deg = float(parts[4])
                except ValueError: print(f"警告: (文件: {os.path.basename(current_file_directory)} 行 {line_num_in_file}) 'start' 參數無效。"); continue
                angle_rad = math.radians(angle_deg)
                
                # --- 更新 Scene 物件的內部狀態 ---
                scene_to_populate.start_position = np.array([x, y, z], dtype=float)
                scene_to_populate.start_angle_deg = angle_deg
                
                scene_to_populate.current_parse_pos[:] = [x, y, z]
                scene_to_populate.current_parse_angle_rad = angle_rad
                scene_to_populate.current_relative_origin_pos[:] = scene_to_populate.current_parse_pos
                scene_to_populate.current_relative_origin_angle_rad = scene_to_populate.current_parse_angle_rad
                # --- END 更新 Scene 狀態 ---
                # start_cmd_found = True # 這個標誌的作用需要重新評估

            # --- 對於 "straight", "curve" 等軌道指令 ---
            # 它們會讀取 scene_to_populate.current_parse_pos 和 current_parse_angle_rad 作為起點
            # 並在創建 segment 後，更新 scene_to_populate.current_parse_pos 和 current_parse_angle_rad 為 segment 的末端狀態
            elif command == "straight" or command == "curve":
                # 確保 current_parse_pos 等已初始化
                if not hasattr(scene_to_populate, 'current_parse_pos'):
                    # 如果之前沒有 start 指令，使用預設值初始化
                    scene_to_populate.current_parse_pos = np.array([0.0,0.0,0.0], dtype=float)
                    scene_to_populate.current_parse_angle_rad = 0.0 # 預設朝 X+
                    scene_to_populate.current_relative_origin_pos = np.copy(scene_to_populate.current_parse_pos)
                    scene_to_populate.current_relative_origin_angle_rad = scene_to_populate.current_parse_angle_rad
                    scene_to_populate.last_background_info = None
                    print(f"提示: (文件: {os.path.basename(current_file_directory)} 行 {line_num_in_file}) 軌道指令前未找到 'start'，將從預設位置開始。")


                # --- 背景觸發器邏輯 (使用 scene_to_populate.last_background_info) ---
                current_track_distance = scene_to_populate.track.total_length
                if hasattr(scene_to_populate, 'last_background_info') and scene_to_populate.last_background_info is not None:
                    scene_to_populate.background_triggers.append((current_track_distance, scene_to_populate.last_background_info))
                    scene_to_populate.last_background_info = None

                # 更新相對原點
                scene_to_populate.current_relative_origin_pos[:] = scene_to_populate.current_parse_pos
                scene_to_populate.current_relative_origin_angle_rad = scene_to_populate.current_parse_angle_rad
                
                segment = None
                try:
                    if command == "straight":
                        if len(parts) < 2: print(f"警告: (文件: {current_filename_for_display} 行 {line_num_in_file}) 'straight' 參數不足。"); continue
                        length = float(parts[1])
                        gradient = float(parts[2]) if len(parts) > 2 else 0.0
                        segment = StraightTrack(scene_to_populate.current_parse_pos, scene_to_populate.current_parse_angle_rad, length, gradient)
                        segment.source_line_number = line_num_in_file # 可以考慮傳遞原始檔案名和行號
                    elif command == "curve":
                        if len(parts) < 3: print(f"警告: (文件: {current_filename_for_display} 行 {line_num_in_file}) 'curve' 參數不足。"); continue
                        radius = float(parts[1])
                        angle_deg = float(parts[2])
                        gradient = float(parts[3]) if len(parts) > 3 else 0.0
                        segment = CurveTrack(scene_to_populate.current_parse_pos, scene_to_populate.current_parse_angle_rad, radius, angle_deg, gradient)
                        segment.source_line_number = line_num_in_file
                except ValueError:
                     print(f"警告: (文件: {current_filename_for_display} 行 {line_num_in_file}) '{command}' 參數無效。"); continue
                
                if segment:
                    scene_to_populate.track.add_segment(segment)
                    scene_to_populate.current_parse_pos = segment.end_pos # 更新 scene 的狀態
                    scene_to_populate.current_parse_angle_rad = segment.end_angle_rad

            
            elif command == "vbranch":
                if not scene_to_populate.track.segments:
                    print(f"警告: ({current_filename_for_display} 行 {line_num_in_file}) 'vbranch' 指令之前沒有任何常規軌道段。將忽略此指令。")
                    continue
                
                parent_segment = scene_to_populate.track.segments[-1]
                
                if len(parts) < 2:
                    print(f"警告: ({current_filename_for_display} 行 {line_num_in_file}) 'vbranch' 指令需要類型 ('straight' 或 'curve')。")
                    continue

                branch_type = parts[1].lower()
                # 初始化 branch_data_dict，包含所有 TrackSegment 和渲染所需的鍵
                branch_data_dict = {
                    "type": branch_type,
                    "points": [],
                    "orientations": [],
                    'ballast_vertices': [], 'rail_left_vertices': [], 'rail_right_vertices': [],
                    'ballast_vao': None, 'rail_left_vao': None, 'rail_right_vao': None,
                    'ballast_vbo': None, 'rail_left_vbo': None, 'rail_right_vbo': None,
                    # 特定於類型的參數可以稍後添加
                }

                # 視覺分岔的起點是父軌道段的末端
                branch_start_pos = np.copy(parent_segment.end_pos) # 使用父軌道段的末端位置
                branch_parent_end_angle_rad = parent_segment.end_angle_rad # 父軌道段的末端角度

                if branch_type == "straight":
                    # vbranch straight <angle_deg_offset> <length> [gradient_permille]
                    if len(parts) < 4:
                        print(f"警告: ({current_filename_for_display} 行 {line_num_in_file}) 'vbranch straight' 需要 <angle_deg_offset> 和 <length>。")
                        continue
                    try:
                        angle_offset_deg = float(parts[2])
                        branch_length = float(parts[3])
                        gradient_permille = float(parts[4]) if len(parts) > 4 else 0.0
                        
                        if branch_length <= 0:
                            print(f"警告: ({current_filename_for_display} 行 {line_num_in_file}) 'vbranch straight' 長度 ({branch_length}) 必須為正。")
                            continue

                        branch_data_dict["angle_deg_offset"] = angle_offset_deg
                        branch_data_dict["length"] = branch_length
                        branch_data_dict["gradient"] = gradient_permille
                        
                        branch_actual_start_angle_rad = branch_parent_end_angle_rad + math.radians(angle_offset_deg)
                        branch_gradient_factor = gradient_permille / 1000.0
                        
                        b_fwd_xz_tuple = (math.cos(branch_actual_start_angle_rad), math.sin(branch_actual_start_angle_rad))
                        b_fwd_xz_arr = np.array(b_fwd_xz_tuple)
                        b_fwd_horiz_3d = np.array([b_fwd_xz_arr[0], 0, b_fwd_xz_arr[1]])
                        
                        # 對於直線 vbranch，其 horizontal_length 就是 branch_length
                        b_horizontal_length_for_grad_calc = branch_length
                        
                        # num_steps_b 的計算可以基於長度，確保平滑度
                        num_steps_b = max(2, int(branch_length * INTERPOLATION_STEPS / 5)) # 與 StraightTrack 類似
                        if num_steps_b < 2: num_steps_b = 2
                        
                        for i_b in range(num_steps_b):
                            t_b = i_b / (num_steps_b - 1)
                            current_horizontal_dist_b = t_b * b_horizontal_length_for_grad_calc
                            current_vertical_change_b = current_horizontal_dist_b * branch_gradient_factor
                            
                            point_pos_b = branch_start_pos + b_fwd_horiz_3d * current_horizontal_dist_b \
                                       + np.array([0, current_vertical_change_b, 0])
                            
                            branch_data_dict["points"].append(point_pos_b)
                            branch_data_dict["orientations"].append(b_fwd_xz_tuple) # 直線方向不變
                            
                    except ValueError:
                        print(f"警告: ({current_filename_for_display} 行 {line_num_in_file}) 'vbranch straight' 參數無效。")
                        continue

                elif branch_type == "curve":
                    # vbranch curve <radius> <angle_deg_sweep> [gradient_permille] [direction_modifier?]
                    if len(parts) < 4:
                        print(f"警告: ({current_filename_for_display} 行 {line_num_in_file}) 'vbranch curve' 需要 <radius> 和 <angle_deg_sweep>。")
                        continue
                    try:
                        branch_radius = float(parts[2])
                        branch_sweep_angle_deg = float(parts[3])
                        
                        gradient_permille = 0.0
                        branch_direction_mode = "forward" # 預設 "forward" (相對於父軌道末端切線方向)

                        # 解析可選的 gradient_permille 和 direction_modifier
                        # gradient 是 parts[4], direction 是 parts[5]
                        if len(parts) > 4: # 至少有一個可選參數
                            try:
                                gradient_permille = float(parts[4])
                                if len(parts) > 5:
                                    modifier_candidate = parts[5].lower()
                                    if modifier_candidate in ["forward", "backward"]:
                                        branch_direction_mode = modifier_candidate
                                    elif modifier_candidate: # 不是有效的修飾符
                                         print(f"警告: ({current_filename_for_display} 行 {line_num_in_file}) 'vbranch curve' 無效的方向修飾符 '{parts[5]}'")
                            except ValueError: # parts[4] 不是 float，那麼它必須是 direction_modifier
                                modifier_candidate = parts[4].lower()
                                if modifier_candidate in ["forward", "backward"]:
                                    branch_direction_mode = modifier_candidate
                                    if len(parts) > 5: # 如果方向在 parts[4]，則 parts[5] 是多餘的
                                        print(f"警告: ({current_filename_for_display} 行 {line_num_in_file}) 'vbranch curve' 在方向修飾符 '{parts[4]}' 後有過多參數。")
                                elif modifier_candidate: # 不是有效的修飾符
                                    print(f"警告: ({current_filename_for_display} 行 {line_num_in_file}) 'vbranch curve' 無效的可選參數 '{parts[4]}'")

                        if abs(branch_radius) < 1e-3 or branch_radius <= 0: 
                             print(f"警告: ({current_filename_for_display} 行 {line_num_in_file}) 'vbranch curve' 半徑 ({branch_radius}) 無效。")
                             continue
                        if abs(branch_sweep_angle_deg) < 1e-3 and branch_sweep_angle_deg != 0.0 :
                             print(f"警告: ({current_filename_for_display} 行 {line_num_in_file}) 'vbranch curve' 掃過角度過小。")
                             # continue # 0度曲線可能是特殊情況，暫不跳過

                        branch_data_dict["radius"] = branch_radius
                        branch_data_dict["angle_deg"] = branch_sweep_angle_deg # 這是掃過的角度
                        branch_data_dict["gradient"] = gradient_permille
                        branch_data_dict["direction_mode"] = branch_direction_mode
                        
                        branch_angle_rad_sweep = math.radians(branch_sweep_angle_deg)
                        branch_gradient_factor = gradient_permille / 1000.0
                        
                        b_horizontal_length = abs(branch_radius * branch_angle_rad_sweep)
                        b_turn_dir = 1.0 if branch_angle_rad_sweep > 0 else -1.0 # 決定曲線是左轉還是右轉
                        
                        # 確定曲線的初始切線方向
                        # "forward" 模式：曲線的初始切線方向 = 父軌道段的末端切線方向
                        # "backward" 模式：曲線的初始切線方向 = 父軌道段末端切線方向 + 180度
                        b_initial_tangent_rad = branch_parent_end_angle_rad
                        if branch_direction_mode == "backward":
                            b_initial_tangent_rad += math.pi 

                        # 計算曲線圓心 (XZ平面)
                        # 從 branch_start_pos (父段末端)，沿著與 b_initial_tangent_rad 垂直的方向移動 branch_radius 距離
                        b_perp_angle_to_tangent = b_initial_tangent_rad + b_turn_dir * (math.pi / 2.0)
                        b_center_offset_xz = np.array([math.cos(b_perp_angle_to_tangent), math.sin(b_perp_angle_to_tangent)]) * branch_radius
                        b_center_xz = np.array([branch_start_pos[0], branch_start_pos[2]]) + b_center_offset_xz
                        
                        # 計算曲線在圓上的起始角度 (用於插值)
                        # 這是從圓心指向 branch_start_pos 的向量的角度
                        b_start_angle_on_circle = b_initial_tangent_rad - b_turn_dir * (math.pi / 2.0)
                        
                        num_steps_b = max(2, int(abs(branch_sweep_angle_deg) * INTERPOLATION_STEPS / 5)) # 與 CurveTrack 類似
                        if num_steps_b < 2: num_steps_b = 2
                                                
                        for i_b in range(num_steps_b):
                            t_b = i_b / (num_steps_b - 1)
                            # 當前點在圓上掃過的實際角度 (相對於 b_start_angle_on_circle)
                            current_angle_on_circle_b = b_start_angle_on_circle + t_b * branch_angle_rad_sweep
                            
                            # 計算當前點的 XZ 坐標 (相對於圓心)
                            point_offset_xz_b = np.array([math.cos(current_angle_on_circle_b), math.sin(current_angle_on_circle_b)]) * branch_radius
                            current_pos_xz_b = b_center_xz + point_offset_xz_b # 這是相對於世界原點的 XZ
                            
                            # 計算 Y 坐標 (基於坡度)
                            current_horizontal_arc_len_b = t_b * b_horizontal_length
                            current_vertical_change_b = current_horizontal_arc_len_b * branch_gradient_factor
                            current_pos_y_b = branch_start_pos[1] + current_vertical_change_b # 從分岔起點的Y開始計算
                            
                            branch_data_dict["points"].append(np.array([current_pos_xz_b[0], current_pos_y_b, current_pos_xz_b[1]]))
                            
                            # 計算該點的水平切線方向 (朝前)
                            tangent_angle_at_current_point_b = current_angle_on_circle_b + b_turn_dir * (math.pi / 2.0)
                            orientation_vec_xz_b_tuple = (math.cos(tangent_angle_at_current_point_b), math.sin(tangent_angle_at_current_point_b))
                            branch_data_dict["orientations"].append(orientation_vec_xz_b_tuple)

                    except ValueError:
                        print(f"警告: ({current_filename_for_display} 行 {line_num_in_file}) 'vbranch curve' 參數無效。")
                        continue
                else:
                    print(f"警告: ({current_filename_for_display} 行 {line_num_in_file}) 無法識別的 'vbranch' 類型: '{branch_type}'。")
                    continue
                
                # 確保生成了足夠的點才添加到父軌道段
                if branch_data_dict.get("points") and len(branch_data_dict.get("points")) >= 2:
                    parent_segment.visual_branches.append(branch_data_dict)
                    # print(f"DEBUG: Added vbranch {branch_type} with {len(branch_data_dict['points'])} points.") # Debug
                else:
                    print(f"警告: ({current_filename_for_display} 行 {line_num_in_file}) vbranch '{branch_type}' 未能生成足够的点，不添加到父轨道段。Points: {branch_data_dict.get('points')}")

            elif command == "building":
                # ... (building 解析邏輯，使用 scene_to_populate.current_relative_origin_pos 等)
                base_param_count = 9; min_parts = 1 + base_param_count
                if len(parts) < min_parts: print(f"警告: ({current_filename_for_display} 行 {line_num_in_file}) 'building' 參數不足。"); continue
                try: rel_x, rel_y, rel_z = map(float, parts[1:4]); rx_deg, rel_ry_deg, rz_deg = map(float, parts[4:7]); w, d, h = map(float, parts[7:10])
                except ValueError: print(f"警告: ({current_filename_for_display} 行 {line_num_in_file}) 'building' 基本參數無效。"); continue
                tex_file = parts[10] if len(parts) > 10 else "building.png"
                u_offset, v_offset, tex_angle_deg, uv_mode, uscale, vscale = 0.0,0.0,0.0,1,1.0,1.0
                try: u_offset = float(parts[11]) if len(parts) > 11 else 0.0; v_offset = float(parts[12]) if len(parts) > 12 else 0.0; tex_angle_deg = float(parts[13]) if len(parts) > 13 else 0.0; uv_mode = int(parts[14]) if len(parts) > 14 else 1; uscale = float(parts[15]) if len(parts) > 15 and uv_mode == 0 else 1.0; vscale = float(parts[16]) if len(parts) > 16 and uv_mode == 0 else 1.0
                except ValueError: pass
                tex_id = texture_loader.load_texture(tex_file) if load_textures and texture_loader else None
                origin_angle = scene_to_populate.current_relative_origin_angle_rad
                cos_a = math.cos(origin_angle); sin_a = math.sin(origin_angle)
                world_offset_x = rel_z * cos_a + rel_x * sin_a
                world_offset_z = rel_z * sin_a - rel_x * cos_a
                world_x = scene_to_populate.current_relative_origin_pos[0] + world_offset_x
                world_y = scene_to_populate.current_relative_origin_pos[1] + rel_y
                world_z = scene_to_populate.current_relative_origin_pos[2] + world_offset_z
                absolute_ry_deg = math.degrees(-origin_angle) + rel_ry_deg - 90
                obj_data_tuple = ("building", world_x, world_y, world_z, rx_deg, absolute_ry_deg, rz_deg, w, d, h, tex_id, u_offset, v_offset, tex_angle_deg, uv_mode, uscale, vscale, tex_file)
                scene_to_populate.buildings.append((line_identifier_for_object, obj_data_tuple))

            elif command == "cylinder":
                # ... (cylinder 解析邏輯) ...
                base_param_count = 8; min_parts = 1 + base_param_count
                if len(parts) < min_parts: print(f"警告: ({current_filename_for_display} 行 {line_num_in_file}) 'cylinder' 參數不足。"); continue
                try: rel_x, rel_y, rel_z = map(float, parts[1:4]); rx_deg, rel_ry_deg, rz_deg = map(float, parts[4:7]); radius = float(parts[7]); height = float(parts[8])
                except ValueError: print(f"警告: ({current_filename_for_display} 行 {line_num_in_file}) 'cylinder' 基本參數無效。"); continue
                tex_file = parts[9] if len(parts) > 9 else "metal.png"
                u_offset, v_offset, tex_angle_deg, uv_mode, uscale, vscale = 0.0,0.0,0.0,1,1.0,1.0
                try: u_offset = float(parts[10]) if len(parts) > 10 else 0.0; v_offset = float(parts[11]) if len(parts) > 11 else 0.0; tex_angle_deg = float(parts[12]) if len(parts) > 12 else 0.0; uv_mode = int(parts[13]) if len(parts) > 13 else 1; uscale = float(parts[14]) if len(parts) > 14 and uv_mode == 0 else 1.0; vscale = float(parts[15]) if len(parts) > 15 and uv_mode == 0 else 1.0
                except ValueError: pass
                tex_id = texture_loader.load_texture(tex_file) if load_textures and texture_loader else None
                origin_angle = scene_to_populate.current_relative_origin_angle_rad; cos_a = math.cos(origin_angle); sin_a = math.sin(origin_angle)
                world_offset_x = rel_z * cos_a + rel_x * sin_a; world_offset_z = rel_z * sin_a - rel_x * cos_a
                world_x = scene_to_populate.current_relative_origin_pos[0] + world_offset_x; world_y = scene_to_populate.current_relative_origin_pos[1] + rel_y; world_z = scene_to_populate.current_relative_origin_pos[2] + world_offset_z
                absolute_ry_deg = math.degrees(-origin_angle) + rel_ry_deg - 90
                obj_data_tuple = ("cylinder", world_x, world_y, world_z, rx_deg, absolute_ry_deg, rz_deg, radius, height, tex_id, u_offset, v_offset, tex_angle_deg, uv_mode, uscale, vscale, tex_file)
                scene_to_populate.cylinders.append((line_identifier_for_object, obj_data_tuple))

            elif command == "tree":
                # ... (tree 解析邏輯) ...
                if len(parts) < 5: print(f"警告: ({current_filename_for_display} 行 {line_num_in_file}) 'tree' 參數不足。"); continue
                try: rel_x, rel_y, rel_z = map(float, parts[1:4]); height = float(parts[4])
                except ValueError: print(f"警告: ({current_filename_for_display} 行 {line_num_in_file}) 'tree' 基本參數無效。"); continue
                if height <=0: print(f"警告: ({current_filename_for_display} 行 {line_num_in_file}) 'tree' 高度必須為正。"); continue
                tex_file = parts[5] if len(parts) > 5 else "tree_leaves.png"
                tex_id = texture_loader.load_texture(tex_file) if load_textures and texture_loader else None
                origin_angle = scene_to_populate.current_relative_origin_angle_rad; cos_a = math.cos(origin_angle); sin_a = math.sin(origin_angle)
                world_offset_x = rel_z * cos_a + rel_x * sin_a; world_offset_z = rel_z * sin_a - rel_x * cos_a
                world_x = scene_to_populate.current_relative_origin_pos[0] + world_offset_x; world_y = scene_to_populate.current_relative_origin_pos[1] + rel_y; world_z = scene_to_populate.current_relative_origin_pos[2] + world_offset_z
                obj_data_tuple = (world_x, world_y, world_z, height, tex_id, tex_file) # 保持樹的元組結構
                scene_to_populate.trees.append((line_identifier_for_object, obj_data_tuple))
                
            elif command == "sphere":
                # ... (sphere 解析邏輯) ...
                base_param_count = 7; min_parts = 1 + base_param_count
                if len(parts) < min_parts: print(f"警告: ({current_filename_for_display} 行 {line_num_in_file}) 'sphere' 參數不足。"); continue
                try: rel_x, rel_y, rel_z = map(float, parts[1:4]); rx_deg, rel_ry_deg, rz_deg = map(float, parts[4:7]); radius = float(parts[7])
                except ValueError: print(f"警告: ({current_filename_for_display} 行 {line_num_in_file}) 'sphere' 基本參數無效。"); continue
                if radius <=0: print(f"警告: ({current_filename_for_display} 行 {line_num_in_file}) 'sphere' 半徑必須為正。"); continue
                tex_file = parts[8] if len(parts) > 8 else "default_sphere.png"
                u_offset, v_offset, tex_angle_deg, uv_mode, uscale, vscale = 0.0,0.0,0.0,1,1.0,1.0
                try: u_offset = float(parts[9]) if len(parts) > 9 else 0.0; v_offset = float(parts[10]) if len(parts) > 10 else 0.0; tex_angle_deg = float(parts[11]) if len(parts) > 11 else 0.0; uv_mode = int(parts[12]) if len(parts) > 12 else 1; uscale = float(parts[13]) if len(parts) > 13 and uv_mode == 0 else 1.0; vscale = float(parts[14]) if len(parts) > 14 and uv_mode == 0 else 1.0
                except ValueError: pass
                tex_id = texture_loader.load_texture(tex_file) if load_textures and texture_loader else None
                origin_angle = scene_to_populate.current_relative_origin_angle_rad; cos_a = math.cos(origin_angle); sin_a = math.sin(origin_angle)
                world_offset_x = rel_z * cos_a + rel_x * sin_a; world_offset_z = rel_z * sin_a - rel_x * cos_a
                world_x = scene_to_populate.current_relative_origin_pos[0] + world_offset_x; world_y = scene_to_populate.current_relative_origin_pos[1] + rel_y; world_z = scene_to_populate.current_relative_origin_pos[2] + world_offset_z
                absolute_ry_deg = math.degrees(-origin_angle) + rel_ry_deg - 90
                obj_data_tuple = ("sphere", world_x, world_y, world_z, rx_deg, absolute_ry_deg, rz_deg, radius, tex_id, u_offset, v_offset, tex_angle_deg, uv_mode, uscale, vscale, tex_file)
                scene_to_populate.spheres.append((line_identifier_for_object, obj_data_tuple))

            elif command == "hill":
                # ... (hill 解析邏輯，使用新的參數)
                base_param_count = 5; min_parts = 1 + base_param_count
                if len(parts) < min_parts: print(f"警告: ({current_filename_for_display} 行 {line_num_in_file}) 'hill' 參數不足。"); continue
                try:
                    center_x = float(parts[1]); base_y = float(parts[2]); center_z = float(parts[3])
                    base_radius = float(parts[4]); peak_height_offset = float(parts[5])
                    if peak_height_offset <= 0 or base_radius <= 0: print(f"警告: ({current_filename_for_display} 行 {line_num_in_file}) 'hill' peak_h_offset 和 radius 必須為正。"); continue
                except ValueError: print(f"警告: ({current_filename_for_display} 行 {line_num_in_file}) 'hill' 基本參數無效。"); continue
                tex_param_start_index = 6
                tex_file = parts[tex_param_start_index] if len(parts) > tex_param_start_index else "grass.png"
                uscale, vscale = 10.0,10.0
                try:
                    uscale = float(parts[tex_param_start_index + 1]) if len(parts) > tex_param_start_index + 1 else 10.0
                    vscale = float(parts[tex_param_start_index + 2]) if len(parts) > tex_param_start_index + 2 else 10.0
                except ValueError: pass
                tex_id = texture_loader.load_texture(tex_file) if load_textures and texture_loader else None
                hill_data_tuple = (center_x, base_y, center_z, base_radius, peak_height_offset, tex_id, uscale, vscale, tex_file)
                scene_to_populate.hills.append((line_identifier_for_object, hill_data_tuple))

            elif command == "skybox":
                # ... (skybox 解析邏輯) ...
                if len(parts) < 2: print(f"警告: ({current_filename_for_display} 行 {line_num_in_file}) 'skybox' 需要 base_name。"); continue
                base_name = parts[1]
                current_info = {'type': 'skybox', 'base_name': base_name}
                if scene_to_populate.initial_background_info is None: scene_to_populate.initial_background_info = current_info
                scene_to_populate.last_background_info = current_info

            elif command == "skydome":
                # ... (skydome 解析邏輯) ...
                if len(parts) < 2: print(f"警告: ({current_filename_for_display} 行 {line_num_in_file}) 'skydome' 需要 texture_file。"); continue
                texture_file = parts[1]
                tex_id = None
                if load_textures and texture_loader: tex_id = texture_loader.load_texture(texture_file)
                current_info = {'type': 'skydome', 'file': texture_file, 'id': tex_id}
                if scene_to_populate.initial_background_info is None: scene_to_populate.initial_background_info = current_info
                scene_to_populate.last_background_info = current_info
                
            elif command == "map":
                # ... (map 解析邏輯) ...
                if len(parts) < 5: print(f"警告: ({current_filename_for_display} 行 {line_num_in_file}) 'map' 參數不足。"); continue
                filename = parts[1]
                try: center_x, center_z, scale_val = map(float, parts[2:5])
                except ValueError: print(f"警告: ({current_filename_for_display} 行 {line_num_in_file}) 'map' 參數無效。"); continue
                scene_to_populate.map_filename = filename
                scene_to_populate.map_world_center_x = center_x
                scene_to_populate.map_world_center_z = center_z
                scene_to_populate.map_world_scale = scale_val

            else:
                print(f"警告: ({current_filename_for_display} 行 {line_num_in_file}) 未知指令 '{command}'")

        except Exception as e:
             print(f"警告: ({current_filename_for_display} 行 {line_num_in_file}) 處理指令 '{line}' 時發生內部錯誤: {e}")
             import traceback
             traceback.print_exc()

    # --- 排序背景觸發器 ---
    scene_to_populate.background_triggers.sort(key=lambda item: item[0])
    return scene_to_populate

# --- 修改 parse_scene_from_lines 和 parse_scene_file ---
def parse_scene_from_lines(lines_list, base_dir_for_import: str, 
    filename_for_display: str, initial_scene: Scene = None, load_textures=True):
    """
    Parses scene definition from a list of strings.
    Args:
        lines_list: A list of strings.
        base_dir_for_import: The base directory for resolving 'import' statements in these lines.
        initial_scene: An optional Scene object to populate. If None, a new one is created.
        load_textures: Whether to load textures.
    Returns:
        A Scene object.
    """
    # 1. 獲取或創建 Scene 物件
    scene_obj = initial_scene if initial_scene is not None else Scene()
    # 2. 初始化或重置 Scene 物件中用於解析的內部狀態
    #    這些狀態由 _parse_scene_content 在處理 'start', 'straight', 'curve', 'skybox', 'skydome' 等指令時使用和更新。
    #    對於頂層調用 (即非 import 的情況)，這些狀態應該基於 Scene 物件的初始值或被重置。
    #    Scene 類的 __init__ 或 clear() 方法應該已經處理了這些的預設值。
    #    例如:
    #    scene_obj.current_parse_pos = np.copy(scene_obj.start_position)
    #    scene_obj.current_parse_angle_rad = math.radians(scene_obj.start_angle_deg)
    #    scene_obj.current_relative_origin_pos = np.copy(scene_obj.current_parse_pos)
    #    scene_obj.current_relative_origin_angle_rad = scene_obj.current_parse_angle_rad
    #    scene_obj.last_background_info = scene_obj.initial_background_info # 或者 None，取決於設計

    # 確保 Scene 的 __init__ 或 clear 已經正確設定了這些：
    # (如果 Scene.__init__ 已經做了，這裡就不需要重複)
    if not hasattr(scene_obj, 'current_parse_pos'):
        scene_obj.current_parse_pos = np.copy(scene_obj.start_position) # 從場景的 start_pos 開始
        scene_obj.current_parse_angle_rad = math.radians(scene_obj.start_angle_deg)
        scene_obj.current_relative_origin_pos = np.copy(scene_obj.current_parse_pos)
        scene_obj.current_relative_origin_angle_rad = scene_obj.current_parse_angle_rad
        scene_obj.last_background_info = scene_obj.initial_background_info # 初始背景也作為 last
    # -------------------------------------------------
    
    # 3. 初始化用於防止循環導入的集合
    imported_files_set = set() # 用於當前 parse_scene_from_lines 調用鏈的導入追蹤

    # 4. 調用核心解析函數
    #    對於從外部（如編輯器）傳入的代表主檔案內容的 lines_list，
    #    is_parsing_imported_file 應為 False。
    populated_scene = _parse_scene_content(
        lines_list=lines_list, 
        scene_to_populate=scene_obj, 
        current_file_directory=base_dir_for_import, 
        current_filename_for_display=filename_for_display,
        imported_files=imported_files_set, 
        is_parsing_imported_file=False, # <--- 關鍵：標記這是根文件/非導入上下文
        load_textures=load_textures
    )
    
    return populated_scene

def parse_scene_file(filepath_to_parse, initial_scene: Scene = None, load_textures=True):
    """
    Parses the scene definition from a file.
    Args:
        filepath_to_parse: Path to the scene definition file.
        initial_scene: An optional Scene object to populate. If None, a new one is created.
        load_textures: Whether to load textures.
    Returns:
        A Scene object, or None if file not found.
    """
    print(f"從檔案 '{filepath_to_parse}' 開始解析場景...")
    try:
        with open(filepath_to_parse, 'r', encoding="utf-8") as f:
            lines = f.readlines()
        # 傳遞檔案所在目錄作為 import 的基礎目錄
        return parse_scene_from_lines(lines, os.path.dirname(filepath_to_parse), 
            os.path.basename(filepath_to_parse),
                                      initial_scene, load_textures)
    except FileNotFoundError:
        print(f"錯誤: 場景檔案 '{filepath_to_parse}' 不存在。")
        return None # 或返回空的 Scene？取決於調用者的期望
    except Exception as e:
        print(f"讀取或解析場景檔案 '{filepath_to_parse}' 時發生未知錯誤: {e}")
        return initial_scene if initial_scene is not None else Scene() # 返回傳入的或新的空場景

# --- 修改 load_scene (主入口函數) ---
def load_scene(force_reload=False, specific_filepath=None):
    """
    Loads or reloads the scene file if modified.
    If specific_filepath is provided, it loads that file directly.
    Otherwise, it uses the global scene_file_path.
    """
    global last_modified_time, current_scene, scene_file_path

    # --- 決定要載入的檔案路徑 ---
    target_filepath = specific_filepath if specific_filepath is not None else scene_file_path
    if specific_filepath is not None: # 如果指定了檔案，總是強制重新載入該檔案
        force_reload = True
        # 更新全域 scene_file_path，這樣下次不指定時會是這個
        scene_file_path = specific_filepath 
    # ----------------------------

    try:
        if not os.path.exists(target_filepath):
            # 如果目標檔案不存在，並且它是全域 scene_file_path，則清理 current_scene
            if target_filepath == scene_file_path:
                print(f"錯誤: 場景檔案 '{target_filepath}' 在檢查更新時未找到。清理當前場景。")
                if current_scene: current_scene.clear()
                if texture_loader: texture_loader.clear_texture_cache()
                last_modified_time = 0
                return True # 表示場景已更改 (變為空)
            else: # 如果是 specific_filepath 且不存在，則直接返回 False
                print(f"錯誤: 指定的場景檔案 '{target_filepath}' 未找到。")
                return False


        current_mod_time = os.path.getmtime(target_filepath)
        # 只有當使用全域 scene_file_path 且未強制重載時，才比較修改時間
        needs_reload = force_reload or \
                       (target_filepath == scene_file_path and current_mod_time != last_modified_time)

        if needs_reload:
            print(f"偵測到場景檔案變更或強制重新載入 '{target_filepath}'...")

            if current_scene and current_scene.track:
                 current_scene.track.clear()
            if texture_loader:
                texture_loader.clear_texture_cache()

            # --- 創建一個新的 Scene 物件來填充 ---
            # 這樣可以確保之前的 current_scene (如果解析失敗) 不會被部分修改
            new_parsed_scene = Scene() 
            # 將 start_position 和 start_angle_deg 的預設值設定好
            # （或者 Scene 的 __init__ 已經做了）
            new_parsed_scene.current_parse_pos = np.copy(new_parsed_scene.start_position)
            new_parsed_scene.current_parse_angle_rad = math.radians(new_parsed_scene.start_angle_deg)
            new_parsed_scene.current_relative_origin_pos = np.copy(new_parsed_scene.current_parse_pos)
            new_parsed_scene.current_relative_origin_angle_rad = new_parsed_scene.current_parse_angle_rad
            new_parsed_scene.last_background_info = None


            # 使用 parse_scene_file 來處理，它內部會調用新的 parse_scene_from_lines
            populated_scene = parse_scene_file(target_filepath, initial_scene=new_parsed_scene, load_textures=True)

            if populated_scene: # parse_scene_file 在找不到檔案時返回 None
                current_scene = populated_scene # 替換全域場景物件
                if target_filepath == scene_file_path: # 只有當載入的是全域路徑時才更新時間戳
                    last_modified_time = current_mod_time
                print("場景已成功載入/重新載入。")
                return True 
            else:
                print(f"場景檔案 '{target_filepath}' 載入失敗。可能保留舊場景或變為空場景。")
                # 如果 parse_scene_file 返回 None (因 FileNotFoundError)，我們不應清除 current_scene
                # 但如果它返回了一個空的 Scene (因其他解析錯誤)，current_scene 會被替換
                # 這裡的邏輯需要確保 current_scene 在失敗時的狀態是合理的
                if current_scene: current_scene.clear() # 如果 populated_scene 為 None，則清除舊的
                return False 

        return False # 不需要重載

    except FileNotFoundError: # 這個 catch 應該在上面 target_filepath 檢查時處理
        # 保留以防萬一，但理論上不應該執行到這裡
        print(f"錯誤: 場景檔案 '{target_filepath}' 未找到 (例外捕獲)。")
        if current_scene: current_scene.clear()
        last_modified_time = 0
        return True 

    except Exception as e:
        print(f"檢查場景檔案更新時發生錯誤: {e}")
        import traceback
        traceback.print_exc() 
        return False

# --- get_current_scene (unchanged) ---
def get_current_scene():
    """獲取當前載入的場景"""
    global current_scene
    return current_scene