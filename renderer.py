# renderer.py
from OpenGL.GL import *
from OpenGL.GLU import *
import numpy as np
import numpy as math # Keep consistent with other files for now
# import math # Original math import removed for consistency
from track import TRACK_WIDTH, BALLAST_WIDTH, BALLAST_HEIGHT  # Keep track constants if used by draw_track
import texture_loader # Keep for loading general textures
import pygame # Keep for font loading and potentially _draw_text_texture
import os

from numba import jit, njit # Keep numba imports

import shaders_inline 

# --- Drawing Parameters (General) ---
# (保持不變)
GROUND_SIZE = 200.0
TREE_TRUNK_RADIUS = 0.2
TREE_LEAVES_RADIUS = 1.5
RAIL_COLOR = (0.4, 0.4, 0.5) # Keep
BALLAST_COLOR = (0.6, 0.55, 0.5) # Keep
CAB_COLOR = (0.2, 0.3, 0.7) # Keep
DASHBOARD_COLOR = (0.8, 0.8, 0.85) # Keep
LEVER_COLOR = (0.8, 0.1, 0.1) # Keep
NEEDLE_COLOR = (0.0, 0.0, 0.0) # Keep
TREE_FALLBACK_COLOR = (0.1, 0.6, 0.15) # 一個樹木的綠色
ALPHA_TEST_THRESHOLD = 0.5 # 常用的值，您可以調整 (0.0 到 1.0)
CYLINDER_SLICES = 32 # Keep (maybe reduce default slightly?)

# --- Minimap Parameters REMOVED ---

# --- REMOVED Globals for managing the current map texture ---

# --- Global HUD Font ---
# (保持不變)
hud_display_font = None
grid_label_font = None
coord_label_font = None
MINIMAP_GRID_LABEL_FONT_SIZE = 18
MINIMAP_COORD_LABEL_FONT_SIZE = 18

# --- Coordinate Display Parameters (Keep) ---
# (保持不變)
COORD_PADDING_X = 10
COORD_PADDING_Y = 10
COORD_TEXT_COLOR = (255, 255, 255, 255)

# --- Texture ID Cache (Update) ---
grass_tex = None
tree_bark_tex = None
tree_leaves_tex = None
cab_metal_tex = None
# --- NEW: Cache for Skybox textures ---
# Store cubemap IDs, keyed by base_name
skybox_texture_cache = {}

# --- REMOVED: Current minimap range variable ---

EDITOR_LABEL_OFFSET_X = 5 # Keep
EDITOR_LABEL_OFFSET_Y = 3 # Keep

# --- REMOVED: zoom_minimap function ---
# cube
#       V=1.0 +-------------------------------------+
#             |         | BOTTOM  |                 |  <-- 假設 Bottom 在頂部 V=0.66 - 0.99
#             |         | (Y-)    |                 |
#       V=0.66+---------+---------+-----------------+
#             |  LEFT   |  FRONT  |  RIGHT  | BACK  |  <-- 中間行 V=0.33 - 0.66
#             |  (X-)   |  (Z+)   |  (X+)   | (Z-)  |
#       V=0.33+---------+---------+---------+-------+
#             |         |  TOP    |                 |  <-- 假設 Top 在底部 V=0.0 - 0.33
#             |         |  (Y+)   |                 |
#       V=0.0 +---------+---------+-----------------+
#             U=0.0    U=0.25    U=0.5     U=0.75  U=1.0
# gableroof
#       V=1.0 +-------------------------------------+
#             |         |         |         |       |  
#             |         |         |         |       |  <-- 山牆
#       V=0.5 +         +         +         +-------+
#             |         |         |         |       |  <-- 山牆
#             |         |         |         |       |
#       V=0.0 +---------+---------+-----------------+
#             U=-1.0    U=-0.75    U=-0.5     U=-0.25  U=0.0 為了紋理水平鏡像因此width是負值也因此倒過來 (可能是法線方向錯誤
DEFAULT_UV_LAYOUTS = {
    # ... (cube, cylinder 的佈局，如果將來也用圖集的話) ...
    "cube": { 
        # 假設一個簡單的十字形或L形展開的部分，你需要定義6個面
        # (u_start, v_start, width, height)
        "front":  (0.25, 0.33, 0.25, 0.33), # Z+
        "back":   (0.75, 0.33, 0.25, 0.33), # Z-
        "left":   (0.0,  0.33, 0.25, 0.33), # X-
        "right":  (0.5,  0.33, 0.25, 0.33), # X+
        "top":    (0.25, 0.0,  0.25, 0.33), # Y+
        "bottom": (0.25, 0.66,  0.25, 0.33)  # Y-
        # 這個佈局只用了一部分圖集，你需要設計一個填滿或高效利用的佈局
    },    "gableroof": { # 人字形屋頂的預設UV佈局
        "left_slope":   (-0.25,  0.0,        -0.375, 1.0 ), # 兩個斜面
        "right_slope":  (-(0.5+0.125),  0.0, -0.375, 1.0 ), 
        "front_gable":  (0.0,  0.0,         -0.25, 0.5  ),# 兩個山牆
        "back_gable":   (0.0,  0.5,       -0.25, 0.5  ) # 
        # 你需要根據你的圖集設計調整這些UV子矩形
    },
    "flexroof_layout": {
        # 這些UV值 (u_start, v_start, width, height) 需要您根據
        # 您為 flexroof 設計的紋理圖集來精心設定。
        # 以下只是佔位符/示例，假設一個簡單的十字型或L型展開的某部分。
        # 頂面 (Y+)
        "top_face":    (0.25, 0.0, 0.25, 0.33), # 
        # 底面 (Y-) - 通常不可見，但可以為其定義以保持完整性
        "bottom_face": (0.25, 0.66, 0.25, 0.33), # 
        # +Z方向側面 (通常是主要屋頂斜面之一，如果 top_l < base_l)
        "side_z_pos":  (0.25, 0.33, 0.25, 0.33),  # 
        # -Z方向側面 (通常是另一個主要屋頂斜面)
        "side_z_neg":  (0.75, 0.33, 0.25, 0.33),  # 
        # +X方向側面 (山牆面或較窄的斜面)
        "side_x_pos":  (0.5, 0.33,  0.25, 0.33), # 
        # -X方向側面
        "side_x_neg":  (0.0, 0.33, 0.25, 0.33)  # 
    }
}

def map_local_uv_to_atlas_subrect(local_u, local_v, atlas_sub_rect_uvwh):
    rect_u, rect_v, rect_w, rect_h = atlas_sub_rect_uvwh
    return rect_u + local_u * rect_w, rect_v + local_v * rect_h

# # 著色器加載和編譯的輔助函數 
# def load_shader(shader_file, shader_type):
#     """載入並編譯單個著色器文件"""
#     shader_source = ""
#     try:
#         with open(shader_file, 'r', encoding='utf-8') as f:
#             shader_source = f.read()
#     except Exception as e:
#         print(f"錯誤: 無法讀取著色器文件 {shader_file}: {e}")
#         return None
# 
#     shader_id = glCreateShader(shader_type)
#     glShaderSource(shader_id, shader_source)
#     glCompileShader(shader_id)
# 
#     # 檢查編譯錯誤
#     if glGetShaderiv(shader_id, GL_COMPILE_STATUS) != GL_TRUE:
#         info_log = glGetShaderInfoLog(shader_id)
#         print(f"著色器編譯錯誤在 {shader_file}:\n{info_log.decode()}")
#         glDeleteShader(shader_id)
#         return None
#     return shader_id
# 
# def create_shader_program(vertex_shader_file, fragment_shader_file):
#     """創建並鏈接著色器程序"""
#     vertex_shader = load_shader(vertex_shader_file, GL_VERTEX_SHADER)
#     fragment_shader = load_shader(fragment_shader_file, GL_FRAGMENT_SHADER)
# 
#     if not vertex_shader or not fragment_shader:
#         return None
# 
#     program_id = glCreateProgram()
#     glAttachShader(program_id, vertex_shader)
#     glAttachShader(program_id, fragment_shader)
#     glLinkProgram(program_id)
# 
#     # 檢查鏈接錯誤
#     if glGetProgramiv(program_id, GL_LINK_STATUS) != GL_TRUE:
#         info_log = glGetProgramInfoLog(program_id)
#         print(f"著色器程序鏈接錯誤:\n{info_log.decode()}")
#         glDeleteProgram(program_id)
#         glDeleteShader(vertex_shader)
#         glDeleteShader(fragment_shader)
#         return None
# 
#     # 鏈接成功後可以刪除單個著色器對象
#     glDeleteShader(vertex_shader)
#     glDeleteShader(fragment_shader)
#     
#     print(f"著色器程序已創建並鏈接: ID={program_id} (VS: {vertex_shader_file}, FS: {fragment_shader_file})")
#     return program_id
# 
# # 在 renderer.py 的頂部某處（或 init_renderer 中）加載山丘著色器
# # _hill_shader_program_id = None # 已在上面定義
# 




# --- Keep set_hud_font ---
# (保持不變)
def set_hud_font(font):
    global hud_display_font, grid_label_font, coord_label_font
    hud_display_font = font
    grid_label_font = None
    coord_label_font = None
    if hud_display_font:
        try:
            grid_label_font = pygame.font.SysFont(None, MINIMAP_GRID_LABEL_FONT_SIZE)
            print(f"網格標籤字體已創建 (大小: {MINIMAP_GRID_LABEL_FONT_SIZE}).")
            import minimap_renderer # Try importing here to avoid circular dependency issues at top level
            minimap_renderer.set_grid_label_font(grid_label_font)
        except Exception as e: print(f"警告: 無法加載網格標籤字體 (大小: {MINIMAP_GRID_LABEL_FONT_SIZE}): {e}"); grid_label_font = None
        try:
            coord_label_font = pygame.font.SysFont(None, MINIMAP_COORD_LABEL_FONT_SIZE)
            print(f"座標標籤字體已創建 (大小: {MINIMAP_COORD_LABEL_FONT_SIZE}).")
            import minimap_renderer
            minimap_renderer.set_coord_label_font(coord_label_font)
        except Exception as e: print(f"警告: 無法加載座標標籤字體 (大小: {MINIMAP_COORD_LABEL_FONT_SIZE}): {e}"); coord_label_font = None
    else: print("警告: 主 HUD 字體未設置，標籤字體無法創建。")


# --- REMOVED: Minimap Texture Loading Functions ---

# --- 著色器加載和編譯輔助函數 ---
def compile_shader_from_source(shader_source, shader_type): # 這個函數用於從字符串編譯
    """編譯單個著色器源碼字符串"""
    if not shader_source:
        print(f"錯誤: 著色器源碼為空 (類型: {shader_type})")
        return None
    shader_id = glCreateShader(shader_type)
    glShaderSource(shader_id, shader_source)
    glCompileShader(shader_id)
    if glGetShaderiv(shader_id, GL_COMPILE_STATUS) != GL_TRUE:
        info_log = glGetShaderInfoLog(shader_id)
        shader_type_str = "Vertex" if shader_type == GL_VERTEX_SHADER else "Fragment" if shader_type == GL_FRAGMENT_SHADER else "Unknown"
        print(f"{shader_type_str} 著色器源碼編譯錯誤:\n{info_log.decode()}")
        glDeleteShader(shader_id)
        return None
    return shader_id

def create_shader_program_from_sources(vertex_source, fragment_source): # 這個函數用於從字符串創建程序
    """從源碼字符串創建並鏈接著色器程序"""
    vertex_shader = compile_shader_from_source(vertex_source, GL_VERTEX_SHADER)
    fragment_shader = compile_shader_from_source(fragment_source, GL_FRAGMENT_SHADER)

    if not vertex_shader or not fragment_shader:
        # compile_shader_from_source 內部已經打印了錯誤，這裡可以不再打印
        # 清理已成功編譯的部分（如果有的話）
        if vertex_shader: glDeleteShader(vertex_shader)
        if fragment_shader: glDeleteShader(fragment_shader)
        return None

    program_id = glCreateProgram()
    glAttachShader(program_id, vertex_shader)
    glAttachShader(program_id, fragment_shader)
    glLinkProgram(program_id)

    if glGetProgramiv(program_id, GL_LINK_STATUS) != GL_TRUE:
        info_log = glGetProgramInfoLog(program_id)
        print(f"著色器程序鏈接錯誤 (源碼):\n{info_log.decode()}")
        glDeleteProgram(program_id) # 清理程序對象
        # 單個shader對象也需要清理
        glDeleteShader(vertex_shader)
        glDeleteShader(fragment_shader)
        return None

    glDeleteShader(vertex_shader) # 鏈接後即可刪除
    glDeleteShader(fragment_shader)
    
    print(f"著色器程序已從源碼創建並鏈接: ID={program_id}")
    return program_id

_hill_shader_program_id = None # 全局變量
_building_shader_program_id = None # <--- 新增全局變量

def init_hill_shader(): # 可以在 init_renderer 中調用
    global _hill_shader_program_id
    if _hill_shader_program_id is None:
        print("正在從 shaders_inline 初始化山丘著色器...") # 添加日誌
        _hill_shader_program_id = create_shader_program_from_sources(
            shaders_inline.HILL_VERTEX_SHADER_SOURCE, 
            shaders_inline.HILL_FRAGMENT_SHADER_SOURCE
        )
        if _hill_shader_program_id is None:
            print("致命錯誤: 無法從源碼初始化山丘著色器程序！")
        else:
            print(f"山丘著色器程序已從源碼成功初始化: ID={_hill_shader_program_id}")
             
def init_building_shader():
    global _building_shader_program_id
    if _building_shader_program_id is None:
        print("正在從 shaders_inline 初始化 Building 著色器...")
        _building_shader_program_id = create_shader_program_from_sources(
            shaders_inline.BUILDING_VERTEX_SHADER_SOURCE,
            shaders_inline.BUILDING_FRAGMENT_SHADER_SOURCE
        )
        if _building_shader_program_id is None:
            print("致命錯誤: 無法從源碼初始化 Building 著色器程序！")
        else:
            print(f"Building 著色器程序已從源碼成功初始化: ID={_building_shader_program_id}")
            
# --- init_renderer (Update) ---
def init_renderer():
    """Initializes the renderer, loads common textures."""
    global grass_tex, tree_bark_tex, tree_leaves_tex, cab_metal_tex
    # Load common non-map textures
    grass_tex = texture_loader.load_texture("grass.png").get("id")
    tree_bark_tex = texture_loader.load_texture("tree_bark.png").get("id")
    tree_leaves_tex = texture_loader.load_texture("tree_leaves.png").get("id")
    cab_metal_tex = texture_loader.load_texture("metal.png").get("id") # Assuming cab uses metal texture

    # --- NEW: Preload common skyboxes if needed? ---
    # Example: Load default skybox if specified elsewhere
    # load_skybox("default_sky") # Example call

    # Set OpenGL states (Keep)
    glEnable(GL_DEPTH_TEST)
    glEnable(GL_TEXTURE_2D)
    glEnable(GL_LIGHTING)
    glEnable(GL_LIGHT0)
    glEnable(GL_COLOR_MATERIAL) # Allow glColor to affect material
    glColorMaterial(GL_FRONT_AND_BACK, GL_AMBIENT_AND_DIFFUSE)

    # Set lighting (Keep)
    glLightfv(GL_LIGHT0, GL_AMBIENT, [0.3, 0.3, 0.3, 1.0])
    glLightfv(GL_LIGHT0, GL_DIFFUSE, [0.8, 0.8, 0.8, 1.0])
    glLightfv(GL_LIGHT0, GL_SPECULAR, [0.5, 0.5, 0.5, 1.0])
    glLightfv(GL_LIGHT0, GL_POSITION, [100.0, 150.0, 100.0, 1.0]) # Position light

    glEnable(GL_NORMALIZE) # Automatically normalize normals

    init_hill_shader() # 初始化山丘著色器
    init_building_shader() # <--- 新增: 初始化 Building 著色器

# --- draw_ground (unchanged) ---
def draw_ground(show_ground):
    # (Logic unchanged)
    if not show_ground: return
    if grass_tex: glBindTexture(GL_TEXTURE_2D, grass_tex); glEnable(GL_TEXTURE_2D)
    else: glDisable(GL_TEXTURE_2D)
    glColor3f(0.3, 0.7, 0.3)
    glBegin(GL_QUADS)
    tex_repeat = GROUND_SIZE / 10.0
    glNormal3f(0, 1, 0)
    glTexCoord2f(0, 0); glVertex3f(-GROUND_SIZE, 0, -GROUND_SIZE)
    glTexCoord2f(tex_repeat, 0); glVertex3f(GROUND_SIZE, 0, -GROUND_SIZE)
    glTexCoord2f(tex_repeat, tex_repeat); glVertex3f(GROUND_SIZE, 0, GROUND_SIZE)
    glTexCoord2f(0, tex_repeat); glVertex3f(-GROUND_SIZE, 0, GROUND_SIZE)
    glEnd()
    if grass_tex: glBindTexture(GL_TEXTURE_2D, 0)
    glEnable(GL_TEXTURE_2D)


# --- draw_track (unchanged) ---
def draw_track(track_obj):
    # (Logic unchanged)
    if not track_obj or not track_obj.segments: return
    glDisable(GL_TEXTURE_2D)
    for segment in track_obj.segments:
        # --- 修改：檢查 is_buffer_ready 標誌 ---
        if not segment.is_buffer_ready:
            # 可選：打印一個日誌，說明跳過了這個段的繪製
            # print(f"TrackSegment (line {segment.source_line_number}): Buffers not ready, skipping draw.")
            continue # 跳過繪製此段
        # ------------------------------------
        # 繪製主軌道段的道碴
        if segment.ballast_vao and segment.ballast_vertices:
            glColor3fv(BALLAST_COLOR)
            
            error_before_bind = glGetError()
            if error_before_bind != GL_NO_ERROR:
                print(f"OpenGL Error {error_before_bind} BEFORE glBindVertexArray (ballast) for segment line {segment.source_line_number}, VAO ID to bind: {segment.ballast_vao}")
                
            glBindVertexArray(segment.ballast_vao)
            
            error_after_bind = glGetError() # PyOpenGL 通常在操作後檢查，但我們也可以手動加
            if error_after_bind != GL_NO_ERROR:
                print(f"OpenGL Error {error_after_bind} AFTER glBindVertexArray (ballast) for segment line {segment.source_line_number}, VAO ID bound: {segment.ballast_vao}")
                
            # --- MODIFICATION: Ensure vertex_count is calculated correctly ---
            # ballast_vertices stores x,y,z per vertex, so len gives total floats. Divide by 3 for vertex count.
            vertex_count = len(segment.ballast_vertices) // 3
            if vertex_count > 0:
                 glDrawArrays(GL_TRIANGLES, 0, vertex_count)
            # --- END OF MODIFICATION ---
            glBindVertexArray(0)
        
        glLineWidth(2.0); # Set line width for rails
        glColor3fv(RAIL_COLOR) # Set color before drawing
        # Main Left Rail
        if segment.rail_left_vao and segment.rail_left_vertices:

            error_before_bind = glGetError()
            if error_before_bind != GL_NO_ERROR:
                print(f"OpenGL Error {error_before_bind} BEFORE glBindVertexArray (rail_left_vao) for segment line {segment.source_line_number}, VAO ID to bind: {segment.ballast_vao}")

            glBindVertexArray(segment.rail_left_vao)
            
            vertex_count = len(segment.rail_left_vertices) // 3
            if vertex_count > 0:
                glDrawArrays(GL_LINE_STRIP, 0, vertex_count)
            glBindVertexArray(0)
        # Main Right Rail
        if segment.rail_right_vao and segment.rail_right_vertices:

            error_before_bind = glGetError()
            if error_before_bind != GL_NO_ERROR:
                print(f"OpenGL Error {error_before_bind} BEFORE glBindVertexArray (rail_right_vao) for segment line {segment.source_line_number}, VAO ID to bind: {segment.ballast_vao}")

            glBindVertexArray(segment.rail_right_vao)
            
            vertex_count = len(segment.rail_right_vertices) // 3
            if vertex_count > 0:
                glDrawArrays(GL_LINE_STRIP, 0, vertex_count)
            glBindVertexArray(0)
#    glEnable(GL_TEXTURE_2D)

        # --- START OF MODIFICATION ---
        # --- Draw Visual Branches for this segment ---
        if hasattr(segment, 'visual_branches') and segment.visual_branches:
            for branch_def in segment.visual_branches:
                # Draw Ballast for the branch
                if branch_def.get('ballast_vao') and branch_def.get('ballast_vertices'):
                    glColor3fv(BALLAST_COLOR) # Use same ballast color, or could be different
                    
                    error_before_bind = glGetError()
                    if error_before_bind != GL_NO_ERROR:
                        print(f"OpenGL Error {error_before_bind} BEFORE glBindVertexArray (branch_def ballast_vao) for segment line {segment.source_line_number}, VAO ID to bind: {segment.ballast_vao}")
                    
                    glBindVertexArray(branch_def['ballast_vao'])
                    
                    vertex_count_b_ballast = len(branch_def['ballast_vertices']) // 3
                    if vertex_count_b_ballast > 0:
                        glDrawArrays(GL_TRIANGLES, 0, vertex_count_b_ballast)
                    glBindVertexArray(0)

                # Draw Left Rail for the branch
                if branch_def.get('rail_left_vao') and branch_def.get('rail_left_vertices'):
                    glColor3fv(RAIL_COLOR) # Use same rail color
                    
                    error_before_bind = glGetError()
                    if error_before_bind != GL_NO_ERROR:
                        print(f"OpenGL Error {error_before_bind} BEFORE glBindVertexArray (branch_def rail_left_vao) for segment line {segment.source_line_number}, VAO ID to bind: {segment.ballast_vao}")
                        
                    glBindVertexArray(branch_def['rail_left_vao'])
                    
                    vertex_count_b_rail_l = len(branch_def['rail_left_vertices']) // 3
                    if vertex_count_b_rail_l > 0:
                        glDrawArrays(GL_LINE_STRIP, 0, vertex_count_b_rail_l)
                    glBindVertexArray(0)

                # Draw Right Rail for the branch
                if branch_def.get('rail_right_vao') and branch_def.get('rail_right_vertices'):
                    glColor3fv(RAIL_COLOR) # Use same rail color
                    
                    error_before_bind = glGetError()
                    if error_before_bind != GL_NO_ERROR:
                        print(f"OpenGL Error {error_before_bind} BEFORE glBindVertexArray (branch_def rail_right_vao) for segment line {segment.source_line_number}, VAO ID to bind: {segment.ballast_vao}")
                        
                    glBindVertexArray(branch_def['rail_right_vao'])
                    
                    vertex_count_b_rail_r = len(branch_def['rail_right_vertices']) // 3
                    if vertex_count_b_rail_r > 0:
                        glDrawArrays(GL_LINE_STRIP, 0, vertex_count_b_rail_r)
                    glBindVertexArray(0)
        # --- END OF MODIFICATION ---

    glEnable(GL_TEXTURE_2D) # Re-enable textures if they were disabled for track drawing

# --- _calculate_uv (unchanged) ---
@njit
def _calculate_uv(u_base, v_base, center_u, center_v, u_offset, v_offset, angle_rad, uv_mode, uscale=1.0, vscale=1.0):
    # (Logic unchanged)
    if uv_mode == 0:
        if uscale == 0: uscale = 1e-6
        if vscale == 0: vscale = 1e-6
        u_scaled = u_base / uscale; v_scaled = v_base / vscale
        u_base = u_scaled; v_base = v_scaled
        center_u_scaled = center_u / uscale; center_v_scaled = center_v / vscale
        center_u = center_u_scaled; center_v = center_v_scaled
    cos_t = math.cos(angle_rad); sin_t = math.sin(angle_rad)
    u_trans = u_base - center_u; v_trans = v_base - center_v
    u_rot = u_trans * cos_t - v_trans * sin_t; v_rot = u_trans * sin_t + v_trans * cos_t
    final_u = u_rot + center_u + u_offset; final_v = v_rot + center_v + v_offset
    return final_u, final_v


def get_yxz_intrinsic_composite_rotation_4x4(rx_deg, ry_deg, rz_deg):
    """
    Calculates a 4x4 composite rotation matrix using YXZ intrinsic order.
    Returns a ROW-MAJOR NumPy array.
    """
    rx_rad, ry_rad, rz_rad = math.radians(rx_deg), math.radians(ry_deg), math.radians(rz_deg)
    
    cos_rx, sin_rx = math.cos(rx_rad), math.sin(rx_rad)
    cos_ry, sin_ry = math.cos(ry_rad), math.sin(ry_rad)
    cos_rz, sin_rz = math.cos(rz_rad), math.sin(rz_rad)

    # All matrices defined here are ROW-MAJOR
    m_y = np.array([
        [cos_ry,  0, sin_ry, 0],
        [0,       1,      0, 0],
        [-sin_ry, 0, cos_ry, 0],
        [0,       0,      0, 1]
    ], dtype=np.float32)
    
    m_x = np.array([
        [1,      0,       0, 0],
        [0, cos_rx, -sin_rx, 0],
        [0, sin_rx,  cos_rx, 0],
        [0,      0,       0, 1]
    ], dtype=np.float32)
    
    m_z = np.array([
        [cos_rz, -sin_rz, 0, 0],
        [sin_rz,  cos_rz, 0, 0],
        [0,            0, 1, 0],
        [0,            0, 0, 1]
    ], dtype=np.float32)
    
    # YXZ intrinsic: R_composite = Ry @ Rx @ Rz
    # This means a vector V is transformed as (Ry @ Rx @ Rz) @ V
    composite_rotation = m_y @ m_x @ m_z
    return composite_rotation # Returns ROW-MAJOR

# --- 新增: 生成立方體網格數據 (模型空間, Atlas UV) ---
def generate_cube_mesh_data(width, depth, height, object_uv_layout_key="cube"):
    """
    Generates vertex data for a cube in model space with Atlas UVs.
    Anchor is at the bottom-center (0,0,0), Y is up.
    Returns: (vertex_data_numpy_array, vertex_count)
    vertex_data format: [vx,vy,vz, nx,ny,nz, atlas_u,atlas_v]
    """
    w2, d2, h_val = width / 2.0, depth / 2.0, height
    
    # 獲取 Atlas 佈局
    uv_layout = DEFAULT_UV_LAYOUTS.get(object_uv_layout_key)
    if not uv_layout:
        print(f"警告: generate_cube_mesh_data - 未找到 UV 佈局 '{object_uv_layout_key}'。將使用 (0,0) 作為所有 UV。")
        # 創建一個空的 fallback 佈局，或者為每個面使用 (0,0,0,0)
        uv_layout = {face: (0,0,0,0) for face in ["front", "back", "left", "right", "top", "bottom"]}

    vertices = []

    # Helper to add quad (two triangles)
    def add_quad(v1, v2, v3, v4, normal, uv_face_key):
        uv_r = uv_layout.get(uv_face_key, (0,0,0,0)) # Default to black UV if key missing
        
        # Triangle 1: v1, v2, v3
        vertices.extend([*v1, *normal, *map_local_uv_to_atlas_subrect(0,0,uv_r)])
        vertices.extend([*v2, *normal, *map_local_uv_to_atlas_subrect(1,0,uv_r)])
        vertices.extend([*v3, *normal, *map_local_uv_to_atlas_subrect(1,1,uv_r)])
        # Triangle 2: v1, v3, v4
        vertices.extend([*v1, *normal, *map_local_uv_to_atlas_subrect(0,0,uv_r)])
        vertices.extend([*v3, *normal, *map_local_uv_to_atlas_subrect(1,1,uv_r)])
        vertices.extend([*v4, *normal, *map_local_uv_to_atlas_subrect(0,1,uv_r)])

    # Front face (Z = +d2)
    add_quad([-w2,0,d2], [w2,0,d2], [w2,h_val,d2], [-w2,h_val,d2], [0,0,1], "front")
    # Back face (Z = -d2)
    add_quad([w2,0,-d2], [-w2,0,-d2], [-w2,h_val,-d2], [w2,h_val,-d2], [0,0,-1], "back")
    # Left face (X = -w2)
    add_quad([-w2,0,-d2], [-w2,0,d2], [-w2,h_val,d2], [-w2,h_val,-d2], [-1,0,0], "left")
    # Right face (X = +w2)
    add_quad([w2,0,d2], [w2,0,-d2], [w2,h_val,-d2], [w2,h_val,d2], [1,0,0], "right")
    # Top face (Y = +h_val)
    add_quad([-w2,h_val,d2], [w2,h_val,d2], [w2,h_val,-d2], [-w2,h_val,-d2], [0,1,0], "top")
    # Bottom face (Y = 0)
    add_quad([-w2,0,-d2], [w2,0,-d2], [w2,0,d2], [-w2,0,d2], [0,-1,0], "bottom")
    
    vertex_data = np.array(vertices, dtype=np.float32)
    vertex_count = len(vertices) // 8 # 8 floats per vertex
    return vertex_data, vertex_count

# --- 新增: 創建 Building VBO/VAO ---
def create_building_buffers(building_entry_with_line_id): # <--- 參數名更改以反映其結構
    """
    Creates VBO and VAO for a single building entry.
    building_entry_with_line_id is (line_identifier, obj_data_tuple_new_structure).
    """
    line_id, obj_data_tuple_original = building_entry_with_line_id # <--- 首先解包行號和元組
    
    EXPECTED_TUPLE_LENGTH = 23
    VAO_ID_INDEX = 20
    VBO_ID_INDEX = 21
    VERTEX_COUNT_INDEX = 22

    current_data_list = list(obj_data_tuple_original) # 操作副本
    while len(current_data_list) < EXPECTED_TUPLE_LENGTH:
        current_data_list.append(None)
    if current_data_list[VERTEX_COUNT_INDEX] is None:
        current_data_list[VERTEX_COUNT_INDEX] = 0

    try:
        if len(obj_data_tuple_original) < 10: # 檢查原始元組長度
            print(f"警告: create_building_buffers - Building (行: {line_id}) 原始 obj_data_tuple 太短，無法獲取尺寸。Tuple: {obj_data_tuple_original}")
            current_data_list[VAO_ID_INDEX] = None
            current_data_list[VBO_ID_INDEX] = None
            current_data_list[VERTEX_COUNT_INDEX] = 0
            return tuple(current_data_list), False

        width = obj_data_tuple_original[7]
        depth = obj_data_tuple_original[8]
        height = obj_data_tuple_original[9]

    except IndexError:
        print(f"警告: create_building_buffers - Building (行: {line_id}) obj_data_tuple 索引錯誤。Tuple: {obj_data_tuple_original}")
        current_data_list[VAO_ID_INDEX] = None
        current_data_list[VBO_ID_INDEX] = None
        current_data_list[VERTEX_COUNT_INDEX] = 0
        return tuple(current_data_list), False
    except TypeError as e: 
        print(f"警告: create_building_buffers - Building (行: {line_id}) 尺寸參數類型錯誤: {e}. Tuple: {obj_data_tuple_original}")
        current_data_list[VAO_ID_INDEX] = None
        current_data_list[VBO_ID_INDEX] = None
        current_data_list[VERTEX_COUNT_INDEX] = 0
        return tuple(current_data_list), False

    if not all(isinstance(dim, (int, float)) and dim > 0 for dim in [width, depth, height]):
        print(f"警告: create_building_buffers - Building (行: {line_id}) 尺寸參數無效 (w={width}, d={depth}, h={height})。")
        current_data_list[VAO_ID_INDEX] = None
        current_data_list[VBO_ID_INDEX] = None
        current_data_list[VERTEX_COUNT_INDEX] = 0
        return tuple(current_data_list), False
        
    old_vao_id = current_data_list[VAO_ID_INDEX] if len(current_data_list) > VAO_ID_INDEX else None
    old_vbo_id = current_data_list[VBO_ID_INDEX] if len(current_data_list) > VBO_ID_INDEX else None
    if old_vao_id is not None:
        try: glDeleteVertexArrays(1, [old_vao_id])
        except Exception: pass 
    if old_vbo_id is not None:
        try: glDeleteBuffers(1, [old_vbo_id])
        except Exception: pass 
    current_data_list[VAO_ID_INDEX] = None
    current_data_list[VBO_ID_INDEX] = None
    current_data_list[VERTEX_COUNT_INDEX] = 0

    vertex_data, vertex_count = generate_cube_mesh_data(width, depth, height, object_uv_layout_key="cube") 

    if vertex_count == 0:
        print(f"警告: Building (行: {line_id}) 调用 generate_cube_mesh_data 未生成頂點數據。")
        return tuple(current_data_list), False

    vbo_id = None
    vao_id = None
    try:
        vbo_id = glGenBuffers(1)
        glBindBuffer(GL_ARRAY_BUFFER, vbo_id)
        glBufferData(GL_ARRAY_BUFFER, vertex_data.nbytes, vertex_data, GL_STATIC_DRAW)

        vao_id = glGenVertexArrays(1)
        glBindVertexArray(vao_id)
        glBindBuffer(GL_ARRAY_BUFFER, vbo_id) 
        stride = 8 * sizeof(GLfloat) 
        glVertexAttribPointer(0, 3, GL_FLOAT, GL_FALSE, stride, ctypes.c_void_p(0))
        glEnableVertexAttribArray(0)
        glVertexAttribPointer(1, 3, GL_FLOAT, GL_FALSE, stride, ctypes.c_void_p(3 * sizeof(GLfloat))) 
        glEnableVertexAttribArray(1)
        glVertexAttribPointer(2, 2, GL_FLOAT, GL_FALSE, stride, ctypes.c_void_p(6 * sizeof(GLfloat))) 
        glEnableVertexAttribArray(2)
        
        glBindVertexArray(0) 
        glBindBuffer(GL_ARRAY_BUFFER, 0) 

        current_data_list[VAO_ID_INDEX] = vao_id
        current_data_list[VBO_ID_INDEX] = vbo_id
        current_data_list[VERTEX_COUNT_INDEX] = vertex_count
        
        return tuple(current_data_list), True

    except Exception as e_gl:
        print(f"錯誤: Building (行: {line_id}) 創建 OpenGL 緩衝區時失敗: {e_gl}")
        if vao_id is not None and glIsVertexArray(vao_id): glDeleteVertexArrays(1, [vao_id])
        if vbo_id is not None and glIsBuffer(vbo_id): glDeleteBuffers(1, [vbo_id])
        current_data_list[VAO_ID_INDEX] = None
        current_data_list[VBO_ID_INDEX] = None
        current_data_list[VERTEX_COUNT_INDEX] = 0
        return tuple(current_data_list), False

# --- 修改: 清理 Building VBO/VAO (參數也需要是 entry_with_line_id) ---
def cleanup_building_buffers_for_entry(building_entry_with_line_id):
    line_id, obj_data_tuple = building_entry_with_line_id # <--- 解包
    
    EXPECTED_TUPLE_LENGTH = 23
    VAO_ID_INDEX = 20
    VBO_ID_INDEX = 21
    VERTEX_COUNT_INDEX = 22

    if len(obj_data_tuple) < EXPECTED_TUPLE_LENGTH:
        # print(f"DEBUG: cleanup_building_buffers_for_entry - Tuple for line {line_id} too short, nothing to clean.")
        return building_entry_with_line_id # 返回原始 entry

    vao_id = obj_data_tuple[VAO_ID_INDEX]
    vbo_id = obj_data_tuple[VBO_ID_INDEX]
    
    if vao_id is not None:
        try: glDeleteVertexArrays(1, [vao_id])
        except Exception as e: print(f"清理 Building VAO {vao_id} (行: {line_id}) 錯誤: {e}")
    if vbo_id is not None:
        try: glDeleteBuffers(1, [vbo_id])
        except Exception as e: print(f"清理 Building VBO {vbo_id} (行: {line_id}) 錯誤: {e}")
    
    new_list = list(obj_data_tuple)
    new_list[VAO_ID_INDEX] = None
    new_list[VBO_ID_INDEX] = None
    new_list[VERTEX_COUNT_INDEX] = 0
    return (line_id, tuple(new_list))

def cleanup_all_building_buffers(scene_buildings_list):
    # print("正在清理所有 Building 的緩衝區...")
    if scene_buildings_list: # 檢查列表是否為空
        for i in range(len(scene_buildings_list)):
            scene_buildings_list[i] = cleanup_building_buffers_for_entry(scene_buildings_list[i])


# --- draw_cube (unchanged) ---
def draw_cube(width, depth, height,
              texture_id_from_scene=None,
              u_offset=0.0, v_offset=0.0, tex_angle_deg=0.0, uv_mode=1,
              uscale=1.0, vscale=1.0,
              texture_has_alpha=False,
              default_alpha_test_threshold=0.1,
              object_uv_layout_key="cube"
              ):
#     print(f"DEBUG:  texture_id_from_scene: {texture_id_from_scene} (type: {type(texture_id_from_scene)})")
    gl_texture_id_to_use = None 
    if texture_id_from_scene is not None: # 檢查是否為 None
        try:
            # (Logic unchanged)
            if glIsTexture(texture_id_from_scene): # 再檢查是否為有效的 GL 紋理對象
                gl_texture_id_to_use = texture_id_from_scene
                glBindTexture(GL_TEXTURE_2D, gl_texture_id_to_use);
                glEnable(GL_TEXTURE_2D)

                # 根據 uv_mode 設置紋理環繞是一個好主意
                wrap_s_mode = GL_REPEAT
                wrap_t_mode = GL_REPEAT

                if uv_mode == 1: # 物件比例貼圖，可能邊緣裁剪更好看，避免接縫問題
                    pass # GL_REPEAT 也可以，取決於紋理設計
                    # wrap_s_mode = GL_CLAMP_TO_EDGE
                    # wrap_t_mode = GL_CLAMP_TO_EDGE
                    
                glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, wrap_s_mode)
                glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, wrap_t_mode)
            else:
                glDisable(GL_TEXTURE_2D)
        except Exception as e_tex_check: # glIsTexture 在某些情況下可能出錯
            print(f"DEBUG: draw_cube - Error checking texture ID {texture_id_from_scene}: {e_tex_check}")
            glDisable(GL_TEXTURE_2D)
    else: # texture_id_from_scene is None
        glDisable(GL_TEXTURE_2D)

    # 處理alpha
    alpha_testing_was_actually_enabled_this_call = False
    if gl_texture_id_to_use and texture_has_alpha: 
        glEnable(GL_ALPHA_TEST)
        glAlphaFunc(GL_GREATER, default_alpha_test_threshold)
        alpha_testing_was_actually_enabled_this_call = True
        
        # 確保 Alpha Test 時的狀態是我們期望的
        glDepthMask(GL_TRUE)   # 允許寫入深度緩衝區，像不透明物體一樣參與深度比較
        glDisable(GL_BLEND)  # Alpha Test 通常不與 Alpha Blending 同時對同一物件使用
        # print(f"DEBUG: Alpha Test ENABLED for texture ID {gl_texture_id_to_use}")
    # else:
        # print(f"DEBUG: Alpha Test NOT enabled. TexID: {gl_texture_id_to_use}, HasAlpha: {texture_has_alpha}")

    w2, d2_half, h_val = width / 2.0, depth / 2.0, height # 注意變數名，原版用 d, h
                                        # 這裡 height 是總高度，所以頂面Y是 height，底面Y是 0
    
    original_tex_angle_rad = math.radians(tex_angle_deg) 
    
    glBegin(GL_QUADS)
    if uv_mode == 2: # --- 新的佈局式紋理方案 ---
        uv_layout = DEFAULT_UV_LAYOUTS.get(object_uv_layout_key)
        if not uv_layout:
            print(f"警告: uv_mode=2 但未找到物件 '{object_uv_layout_key}' 的UV佈局。紋理可能不正確。")
            # 在這種情況下，可以選擇不繪製紋理，或者使用(0,0)作為所有UV
            # 為了避免崩潰，我們先讓它繼續，但紋理會是錯的
        
        # 繪製6個面，每個面使用 uv_layout 中定義的子矩形
        # 頂點順序：左下、右下、右上、左上 (當你面向該面時)
        # 局部UV也按此順序：(0,0), (1,0), (1,1), (0,1)

        # 前面 (Front Face, Z = +d2_half)
        if uv_layout and "front" in uv_layout:
            uv_r = uv_layout["front"]
            glNormal3f(0,0,1)
            glTexCoord2f(*map_local_uv_to_atlas_subrect(0,0,uv_r)); glVertex3f(-w2, 0,     d2_half)
            glTexCoord2f(*map_local_uv_to_atlas_subrect(1,0,uv_r)); glVertex3f( w2, 0,     d2_half)
            glTexCoord2f(*map_local_uv_to_atlas_subrect(1,1,uv_r)); glVertex3f( w2, h_val, d2_half)
            glTexCoord2f(*map_local_uv_to_atlas_subrect(0,1,uv_r)); glVertex3f(-w2, h_val, d2_half)

        # 後面 (Back Face, Z = -d2_half)
        if uv_layout and "back" in uv_layout:
            uv_r = uv_layout["back"]
            glNormal3f(0,0,-1)
            glTexCoord2f(*map_local_uv_to_atlas_subrect(0,0,uv_r)); glVertex3f( w2, 0,     -d2_half) # 注意頂點順序以保持法線向外
            glTexCoord2f(*map_local_uv_to_atlas_subrect(1,0,uv_r)); glVertex3f(-w2, 0,     -d2_half)
            glTexCoord2f(*map_local_uv_to_atlas_subrect(1,1,uv_r)); glVertex3f(-w2, h_val, -d2_half)
            glTexCoord2f(*map_local_uv_to_atlas_subrect(0,1,uv_r)); glVertex3f( w2, h_val, -d2_half)

        # 左面 (Left Face, X = -w2)
        if uv_layout and "left" in uv_layout:
            uv_r = uv_layout["left"]
            glNormal3f(-1,0,0)
            glTexCoord2f(*map_local_uv_to_atlas_subrect(0,0,uv_r)); glVertex3f(-w2, 0,     -d2_half)
            glTexCoord2f(*map_local_uv_to_atlas_subrect(1,0,uv_r)); glVertex3f(-w2, 0,      d2_half)
            glTexCoord2f(*map_local_uv_to_atlas_subrect(1,1,uv_r)); glVertex3f(-w2, h_val,  d2_half)
            glTexCoord2f(*map_local_uv_to_atlas_subrect(0,1,uv_r)); glVertex3f(-w2, h_val, -d2_half)

        # 右面 (Right Face, X = +w2)
        if uv_layout and "right" in uv_layout:
            uv_r = uv_layout["right"]
            glNormal3f(1,0,0)
            glTexCoord2f(*map_local_uv_to_atlas_subrect(0,0,uv_r)); glVertex3f( w2, 0,      d2_half)
            glTexCoord2f(*map_local_uv_to_atlas_subrect(1,0,uv_r)); glVertex3f( w2, 0,     -d2_half)
            glTexCoord2f(*map_local_uv_to_atlas_subrect(1,1,uv_r)); glVertex3f( w2, h_val, -d2_half)
            glTexCoord2f(*map_local_uv_to_atlas_subrect(0,1,uv_r)); glVertex3f( w2, h_val,  d2_half)

        # 頂面 (Top Face, Y = +h_val)
        if uv_layout and "top" in uv_layout:
            uv_r = uv_layout["top"]
            glNormal3f(0,1,0)
            glTexCoord2f(*map_local_uv_to_atlas_subrect(0,0,uv_r)); glVertex3f(-w2, h_val,  d2_half) # 左後 (從上往下看)
            glTexCoord2f(*map_local_uv_to_atlas_subrect(1,0,uv_r)); glVertex3f( w2, h_val,  d2_half) # 右後
            glTexCoord2f(*map_local_uv_to_atlas_subrect(1,1,uv_r)); glVertex3f( w2, h_val, -d2_half) # 右前
            glTexCoord2f(*map_local_uv_to_atlas_subrect(0,1,uv_r)); glVertex3f(-w2, h_val, -d2_half) # 左前
            
        # 底面 (Bottom Face, Y = 0)
        if uv_layout and "bottom" in uv_layout:
            uv_r = uv_layout["bottom"]
            glNormal3f(0,-1,0)
            glTexCoord2f(*map_local_uv_to_atlas_subrect(0,0,uv_r)); glVertex3f(-w2, 0,     -d2_half) # 左前
            glTexCoord2f(*map_local_uv_to_atlas_subrect(1,0,uv_r)); glVertex3f( w2, 0,     -d2_half) # 右前
            glTexCoord2f(*map_local_uv_to_atlas_subrect(1,1,uv_r)); glVertex3f( w2, 0,      d2_half) # 右後
            glTexCoord2f(*map_local_uv_to_atlas_subrect(0,1,uv_r)); glVertex3f(-w2, 0,      d2_half) # 左後

    else: # --- uv_mode == 0 or uv_mode == 1 (舊的紋理邏輯) ---        
        # Bottom face (Y=0)
        face_w_b, face_h_b = width, depth
        cu_b, cv_b = (0.5, 0.5) if uv_mode == 1 else (face_w_b / 2.0, face_h_b / 2.0)
        bc_b = [(1,0), (0,0), (0,1), (1,1)] if uv_mode == 1 else [(face_w_b,0), (0,0), (0,face_h_b), (face_w_b,face_h_b)]
        glNormal3f(0, -1, 0)
        uv = _calculate_uv(*bc_b[0], cu_b,cv_b, u_offset,v_offset,original_tex_angle_rad,uv_mode,uscale,vscale);glTexCoord2f(*uv);glVertex3f( w2,0,d2_half)
        uv = _calculate_uv(*bc_b[1], cu_b,cv_b, u_offset,v_offset,original_tex_angle_rad,uv_mode,uscale,vscale);glTexCoord2f(*uv);glVertex3f(-w2,0,d2_half)
        uv = _calculate_uv(*bc_b[2], cu_b,cv_b, u_offset,v_offset,original_tex_angle_rad,uv_mode,uscale,vscale);glTexCoord2f(*uv);glVertex3f(-w2,0,-d2_half)
        uv = _calculate_uv(*bc_b[3], cu_b,cv_b, u_offset,v_offset,original_tex_angle_rad,uv_mode,uscale,vscale);glTexCoord2f(*uv);glVertex3f( w2,0,-d2_half)
        
        # Top face (Y=height)
        face_w_t, face_h_t = width, depth
        cu_t, cv_t = (0.5, 0.5) if uv_mode == 1 else (face_w_t / 2.0, face_h_t / 2.0)
        bc_t = [(1,1), (0,1), (0,0), (1,0)] if uv_mode == 1 else [(face_w_t,face_h_t), (0,face_h_t), (0,0), (face_w_t,0)]
        glNormal3f(0, 1, 0)
        uv = _calculate_uv(*bc_t[0], cu_t,cv_t, u_offset,v_offset,original_tex_angle_rad,uv_mode,uscale,vscale);glTexCoord2f(*uv);glVertex3f( w2,height,-d2_half)
        uv = _calculate_uv(*bc_t[1], cu_t,cv_t, u_offset,v_offset,original_tex_angle_rad,uv_mode,uscale,vscale);glTexCoord2f(*uv);glVertex3f(-w2,height,-d2_half)
        uv = _calculate_uv(*bc_t[2], cu_t,cv_t, u_offset,v_offset,original_tex_angle_rad,uv_mode,uscale,vscale);glTexCoord2f(*uv);glVertex3f(-w2,height,d2_half)
        uv = _calculate_uv(*bc_t[3], cu_t,cv_t, u_offset,v_offset,original_tex_angle_rad,uv_mode,uscale,vscale);glTexCoord2f(*uv);glVertex3f( w2,height,d2_half)
        
        # Front face (Z=d2_half)
        face_w_f, face_h_f = width, height
        cu_f, cv_f = (0.5,0.5) if uv_mode == 1 else (face_w_f/2.0, face_h_f/2.0)
        bc_f = [(1,0), (0,0), (0,1), (1,1)] if uv_mode == 1 else [(face_w_f,0), (0,0), (0,face_h_f), (face_w_f,face_h_f)]
        glNormal3f(0,0,1)
        uv = _calculate_uv(*bc_f[0], cu_f,cv_f,u_offset,v_offset,original_tex_angle_rad,uv_mode,uscale,vscale);glTexCoord2f(*uv);glVertex3f( w2,0,d2_half)
        uv = _calculate_uv(*bc_f[1], cu_f,cv_f,u_offset,v_offset,original_tex_angle_rad,uv_mode,uscale,vscale);glTexCoord2f(*uv);glVertex3f(-w2,0,d2_half)
        uv = _calculate_uv(*bc_f[2], cu_f,cv_f,u_offset,v_offset,original_tex_angle_rad,uv_mode,uscale,vscale);glTexCoord2f(*uv);glVertex3f(-w2,height,d2_half)
        uv = _calculate_uv(*bc_f[3], cu_f,cv_f,u_offset,v_offset,original_tex_angle_rad,uv_mode,uscale,vscale);glTexCoord2f(*uv);glVertex3f( w2,height,d2_half)
        
        # Back face (Z=-d2_half)
        face_w_k, face_h_k = width, height
        cu_k, cv_k = (0.5,0.5) if uv_mode == 1 else (face_w_k/2.0, face_h_k/2.0)
        # UV 的 bc_k 順序可能需要調整以匹配紋理方向，原版是 (0,1), (1,1), (1,0), (0,0)
        # 這對應 (width,height), (0,height), (0,0), (width,0) in world units mode
        # 這裡保持你的原始版本
        bc_k = [(0,1), (1,1), (1,0), (0,0)] if uv_mode == 1 else [(face_w_k,face_h_k), (0,face_h_k), (0,0), (face_w_k,0)] 
        glNormal3f(0,0,-1)
        uv = _calculate_uv(*bc_k[0], cu_k,cv_k,u_offset,v_offset,original_tex_angle_rad,uv_mode,uscale,vscale);glTexCoord2f(*uv);glVertex3f( w2,height,-d2_half) # 之前是 (w,h,-d) -> 應該是 (-w2,height,-d2_half) ?
        uv = _calculate_uv(*bc_k[1], cu_k,cv_k,u_offset,v_offset,original_tex_angle_rad,uv_mode,uscale,vscale);glTexCoord2f(*uv);glVertex3f(-w2,height,-d2_half) # (w2,height,-d2_half) ?
        uv = _calculate_uv(*bc_k[2], cu_k,cv_k,u_offset,v_offset,original_tex_angle_rad,uv_mode,uscale,vscale);glTexCoord2f(*uv);glVertex3f(-w2,0,-d2_half)
        uv = _calculate_uv(*bc_k[3], cu_k,cv_k,u_offset,v_offset,original_tex_angle_rad,uv_mode,uscale,vscale);glTexCoord2f(*uv);glVertex3f( w2,0,-d2_half)

        # Left face (X=-w2)
        face_w_l, face_h_l = depth, height
        cu_l, cv_l = (0.5,0.5) if uv_mode == 1 else (face_w_l/2.0, face_h_l/2.0)
        bc_l = [(1,0), (0,0), (0,1), (1,1)] if uv_mode == 1 else [(face_w_l,0), (0,0), (0,face_h_l), (face_w_l,face_h_l)]
        glNormal3f(-1,0,0)
        uv = _calculate_uv(*bc_l[0], cu_l,cv_l,u_offset,v_offset,original_tex_angle_rad,uv_mode,uscale,vscale);glTexCoord2f(*uv);glVertex3f(-w2,0,-d2_half)
        uv = _calculate_uv(*bc_l[1], cu_l,cv_l,u_offset,v_offset,original_tex_angle_rad,uv_mode,uscale,vscale);glTexCoord2f(*uv);glVertex3f(-w2,0, d2_half)
        uv = _calculate_uv(*bc_l[2], cu_l,cv_l,u_offset,v_offset,original_tex_angle_rad,uv_mode,uscale,vscale);glTexCoord2f(*uv);glVertex3f(-w2,height, d2_half)
        uv = _calculate_uv(*bc_l[3], cu_l,cv_l,u_offset,v_offset,original_tex_angle_rad,uv_mode,uscale,vscale);glTexCoord2f(*uv);glVertex3f(-w2,height,-d2_half)
        
        # Right face (X=w2)
        face_w_r, face_h_r = depth, height
        cu_r, cv_r = (0.5,0.5) if uv_mode == 1 else (face_w_r/2.0, face_h_r/2.0)
        bc_r = [(0,0), (1,0), (1,1), (0,1)] if uv_mode == 1 else [(0,0), (face_w_r,0), (face_w_r,face_h_r), (0,face_h_r)]
        glNormal3f(1,0,0)
        uv = _calculate_uv(*bc_r[0], cu_r,cv_r,u_offset,v_offset,original_tex_angle_rad,uv_mode,uscale,vscale);glTexCoord2f(*uv);glVertex3f( w2,0, d2_half)
        uv = _calculate_uv(*bc_r[1], cu_r,cv_r,u_offset,v_offset,original_tex_angle_rad,uv_mode,uscale,vscale);glTexCoord2f(*uv);glVertex3f( w2,0,-d2_half)
        uv = _calculate_uv(*bc_r[2], cu_r,cv_r,u_offset,v_offset,original_tex_angle_rad,uv_mode,uscale,vscale);glTexCoord2f(*uv);glVertex3f( w2,height,-d2_half)
        uv = _calculate_uv(*bc_r[3], cu_r,cv_r,u_offset,v_offset,original_tex_angle_rad,uv_mode,uscale,vscale);glTexCoord2f(*uv);glVertex3f( w2,height, d2_half)
    glEnd()
    # --- END of geometry ---

    if alpha_testing_was_actually_enabled_this_call:
        glDisable(GL_ALPHA_TEST) # 只恢復由此調用明確啟用的狀態
    
    if gl_texture_id_to_use: # 如果之前綁定了紋理
        glBindTexture(GL_TEXTURE_2D, 0) # 完成後解綁
    
    # 不應在這裡盲目地 glEnable(GL_TEXTURE_2D)，除非 draw_cube 的契約要求它這樣做。
    # 通常，OpenGL 狀態由調用者或更高層的渲染循環管理。
    # 如果你的其他代碼依賴於 draw_cube 後 GL_TEXTURE_2D 總是啟用的，
    # 則需要根據情況決定是否在這裡恢復。
    # 但一個好的原則是，繪製函數應盡可能少地改變全局狀態，或者恢復它修改的狀態。


# --- draw_cylinder (unchanged) ---
def draw_cylinder(radius, height, texture_id_from_scene=None,
                  u_offset=0.0, v_offset=0.0, tex_angle_deg=0.0, uv_mode=1,
                  uscale=1.0, vscale=1.0,
              texture_has_alpha=False,
              default_alpha_test_threshold=0.1
                  ):
    # (Logic unchanged)
    gl_texture_id_to_use = None 
    if texture_id_from_scene is not None:
        try:
            if glIsTexture(texture_id_from_scene):
                gl_texture_id_to_use = texture_id_from_scene
                glBindTexture(GL_TEXTURE_2D, gl_texture_id_to_use);
                glEnable(GL_TEXTURE_2D)
#                 glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_REPEAT)
#                 glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_REPEAT)
                # ... (設置 wrap mode, 處理 GLU 的紋理矩陣等，如之前 cylinder 的代碼)
                # 之前的 cylinder 紋理矩陣操作：
                glMatrixMode(GL_TEXTURE); glPushMatrix(); glLoadIdentity()
                glTranslatef(u_offset, v_offset, 0)
                if uv_mode == 0:
                    safe_uscale = uscale if abs(uscale) > 1e-6 else 1e-6
                    safe_vscale = vscale if abs(vscale) > 1e-6 else 1e-6
                    glScalef(1.0 / safe_uscale, 1.0 / safe_vscale, 1.0)
                # 注意： cylinder 的紋理旋轉可能不像 cube 那樣直接用 tex_angle_deg，
                # GLU 的 UV 生成有其固定方式。這裡的 tex_angle_deg 可能需要不同的應用方式，
                # 或者對於 GLU cylinder，紋理旋轉效果有限。暫時不加入 glRotatef(tex_angle_deg, ...)。
                glMatrixMode(GL_MODELVIEW) # 切回
        except Exception as e_tex_check: # glIsTexture 在某些情況下可能出錯
            print(f"DEBUG: draw_cylinder - Error checking texture ID {texture_id_from_scene}: {e_tex_check}")
            glDisable(GL_TEXTURE_2D)
    else:
        glDisable(GL_TEXTURE_2D)

    # 處理alpha
    alpha_testing_was_actually_enabled_this_call = False
    if gl_texture_id_to_use and texture_has_alpha: 
        glEnable(GL_ALPHA_TEST)
        glAlphaFunc(GL_GREATER, default_alpha_test_threshold)
        alpha_testing_was_actually_enabled_this_call = True
        
        # 確保 Alpha Test 時的狀態是我們期望的
        glDepthMask(GL_TRUE)   # 允許寫入深度緩衝區，像不透明物體一樣參與深度比較
        glDisable(GL_BLEND)  # Alpha Test 通常不與 Alpha Blending 同時對同一物件使用
        # print(f"DEBUG: Alpha Test ENABLED for texture ID {gl_texture_id_to_use}")
    # else:
        # print(f"DEBUG: Alpha Test NOT enabled. TexID: {gl_texture_id_to_use}, HasAlpha: {texture_has_alpha}")
        
    quadric = gluNewQuadric()
    if quadric:
        gluQuadricTexture(quadric, GL_TRUE if gl_texture_id_to_use else GL_FALSE);
        gluQuadricNormals(quadric, GLU_SMOOTH)
        
        # --- 1. 處理圓柱側面 (保持不變) ---
        glMatrixMode(GL_TEXTURE)
        glPushMatrix() # 保存側面之前的紋理矩陣 (可能是單位矩陣)
        glLoadIdentity()
        # 應用側面的 UV 變換 (平移、uv_mode=0 的縮放)
        # 為了與 _calculate_uv 的旋轉中心一致，平移和縮放可能需要在旋轉之後或之前特定處理
        # 簡化：先平移，再縮放 (uv_mode=0)，旋轉由 _calculate_uv 內部處理
        # 但 gluCylinder 的旋轉是模型變換，不是紋理變換，所以這裡的 tex_angle_deg 不直接用 glRotatef
        
        # 參考 _calculate_uv 的邏輯：先移到中心，旋轉，再移回來，然後平移
        # 但 gluCylinder 的 UV 是柱面展開，tex_angle_deg 更像是 U 方向的偏移
        # 這裡的 u_offset, v_offset, uscale, vscale (for uv_mode=0) 用於側面
        temp_u_offset_cyl = u_offset
        temp_v_offset_cyl = v_offset
        
        # 如果 tex_angle_deg != 0，對於側面，它更像是 U 方向的滾動
        # 我們可以將其轉換為一個 U 偏移
        # 一個完整的圓周對應 UV 的 U 方向從 0 到 1 (或 uscale，如果 uv_mode=1)
        # angle_rad_cyl_tex = math.radians(tex_angle_deg)
        # u_shift_from_angle = (angle_rad_cyl_tex / (2 * math.pi)) # 假設U方向0-1對應360度
        # temp_u_offset_cyl += u_shift_from_angle

        glTranslatef(temp_u_offset_cyl, temp_v_offset_cyl, 0)
        if uv_mode == 0: # 世界單位縮放 (側面)
            # 這裡的 uscale/vscale 是每個世界單位對應多少紋理單位
            # 所以 glScalef 應該是 1.0 / scale
            safe_uscale_cyl = uscale if abs(uscale) > 1e-6 else 1e-6
            safe_vscale_cyl = vscale if abs(vscale) > 1e-6 else 1e-6
            glScalef(1.0 / safe_uscale_cyl, 1.0 / safe_vscale_cyl, 1.0)
        elif uv_mode == 1: # 相對縮放 (側面，紋理重複次數)
            # 這裡的 uscale/vscale 是紋理在整個U/V長度上的重複次數
            # gluCylinder 的U從0到1對應圓周，V從0到1對應高度
            glScalef(uscale, vscale, 1.0)


        glMatrixMode(GL_MODELVIEW)
        gluCylinder(quadric, radius, radius, height, CYLINDER_SLICES, 1)
        
        # 恢復到繪製側面之前的紋理矩陣狀態 (很可能是單位矩陣)
        glMatrixMode(GL_TEXTURE)
        glPopMatrix() # 彈出為側面設置的紋理矩陣
        glMatrixMode(GL_MODELVIEW)


        # --- 2. 處理上下圓盤 (Caps) ---
        glMatrixMode(GL_TEXTURE)
        glPushMatrix() # 為圓盤保存當前的紋理矩陣 (可能是單位矩陣)
        glLoadIdentity() # 開始為圓盤設置新的紋理矩陣

        # 圓盤的 UV 中心通常被認為是 (0.5, 0.5)
        # 我們希望所有變換都圍繞這個中心點 (或者如果 uv_mode=0，則基於世界單位)

        # 步驟 a: 將 gluDisk 生成的 UV (假設範圍 0-1) 的中心 (0.5, 0.5) 平移到原點 (0,0)
        glTranslatef(0.5, 0.5, 0.0)

        # 步驟 b: 應用紋理自身的二維旋轉
        glRotatef(tex_angle_deg, 0, 0, 1) # 繞 Z 軸旋轉（在 2D UV 空間中）

        # 步驟 c: 應用縮放
#         if uv_mode == 0: # 世界單位/絕對縮放
#             # gluDisk 的 UV 0-1 對應圓盤直徑 2*radius
#             # 我們希望 uscale/vscale 是紋理在世界單位下的尺寸
#             # 所以 UV 需要乘以 (radius / uscale)
#             # 但 gluDisk 的 UV 映射比較複雜，直接用 radius 可能不准確
#             # 一個近似：假設 gluDisk 的 UV (0,0) 到 (1,1) 覆蓋了圓盤的外接正方形
#             # 如果 uscale 是10個世界單位，半徑是2，那麼紋理應該重複 2*radius / uscale 次
#             # (2*radius) / uscale 是紋理在這個直徑上的重複次數
#             # 所以 UV 需要乘以這個值
#             # 這裡需要實驗，先用一個簡化模型：
#             # 假設我們希望 uscale 是紋理鋪滿 N 個圓盤直徑的 N 值
#             # safe_uscale = uscale if abs(uscale) > 1e-6 else 1e-6
#             # safe_vscale = vscale if abs(vscale) > 1e-6 else 1e-6
#             # glScalef(1.0 / safe_uscale, 1.0 / safe_vscale, 1.0)
#             # 另一種理解 uv_mode=0 的方式是：uscale 是紋理本身在U方向的世界寬度
#             # gluDisk 的 U 方向 0-1 對應了 2*radius 的世界寬度。
#             # 所以，生成的 u_glu 需要轉換成世界單位 (u_glu * 2*radius)，然後再除以 uscale (紋理的世界寬度)
#             # 最終的縮放因子是 (2*radius / uscale)
#             actual_uscale_factor = (2 * radius) / (uscale if abs(uscale) > 1e-6 else 1e-6)
#             actual_vscale_factor = (2 * radius) / (vscale if abs(vscale) > 1e-6 else 1e-6)
#             glScalef(actual_uscale_factor, actual_vscale_factor, 1.0)
# 
#         elif uv_mode == 1: # 相對縮放 (紋理重複次數)
#             # uscale, vscale 直接表示紋理在圓盤 UV 0-1 範圍內的重複次數
#             safe_uscale = uscale if abs(uscale) > 1e-6 else 1e-6
#             safe_vscale = vscale if abs(vscale) > 1e-6 else 1e-6
#             glScalef(safe_uscale, safe_vscale, 1.0)
        
        # 步驟 d: 將 UV 中心平移回 (0.5, 0.5)
        glTranslatef(-0.5, -0.5, 0.0)
        
        # 步驟 e: 最後應用 u_offset, v_offset (這些是最終的平移)
        glTranslatef(u_offset, v_offset, 0.0)

        glMatrixMode(GL_MODELVIEW) # 切換回模型視圖準備繪製 gluDisk

        # 繪製底部圓盤
        glPushMatrix()
        glRotatef(180, 1, 0, 0)
        gluDisk(quadric, 0, radius, CYLINDER_SLICES, 1)
        glPopMatrix()

        # 繪製頂部圓盤 (使用相同的紋理矩陣)
        glPushMatrix()
        glTranslatef(0, 0, height)
        gluDisk(quadric, 0, radius, CYLINDER_SLICES, 1)
        glPopMatrix()

        # 恢復紋理矩陣
        glMatrixMode(GL_TEXTURE)
        glPopMatrix() # 彈出為圓盤設置的紋理矩陣
        glMatrixMode(GL_MODELVIEW)

        gluDeleteQuadric(quadric)

        
    else:
        print("Error creating GLU quadric object for cylinder.")
#     glBindTexture(GL_TEXTURE_2D, 0)
#     glEnable(GL_TEXTURE_2D)
    if alpha_testing_was_actually_enabled_this_call:
        glDisable(GL_ALPHA_TEST) # 只恢復由此調用明確啟用的狀態
    
    if gl_texture_id_to_use: # 如果之前綁定了紋理
        # 恢復 GLU 的紋理矩陣 (如果修改了)
        glMatrixMode(GL_TEXTURE)
        glPopMatrix() # 彈出為 cylinder 紋理變換所做的 push
        glMatrixMode(GL_MODELVIEW)
        glBindTexture(GL_TEXTURE_2D, 0)

def draw_sphere(radius, texture_id=None, slices=16, stacks=16,
                u_offset=0.0, v_offset=0.0, tex_angle_deg=0.0, uv_mode=1,
                uscale=1.0, vscale=1.0):
    """繪製一個球體"""
    # 啟用/禁用紋理
    if texture_id is not None and glIsTexture(texture_id):
        glBindTexture(GL_TEXTURE_2D, texture_id)
        glEnable(GL_TEXTURE_2D)
        # 球體貼圖通常需要重複或邊緣鉗制
        # GL_REPEAT 在極點附近可能效果不好，先用 GL_CLAMP_TO_EDGE
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_CLAMP_TO_EDGE)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_CLAMP_TO_EDGE)
    else:
        glDisable(GL_TEXTURE_2D)

    # 創建 GLU quadric 物件
    quadric = gluNewQuadric()
    if quadric:
        gluQuadricTexture(quadric, GL_TRUE) # 啟用紋理座標生成
        gluQuadricNormals(quadric, GLU_SMOOTH) # 生成平滑法線

        # --- 處理紋理變換 (如果需要) ---
        # 注意：gluSphere 的 UV 生成方式固定，簡單的偏移/旋轉/縮放可能效果不如預期
        # 這裡可以嘗試應用紋理矩陣，但效果可能需要實驗調整
        apply_texture_matrix = abs(u_offset) > 1e-6 or abs(v_offset) > 1e-6 or abs(tex_angle_deg) > 1e-6 or uv_mode == 0
        if apply_texture_matrix:
            glMatrixMode(GL_TEXTURE)
            glPushMatrix()
            glLoadIdentity()
            # 將中心移到 (0.5, 0.5) 以便旋轉和縮放
            glTranslatef(0.5, 0.5, 0.0)
            if uv_mode == 0: # 世界單位模式
                # gluSphere 生成的 UV 在 0-1 範圍，直接縮放可能意義不大
                # 或許應該理解為每單位世界半徑對應多少 UV 範圍？這裡先簡單縮放
                safe_uscale = uscale if abs(uscale) > 1e-6 else 1e-6
                safe_vscale = vscale if abs(vscale) > 1e-6 else 1e-6
                glScalef(1.0 / safe_uscale, 1.0 / safe_vscale, 1.0)
            glRotatef(tex_angle_deg, 0, 0, 1) # 紋理 Z 軸旋轉
            glTranslatef(u_offset, v_offset, 0) # 應用偏移
            # 將中心移回原點
            glTranslatef(-0.5, -0.5, 0.0)
            glMatrixMode(GL_MODELVIEW) # 切換回模型視圖矩陣

        # --- 繪製球體 ---
        # 可能需要旋轉 gluSphere 以匹配常見的球形貼圖方向（如等距柱狀投影）
        # 通常是繞 X 軸旋轉 -90 度
        glPushMatrix()
        glRotatef(-90.0, 1.0, 0.0, 0.0)
        gluSphere(quadric, radius, slices, stacks)
        glPopMatrix()

        # --- 恢復紋理矩陣 (如果應用了) ---
        if apply_texture_matrix:
            glMatrixMode(GL_TEXTURE)
            glPopMatrix()
            glMatrixMode(GL_MODELVIEW) # 確保切換回模型視圖

        gluDeleteQuadric(quadric) # 釋放物件
    else:
        print("Error: 無法創建 GLU quadric 物件繪製球體。")

    # 恢復紋理狀態
    glBindTexture(GL_TEXTURE_2D, 0)
    # 確保 TEXTURE_2D 在函數結束時是啟用的 (如果之前是)
    # 或者由調用者負責管理總體狀態
    # glEnable(GL_TEXTURE_2D) # 如果希望保持啟用


def draw_gableroof(
    # 核心幾何參數
    base_width,          # 屋頂基底寬度 (山牆方向)
    base_length,         # 屋頂基底長度 (屋脊方向)
    ridge_height_offset, # 屋脊頂點相對於屋簷的Y偏移
    # eave_y_local,      # 屋簷在局部Y軸的座標 (通常為0，因為父級 transform 已定位)
                         # 如果 rel_y 本身就是屋簷的世界Y，那麼繪製時的局部Y就是0
    # 形狀調整參數
    ridge_x_pos_offset,  # 屋脊線相對於 base_width 中心的X偏移 (0為對稱)
    eave_overhang_x,     # X方向 (寬度方向) 的屋簷懸挑
    eave_overhang_z,     # Z方向 (長度方向) 的屋簷懸挑
    
    # 紋理相關
    texture_id,
    texture_has_alpha,
    original_tex_file, # 可選，用於調試
    alpha_test_threshold=0.1 
):
    # 0. Alpha Testing 設置
    alpha_testing_was_enabled_this_call = False
    if texture_id is not None and glIsTexture(texture_id):
        glBindTexture(GL_TEXTURE_2D, texture_id)
        glEnable(GL_TEXTURE_2D)
        if texture_has_alpha:
            glEnable(GL_ALPHA_TEST)
            glAlphaFunc(GL_GREATER, alpha_test_threshold)
            alpha_testing_was_enabled_this_call = True
            glDepthMask(GL_TRUE)
            glDisable(GL_BLEND)
    else:
        glDisable(GL_TEXTURE_2D)
        glColor3f(0.6, 0.2, 0.2) # 無紋理時的屋頂顏色 (例如棕紅色)

    # 1. 獲取此屋頂的UV佈局
    uv_layout = DEFAULT_UV_LAYOUTS.get("gableroof")
    if not uv_layout:
        print("警告: 未找到 gableroof 的UV佈局！紋理可能無法正確顯示。")
        # 可以設計一個回退的UV方案，或者直接返回

    # 2. 計算頂點 (在屋頂的局部座標系中)
    # 局部座標系原點 (0,0,0) 可以視為屋頂基底矩形的中心，Y=0 在屋簷高度。
    
    # 屋簷Y座標在局部系統中為0
    e_y = 0.0 
    # 屋脊Y座標
    r_y = ridge_height_offset 
    # 屋脊X座標（考慮了非對稱偏移）
    r_x = ridge_x_pos_offset 

    # 基底半寬和半長
    hw = base_width / 2.0
    hl = base_length / 2.0

    # 計算帶有懸挑的屋簷邊界
    e_lx = -hw - eave_overhang_x  # 左懸挑邊緣X
    e_rx =  hw + eave_overhang_x  # 右懸挑邊緣X
    e_fz = -hl - eave_overhang_z  # 前懸挑邊緣Z (屋脊開始處)
    e_bz =  hl + eave_overhang_z  # 後懸挑邊緣Z (屋脊結束處)

    # 屋脊的Z座標範圍也受懸挑影響
    r_fz_actual = e_fz
    r_bz_actual = e_bz


    # 計算懸挑後屋簷點的Y座標
    e_y_base = 0.0 
    e_y_overhang_left = e_y_base # 預設與基底屋簷同高
    e_y_overhang_right = e_y_base # 預設與基底屋簷同高

    # 計算左斜面的X方向坡度 (dy/dx)
    dx_slope_left = r_x - (-hw) # 從牆體左邊緣到屋脊的X距離
    if not math.isclose(dx_slope_left, 0):
        slope_y_per_x_left = (r_y - e_y_base) / dx_slope_left
        e_y_overhang_left = e_y_base - (eave_overhang_x * slope_y_per_x_left)
    # else: 如果 dx_slope_left 為0 (屋脊在牆體左邊緣)，則左斜面是垂直的或不存在，
    #       eave_overhang_x 對其Y座標無影響，或者說這個懸挑沒有幾何意義。
    #       這種情況下，e_y_overhang_left 保持 e_y_base。

    # 計算右斜面的X方向坡度 (dy/dx)
    dx_slope_right = hw - r_x # 從屋脊到牆體右邊緣的X距離
    if not math.isclose(dx_slope_right, 0):
        slope_y_per_x_right = (r_y - e_y_base) / dx_slope_right
        e_y_overhang_right = e_y_base - (eave_overhang_x * slope_y_per_x_right)
    # else: 屋脊在牆體右邊緣，右斜面垂直或不存在。
    
    # 定義8個主要的屋頂角點
    # 屋簷角點 (Eave Corners) - 4個
    ec_fl = [e_lx, e_y_overhang_left, e_fz] # 前左
    ec_fr = [e_rx, e_y_overhang_right, e_fz] # 前右
    ec_bl = [e_lx, e_y_overhang_left, e_bz] # 後左
    ec_br = [e_rx, e_y_overhang_right, e_bz] # 後右
    
    # 屋脊角點 (Ridge Corners) - 2個 (如果屋脊X偏移為0，則X為0)
    rc_f = [r_x, r_y, r_fz_actual] # 前
    rc_b = [r_x, r_y, r_bz_actual] # 後

    # --- 開始繪製各個面 ---
    
    # 左斜屋頂面 (Left Slope)
    # 頂點順序 (例如，從前下角開始，逆時針，確保法線朝外上)
    # LS1: ec_fl (前左屋簷)
    # LS2: ec_bl (後左屋簷)
    # LS3: rc_b  (後屋脊)
    # LS4: rc_f  (前屋脊)
    if not math.isclose(r_x, e_lx): # 只有當屋脊不與左屋簷重合時才繪製
        glBegin(GL_QUADS)
        norm_ls = np.cross(np.subtract(ec_bl,ec_fl), np.subtract(rc_f,ec_fl))
        norm_ls_mag = np.linalg.norm(norm_ls)
        if norm_ls_mag > 1e-6: glNormal3fv(norm_ls / norm_ls_mag)
        else: glNormal3f(0,1,0) # Fallback

        uv_r_ls = uv_layout.get("left_slope", (0,0,1,1)) # 獲取UV子矩形，帶預設
        glTexCoord2f(*map_local_uv_to_atlas_subrect(0,0,uv_r_ls)); glVertex3fv(ec_fl) # 局部UV (0,0)
        glTexCoord2f(*map_local_uv_to_atlas_subrect(0,1,uv_r_ls)); glVertex3fv(ec_bl) # 局部UV (0,1)
        glTexCoord2f(*map_local_uv_to_atlas_subrect(1,1,uv_r_ls)); glVertex3fv(rc_b)  # 局部UV (1,1)
        glTexCoord2f(*map_local_uv_to_atlas_subrect(1,0,uv_r_ls)); glVertex3fv(rc_f)  # 局部UV (1,0)
        glEnd()

    # 右斜屋頂面 (Right Slope)
    # 頂點順序 (例如，從前屋脊開始，逆時針)
    # RS1: rc_f  (前屋脊)
    # RS2: rc_b  (後屋脊)
    # RS3: ec_br (後右屋簷)
    # RS4: ec_fr (前右屋簷)
    if not math.isclose(r_x, e_rx): # 只有當屋脊不與右屋簷重合時才繪製
        glBegin(GL_QUADS)
        norm_rs = np.cross(np.subtract(rc_b,rc_f), np.subtract(ec_fr,rc_f))
        norm_rs_mag = np.linalg.norm(norm_rs)
        if norm_rs_mag > 1e-6: glNormal3fv(norm_rs / norm_rs_mag)
        else: glNormal3f(0,1,0)

        uv_r_rs = uv_layout.get("right_slope", (0,0,1,1))
        glTexCoord2f(*map_local_uv_to_atlas_subrect(0,0,uv_r_rs)); glVertex3fv(rc_f)
        glTexCoord2f(*map_local_uv_to_atlas_subrect(0,1,uv_r_rs)); glVertex3fv(rc_b)
        glTexCoord2f(*map_local_uv_to_atlas_subrect(1,1,uv_r_rs)); glVertex3fv(ec_br)
        glTexCoord2f(*map_local_uv_to_atlas_subrect(1,0,uv_r_rs)); glVertex3fv(ec_fr)
        glEnd()

    # 山牆的繪製 (三角形)
    # 山牆的基底是 base_width，而不是懸挑後的寬度
    # 局部座標系中，山牆在 Z = -hl 和 Z = +hl 的平面上
    
    # 前山牆 (Front Gable, Z = -hl)
    # 頂點 (逆時針，法線朝 -Z)
    fg_v1 = [-hw, e_y, -hl]  # 左下
    fg_v2 = [ hw, e_y, -hl]  # 右下
    fg_v3 = [r_x, r_y, -hl]  # 頂點 (屋脊在前山牆平面上的投影)
    if base_width > 1e-6: # 確保山牆有寬度
        glBegin(GL_TRIANGLES)
        norm_fg = np.array([0,0,-1.0]) # 簡化法線，實際應計算
        # 如果要精確法線：np.cross(np.subtract(fg_v2,fg_v1), np.subtract(fg_v3,fg_v1))
        glNormal3fv(norm_fg)
        uv_r_fg = uv_layout.get("front_gable", (0,0,1,1))
        # 三角形的UV映射到方形區域，這裡用簡單的映射
        glTexCoord2f(*map_local_uv_to_atlas_subrect(0,0,uv_r_fg)); glVertex3fv(fg_v1) # 方形左下
        glTexCoord2f(*map_local_uv_to_atlas_subrect(1,0,uv_r_fg)); glVertex3fv(fg_v2) # 方形右下
        glTexCoord2f(*map_local_uv_to_atlas_subrect(0.5,1,uv_r_fg)); glVertex3fv(fg_v3)# 方形頂中
        glEnd()

    # 後山牆 (Back Gable, Z = +hl)
    # 頂點 (逆時針，法線朝 +Z)
    bg_v1 = [ hw, e_y,  hl]  # 右下 (從+Z方向看是左下)
    bg_v2 = [-hw, e_y,  hl]  # 左下 (從+Z方向看是右下)
    bg_v3 = [r_x, r_y,  hl]  # 頂點
    if base_width > 1e-6:
        glBegin(GL_TRIANGLES)
        norm_bg = np.array([0,0,1.0]) # 簡化法線
        glNormal3fv(norm_bg)
        uv_r_bg = uv_layout.get("back_gable", (0,0,1,1))
        glTexCoord2f(*map_local_uv_to_atlas_subrect(0,0,uv_r_bg)); glVertex3fv(bg_v1)
        glTexCoord2f(*map_local_uv_to_atlas_subrect(1,0,uv_r_bg)); glVertex3fv(bg_v2)
        glTexCoord2f(*map_local_uv_to_atlas_subrect(0.5,1,uv_r_bg)); glVertex3fv(bg_v3)
        glEnd()



    # 3. 恢復OpenGL狀態
    if alpha_testing_was_enabled_this_call:
        glDisable(GL_ALPHA_TEST)
    if texture_id is not None and glIsTexture(texture_id):
        glBindTexture(GL_TEXTURE_2D, 0)
        # glDisable(GL_TEXTURE_2D) # 通常不由繪製函數禁用，除非它明確只為自己啟用
    else: # 如果之前是glColor3f
        glColor3f(1,1,1) # 恢復預設顏色
        
def draw_flexroof(
    base_w, base_l, top_w, top_l, height,
    top_off_x, top_off_z,
    texture_id=None, # OpenGL 紋理 ID
    texture_has_alpha=False,
    # original_tex_file=None, # 可選，用於調試，如果 scene_parser 傳遞了它
    alpha_test_threshold=0.1, # 預設的 alpha 測試閾值
    uv_layout_key_internal="flexroof_layout" # 內部使用的固定鍵名
):
    # 0. 紋理和 Alpha 測試設置
    gl_texture_id_to_use = None
    alpha_testing_was_enabled_this_call = False

    if texture_id is not None:
        try:
            if glIsTexture(texture_id):
                gl_texture_id_to_use = texture_id
                glBindTexture(GL_TEXTURE_2D, gl_texture_id_to_use)
                glEnable(GL_TEXTURE_2D)
                # 假設使用 GL_REPEAT，如果邊緣需要裁剪，可以改為 GL_CLAMP_TO_EDGE
                glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_REPEAT)
                glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_REPEAT)
            else:
                glDisable(GL_TEXTURE_2D)
        except Exception as e_tex_check:
            print(f"DEBUG: draw_flexroof - Error checking texture ID {texture_id}: {e_tex_check}")
            glDisable(GL_TEXTURE_2D)
    else:
        glDisable(GL_TEXTURE_2D)
        glColor3f(1.0, 1.0, 1.0) # 無紋理時的預設顏色

    if gl_texture_id_to_use and texture_has_alpha:
        glEnable(GL_ALPHA_TEST)
        glAlphaFunc(GL_GREATER, alpha_test_threshold)
        alpha_testing_was_enabled_this_call = True
        glDepthMask(GL_TRUE)
        glDisable(GL_BLEND)

    # 1. 獲取此屋頂的UV佈局 (使用內部固定的鍵名)
    uv_layout_map = DEFAULT_UV_LAYOUTS.get(uv_layout_key_internal)
    if not uv_layout_map:
        print(f"警告: 未找到 flexroof 的UV佈局 (鍵: '{uv_layout_key_internal}')！紋理可能無法正確顯示。")
        # Fallback: 創建一個空的 uv_layout_map，這樣 get 不會失敗，但紋理會是 (0,0)
        uv_layout_map = {} 

    # 2. 計算8個頂點的局部座標
    # 下底面中心在 (0,0,0)，Y=0
    # 上底面中心在 (top_off_x, height, top_off_z)，Y=height

    # 下底面頂點 (Y=0)
    b_half_w, b_half_l = base_w / 2.0, base_l / 2.0
    v_bottom_fnw = np.array([-b_half_w, 0.0, -b_half_l]) # 前西北 (Front-North-West)
    v_bottom_fne = np.array([ b_half_w, 0.0, -b_half_l]) # 前東北
    v_bottom_fse = np.array([ b_half_w, 0.0,  b_half_l]) # 前東南
    v_bottom_fsw = np.array([-b_half_w, 0.0,  b_half_l]) # 前西南

    # 上底面頂點 (Y=height)，相對於上底中心 (top_off_x, height, top_off_z)
    t_half_w, t_half_l = top_w / 2.0, top_l / 2.0
    v_top_fnw = np.array([top_off_x - t_half_w, height, top_off_z - t_half_l])
    v_top_fne = np.array([top_off_x + t_half_w, height, top_off_z - t_half_l])
    v_top_fse = np.array([top_off_x + t_half_w, height, top_off_z + t_half_l])
    v_top_fsw = np.array([top_off_x - t_half_w, height, top_off_z + t_half_l])

    # 3. 開始繪製各個面
    

    # 頂面 (Top Face, Y = height) - 只有當 top_w 和 top_l 都大於0時才繪製四邊形
    if top_w > 1e-6 and top_l > 1e-6: # 使用小容差比較浮點數
        uv_r_top = uv_layout_map.get("top_face", (0,0,0,0)) # 提供預設以防鍵缺失
        glNormal3f(0, 1, 0) # 法線朝上
        # 頂點順序：v_top_fsw, v_top_fse, v_top_fne, v_top_fnw (例如，從+Z邊的左點開始逆時針)
        # 對應局部UV： (0,0), (1,0), (1,1), (0,1)
        glBegin(GL_QUADS)
        glTexCoord2f(*map_local_uv_to_atlas_subrect(0,0,uv_r_top)); glVertex3fv(v_top_fsw)
        glTexCoord2f(*map_local_uv_to_atlas_subrect(1,0,uv_r_top)); glVertex3fv(v_top_fse)
        glTexCoord2f(*map_local_uv_to_atlas_subrect(1,1,uv_r_top)); glVertex3fv(v_top_fne)
        glTexCoord2f(*map_local_uv_to_atlas_subrect(0,1,uv_r_top)); glVertex3fv(v_top_fnw)
        glEnd()
        
    # 底面 (Bottom Face, Y = 0) - 通常不需要渲染，但可以保留邏輯
    # uv_r_bottom = uv_layout_map.get("bottom_face", (0,0,0,0))
    # glNormal3f(0, -1, 0)
    # # 順序：v_bottom_fnw, v_bottom_fne, v_bottom_fse, v_bottom_fsw (例如，從-Z邊的左點開始逆時針)
    # glTexCoord2f(*map_local_uv_to_atlas_subrect(0,0,uv_r_bottom)); glVertex3fv(v_bottom_fnw)
    # glTexCoord2f(*map_local_uv_to_atlas_subrect(1,0,uv_r_bottom)); glVertex3fv(v_bottom_fne)
    # glTexCoord2f(*map_local_uv_to_atlas_subrect(1,1,uv_r_bottom)); glVertex3fv(v_bottom_fse)
    # glTexCoord2f(*map_local_uv_to_atlas_subrect(0,1,uv_r_bottom)); glVertex3fv(v_bottom_fsw)


    # 輔助函數，用於繪製一個側面 (可以是四邊形或三角形)
    def draw_side_face(v_bottom_1, v_bottom_2, v_top_1, v_top_2, uv_rect_info, expected_normal_approx):
        # expected_normal_approx 是一個大致的期望法線方向，用於校驗計算出的法線
        
        # 判斷頂部邊是否退化成一個點 (即 v_top_1 和 v_top_2 非常接近)
        # 這裡的 v_top_1 和 v_top_2 是指構成這個特定側面頂邊的兩個上部頂點
        is_top_edge_degenerate = np.linalg.norm(v_top_1 - v_top_2) < 1e-5 

        if is_top_edge_degenerate: # 頂部退化成點 -> 側面是三角形
            # 三角形頂點: v_bottom_1, v_bottom_2, v_top_1 (或 v_top_2，它們是同一個點)
            p_apex_side = v_top_1 
            normal_calc = np.cross(v_bottom_2 - v_bottom_1, p_apex_side - v_bottom_1)
            # 進行法線方向校驗和標準化
            if np.dot(normal_calc, expected_normal_approx) < 0: normal_calc = -normal_calc
            norm_val = np.linalg.norm(normal_calc)
            if norm_val > 1e-6: glNormal3fv(normal_calc / norm_val)
            else: glNormal3fv(expected_normal_approx) # Fallback

            glBegin(GL_TRIANGLES)
            glTexCoord2f(*map_local_uv_to_atlas_subrect(0,0,uv_rect_info)); glVertex3fv(v_bottom_1)
            glTexCoord2f(*map_local_uv_to_atlas_subrect(1,0,uv_rect_info)); glVertex3fv(v_bottom_2)
            glTexCoord2f(*map_local_uv_to_atlas_subrect(0.5,1,uv_rect_info)); glVertex3fv(p_apex_side)
            glEnd()
        else: # 側面是四邊形
            # 四邊形頂點: v_bottom_1, v_bottom_2, v_top_2, v_top_1 (確保順序)
            normal_calc = np.cross(v_bottom_2 - v_bottom_1, v_top_1 - v_bottom_1) # 用 p0,p1,p3
             # 進行法線方向校驗和標準化
            if np.dot(normal_calc, expected_normal_approx) < 0: normal_calc = -normal_calc
            norm_val = np.linalg.norm(normal_calc)
            if norm_val > 1e-6: glNormal3fv(normal_calc / norm_val)
            else: glNormal3fv(expected_normal_approx)

            glBegin(GL_QUADS)
            glTexCoord2f(*map_local_uv_to_atlas_subrect(0,0,uv_rect_info)); glVertex3fv(v_bottom_1)
            glTexCoord2f(*map_local_uv_to_atlas_subrect(1,0,uv_rect_info)); glVertex3fv(v_bottom_2)
            glTexCoord2f(*map_local_uv_to_atlas_subrect(1,1,uv_rect_info)); glVertex3fv(v_top_2)
            glTexCoord2f(*map_local_uv_to_atlas_subrect(0,1,uv_rect_info)); glVertex3fv(v_top_1)
            glEnd()

    # 四個側面
    
    # -Z 面
    draw_side_face(v_bottom_fnw, v_bottom_fne, v_top_fnw, v_top_fne, 
                   uv_layout_map.get("side_z_neg", (0,0,0,0)), np.array([0,0,-1.0]))
    # +X 面
    draw_side_face(v_bottom_fne, v_bottom_fse, v_top_fne, v_top_fse, 
                   uv_layout_map.get("side_x_pos", (0,0,0,0)), np.array([1.0,0,0]))
    # +Z 面
    draw_side_face(v_bottom_fse, v_bottom_fsw, v_top_fse, v_top_fsw, 
                   uv_layout_map.get("side_z_pos", (0,0,0,0)), np.array([0,0,1.0]))
    # -X 面
    draw_side_face(v_bottom_fsw, v_bottom_fnw, v_top_fsw, v_top_fnw, 
                   uv_layout_map.get("side_x_neg", (0,0,0,0)), np.array([-1.0,0,0]))
    


    # 4. 恢復OpenGL狀態
    if alpha_testing_was_enabled_this_call:
        glDisable(GL_ALPHA_TEST)
    
    if gl_texture_id_to_use:
        glBindTexture(GL_TEXTURE_2D, 0)
    else: # 如果之前是 glColor3f
        glColor3f(1,1,1) # 恢復預設顏色

# --- draw_tree (unchanged) ---
def draw_tree(x, y, z, height, texture_id=None): # 函數簽名保持不變
    """
    使用兩個交叉的垂直平面繪製樹木，並應用 Alpha Testing。
    如果提供了有效的 texture_id，則使用其 Alpha 通道進行測試。
    否則，繪製純色。
    不需要排序，但透明邊緣會比較硬。
    """
    # 基本的輸入驗證
    if height <= 0:
        return

    # 計算樹木平面尺寸 (保持與之前一致)
    width = height * 0.6
    half_width = width / 2.0

    # --- 保存相關的 OpenGL 狀態 ---
    # 保存啟用狀態、深度緩衝區狀態、Alpha 測試狀態、光照、當前顏色等
    glPushAttrib(GL_ENABLE_BIT | GL_DEPTH_BUFFER_BIT | GL_COLOR_BUFFER_BIT | GL_LIGHTING_BIT | GL_CURRENT_BIT | GL_TEXTURE_BIT | GL_POLYGON_BIT | GL_ALPHA_TEST) # <-- 添加 GL_ALPHA_TEST

    try: # 使用 try...finally 確保狀態能恢復
        # --- 判斷是否有有效紋理 ---
        has_texture = texture_id is not None and glIsTexture(texture_id)

        if has_texture:
            # --- 設置 Alpha Testing 狀態 ---
            glEnable(GL_ALPHA_TEST)
            # 設置 Alpha 函數：只有當像素的 Alpha 值大於閾值時才通過
            glAlphaFunc(GL_GREATER, ALPHA_TEST_THRESHOLD)

            # --- 設置紋理狀態 ---
            glEnable(GL_TEXTURE_2D)
            glBindTexture(GL_TEXTURE_2D, texture_id)
            glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_CLAMP_TO_EDGE)
            glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_CLAMP_TO_EDGE)
            glColor4f(1.0, 1.0, 1.0, 1.0) # 使用白色確保紋理顏色

            # Alpha Testing 時，通常不需要禁用光照（除非你特意想要無光照效果）
            # glEnable(GL_LIGHTING) # 可以保持光照啟用

            # Alpha Testing 時，必須啟用深度寫入，像不透明物體一樣處理
            glDepthMask(GL_TRUE)
            # 不需要啟用 GL_BLEND
            # glDisable(GL_BLEND)

        else:
            # 沒有紋理，禁用紋理和 Alpha 測試，繪製純色
            glDisable(GL_TEXTURE_2D)
            glDisable(GL_ALPHA_TEST) # 確保禁用
            r, g, b = TREE_FALLBACK_COLOR
            glColor3f(r, g, b)
            # 繪製純色時，保持深度寫入開啟
            glDepthMask(GL_TRUE)
            # 繪製純色時，通常啟用光照
            glEnable(GL_LIGHTING)


        # --- 繪製兩個交叉的面片 (繪製邏輯不變) ---
        glPushMatrix()
        glTranslatef(x, y, z)
        glBegin(GL_QUADS)
        # 面片 1: 沿 X 軸
        if has_texture: glTexCoord2f(0.0, 0.0); glVertex3f(-half_width, 0,      0)
        else: glVertex3f(-half_width, 0,      0)
        if has_texture: glTexCoord2f(1.0, 0.0); glVertex3f( half_width, 0,      0)
        else: glVertex3f( half_width, 0,      0)
        if has_texture: glTexCoord2f(1.0, 1.0); glVertex3f( half_width, height, 0)
        else: glVertex3f( half_width, height, 0)
        if has_texture: glTexCoord2f(0.0, 1.0); glVertex3f(-half_width, height, 0)
        else: glVertex3f(-half_width, height, 0)
        # 面片 2: 沿 Z 軸
        if has_texture: glTexCoord2f(0.0, 0.0); glVertex3f(0,      0,      -half_width)
        else: glVertex3f(0,      0,      -half_width)
        if has_texture: glTexCoord2f(1.0, 0.0); glVertex3f(0,      0,       half_width)
        else: glVertex3f(0,      0,       half_width)
        if has_texture: glTexCoord2f(1.0, 1.0); glVertex3f(0,      height,  half_width)
        else: glVertex3f(0,      height,  half_width)
        if has_texture: glTexCoord2f(0.0, 1.0); glVertex3f(0,      height, -half_width)
        else: glVertex3f(0,      height, -half_width)
        glEnd()
        glPopMatrix()

    finally:
        # --- 恢復之前保存的 OpenGL 狀態 ---
        glPopAttrib()
        # 確保紋理單元狀態乾淨
        glBindTexture(GL_TEXTURE_2D, 0)

# def draw_tree(x, y, z, height):
#     # (Logic unchanged)
#     trunk_height = height * 0.6; leaves_height = height * 0.4
#     glPushMatrix(); glTranslatef(x, y, z)
#     # Trunk
#     if tree_bark_tex and glIsTexture(tree_bark_tex): glBindTexture(GL_TEXTURE_2D, tree_bark_tex); glEnable(GL_TEXTURE_2D); glColor3f(1.0, 1.0, 1.0)
#     else: glDisable(GL_TEXTURE_2D); glColor3f(0.5, 0.35, 0.05)
#     quadric = gluNewQuadric();
#     if quadric: gluQuadricTexture(quadric, GL_TRUE); gluQuadricNormals(quadric, GLU_SMOOTH); glPushMatrix(); glRotatef(-90, 1, 0, 0); gluCylinder(quadric, TREE_TRUNK_RADIUS, TREE_TRUNK_RADIUS * 0.8, trunk_height, CYLINDER_SLICES//2, 1); glPopMatrix(); gluDeleteQuadric(quadric)
#     else: print("Error creating quadric for tree trunk.")
#     # Leaves
#     if tree_leaves_tex and glIsTexture(tree_leaves_tex): glBindTexture(GL_TEXTURE_2D, tree_leaves_tex); glEnable(GL_TEXTURE_2D); glColor3f(1.0, 1.0, 1.0)
#     else: glDisable(GL_TEXTURE_2D); glColor3f(0.1, 0.5, 0.1)
#     glPushMatrix(); glTranslatef(0, trunk_height, 0)
#     quadric = gluNewQuadric();
#     if quadric: gluQuadricTexture(quadric, GL_TRUE); gluQuadricNormals(quadric, GLU_SMOOTH); glPushMatrix(); glRotatef(-90, 1, 0, 0); gluCylinder(quadric, TREE_LEAVES_RADIUS, 0, leaves_height * 1.5, CYLINDER_SLICES, 5); glPopMatrix(); gluDeleteQuadric(quadric)
#     else: print("Error creating quadric for tree leaves.")
#     glPopMatrix(); glPopMatrix()
#     glBindTexture(GL_TEXTURE_2D, 0); glEnable(GL_TEXTURE_2D); glColor3f(1.0, 1.0, 1.0)

def generate_hill_mesh_data(center_x, base_y, center_z,
                            base_radius, peak_height_offset,
                            uscale=10.0, vscale=10.0,
                            u_offset=0.0, v_offset=0.0,
                            resolution=20):
    """
    Generates vertex data (positions, normals, texcoords) for a hill.
    Returns a NumPy array of vertices and the total vertex count.
    Vertices are ordered for GL_TRIANGLE_STRIP.
    Vertex format: [x, y, z, nx, ny, nz, u, v]
    """
    if peak_height_offset <= 1e-6 or base_radius <= 1e-6 or resolution < 2:
        return np.array([], dtype=np.float32), 0

    vertices_list = []

    for i in range(resolution): # 沿著 Z 方向 (或者說半徑方向的一個維度)
        for j in range(resolution + 1): # 沿著 X 方向 (或者說半徑方向的另一個維度)
            for k in range(2): # 每個網格點處理兩次，形成條帶 (i,j) 和 (i+1, j)
                current_i = i + k
                
                nx_norm = (j / resolution) * 2.0 - 1.0 # Normalized x in [-1, 1]
                nz_norm = (current_i / resolution) * 2.0 - 1.0 # Normalized z in [-1, 1]

                world_dx = nx_norm * base_radius
                world_dz = nz_norm * base_radius

                distance_from_center = math.sqrt(world_dx**2 + world_dz**2)
                height_from_base = 0.0
                if distance_from_center <= base_radius:
                    # Cosine interpolation for height
                    height_from_base = peak_height_offset * 0.5 * (math.cos(math.pi * distance_from_center / base_radius) + 1.0)
                
                # Vertex position
                vx = center_x + world_dx
                vy = base_y + height_from_base
                vz = center_z + world_dz

                # Approximate Normal (can be improved with finite differences if needed)
                norm_x, norm_y, norm_z = 0.0, 1.0, 0.0 # Default up
                if 1e-6 < distance_from_center <= base_radius:
                    # Derivative of cosine interpolation (simplified)
                    slope_factor = -peak_height_offset * 0.5 * math.pi / base_radius * math.sin(math.pi * distance_from_center / base_radius)
                    # Distribute slope to x and z components of normal
                    raw_nx = - (world_dx / distance_from_center) * slope_factor
                    raw_nz = - (world_dz / distance_from_center) * slope_factor
                    # y component remains 1 (approx), then normalize
                    normal_magnitude = math.sqrt(raw_nx**2 + 1.0**2 + raw_nz**2)
                    if normal_magnitude > 1e-6:
                        norm_x = raw_nx / normal_magnitude
                        norm_y = 1.0 / normal_magnitude
                        norm_z = raw_nz / normal_magnitude
                
                # Texture Coordinates
                # Map world_dx, world_dz from [-base_radius, +base_radius] to [0,1] then apply scale/offset
                # Raw UVs before scale/offset
                raw_u = (world_dx / (2.0 * base_radius)) + 0.5
                raw_v = (world_dz / (2.0 * base_radius)) + 0.5
                # Apply scale and offset
                tex_u = raw_u * uscale + u_offset
                tex_v = raw_v * vscale + v_offset
                
                vertices_list.extend([vx, vy, vz, norm_x, norm_y, norm_z, tex_u, tex_v])

    vertex_data = np.array(vertices_list, dtype=np.float32)
    vertex_count = len(vertices_list) // 8 # 8 floats per vertex (pos, norm, uv)
    return vertex_data, vertex_count



def create_hill_buffers(hill_entry):
    """
    Creates VBO and VAO for a single hill entry.
    hill_entry is a tuple: (line_identifier, hill_data_tuple)
    hill_data_tuple needs to be mutable or replaced if we store IDs back.
    A better approach might be to pass the hill_data_tuple directly if it's a mutable list/dict,
    or pass the scene.hills list and an index.
    For now, let's assume we can modify/replace the tuple in the scene.hills list.
    """
    line_id, hill_data = hill_entry
    
    # Unpack parameters needed for mesh generation
    # Indices match the new tuple structure in scene_parser.py
    obj_type, cx, base_y, cz, radius, peak_h_off, \
    uscale, vscale, u_off, v_off, \
    _tex_file, _tex_id, _tex_alpha, _parent_ry = hill_data[:14] # Get first 14 elements

    # Generate mesh data
    vertex_data, vertex_count = generate_hill_mesh_data(
        cx, base_y, cz, radius, peak_h_off,
        uscale, vscale, u_off, v_off,
        resolution=20 # Or make resolution a parameter from scene_parser if needed
    )

    if vertex_count == 0:
        print(f"警告: 山丘 (行: {line_id}) 未生成頂點數據，無法創建緩衝區。")
        # Ensure any old buffers are cleared and IDs are None
        new_hill_data = list(hill_data)
        if len(new_hill_data) > 14 and new_hill_data[14] is not None: cleanup_hill_buffers(hill_entry) # VAO ID
        new_hill_data[14] = None # vao_id
        new_hill_data[15] = None # vbo_id
        new_hill_data[16] = 0    # vertex_count
        return tuple(new_hill_data), False # Return modified tuple and status

    # Create VBO
    vbo_id = glGenBuffers(1)
    glBindBuffer(GL_ARRAY_BUFFER, vbo_id)
    glBufferData(GL_ARRAY_BUFFER, vertex_data.nbytes, vertex_data, GL_STATIC_DRAW)

    # Create VAO
    vao_id = glGenVertexArrays(1)
    glBindVertexArray(vao_id)

    glBindBuffer(GL_ARRAY_BUFFER, vbo_id) # Bind VBO to this VAO's context

    # Vertex attribute pointers (must match shader layout)
    # Stride: 8 floats * 4 bytes/float = 32 bytes
    stride = 8 * sizeof(GLfloat)
    # Position attribute (location = 0)
    glVertexAttribPointer(0, 3, GL_FLOAT, GL_FALSE, stride, ctypes.c_void_p(0))
    glEnableVertexAttribArray(0)
    # Normal attribute (location = 1)
    glVertexAttribPointer(1, 3, GL_FLOAT, GL_FALSE, stride, ctypes.c_void_p(3 * sizeof(GLfloat)))
    glEnableVertexAttribArray(1)
    # Texture coordinate attribute (location = 2)
    glVertexAttribPointer(2, 2, GL_FLOAT, GL_FALSE, stride, ctypes.c_void_p(6 * sizeof(GLfloat)))
    glEnableVertexAttribArray(2)

    glBindVertexArray(0) # Unbind VAO
    glBindBuffer(GL_ARRAY_BUFFER, 0) # Unbind VBO (optional, VAO remembers VBO binding for attributes)

    # Store IDs and vertex_count back into a new tuple (since tuples are immutable)
    # This assumes hill_data was the original tuple from scene_parser
    new_hill_data_list = list(hill_data)
    new_hill_data_list[14] = vao_id
    new_hill_data_list[15] = vbo_id
    new_hill_data_list[16] = vertex_count
    
#     print(f"山丘 (行: {line_id}) 緩衝區已創建: VAO={vao_id}, VBO={vbo_id}, 頂點數={vertex_count}")
    return tuple(new_hill_data_list), True # Return modified tuple and status

def cleanup_hill_buffers_for_entry(hill_entry):
    """Cleans up VBO and VAO for a single hill entry."""
    _line_id, hill_data = hill_entry
    # Indices match the new tuple structure
    vao_id = hill_data[14]
    vbo_id = hill_data[15]

    if vao_id is not None:
        try:
            glDeleteVertexArrays(1, [vao_id])
        except Exception as e: print(f"清理山丘 VAO {vao_id} 錯誤: {e}")
    if vbo_id is not None:
        try:
            glDeleteBuffers(1, [vbo_id])
        except Exception as e: print(f"清理山丘 VBO {vbo_id} 錯誤: {e}")
    
    # Return a new tuple with None for IDs, useful for updating the scene list
    new_hill_data_list = list(hill_data)
    new_hill_data_list[14] = None
    new_hill_data_list[15] = None
    new_hill_data_list[16] = 0
    return (_line_id, tuple(new_hill_data_list))

def cleanup_all_hill_buffers(scene_hills_list):
    """Cleans up VBOs and VAOs for all hills in the provided list."""
    print("正在清理所有山丘的緩衝區...")
    for i in range(len(scene_hills_list)):
        # cleanup_hill_buffers_for_entry returns the modified entry
        scene_hills_list[i] = cleanup_hill_buffers_for_entry(scene_hills_list[i])

def draw_hill(center_x, base_y, center_z,
              base_radius, peak_height_offset,
              resolution=20,
#               texture_id=None,
              texture_id_from_scene=None,
              uscale=10.0, vscale=10.0,
              u_offset=0.0, v_offset=0.0,
              texture_has_alpha=False,
              default_alpha_test_threshold=0.1
              ):
    """
    繪製一個基於餘弦插值的山丘。

    Args:
        center_x, center_z: 山峰中心的 XZ 座標。
        base_y: 山丘基底的 Y 座標。
        base_radius: 山丘基底的半徑。
        peak_height_offset: 山峰相對於基底 Y 的高度。
        resolution: 山丘網格的精細度 (例如 20x20 個四邊形)。
        texture_id: 應用於山丘的紋理 ID (如果為 None 則不使用紋理)。
        uscale, vscale: 紋理在 U 和 V 方向上的重複次數。
    """
    # --- 參數驗證 ---
    if peak_height_offset  <= 0 or base_radius <= 0 or resolution < 2:
        return

    # --- 紋理設定 ---
    gl_texture_id_to_use = None 
    if texture_id_from_scene is not None:
        try:
            if glIsTexture(texture_id_from_scene):
                gl_texture_id_to_use = texture_id_from_scene
                glBindTexture(GL_TEXTURE_2D, gl_texture_id_to_use)
                glEnable(GL_TEXTURE_2D)
                # 設置紋理環繞方式，REPEAT 比較常用於地形
                glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_REPEAT)
                glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_REPEAT)
                glColor4f(1.0, 1.0, 1.0, 1.0) # 確保紋理顏色不受glColor影響
        except Exception as e_tex_check: # glIsTexture 在某些情況下可能出錯
            print(f"DEBUG: draw_hill - Error checking texture ID {texture_id_from_scene}: {e_tex_check}")
            glDisable(GL_TEXTURE_2D)
    else:
        glDisable(GL_TEXTURE_2D)
        # 如果沒有紋理，可以設置一個預設顏色，例如棕色或綠色
        glColor3f(0.4, 0.5, 0.3) # 示例：深綠色

    # 處理alpha
    alpha_testing_was_actually_enabled_this_call = False
    if gl_texture_id_to_use and texture_has_alpha: 
        glEnable(GL_ALPHA_TEST)
        glAlphaFunc(GL_GREATER, default_alpha_test_threshold)
        alpha_testing_was_actually_enabled_this_call = True
        
        # 確保 Alpha Test 時的狀態是我們期望的
        glDepthMask(GL_TRUE)   # 允許寫入深度緩衝區，像不透明物體一樣參與深度比較
        glDisable(GL_BLEND)  # Alpha Test 通常不與 Alpha Blending 同時對同一物件使用
        # print(f"DEBUG: Alpha Test ENABLED for texture ID {gl_texture_id_to_use}")
    # else:
        # print(f"DEBUG: Alpha Test NOT enabled. TexID: {gl_texture_id_to_use}, HasAlpha: {texture_has_alpha}")

    # --- 網格生成與繪製 ---
    # 我們使用 GL_TRIANGLE_STRIP 來繪製，效率較高
    for i in range(resolution): # 沿著 Z 方向 (或者說半徑方向的一個維度)
        glBegin(GL_TRIANGLE_STRIP)
        for j in range(resolution + 1): # 沿著 X 方向 (或者說半徑方向的另一個維度)
            for k in range(2): # 每個網格點處理兩次，形成條帶 (i,j) 和 (i+1, j)
                current_i = i + k
                # 計算當前點在 [-1, 1] x [-1, 1] 範圍內的標準化座標
                nx = (j / resolution) * 2.0 - 1.0
                nz = (current_i / resolution) * 2.0 - 1.0

                # 縮放到實際的世界座標 (相對於中心點)
                world_dx = nx * base_radius
                world_dz = nz * base_radius

                # 計算到中心的水平距離
                distance = math.sqrt(world_dx**2 + world_dz**2)

                # 計算高度基於 base_y 和 peak_height_offset (使用餘弦插值)
                height_from_base  = 0.0
                if distance <= base_radius:
                    height_from_base  = peak_height_offset  * 0.5 * (math.cos(math.pi * distance / base_radius) + 1.0)

                # 計算實際世界座標
                world_x = center_x + world_dx
                world_z = center_z + world_dz
                world_y = base_y + height_from_base  # 高度直接是 Y 座標 (使用 base_y)

                # --- 計算近似法向量 ---
                # 為了簡化，我們先給一個朝上的法向量，之後可以改進
                # 更精確的方法是計算數值導數或使用解析導數（如果插值函數可導）
                # 這裡使用一個簡單的近似：根據坡度稍微傾斜法向量
                normal_x = 0.0
                normal_y = 1.0
                normal_z = 0.0
                if distance > 1e-6 and distance <= base_radius:
                     # 導數的近似值 (未歸一化)
                     slope_factor = -peak_height_offset * 0.5 * math.pi / base_radius * math.sin(math.pi * distance / base_radius)
                     # 將斜率分配到 x 和 z 方向
                     normal_x = - (world_dx / distance) * slope_factor
                     normal_z = - (world_dz / distance) * slope_factor
                     # y 分量保持為 1 (近似)，然後歸一化
                     norm = math.sqrt(normal_x**2 + 1.0**2 + normal_z**2)
                     if norm > 1e-6:
                         normal_x /= norm
                         normal_y /= norm
                         normal_z /= norm

                glNormal3f(normal_x, normal_y, normal_z)

                # --- 計算紋理座標 ---
                # 將 [-radius, +radius] 映射到 [0, U] 和 [0, V]
                # --- MODIFICATION START: Apply u_offset and v_offset to texture coordinates ---
                u_raw = (world_dx / (2.0 * base_radius) + 0.5) * uscale
                v_raw = (world_dz / (2.0 * base_radius) + 0.5) * vscale
                glTexCoord2f(u_raw + u_offset, v_raw + v_offset)
                # --- MODIFICATION END ---

                # --- 繪製頂點 ---
                glVertex3f(world_x, world_y, world_z)
        glEnd() # 結束當前的 TRIANGLE_STRIP

    # --- 恢復狀態 ---
    if alpha_testing_was_actually_enabled_this_call:
        glDisable(GL_ALPHA_TEST) # 只恢復由此調用明確啟用的狀態
    
    if gl_texture_id_to_use: # 如果之前綁定了紋理
        glBindTexture(GL_TEXTURE_2D, 0) # 完成後解綁
    # 繪製結束後不需要禁用 GL_TEXTURE_2D，交給調用者管理
    
# --- draw_scene_objects ---
def draw_scene_objects(scene):
    global _hill_shader_program_id
    global _building_shader_program_id
#     glEnable(GL_BLEND)
    # (Logic unchanged)
    glColor3f(1.0, 1.0, 1.0)
    # Buildings
    
    # --- 處理 Buildings (VBO 版本) ---
    if hasattr(scene, 'buildings') and scene.buildings:
        if _building_shader_program_id:
            glUseProgram(_building_shader_program_id)
            # --- 設置一次性的 Uniforms (光照, 視圖, 投影) ---
            # (這些通常在渲染循環開始時為特定著色器設置一次，這裡假設已設置好)
            # light_pos_loc = glGetUniformLocation(_building_shader_program_id, "lightPos_worldspace")
            # glUniform3f(light_pos_loc, 100.0, 150.0, 100.0) ... etc.
            # view_loc = glGetUniformLocation(_building_shader_program_id, "view")
            # glUniformMatrix4fv(view_loc, 1, GL_FALSE, glGetFloatv(GL_MODELVIEW_MATRIX))
            # proj_loc = glGetUniformLocation(_building_shader_program_id, "projection")
            # glUniformMatrix4fv(proj_loc, 1, GL_FALSE, glGetFloatv(GL_PROJECTION_MATRIX))
            # ... (其他光照和觀察者位置 uniforms)
            # --- 新增: 為 Building 著色器設置 View 和 Projection Uniforms ---
            current_view_matrix_for_building = glGetFloatv(GL_MODELVIEW_MATRIX)
            view_loc_bldg = glGetUniformLocation(_building_shader_program_id, "view")
            if view_loc_bldg != -1:
                glUniformMatrix4fv(view_loc_bldg, 1, GL_FALSE, current_view_matrix_for_building)
            else:
                print("警告: Building shader - 'view' uniform location not found.")

            current_proj_matrix_for_building = glGetFloatv(GL_PROJECTION_MATRIX)
            proj_loc_bldg = glGetUniformLocation(_building_shader_program_id, "projection")
            if proj_loc_bldg != -1:
                glUniformMatrix4fv(proj_loc_bldg, 1, GL_FALSE, current_proj_matrix_for_building)
            else:
                print("警告: Building shader - 'projection' uniform location not found.")

            # --- 新增: 為 Building 著色器設置光照相關的 Uniforms (可以參考 hill 的部分) ---
            # 這些 uniforms 通常對於使用相同光照模型的著色器是共享的
            light_pos_loc_bldg = glGetUniformLocation(_building_shader_program_id, "lightPos_worldspace")
            if light_pos_loc_bldg != -1: glUniform3f(light_pos_loc_bldg, 100.0, 150.0, 100.0) # 示例光源位置
            
            light_color_loc_bldg = glGetUniformLocation(_building_shader_program_id, "lightColor")
            if light_color_loc_bldg != -1: glUniform3f(light_color_loc_bldg, 0.8, 0.8, 0.8) # 示例光源顏色

            # 獲取 viewPos_worldspace (通常是相機位置)
            # 這需要相機實例，或者從glGetFloatv(GL_MODELVIEW_MATRIX)的逆矩陣計算
            # 為了簡化，如果你的相機位置在 shader 中不需要動態更新，可以先硬編碼或傳一個近似值
            # 或者，如果 main.py 在每一幀開始時就為所有 shader 設置了 viewPos，這裡可能不需要重複
            view_matrix_inv_bldg = np.linalg.inv(current_view_matrix_for_building)
            cam_pos_from_mv_bldg = view_matrix_inv_bldg[3,:3]
            view_pos_loc_bldg = glGetUniformLocation(_building_shader_program_id, "viewPos_worldspace")
            if view_pos_loc_bldg != -1: glUniform3fv(view_pos_loc_bldg, 1, cam_pos_from_mv_bldg)

            ambient_loc_bldg = glGetUniformLocation(_building_shader_program_id, "u_ambient_strength")
            if ambient_loc_bldg != -1: glUniform1f(ambient_loc_bldg, 0.5) # 示例值
            
            specular_loc_bldg = glGetUniformLocation(_building_shader_program_id, "u_specular_strength")
            if specular_loc_bldg != -1: glUniform1f(specular_loc_bldg, 0.3) # 示例值
            
            shininess_loc_bldg = glGetUniformLocation(_building_shader_program_id, "u_shininess")
            if shininess_loc_bldg != -1: glUniform1f(shininess_loc_bldg, 16.0) # 示例值
            # --- 結束新增光照 Uniforms ---

            # --- 新增: 為 Building 著色器設置光照相關的 Uniforms (可以參考 hill 的部
#                 obj_data_tuple = (
#                     "building", # 0
#                     world_x, world_y, world_z, # 1 2 3
#                     rx_deg, absolute_ry_deg, rz_deg, # 4 5 6
#                     w, d, h, # 7 8 9
# #                     tex_id,
#                     u_offset, v_offset, tex_angle_deg, # 10 11 12
#                     uv_mode, uscale, vscale, # 13 14 15
#                     tex_file, # 原始檔名 16
#                     gl_texture_id_from_loader, # OpenGL 紋理 ID 17
#                     texture_has_alpha_flag, # 新增的 Alpha 標誌 18
#                     math.degrees(origin_angle), # <--- 新增：存儲父原點的Y旋轉角度 (度) 19
#                     None,  # 20: vao_id (placeholder)
#                     None,  # 21: vbo_id (placeholder)
#                     0      # 22: vertex_count (placeholder)                                        
#                     )

            for item in scene.buildings:
                line_num, obj_data_tuple = item
#                 print(f"obj_data_tuple: {obj_data_tuple}")
                EXPECTED_TUPLE_LENGTH = 23
                VAO_ID_INDEX = 20
                VERTEX_COUNT_INDEX = 22
                GL_TEXTURE_ID_INDEX = 17
                TEXTURE_HAS_ALPHA_INDEX = 18
                
                if len(obj_data_tuple) < EXPECTED_TUPLE_LENGTH: 
                    print(f"警告: Building (行: {line_num}) obj_data_tuple 結構不完整，跳過渲染。Got {len(obj_data_tuple)}, expected {EXPECTED_TUPLE_LENGTH}")
                    continue 
                
                try:
                    # 解包用於模型變換和紋理的參數
                    # obj_type = obj_data_tuple[0] # "building"
                    world_x, world_y, world_z = obj_data_tuple[1:4]
                    rx_deg, absolute_ry_deg, rz_deg = obj_data_tuple[4:7]
                    
                    gl_texture_id = obj_data_tuple[GL_TEXTURE_ID_INDEX]
                    texture_has_alpha = obj_data_tuple[TEXTURE_HAS_ALPHA_INDEX]
                    
                    vao_id = obj_data_tuple[VAO_ID_INDEX]
                    vertex_count = obj_data_tuple[VERTEX_COUNT_INDEX]
                
#                 try:
#                     _obj_type, world_x, world_y, world_z, \
#                     rx_deg, absolute_ry_deg, rz_deg, \
#                     _w, _d, _h, \
#                     _tex_file, gl_texture_id, texture_has_alpha, \
#                     _parent_origin_ry_deg, \
#                     vao_id, _vbo_id, vertex_count = obj_data_tuple
                except ValueError:
                    print(f"警告: Building (行: {line_num}) obj_data_tuple 解包失敗，跳過渲染。")
                    continue


                if vao_id is None or vertex_count == 0:
                    # print(f"信息: Building (行: {line_num}) VAO ({vao_id}) 或頂點數 ({vertex_count}) 無效，跳過VBO繪製。")
                    continue

                # --- 計算 Model Matrix ---
                model_matrix = np.identity(4, dtype=np.float32)
                # 1. 平移 (Translate)
                trans_mat = np.array([
                    [1,0,0,world_x],
                    [0,1,0,world_y],
                    [0,0,1,world_z],
                    [0,0,0,1]
                ], dtype=np.float32)
                

                # 2. 獲取純複合旋轉矩陣 R_composite (Row-major)
                #    使用 building 的 rx_deg, absolute_ry_deg, rz_deg
                composite_rotation_mat = get_yxz_intrinsic_composite_rotation_4x4(
                    rx_deg, absolute_ry_deg, rz_deg
                )



                # 3. 組合 Model Matrix: M = T @ R
                #    這對應於 V_world = T * R * V_model
                #    即，先對模型空間頂點 V_model 應用複合旋轉 R，得到旋轉後的局部偏移，
                #    然後再應用平移 T，將其移動到世界位置。
                model_matrix_row_major = trans_mat @ composite_rotation_mat 
                
                
#                 print(f"model_matrix: {model_matrix}")
                model_loc = glGetUniformLocation(_building_shader_program_id, "model")
#                 print(f"model_loc: {model_loc}")
#                 print(f"_building_shader_program_id: {_building_shader_program_id}")
#                 print(f"Building (行: {line_num}) Model Matrix:\n{model_matrix}")
                if model_loc != -1: 
                    # 將行主序的 NumPy 矩陣傳遞給 glUniformMatrix4fv，並設置 transpose = GL_TRUE
                    glUniformMatrix4fv(model_loc, 1, GL_TRUE, model_matrix_row_major) 
                                                    # ^^^^^^^^ 注意這裡改成了 GL_TRUE
                else:
                    print(f"警告: Building (行: {line_num}) 無法找到 'model' uniform location。")
                    # continue
                    
                    
                # --- 設置紋理和 Alpha Uniforms ---
                use_tex_loc = glGetUniformLocation(_building_shader_program_id, "u_use_texture")
                fallback_color_loc = glGetUniformLocation(_building_shader_program_id, "u_fallback_color")
                
                if gl_texture_id is not None and glIsTexture(gl_texture_id):
                    glUniform1i(use_tex_loc, 1) # true
                    glActiveTexture(GL_TEXTURE0)
                    glBindTexture(GL_TEXTURE_2D, gl_texture_id)
                    tex_sampler_loc = glGetUniformLocation(_building_shader_program_id, "texture_diffuse1")
                    glUniform1i(tex_sampler_loc, 0) # Texture unit 0
                else:
                    glUniform1i(use_tex_loc, 0) # false
                    glUniform3f(fallback_color_loc, 0.7, 0.7, 0.7) # Default fallback color

                has_alpha_loc = glGetUniformLocation(_building_shader_program_id, "u_texture_has_alpha")
                glUniform1i(has_alpha_loc, 1 if texture_has_alpha else 0)
                alpha_thresh_loc = glGetUniformLocation(_building_shader_program_id, "u_alpha_test_threshold")
                glUniform1f(alpha_thresh_loc, ALPHA_TEST_THRESHOLD)


                # *** 新增/修改：傳遞紋理變換 Uniforms ***
                # 從 obj_data_tuple 解包 (索引可能需要根據您的元組結構調整)
                # obj_data_tuple[10:16] 包含: u_offset, v_offset, tex_angle_deg, uv_mode, uscale, vscale
                u_offset_val = obj_data_tuple[10]
                v_offset_val = obj_data_tuple[11]
                tex_angle_deg_val = obj_data_tuple[12]
                # uv_mode_val = obj_data_tuple[13] # 這個不再需要傳給著色器
                uscale_val = obj_data_tuple[14]
                vscale_val = obj_data_tuple[15]

                u_tex_offset_loc = glGetUniformLocation(_building_shader_program_id, "u_tex_offset")
                if u_tex_offset_loc != -1: glUniform2f(u_tex_offset_loc, u_offset_val, v_offset_val)
                
                u_tex_angle_rad_loc = glGetUniformLocation(_building_shader_program_id, "u_tex_angle_rad")
                if u_tex_angle_rad_loc != -1: glUniform1f(u_tex_angle_rad_loc, math.radians(tex_angle_deg_val))
                
                u_tex_scale_loc = glGetUniformLocation(_building_shader_program_id, "u_tex_scale")
                if u_tex_scale_loc != -1: glUniform2f(u_tex_scale_loc, uscale_val, vscale_val)
                # --- 結束新增/修改 ---
                
                
                # --- 繪製 ---
                glBindVertexArray(vao_id)
                glDrawArrays(GL_TRIANGLES, 0, vertex_count)
            
            glBindVertexArray(0) # Unbind after loop (or inside if other objects use different VAOs)
            glUseProgram(0) # Unbind shader program
            glActiveTexture(GL_TEXTURE0) # Reset active texture unit
            glBindTexture(GL_TEXTURE_2D, 0) # Unbind texture
        else:
            if not _building_shader_program_id:
                print("警告: Building 著色器未初始化，無法渲染 Buildings。")
            # 可以選擇在這裡調用舊的立即模式繪製作為 fallback (如果還保留了 draw_cube)
            # for item in scene.buildings: ... glTranslate/glRotate/draw_cube ...
    
#     for item in scene.buildings:
#         line_num, obj_data = item # 先解包出 行號 和 原始數據元組
# 
#         # --- 根據新的元組結構解包 ---
#         # 假設 obj_data 結構為:
#         # (obj_type, x, y, z, rx, abs_ry, rz, w, d, h,  <-- 索引 0-9
#         #  u_offset, v_offset, tex_angle_deg, uv_mode, uscale, vscale, <-- 索引 10-15
#         #  tex_filename,                               <-- 索引 16
#         #  gl_texture_id,                              <-- 索引 17
#         #  texture_has_alpha_flag                      <-- 索引 18
#         # )
#         # 再從原始數據元組解包出繪製所需變數
#         (obj_type, x, y, z, rx, abs_ry, rz, w, d, h,
# #          tex_id,
#          u_offset, v_offset, tex_angle_deg, uv_mode, uscale, vscale, tex_file,
#          gl_tex_id_val, tex_has_alpha_val, parent_origin_ry_deg
#          ) = obj_data
#         glPushMatrix();
#         glTranslatef(x, y, z);
#         glRotatef(abs_ry, 0, 1, 0);
#         glRotatef(rx, 1, 0, 0);
#         glRotatef(rz, 0, 0, 1)
# #         print(f'gl_tex_id_val:{gl_tex_id_val}')
#         draw_cube(w, d, h,
# #                   tex_id,
#                   gl_tex_id_val, 
#                   u_offset, v_offset, tex_angle_deg,
#                   uv_mode, uscale, vscale,
#                   tex_has_alpha_val
#                   )
#         glPopMatrix()
        
    # Cylinders
    for item in scene.cylinders:
        line_num, obj_data = item # 先解包出 行號 和 原始數據元組
        # 再從原始數據元組解包出繪製所需變數
        (obj_type, x, y, z, rx, abs_ry, rz, radius, h,
#          tex_id,
         u_offset, v_offset, tex_angle_deg, uv_mode, uscale, vscale, tex_file,
         gl_tex_id_val, tex_has_alpha_val, parent_origin_ry_deg
         ) = obj_data
        glPushMatrix();
        glTranslatef(x, y, z);
        glRotatef(abs_ry, 0, 1, 0);
        glRotatef(rz, 0, 0, 1)
        glRotatef(rx, 1, 0, 0);
        glPushMatrix();
        glRotatef(-90, 1, 0, 0)
        draw_cylinder(radius, h,
#                       tex_id,
                  gl_tex_id_val, 
                      u_offset, v_offset, tex_angle_deg,
                      uv_mode, uscale, vscale,
                  tex_has_alpha_val
                      )
        glPopMatrix();
        glPopMatrix()
    # Trees
# 注意：我們這裡不再設置全局 glColor，因為 draw_tree 內部會處理顏色
#     glColor3f(1.0, 1.0, 1.0)
    for item in scene.trees:
        line_num, tree_data = item # 先解包出 行號 和 原始數據元組
        # 再從原始數據元組解包出繪製所需變數
        # --- 修改：解包新的數據元組結構 ---
        try:
            # 結構: (world_x, world_y, world_z, height, tex_id, tex_file)
            obj_type, x, y, z, height, tex_id, tex_file, parent_origin_ry_deg = tree_data
        except ValueError:
            print(f"警告: 解包 tree 數據時出錯 (來源行: {line_num})")
            continue # 跳過這個損壞的數據
        draw_tree(x, y, z, height, texture_id=tex_id)

    # Spheres
    glColor3f(1.0, 1.0, 1.0) # 設置預設顏色或從物件數據讀取
    for item in scene.spheres:
        line_num, obj_data_tuple = item # 解包行號和數據
        # 從數據元組解包繪製所需變數 (確保順序與 scene_parser 中打包時一致)
        try:
            (obj_type, x, y, z,
             rx, abs_ry, rz, # 使用絕對 Y 旋轉
             radius, tex_id,
             u_offset, v_offset, tex_angle_deg, uv_mode, uscale, vscale,
             tex_file, parent_origin_ry_deg) = obj_data_tuple
        except ValueError:
             print(f"警告: 解包 sphere 數據時出錯 (來源行: {line_num})")
             continue # 跳過這個物件

        glPushMatrix()
        glTranslatef(x, y, z)
        # 應用旋轉 (與 building/cylinder 保持一致的順序)
        glRotatef(abs_ry, 0, 1, 0) # 1. 繞世界 Y 軸旋轉
        glRotatef(rx, 1, 0, 0)     # 2. 繞自身 X 軸旋轉
        glRotatef(rz, 0, 0, 1)     # 3. 繞自身 Z 軸旋轉

        # 調用新的繪製函數
        draw_sphere(radius, tex_id, 16, 16, # 使用預設精度
                    u_offset, v_offset, tex_angle_deg, uv_mode, uscale, vscale)

        glPopMatrix()

    # --- Draw Hills (Using VBO and Shaders) ---
    if hasattr(scene, 'hills') and scene.hills:
        if _hill_shader_program_id is not None: # 確保著色器已成功加載和鏈接
            glUseProgram(_hill_shader_program_id)

            # --- 設置一次性的 Uniforms (對於所有山丘可能相同的) ---
            # 這些也可以在渲染循環開始時為 _hill_shader_program_id 設置一次
            # 光源信息 (示例，您應該從場景或全局設置中獲取)
            light_pos_loc = glGetUniformLocation(_hill_shader_program_id, "lightPos_worldspace")
            glUniform3f(light_pos_loc, 100.0, 150.0, 100.0)
            light_color_loc = glGetUniformLocation(_hill_shader_program_id, "lightColor")
            glUniform3f(light_color_loc, 0.8, 0.8, 0.8)
            
            # 光照強度和材質參數 (示例，可以設為固定值或從材質系統獲取)
            ambient_loc = glGetUniformLocation(_hill_shader_program_id, "u_ambient_strength")
            glUniform1f(ambient_loc, 0.2)
            specular_loc = glGetUniformLocation(_hill_shader_program_id, "u_specular_strength")
            glUniform1f(specular_loc, 0.3)
            shininess_loc = glGetUniformLocation(_hill_shader_program_id, "u_shininess")
            glUniform1f(shininess_loc, 16.0)

            # View 和 Projection 矩陣 (這些通常在主渲染循環中為每個著色器設置)
            current_mv_matrix = glGetFloatv(GL_MODELVIEW_MATRIX) # View matrix
            view_loc = glGetUniformLocation(_hill_shader_program_id, "view")
            glUniformMatrix4fv(view_loc, 1, GL_FALSE, current_mv_matrix)
            
            current_proj_matrix = glGetFloatv(GL_PROJECTION_MATRIX)
            proj_loc = glGetUniformLocation(_hill_shader_program_id, "projection")
            glUniformMatrix4fv(proj_loc, 1, GL_FALSE, current_proj_matrix)

            # View position (攝影機世界座標)
            view_matrix_inv = np.linalg.inv(current_mv_matrix)
            cam_pos_from_mv = view_matrix_inv[3,:3] 
            view_pos_loc = glGetUniformLocation(_hill_shader_program_id, "viewPos_worldspace")
            glUniform3fv(view_pos_loc, 1, cam_pos_from_mv)
            # --- 結束一次性 Uniforms 設置 ---

            for item in scene.hills:
                line_identifier, hill_data_tuple = item
                
                try:
                    if len(hill_data_tuple) < 17: continue
                    obj_type_str = hill_data_tuple[0]
                    if obj_type_str != "hill": continue

                    # 解包繪製時需要的參數
                    gl_texture_id     = hill_data_tuple[11]
                    texture_has_alpha = hill_data_tuple[12]
                    vao_id            = hill_data_tuple[14]
                    vertex_count      = hill_data_tuple[16]

                    if vao_id is None or vertex_count == 0:
                        # print(f"信息: 山丘 (行: {line_identifier}) VAO ({vao_id}) 或頂點數 ({vertex_count}) 無效，跳過VBO繪製。") # 已有此信息
                        continue

                except (ValueError, TypeError, IndexError) as e_unpack_render:
                    print(f"警告: 解包 hill 數據 (renderer) 時出錯 (行: {line_identifier}): {e_unpack_render}")
                    continue 

                # Model 矩陣 (山丘頂點是世界座標，所以是單位矩陣)
                model_matrix = np.identity(4, dtype=np.float32) 
                model_loc = glGetUniformLocation(_hill_shader_program_id, "model")
#                 print(f"_hill_shader_program_id: {_hill_shader_program_id}")
                glUniformMatrix4fv(model_loc, 1, GL_FALSE, model_matrix)

                # --- 設置每個山丘特定的 Uniforms ---
                use_texture_loc = glGetUniformLocation(_hill_shader_program_id, "u_use_diffuse_texture")
                fallback_color_loc = glGetUniformLocation(_hill_shader_program_id, "u_fallback_diffuse_color")
                
                if gl_texture_id is not None and glIsTexture(gl_texture_id):
                    glUniform1i(use_texture_loc, 1) # true: 使用紋理
                    glActiveTexture(GL_TEXTURE0)
                    glBindTexture(GL_TEXTURE_2D, gl_texture_id)
                    tex_sampler_loc = glGetUniformLocation(_hill_shader_program_id, "texture_diffuse1")
                    glUniform1i(tex_sampler_loc, 0) # 紋理單元 0
                else:
                    glUniform1i(use_texture_loc, 0) # false: 不使用紋理
                    # 設置無紋理時的回退顏色
                    # 您可以在這裡定義山丘的預設無紋理顏色
                    glUniform3f(fallback_color_loc, 0.35, 0.85, 0.25) # 例如：一種深綠色/棕色
                    # 如果不綁定紋理，確保紋理單元0上沒有意外的紋理
                    # glActiveTexture(GL_TEXTURE0)
                    # glBindTexture(GL_TEXTURE_2D, 0) # 或者綁定一個1x1的白色紋理

                has_alpha_uniform_loc = glGetUniformLocation(_hill_shader_program_id, "u_texture_has_alpha")
                glUniform1i(has_alpha_uniform_loc, 1 if texture_has_alpha else 0)
                alpha_thresh_uniform_loc = glGetUniformLocation(_hill_shader_program_id, "u_alpha_test_threshold")
                glUniform1f(alpha_thresh_uniform_loc, ALPHA_TEST_THRESHOLD) # 使用全局的閾值

                # 綁定VAO並繪製
                glBindVertexArray(vao_id)
                glDrawArrays(GL_TRIANGLE_STRIP, 0, vertex_count)
                # glBindVertexArray(0) # 可以在循環結束後統一解綁，或者每次都解綁

            # 循環結束後解綁
            glBindVertexArray(0)
            glUseProgram(0)
            glActiveTexture(GL_TEXTURE0) # 重置回默認紋理單元
            glBindTexture(GL_TEXTURE_2D, 0) # 解綁2D紋理

        elif _hill_shader_program_id is None and hasattr(scene, 'hills') and scene.hills:
             print(f"警告: 山丘著色器程序未初始化，無法使用VBO渲染山丘。")
             # 此處可以選擇是否調用舊的立即模式 draw_hill 作為回退
             # for item in scene.hills:
             #    ... (解包舊的 hill_data 參數) ...
             #    old_draw_hill_function(...)
        # --- 結束山丘繪製 ---

#         # 不需要 Push/Pop Matrix，因為 draw_hill 使用絕對座標
#         # 可以直接調用繪製函數
#         draw_hill(cx, base_y, cz, radius, peak_h_offset,
#                   resolution=20, # Or make this configurable from scene.txt if needed
# #                   texture_id=tex_id,
#                   texture_id_from_scene=gl_tex_id_val,
#                   uscale=uscale, vscale=vscale,
#                   u_offset=u_offset, v_offset=v_offset,
#                   texture_has_alpha=tex_has_alpha_val
#                   )

    # --- Draw Gableroofs ---
    if hasattr(scene, 'gableroofs'):
        for item in scene.gableroofs:
            line_identifier, roof_data_tuple = item
            try:
                # 根據 scene_parser 中 gableroof_data_tuple 的結構解包
                # onj_type, 
                # (world_x, world_y, world_z, abs_rx, abs_ry, abs_rz,  <-- 1-7
                #  base_w, base_l, ridge_h_off,                       <-- 7-10
                #  ridge_x_pos, eave_over_x, eave_over_z,             <-- 10-12
                #  gl_tex_id, tex_has_alpha, tex_f_orig                 <-- 13-16
                # )
                world_x, world_y, world_z, abs_rx, abs_ry, abs_rz = roof_data_tuple[1:7]
                base_w, base_l, ridge_h_off = roof_data_tuple[7:10]
                # eave_h_from_parser = roof_data_tuple[8] # 如果你之前有 eave_h
                
                ridge_x_pos_offset_val = roof_data_tuple[10]
                eave_overhang_x_val = roof_data_tuple[11]
                eave_overhang_z_val = roof_data_tuple[12]
                
                gl_texture_id_val = roof_data_tuple[13]
                texture_has_alpha_val = roof_data_tuple[14]
                texture_atlas_file_original = roof_data_tuple[15]

            except (IndexError, ValueError) as e:
                print(f"警告: 解包 gableroof 數據時出錯 (行標識: {line_identifier})。錯誤: {e}")
                print(f"DEBUG: Gableroof data tuple was: {roof_data_tuple}")
                continue

            glPushMatrix()
            glTranslatef(world_x, world_y, world_z) # 平移到屋頂的基準點 (例如牆頂中心)
            
            # 應用旋轉 (順序很重要，例如 Y-X-Z)
            glRotatef(abs_ry, 0, 1, 0)  # Yaw
            glRotatef(abs_rx, 1, 0, 0)  # Pitch
            glRotatef(abs_rz, 0, 0, 1)  # Roll
            
            # draw_gableroof 的 eave_y_coord 參數：
            # 由於我們已經通過 translatef 將原點移動到了 world_y (屋頂的基準Y)，
            # 所以在 draw_gableroof 的局部座標系中，屋簷的高度通常是 0。
            # ridge_height_offset 則是相對於這個局部 Y=0 的高度。
            # 因此，傳給 draw_gableroof 的 eave_y_coord 應該是 0。
            # 這假設 scene_parser 中的 rel_y 參數已經代表了屋簷的絕對Y座標
            # 或者說，world_y 就是屋簷的Y座標。
            
            draw_gableroof(
                base_width=base_w, 
                base_length=base_l, 
                ridge_height_offset=ridge_h_off, 
#                 eave_y_coord=0.0, # <--- 在局部座標系中，屋簷在Y=0
                ridge_x_pos_offset=ridge_x_pos_offset_val,
                eave_overhang_x=eave_overhang_x_val, 
                eave_overhang_z=eave_overhang_z_val,
                texture_id=gl_texture_id_val, 
                texture_has_alpha=texture_has_alpha_val,
                original_tex_file=texture_atlas_file_original 
                # alpha_test_threshold 可以使用 draw_gableroof 中的預設值
            )
            glPopMatrix()


    # --- Draw flexroofs ---
    if hasattr(scene, 'flexroofs'):
        for item in scene.flexroofs:
            line_identifier, flexroof_data = item
            try:
                # 解包 flexroof_data_tuple (與 scene_parser.py 中打包時一致)
                # (obj_type, wx, wy, wz, abs_rx, final_ry, abs_rz,  <-- 0-6
                #  base_w, base_l, top_w, top_l, height,             <-- 7-11
                #  top_off_x, top_off_z,                             <-- 12-13
                #  tex_id, tex_alpha, tex_file,                      <-- 14-16
                #  parent_origin_ry_deg                              <-- 17
                # )
                obj_type_str, \
                world_x, world_y, world_z, \
                abs_rx_deg, final_world_ry_deg, abs_rz_deg, \
                base_w_val, base_l_val, top_w_val, top_l_val, height_val, \
                top_off_x_val, top_off_z_val, \
                gl_texture_id_val, texture_has_alpha_val, texture_atlas_file_val, \
                _parent_origin_ry_deg_val = flexroof_data

                if obj_type_str != "flexroof": # 安全檢查
                    print(f"警告: 在 flexroofs 列表中發現非 flexroof 物件: {obj_type_str}")
                    continue

            except (IndexError, ValueError) as e_unpack:
                print(f"警告: 解包 flexroof 數據時出錯 (行標識: {line_identifier})。錯誤: {e_unpack}")
                print(f"DEBUG: Flexroof data tuple was: {flexroof_data}")
                continue

            glPushMatrix()
            glTranslatef(world_x, world_y, world_z) # 平移到物件的世界基準點
            
            # 應用旋轉 (順序通常是 Y (Yaw), X (Pitch), Z (Roll) 相對於自身)
            glRotatef(final_world_ry_deg, 0, 1, 0)  # 1. Yaw (已經包含了父原點的旋轉)
            glRotatef(abs_rx_deg,       1, 0, 0)  # 2. Pitch
            glRotatef(abs_rz_deg,       0, 0, 1)  # 3. Roll
            
            # 調用新的繪製函數
            draw_flexroof(
                base_w_val, base_l_val, top_w_val, top_l_val, height_val,
                top_off_x_val, top_off_z_val,
                texture_id=gl_texture_id_val,
                texture_has_alpha=texture_has_alpha_val
                # alpha_test_threshold 可以使用 draw_flexroof 中的預設值
                # uv_layout_key_internal 也是使用 draw_flexroof 中的預設值
            )
            glPopMatrix()


#     glDisable(GL_BLEND)



# --- draw_tram_cab (unchanged) ---
def draw_tram_cab(tram, camera):
    # (Logic unchanged)
    cab_width = 3; cab_height = 1; cab_depth = 2; cab_floor_y = 1.5
    dash_height = 0.6; dash_depth = 0.3; dash_pos_y = 1.5; dash_pos_z = -1
    speedo_radius = 0.15; speedo_center_x = -cab_width * 0.25; speedo_center_y = dash_pos_y + dash_height * 0.6; speedo_center_z = dash_pos_z - dash_depth * 0.5 + 0.51
    lever_base_x = cab_width * 0; lever_base_y = dash_pos_y + dash_height * 0.2; lever_base_z = dash_pos_z - dash_depth * 0.4 + 0.5; lever_length = 0.4; lever_max_angle = -40.0
    glPushMatrix()
    glTranslatef(tram.position[0], tram.position[1], tram.position[2])
    render_angle_y = math.degrees(math.arctan2(tram.forward_vector_xz[0], tram.forward_vector_xz[1]))
    glRotatef(180.0, 0, 1, 0); glRotatef(render_angle_y, 0, 1, 0)
    # Optional Platform
    platform_width = cab_width + 0.2; platform_length = cab_depth + 1.0; platform_height = 0.2
    glColor3f(0.5, 0.5, 0.5); glPushMatrix(); glTranslatef(0, -platform_height, -platform_length / 2 + cab_depth/2); draw_cube(platform_width, platform_length, platform_height); glPopMatrix()
    # Cab Shell
    glColor3fv(CAB_COLOR);
    if cab_metal_tex: glBindTexture(GL_TEXTURE_2D, cab_metal_tex); glEnable(GL_TEXTURE_2D) # Typo GL_TEXTURE_D fixed
    else: glDisable(GL_TEXTURE_2D)
    glBegin(GL_QUADS) # Keeping immediate mode for cab for now
    # Floor
    glNormal3f(0, 1, 0); glVertex3f(-cab_width/2, 1, -cab_depth/2); glVertex3f( cab_width/2, 1, -cab_depth/2); glVertex3f( cab_width/2, 1,  cab_depth/2); glVertex3f(-cab_width/2, 1,  cab_depth/2)
    # head wall
    glNormal3f(0, 0, -1); glVertex3f(-cab_width/2, 1 + cab_height, -cab_depth/2); glVertex3f( cab_width/2, 1 + cab_height, -cab_depth/2); glVertex3f( cab_width/2, 1,          -cab_depth/2); glVertex3f(-cab_width/2, 1,          -cab_depth/2)
    # Left wall
    glNormal3f(-1, 0, 0); glVertex3f(-cab_width/2, 1 + cab_height,  cab_depth/2); glVertex3f(-cab_width/2, 1 + cab_height, -cab_depth/2); glVertex3f(-cab_width/2, 1,          -cab_depth/2); glVertex3f(-cab_width/2, 1,           cab_depth/2)
    # Right wall
    glNormal3f(1, 0, 0); glVertex3f( cab_width/2, 1 + cab_height, -cab_depth/2); glVertex3f( cab_width/2, 1 + cab_height,  cab_depth/2); glVertex3f( cab_width/2, 1,           cab_depth/2); glVertex3f( cab_width/2, 1,          -cab_depth/2)
    # back wall
    glNormal3f(0, 0, 1); glVertex3f(-cab_width/2, 1 + cab_height + 1, cab_depth/2); glVertex3f( cab_width/2, 1 + cab_height + 1, cab_depth/2); glVertex3f( cab_width/2, 1,          cab_depth/2); glVertex3f(-cab_width/2, 1,          cab_depth/2)
    # top
    glNormal3f(0, -1, 0); glVertex3f(-cab_width/2, 1 + cab_height + 1, -cab_depth/2); glVertex3f( cab_width/2, 1 + cab_height + 1, -cab_depth/2); glVertex3f( cab_width/2, 1 + cab_height + 1,  cab_depth/2); glVertex3f(-cab_width/2, 1 + cab_height + 1,  cab_depth/2)
    # middle front wall
    glNormal3f(0, 0, -1); glVertex3f(-cab_width/5, 1 + cab_height + 1, -cab_depth/2); glVertex3f( cab_width/5, 1 + cab_height + 1, -cab_depth/2); glVertex3f( cab_width/5, 1 + cab_height,          -cab_depth/2); glVertex3f(-cab_width/5, 1 + cab_height,          -cab_depth/2)
    # left A-pillar
    glNormal3f(0, 0, -1); glVertex3f(-cab_width/2, 1 + cab_height + 1, -cab_depth/2); glVertex3f(-cab_width/2 + 0.1, 1 + cab_height + 1, -cab_depth/2); glVertex3f(-cab_width/2 + 0.1, 1 + cab_height, -cab_depth/2); glVertex3f(-cab_width/2, 1 + cab_height, -cab_depth/2)
    glNormal3f(-1, 0, 0); glVertex3f(-cab_width/2, 1 + cab_height + 1,  -cab_depth/2 + 0.5); glVertex3f(-cab_width/2, 1 + cab_height + 1, -cab_depth/2); glVertex3f(-cab_width/2, 1 + cab_height, -cab_depth/2); glVertex3f(-cab_width/2, 1 + cab_height, -cab_depth/2 + 0.5)
    # right B-pillar
    glNormal3f(0, 0, -1); glVertex3f(cab_width/2, 1 + cab_height + 1, -cab_depth/2); glVertex3f(cab_width/2 - 0.1, 1 + cab_height + 1, -cab_depth/2); glVertex3f(cab_width/2 - 0.1, 1 + cab_height, -cab_depth/2); glVertex3f(cab_width/2, 1 + cab_height, -cab_depth/2)
    glNormal3f(1, 0, 0); glVertex3f( cab_width/2, 1 + cab_height + 1, -cab_depth/2 + 0.5); glVertex3f( cab_width/2, 1 + cab_height + 1,  -cab_depth/2); glVertex3f( cab_width/2, 1 + cab_height,           -cab_depth/2); glVertex3f( cab_width/2, 1 + cab_height,          -cab_depth/2 + 0.5)
    glEnd()
    # Dashboard
    glColor3fv(DASHBOARD_COLOR); glDisable(GL_TEXTURE_2D); glPushMatrix(); glTranslatef(0, dash_pos_y, dash_pos_z); glRotatef(-15, 1, 0, 0); draw_cube(cab_width * 0.95, dash_depth, dash_height); glPopMatrix()
    # Gauges and Lever
    glDisable(GL_LIGHTING); glLineWidth(2.0)
    # Speedo
    glColor3f(0.9, 0.9, 0.9); glPushMatrix(); glTranslatef(0, dash_pos_y, dash_pos_z); glRotatef(-15, 1, 0, 0); glTranslatef(speedo_center_x, speedo_center_y - dash_pos_y , speedo_center_z - dash_pos_z )
    glBegin(GL_TRIANGLE_FAN); glVertex3f(0, 0, 0.01);
    for i in range(33): angle = math.radians(i * 360 / 32); glVertex3f(math.cos(angle) * speedo_radius, math.sin(angle) * speedo_radius, 0.01)
    glEnd()
    glColor3f(0.1, 0.1, 0.1); glBegin(GL_LINES)
    max_spd_kmh = tram.max_speed * 3.6 if tram.max_speed > 0 else 80.0 # Avoid division by zero
    for speed_kmh in range(0, int(max_spd_kmh) + 1, 10):
        angle_rad = math.radians(90 - (speed_kmh / max_spd_kmh) * 180)
        x1 = math.cos(angle_rad) * speedo_radius * 0.8; y1 = math.sin(angle_rad) * speedo_radius * 0.8; x2 = math.cos(angle_rad) * speedo_radius; y2 = math.sin(angle_rad) * speedo_radius
        glVertex3f(x1, y1, 0.02); glVertex3f(x2, y2, 0.02)
    glEnd()
    current_kmh = tram.get_speed_kmh(); speed_ratio = current_kmh / max_spd_kmh if max_spd_kmh > 0 else 0
    needle_angle_rad = math.radians(90 - speed_ratio * 180)
    glColor3fv(NEEDLE_COLOR); glBegin(GL_TRIANGLES)
    glVertex3f(0, 0, 0.03); needle_x = math.cos(needle_angle_rad) * speedo_radius * 0.9; needle_y = math.sin(needle_angle_rad) * speedo_radius * 0.9; side_angle = needle_angle_rad + math.pi / 2
    glVertex3f(needle_x, needle_y, 0.03); glVertex3f(math.cos(side_angle) * 0.01, math.sin(side_angle) * 0.01, 0.03)
    glEnd(); glPopMatrix()
    # Lever
    glColor3fv(LEVER_COLOR); glPushMatrix(); glTranslatef(0, dash_pos_y, dash_pos_z); glRotatef(-15, 1, 0, 0); glTranslatef(lever_base_x, lever_base_y - dash_pos_y, lever_base_z - dash_pos_z)
    control_state = tram.get_control_state(); lever_angle = control_state * lever_max_angle
    glRotatef(lever_angle, 1, 0, 0); lever_width = 0.05
    glBegin(GL_QUADS)
    glNormal3f(0,0,1); glVertex3f(-lever_width/2, lever_length, lever_width/2); glVertex3f(lever_width/2, lever_length, lever_width/2); glVertex3f(lever_width/2, 0, lever_width/2); glVertex3f(-lever_width/2, 0, lever_width/2)
    glNormal3f(0,0,-1); glVertex3f(-lever_width/2, 0, -lever_width/2); glVertex3f(lever_width/2, 0, -lever_width/2); glVertex3f(lever_width/2, lever_length, -lever_width/2); glVertex3f(-lever_width/2, lever_length, -lever_width/2)
    glNormal3f(0,1,0); glVertex3f(-lever_width/2, lever_length, -lever_width/2); glVertex3f(lever_width/2, lever_length, -lever_width/2); glVertex3f(lever_width/2, lever_length, lever_width/2); glVertex3f(-lever_width/2, lever_length, lever_width/2)
    glNormal3f(0,-1,0); glVertex3f(-lever_width/2, 0, lever_width/2); glVertex3f(lever_width/2, 0, lever_width/2); glVertex3f(lever_width/2, 0, -lever_width/2); glVertex3f(-lever_width/2, 0, -lever_width/2)
    glNormal3f(-1,0,0); glVertex3f(-lever_width/2, lever_length, lever_width/2); glVertex3f(-lever_width/2, 0, lever_width/2); glVertex3f(-lever_width/2, 0, -lever_width/2); glVertex3f(-lever_width/2, lever_length, -lever_width/2)
    glNormal3f(1,0,0); glVertex3f(lever_width/2, lever_length, -lever_width/2); glVertex3f(lever_width/2, 0, -lever_width/2); glVertex3f(lever_width/2, 0, lever_width/2); glVertex3f(lever_width/2, lever_length, lever_width/2)
    glEnd(); glPopMatrix()
    glEnable(GL_LIGHTING); glEnable(GL_TEXTURE_2D); glPopMatrix()


# --- _draw_text_texture (unchanged) ---
def _draw_text_texture(text_surface, x, y):
    # (Logic unchanged)
    if not text_surface: return
    text_width, text_height = text_surface.get_size()
    if text_width <= 0 or text_height <= 0: return
    try:
        texture_data = pygame.image.tostring(text_surface, "RGBA", True)
        tex_id = glGenTextures(1)
        glBindTexture(GL_TEXTURE_2D, tex_id)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR); glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_CLAMP_TO_EDGE); glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_CLAMP_TO_EDGE)
        glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA, text_width, text_height, 0, GL_RGBA, GL_UNSIGNED_BYTE, texture_data)
        glEnable(GL_TEXTURE_2D)
        glBegin(GL_QUADS)
        glTexCoord2f(0, 0); glVertex2f(x, y)
        glTexCoord2f(1, 0); glVertex2f(x + text_width, y)
        glTexCoord2f(1, 1); glVertex2f(x + text_width, y + text_height)
        glTexCoord2f(0, 1); glVertex2f(x, y + text_height)
        glEnd()
        glBindTexture(GL_TEXTURE_2D, 0)
        glDeleteTextures(1, [tex_id])
    except Exception as e:
        print(f"Error drawing text texture: {e}")
        if 'tex_id' in locals() and tex_id and glIsTexture(tex_id): glDeleteTextures(1, [tex_id])


# --- draw_info (unchanged) ---
def draw_info(tram, screen_width, screen_height):
    # (Logic unchanged)
    global hud_display_font
    if not hud_display_font: return
    pos = tram.position; dist_m = tram.distance_on_track; speed_kmh = tram.get_speed_kmh()
    coord_text = f"X: {pos[0]:>6.1f} Y: {pos[1]:>6.1f} Z: {pos[2]:>6.1f}"
    dist_km = dist_m / 1000.0; dist_text = f"Kilo: {dist_km:>7.3f} km"
    speed_text = f"Speed: {speed_kmh:>5.1f} km/h"
    info_text = f"{coord_text}\n{dist_text}\n{speed_text}"
    try: text_surface = hud_display_font.render(info_text, True, COORD_TEXT_COLOR); text_width, text_height = text_surface.get_size()
    except Exception as e: print(f"渲染 HUD 文字時出錯: {e}"); return
    glMatrixMode(GL_PROJECTION); glPushMatrix(); glLoadIdentity(); gluOrtho2D(0, screen_width, 0, screen_height)
    glMatrixMode(GL_MODELVIEW); glPushMatrix(); glLoadIdentity()
    glPushAttrib(GL_ENABLE_BIT | GL_TEXTURE_BIT | GL_COLOR_BUFFER_BIT | GL_CURRENT_BIT | GL_DEPTH_BUFFER_BIT)
    glDisable(GL_DEPTH_TEST); glDisable(GL_LIGHTING); glEnable(GL_TEXTURE_2D); glEnable(GL_BLEND); glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
    draw_x = COORD_PADDING_X; draw_y = screen_height - COORD_PADDING_Y - text_height
    _draw_text_texture(text_surface, draw_x, draw_y)
    glPopAttrib()
    glMatrixMode(GL_PROJECTION); glPopMatrix(); glMatrixMode(GL_MODELVIEW); glPopMatrix()


# --- Keep Test Drawing Functions if needed ---
# (Unchanged)
def test_draw_cube_centered(width, depth, height, texture_id=None):
    return
#     if texture_id is not None and glIsTexture(texture_id): glBindTexture(GL_TEXTURE_2D, texture_id); glEnable(GL_TEXTURE_2D)
#     else: glDisable(GL_TEXTURE_2D)
#     w2, d2, h2 = width / 2.0, depth / 2.0, height / 2.0
#     glBegin(GL_QUADS)
#     glNormal3f(0, -1, 0); glTexCoord2f(1, 1); glVertex3f( w2, -h2, -d2); glTexCoord2f(0, 1); glVertex3f(-w2, -h2, -d2); glTexCoord2f(0, 0); glVertex3f(-w2, -h2,  d2); glTexCoord2f(1, 0); glVertex3f( w2, -h2,  d2)
#     glNormal3f(0, 1, 0); glTexCoord2f(1, 1); glVertex3f( w2, h2,  d2); glTexCoord2f(0, 1); glVertex3f(-w2, h2,  d2); glTexCoord2f(0, 0); glVertex3f(-w2, h2, -d2); glTexCoord2f(1, 0); glVertex3f( w2, h2, -d2)
#     glNormal3f(0, 0, 1); glTexCoord2f(1, 1); glVertex3f( w2,  h2, d2); glTexCoord2f(0, 1); glVertex3f(-w2,  h2, d2); glTexCoord2f(0, 0); glVertex3f(-w2, -h2, d2); glTexCoord2f(1, 0); glVertex3f( w2, -h2, d2)
#     glNormal3f(0, 0, -1); glTexCoord2f(1, 1); glVertex3f( w2, -h2, -d2); glTexCoord2f(0, 1); glVertex3f(-w2, -h2, -d2); glTexCoord2f(0, 0); glVertex3f(-w2,  h2, -d2); glTexCoord2f(1, 0); glVertex3f( w2,  h2, -d2)
#     glNormal3f(-1, 0, 0); glTexCoord2f(1, 1); glVertex3f(-w2,  h2,  d2); glTexCoord2f(0, 1); glVertex3f(-w2,  h2, -d2); glTexCoord2f(0, 0); glVertex3f(-w2, -h2, -d2); glTexCoord2f(1, 0); glVertex3f(-w2, -h2,  d2)
#     glNormal3f(1, 0, 0); glTexCoord2f(1, 1); glVertex3f( w2,  h2, -d2); glTexCoord2f(0, 1); glVertex3f( w2,  h2,  d2); glTexCoord2f(0, 0); glVertex3f( w2, -h2,  d2); glTexCoord2f(1, 0); glVertex3f( w2, -h2, -d2)
#     glEnd(); glBindTexture(GL_TEXTURE_2D, 0); glEnable(GL_TEXTURE_2D)

def test_draw_cylinder_y_up_centered(radius, height, texture_id=None, slices=CYLINDER_SLICES):
    return
#     if texture_id is not None and glIsTexture(texture_id): glBindTexture(GL_TEXTURE_2D, texture_id); glEnable(GL_TEXTURE_2D)
#     else: glDisable(GL_TEXTURE_2D)
#     quadric = gluNewQuadric();
#     if not quadric: print("Error creating quadric"); return
#     gluQuadricTexture(quadric, GL_TRUE); gluQuadricNormals(quadric, GLU_SMOOTH)
#     half_height = height / 2.0
#     glPushMatrix(); glRotatef(-90, 1, 0, 0); glTranslatef(0, 0, -half_height)
#     gluCylinder(quadric, radius, radius, height, slices, 1)
#     gluDisk(quadric, 0, radius, slices, 1)
#     glPushMatrix(); glTranslatef(0, 0, height); gluDisk(quadric, 0, radius, slices, 1); glPopMatrix()
#     glPopMatrix(); gluDeleteQuadric(quadric); glBindTexture(GL_TEXTURE_2D, 0); glEnable(GL_TEXTURE_2D)

# --- REMOVED: _render_map_view function ---
# --- REMOVED: draw_minimap function ---

# --- NEW: Skybox/Skydome loading and drawing ---
TEXTURE_LOAD_FAILED_MARKER = "LOAD_FAILED"

def load_skybox(base_name):
    """
    Loads a skybox (cubemap) texture from 6 individual files.
    Files must be named <base_name>_px.png, <base_name>_nx.png, etc.
    Uses texture caching and marks failed loads to prevent repeated attempts.
    """
    global skybox_texture_cache, texture_loader, TEXTURE_LOAD_FAILED_MARKER # 確保能訪問全域變數

    if not texture_loader:
        print("警告: 無法載入 Skybox，texture_loader 未設定。")
        skybox_texture_cache[base_name] = TEXTURE_LOAD_FAILED_MARKER
        return None

    # 如果快取中已經有明確的成功或失敗記錄，直接處理
    if base_name in skybox_texture_cache:
        cached_value = skybox_texture_cache[base_name]
        if cached_value == TEXTURE_LOAD_FAILED_MARKER:
            # print(f"Skybox '{base_name}' previously failed to load, skipping.") # 可選的靜默提示
            return None
        # 假設成功時存的是 texture_id (一個整數)
        # 需要檢查它是否仍然是一個有效的 OpenGL 紋理名稱
        # 這裡 glIsTexture 可能需要在正確的上下文中調用，如果 load_skybox 可能在無上下文時被間接查詢快取則需要注意
        # 但通常 load_skybox 的主要呼叫路徑 (draw_skybox) 是有上下文的
        try:
            if isinstance(cached_value, int) and glIsTexture(cached_value):
                 # print(f"Skybox '{base_name}' found in cache with ID: {cached_value}")
                 return cached_value
        except Exception as e:
            # 如果 glIsTexture 出錯 (例如上下文問題)，則當作快取無效，繼續嘗試載入
            print(f"檢查 Skybox 快取中 ID {cached_value} 時出錯: {e}，將嘗試重新載入 '{base_name}'。")
            pass # 繼續執行下面的載入邏輯

    # 首次嘗試載入此 base_name，或者之前的快取條目無效
    print(f"Skybox '{base_name}': 首次嘗試或重新嘗試載入...")

    texture_id = glGenTextures(1)
    glBindTexture(GL_TEXTURE_CUBE_MAP, texture_id)

    suffixes = ["px", "nx", "py", "ny", "pz", "nz"]
    targets = [
        GL_TEXTURE_CUBE_MAP_POSITIVE_X, GL_TEXTURE_CUBE_MAP_NEGATIVE_X,
        GL_TEXTURE_CUBE_MAP_POSITIVE_Y, GL_TEXTURE_CUBE_MAP_NEGATIVE_Y,
        GL_TEXTURE_CUBE_MAP_POSITIVE_Z, GL_TEXTURE_CUBE_MAP_NEGATIVE_Z
    ]

    all_loaded_successfully = True
    for i in range(6):
        filename = f"{base_name}_{suffixes[i]}.png"
        filepath = os.path.join("textures", filename)
        
        # 減少重複的 "載入 Skybox 面" 打印，只在首次嘗試載入這個 base_name 時打印一次每個面
        # (這個首次嘗試是在這個函數被完整執行一次的意義上)
        print(f"  嘗試載入 Skybox 面: {filepath}")

        if not os.path.exists(filepath):
            print(f"  警告: Skybox 紋理檔案 '{filepath}' (屬於 '{base_name}') 不存在。")
            all_loaded_successfully = False
            break

        try:
            surface = pygame.image.load(filepath)
            texture_data = pygame.image.tostring(surface, "RGBA", False) # RGBA 和 Y軸不翻轉
            glTexImage2D(targets[i], 0, GL_RGBA, surface.get_width(), surface.get_height(),
                         0, GL_RGBA, GL_UNSIGNED_BYTE, texture_data)
        except Exception as e:
            print(f"  載入 Skybox 紋理 '{filepath}' (屬於 '{base_name}') 時發生錯誤: {e}")
            all_loaded_successfully = False
            break

    if all_loaded_successfully:
        glTexParameteri(GL_TEXTURE_CUBE_MAP, GL_TEXTURE_MAG_FILTER, GL_LINEAR)
        glTexParameteri(GL_TEXTURE_CUBE_MAP, GL_TEXTURE_MIN_FILTER, GL_LINEAR)
        glTexParameteri(GL_TEXTURE_CUBE_MAP, GL_TEXTURE_WRAP_S, GL_CLAMP_TO_EDGE)
        glTexParameteri(GL_TEXTURE_CUBE_MAP, GL_TEXTURE_WRAP_T, GL_CLAMP_TO_EDGE)
        glTexParameteri(GL_TEXTURE_CUBE_MAP, GL_TEXTURE_WRAP_R, GL_CLAMP_TO_EDGE)
        glBindTexture(GL_TEXTURE_CUBE_MAP, 0)
        skybox_texture_cache[base_name] = texture_id
        print(f"Skybox '{base_name}' 已成功載入並快取 (ID: {texture_id}).")
        return texture_id
    else:
        glBindTexture(GL_TEXTURE_CUBE_MAP, 0)
        # 只有當 texture_id 是一個有效的紋理名時才刪除
        # glIsTexture 必須在有效的OpenGL上下文中調用
        try:
            if glIsTexture(texture_id):
                 glDeleteTextures(1, [texture_id])
        except Exception as e_del: # 捕獲 glIsTexture 或 glDeleteTextures 可能的錯誤
            print(f"  警告: 嘗試清理部分載入的 Skybox 紋理 (ID: {texture_id}) 時出錯: {e_del}")
            pass # 即使清理失敗，也要繼續標記為失敗

        print(f"Skybox '{base_name}' 載入失敗。在快取中標記為失敗。")
        skybox_texture_cache[base_name] = TEXTURE_LOAD_FAILED_MARKER
        return None


def draw_skybox(base_name, size=1.0):
    """
    Draws a skybox cube centered around the origin.
    Uses texture caching and handles failed loads.
    """
    global skybox_texture_cache, TEXTURE_LOAD_FAILED_MARKER

    skybox_id_or_marker = skybox_texture_cache.get(base_name)
    skybox_id_to_use = None

    if skybox_id_or_marker is None:
        # 快取中沒有記錄，是第一次嘗試處理這個 base_name
        # print(f"Skybox '{base_name}': 快取未命中，執行首次嘗試載入...") # 日誌已移到 load_skybox 內部
        loaded_id = load_skybox(base_name) # load_skybox 會處理打印、快取成功或失敗標記
        if loaded_id is None: # load_skybox 返回 None 表示載入失敗
            # print(f"警告: Skybox '{base_name}' 首次載入失敗，無法繪製。") # load_skybox 內部會打印失敗
            return # 不繪製
        skybox_id_to_use = loaded_id
    elif skybox_id_or_marker == TEXTURE_LOAD_FAILED_MARKER:
        # 之前已嘗試載入且失敗，直接返回，不重複打印錯誤
        # print(f"Skybox '{base_name}': 檢測到之前載入失敗，跳過繪製。") # 可選的靜默日誌
        return
    else:
        # 快取中是有效的 texture_id (整數)
        # 需要再次驗證它是否仍然是一個有效的 OpenGL 紋理（以防上下文丟失後重建等極端情況）
        try:
            if isinstance(skybox_id_or_marker, int) and glIsTexture(skybox_id_or_marker):
                skybox_id_to_use = skybox_id_or_marker
            else: # 快取中的 ID 無效了
                print(f"Skybox '{base_name}': 快取中的 ID {skybox_id_or_marker} 無效，嘗試重新載入...")
                loaded_id = load_skybox(base_name) # 重新載入 (load_skybox 會更新快取)
                if loaded_id is None:
                    return
                skybox_id_to_use = loaded_id
        except Exception as e_check:
            print(f"Skybox '{base_name}': 檢查快取 ID {skybox_id_or_marker} 時出錯 ({e_check})，嘗試重新載入...")
            loaded_id = load_skybox(base_name)
            if loaded_id is None:
                return
            skybox_id_to_use = loaded_id
            
    if skybox_id_to_use is None: # 雙重保險，如果經歷上述邏輯後仍然沒有有效ID
        print(f"嚴重警告: Skybox '{base_name}' 在所有檢查後仍無有效 ID 可用，無法繪製。")
        return

    # --- 實際的繪製邏輯 ---
    glPushAttrib(GL_ENABLE_BIT | GL_DEPTH_BUFFER_BIT | GL_POLYGON_BIT | GL_TEXTURE_BIT | GL_LIGHTING_BIT | GL_CURRENT_BIT)
    try:
        glEnable(GL_TEXTURE_CUBE_MAP)
        glBindTexture(GL_TEXTURE_CUBE_MAP, skybox_id_to_use)

        glDisable(GL_LIGHTING)
        glDisable(GL_DEPTH_TEST)
        glDisable(GL_CULL_FACE)
        glColor3f(1.0, 1.0, 1.0)

        s = size / 2.0
        glBegin(GL_QUADS)
        # Positive X face (+X)
        glTexCoord3f( 1, -1, -1); glVertex3f( s, -s, -s)
        glTexCoord3f( 1, -1,  1); glVertex3f( s, -s,  s)
        glTexCoord3f( 1,  1,  1); glVertex3f( s,  s,  s)
        glTexCoord3f( 1,  1, -1); glVertex3f( s,  s, -s)
        # Negative X face (-X)
        glTexCoord3f(-1, -1,  1); glVertex3f(-s, -s,  s)
        glTexCoord3f(-1, -1, -1); glVertex3f(-s, -s, -s)
        glTexCoord3f(-1,  1, -1); glVertex3f(-s,  s, -s)
        glTexCoord3f(-1,  1,  1); glVertex3f(-s,  s,  s)
        # Positive Y face (+Y) - Top
        glTexCoord3f(-1,  1, -1); glVertex3f(-s,  s, -s)
        glTexCoord3f( 1,  1, -1); glVertex3f( s,  s, -s)
        glTexCoord3f( 1,  1,  1); glVertex3f( s,  s,  s)
        glTexCoord3f(-1,  1,  1); glVertex3f(-s,  s,  s)
        # Negative Y face (-Y) - Bottom
        glTexCoord3f(-1, -1,  1); glVertex3f(-s, -s,  s)
        glTexCoord3f( 1, -1,  1); glVertex3f( s, -s,  s)
        glTexCoord3f( 1, -1, -1); glVertex3f( s, -s, -s)
        glTexCoord3f(-1, -1, -1); glVertex3f(-s, -s, -s)
        # Positive Z face (+Z)
        glTexCoord3f( 1, -1,  1); glVertex3f( s, -s,  s)
        glTexCoord3f(-1, -1,  1); glVertex3f(-s, -s,  s)
        glTexCoord3f(-1,  1,  1); glVertex3f(-s,  s,  s)
        glTexCoord3f( 1,  1,  1); glVertex3f( s,  s,  s)
        # Negative Z face (-Z)
        glTexCoord3f(-1, -1, -1); glVertex3f(-s, -s, -s)
        glTexCoord3f( 1, -1, -1); glVertex3f( s, -s, -s)
        glTexCoord3f( 1,  1, -1); glVertex3f( s,  s, -s)
        glTexCoord3f(-1,  1, -1); glVertex3f(-s,  s, -s)
        glEnd()

        glBindTexture(GL_TEXTURE_CUBE_MAP, 0)
        glDisable(GL_TEXTURE_CUBE_MAP)
    finally:
        glPopAttrib()
        
def draw_skydome(texture_id, radius=1.0, slices=32, stacks=16):
    """
    Draws a skydome (sphere) centered around the origin.
    Requires a 2D texture (presumably equirectangular) to be loaded.
    Assumes camera is at the origin.
    Radius is mostly cosmetic, real 'distance' handled by depth settings.
    """
    if texture_id is None or not glIsTexture(texture_id):
        print("警告: Skydome 紋理無效，無法繪製。")
        return

    glPushAttrib(GL_ENABLE_BIT | GL_DEPTH_BUFFER_BIT | GL_POLYGON_BIT | GL_TEXTURE_BIT | GL_LIGHTING_BIT | GL_CURRENT_BIT)
    glEnable(GL_TEXTURE_2D)
    glBindTexture(GL_TEXTURE_2D, texture_id)
    # Set wrap mode - REPEAT might be ok, CLAMP_TO_EDGE prevents edge artifacts
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_CLAMP_TO_EDGE)
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_CLAMP_TO_EDGE)

    glDisable(GL_LIGHTING)
    glDisable(GL_DEPTH_TEST)
    # glDepthMask(GL_FALSE)
    glDisable(GL_CULL_FACE) # Draw the inside of the sphere

    glColor3f(1.0, 1.0, 1.0)

    quadric = gluNewQuadric()
    if quadric:
        gluQuadricTexture(quadric, GL_TRUE)
        gluQuadricNormals(quadric, GLU_SMOOTH) # Normals might not be strictly needed if lighting is off
        gluQuadricOrientation(quadric, GLU_INSIDE) # Tell GLU we are viewing from inside

        # Draw the sphere
        # Need to rotate it so the texture map is aligned correctly (Y-up)
        glPushMatrix()
        glRotatef(-90.0, 1.0, 0.0, 0.0) # Rotate sphere so Z becomes Y
        gluSphere(quadric, radius, slices, stacks)
        glPopMatrix()

        gluDeleteQuadric(quadric)
    else:
        print("Error creating GLU quadric for skydome.")

    glBindTexture(GL_TEXTURE_2D, 0)
    # Restore states
    # glEnable(GL_DEPTH_TEST)
    # glDepthMask(GL_TRUE)
    # glEnable(GL_CULL_FACE)
    glPopAttrib()


# --- NEW: Wrapper function to draw the background ---
def draw_background(background_info, camera, tram=None): # <--- tram 設為可選參數
    """
    Draws the appropriate background (Skybox or Skydome).
    If tram is provided, rotation considers both tram and camera.
    If tram is None (e.g., in editor preview), rotation only considers camera.
    """
    if background_info is None: return
    bg_type = background_info.get('type')
    if not bg_type: print("警告: 背景資訊缺少 'type'。"); return

    glMatrixMode(GL_PROJECTION); glPushMatrix()
    glMatrixMode(GL_MODELVIEW); glPushMatrix()
    glLoadIdentity()

    # --- 計算觀察方向 ---
    camera_yaw_rad = np.radians(camera.yaw)
    camera_pitch_rad = np.radians(camera.pitch)

    final_world_yaw_rad = camera_yaw_rad # 預設只考慮攝影機

    if tram is not None:
        # 如果有電車物件，疊加電車朝向
        # 確認 atan2 參數順序！假設 forward_vector_xz 是 (cos(angle), sin(angle)) 相對 Z+
        tram_forward_rad = np.arctan2(tram.forward_vector_xz[0], tram.forward_vector_xz[1])
        final_world_yaw_rad += tram_forward_rad

    # 計算最終觀察向量
    final_look_dir_x = np.cos(camera_pitch_rad) * np.sin(final_world_yaw_rad)
    final_look_dir_y = np.sin(camera_pitch_rad)
    final_look_dir_z = np.cos(camera_pitch_rad) * np.cos(final_world_yaw_rad)

    up_x, up_y, up_z = 0.0, 1.0, 0.0 # 簡化 Up 向量

    # 應用只含旋轉的視圖
    gluLookAt(0.0, 0.0, 0.0,
              final_look_dir_x, final_look_dir_y, final_look_dir_z,
              up_x, up_y, up_z)

    # --- 繪製 ---
    original_depth_mask = glGetBooleanv(GL_DEPTH_WRITEMASK)
    try:
        # --- (繪製 skybox/skydome 的邏輯不變) ---
        if bg_type == 'skybox':
            base_name = background_info.get('base_name')
            if base_name: draw_skybox(base_name, size=100)
            else: print("警告: Skybox 背景資訊缺少 'base_name'。")
        elif bg_type == 'skydome':
            texture_id = background_info.get('id')
            # ... (繪製和動態載入邏輯) ...
            if texture_id: draw_skydome(texture_id, radius=100)
            else:
                file_name = background_info.get('file')
                if file_name and texture_loader:
                    loaded_id = texture_loader.load_texture(file_name).get("id")
                    if loaded_id:
                        background_info['id'] = loaded_id
                        draw_skydome(loaded_id, radius=100)
        else:
             print(f"警告: 無法識別的背景類型 '{bg_type}'。")

    finally:
        glDepthMask(original_depth_mask) # 恢復

    # --- 恢復矩陣 ---
    glMatrixMode(GL_PROJECTION); glPopMatrix()
    glMatrixMode(GL_MODELVIEW); glPopMatrix()
