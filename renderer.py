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
#             U=-1.0    U=-0.75    U=-0.5     U=-0.25  U=0.0 為了紋理水平鏡像因此width是負值也因此倒過來
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
    }
}

def map_local_uv_to_atlas_subrect(local_u, local_v, atlas_sub_rect_uvwh):
    rect_u, rect_v, rect_w, rect_h = atlas_sub_rect_uvwh
    return rect_u + local_u * rect_w, rect_v + local_v * rect_h

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

#     # --- 重新計算山牆的頂點，使其與懸挑對齊 ---
#     # 前山牆 (Front Gable, Z = -hl, 使用懸挑後的X邊界 e_lx, e_rx)
#     fg_v1 = [e_lx, e_y, -hl]  # 左下 (懸挑後的X)
#     fg_v2 = [e_rx, e_y, -hl]  # 右下 (懸挑後的X)
#     fg_v3 = [r_x,  r_y, -hl]  # 屋脊點 (X是屋脊偏移，Z是基底邊界)
# 
#     # 後山牆 (Back Gable, Z = +hl, 使用懸挑後的X邊緣 e_lx, e_rx)
#     bg_v1 = [e_rx, e_y,  hl]  # 右下 (懸挑後的X)
#     bg_v2 = [e_lx, e_y,  hl]  # 左下 (懸挑後的X)
#     bg_v3 = [r_x,  r_y,  hl]  # 屋脊點
# 
#     # --- 繪製山牆 (使用新的 fg_v1,2,3 和 bg_v1,2,3) ---
#     glBegin(GL_TRIANGLES)
#     # 前山牆
#     if not math.isclose(e_lx, e_rx): # 確保山牆有寬度 (即 eave_overhang_x 不是負到讓 e_lx > e_rx)
#         uv_rect_fg = uv_layout.get("front_gable", (0,0,1,1))
#         norm_fg = np.array([0,0,-1.0]) # 簡化法線 (朝向 -Z)
#         # 如果要精確法線: norm_fg = np.cross(np.subtract(fg_v2,fg_v1), np.subtract(fg_v3,fg_v1)); ...normalize...
#         glNormal3fv(norm_fg)
#         glTexCoord2f(*map_local_uv_to_atlas_subrect(0,0,uv_rect_fg)); glVertex3fv(fg_v1)
#         glTexCoord2f(*map_local_uv_to_atlas_subrect(1,0,uv_rect_fg)); glVertex3fv(fg_v2)
#         glTexCoord2f(*map_local_uv_to_atlas_subrect(0.5,1,uv_rect_fg)); glVertex3fv(fg_v3)
# 
#     # 後山牆
#     if not math.isclose(e_lx, e_rx):
#         uv_rect_bg = uv_layout.get("back_gable", (0,0,1,1))
#         norm_bg = np.array([0,0,1.0]) # 簡化法線 (朝向 +Z)
#         # 如果要精確法線: norm_bg = np.cross(np.subtract(bg_v2,bg_v1), np.subtract(bg_v3,bg_v1)); ...normalize...
#         glNormal3fv(norm_bg)
#         glTexCoord2f(*map_local_uv_to_atlas_subrect(0,0,uv_rect_bg)); glVertex3fv(bg_v1) # 注意頂點順序以匹配UV
#         glTexCoord2f(*map_local_uv_to_atlas_subrect(1,0,uv_rect_bg)); glVertex3fv(bg_v2)
#         glTexCoord2f(*map_local_uv_to_atlas_subrect(0.5,1,uv_rect_bg)); glVertex3fv(bg_v3) # bg_v3 的UV應與fg_v3類似
#                                                                                       # 修正：應為 uv_rect_bg
#         # 修正上一行的UV映射，應該使用 uv_rect_bg
#         # 實際應為：
#         # glTexCoord2f(*map_local_uv_to_atlas_subrect(0.5,1,uv_rect_bg)); glVertex3fv(bg_v3)
#     glEnd()

    # 3. 恢復OpenGL狀態
    if alpha_testing_was_enabled_this_call:
        glDisable(GL_ALPHA_TEST)
    if texture_id is not None and glIsTexture(texture_id):
        glBindTexture(GL_TEXTURE_2D, 0)
        # glDisable(GL_TEXTURE_2D) # 通常不由繪製函數禁用，除非它明確只為自己啟用
    else: # 如果之前是glColor3f
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

def draw_hill(center_x, base_y, center_z,
              base_radius, peak_height_offset,
              resolution=20,
#               texture_id=None,
              texture_id_from_scene=None,
              uscale=10.0, vscale=10.0,
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
                u = (world_dx / (2.0 * base_radius) + 0.5) * uscale
                v = (world_dz / (2.0 * base_radius) + 0.5) * vscale
                glTexCoord2f(u, v)

                # --- 繪製頂點 ---
                glVertex3f(world_x, world_y, world_z)
        glEnd() # 結束當前的 TRIANGLE_STRIP

    # --- 恢復狀態 ---
    if alpha_testing_was_actually_enabled_this_call:
        glDisable(GL_ALPHA_TEST) # 只恢復由此調用明確啟用的狀態
    
    if gl_texture_id_to_use: # 如果之前綁定了紋理
        glBindTexture(GL_TEXTURE_2D, 0) # 完成後解綁
    # 繪製結束後不需要禁用 GL_TEXTURE_2D，交給調用者管理
    
# --- draw_scene_objects (unchanged) ---
def draw_scene_objects(scene):
#     glEnable(GL_BLEND)
    # (Logic unchanged)
    glColor3f(1.0, 1.0, 1.0)
    # Buildings
    for item in scene.buildings:
        line_num, obj_data = item # 先解包出 行號 和 原始數據元組

        # --- 根據新的元組結構解包 ---
        # 假設 obj_data 結構為:
        # (obj_type, x, y, z, rx, abs_ry, rz, w, d, h,  <-- 索引 0-9
        #  u_offset, v_offset, tex_angle_deg, uv_mode, uscale, vscale, <-- 索引 10-15
        #  tex_filename,                               <-- 索引 16
        #  gl_texture_id,                              <-- 索引 17
        #  texture_has_alpha_flag                      <-- 索引 18
        # )
        # 再從原始數據元組解包出繪製所需變數
        (obj_type, x, y, z, rx, abs_ry, rz, w, d, h,
#          tex_id,
         u_offset, v_offset, tex_angle_deg, uv_mode, uscale, vscale, tex_file,
         gl_tex_id_val, tex_has_alpha_val
         ) = obj_data
        glPushMatrix();
        glTranslatef(x, y, z);
        glRotatef(abs_ry, 0, 1, 0);
        glRotatef(rx, 1, 0, 0);
        glRotatef(rz, 0, 0, 1)
#         print(f'gl_tex_id_val:{gl_tex_id_val}')
        draw_cube(w, d, h,
#                   tex_id,
                  gl_tex_id_val, 
                  u_offset, v_offset, tex_angle_deg,
                  uv_mode, uscale, vscale,
                  tex_has_alpha_val
                  )
        glPopMatrix()
    # Cylinders
    for item in scene.cylinders:
        line_num, obj_data = item # 先解包出 行號 和 原始數據元組
        # 再從原始數據元組解包出繪製所需變數
        (obj_type, x, y, z, rx, abs_ry, rz, radius, h,
#          tex_id,
         u_offset, v_offset, tex_angle_deg, uv_mode, uscale, vscale, tex_file,
         gl_tex_id_val, tex_has_alpha_val
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
            x, y, z, height, tex_id, tex_file = tree_data
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
             tex_file) = obj_data_tuple
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

    # --- Draw Hills ---
    glColor3f(1.0, 1.0, 1.0) # 重設顏色，draw_hill 內部會處理紋理或顏色
    for item in scene.hills:
        line_num, hill_data = item # 解包行號和數據
        try:
            # 解包 hill_data (與 scene_parser 中打包時一致)
            (cx, base_y, cz, radius, peak_h_offset,
#              tex_id,
             uscale, vscale, tex_file,
             gl_tex_id_val, tex_has_alpha_val
             ) = hill_data
        except ValueError:
             print(f"警告: 解包 hill 數據時出錯 (來源行: {line_num})")
             continue # 跳過這個物件

        # 不需要 Push/Pop Matrix，因為 draw_hill 使用絕對座標
        # 可以直接調用繪製函數
        draw_hill(cx, base_y, cz, radius, peak_h_offset,
                  10, # 可以將解析度設為可配置或常數
#                   texture_id=tex_id,
                  gl_tex_id_val, 
                  uscale, vscale,
                  tex_has_alpha_val
                  )

    # --- Draw Gableroofs ---
    if hasattr(scene, 'gableroofs'):
        for item in scene.gableroofs:
            line_identifier, roof_data_tuple = item
            try:
                # 根據 scene_parser 中 gableroof_data_tuple 的結構解包
                # (world_x, world_y, world_z, abs_rx, abs_ry, abs_rz,  <-- 0-5
                #  base_w, base_l, ridge_h_off,                       <-- 6-8
                #  ridge_x_pos, eave_over_x, eave_over_z,             <-- 9-11
                #  gl_tex_id, tex_has_alpha, tex_f_orig                 <-- 12-14
                # )
                world_x, world_y, world_z, abs_rx, abs_ry, abs_rz = roof_data_tuple[0:6]
                base_w, base_l, ridge_h_off = roof_data_tuple[6:9]
                # eave_h_from_parser = roof_data_tuple[8] # 如果你之前有 eave_h
                
                ridge_x_pos_offset_val = roof_data_tuple[9]
                eave_overhang_x_val = roof_data_tuple[10]
                eave_overhang_z_val = roof_data_tuple[11]
                
                gl_texture_id_val = roof_data_tuple[12]
                texture_has_alpha_val = roof_data_tuple[13]
                texture_atlas_file_original = roof_data_tuple[14]

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

def load_skybox(base_name):
    """
    Loads a skybox (cubemap) texture from 6 individual files.
    Files must be named <base_name>_px.png, <base_name>_nx.png, etc.
    Uses texture caching.
    """
    global skybox_texture_cache, texture_loader
    if not texture_loader:
        print("警告: 無法載入 Skybox，texture_loader 未設定。")
        return None
    if base_name in skybox_texture_cache:
        return skybox_texture_cache[base_name]

    texture_id = glGenTextures(1)
    glBindTexture(GL_TEXTURE_CUBE_MAP, texture_id)

    # Order and targets for cubemap faces
    # PyOpenGL uses different constants than standard OpenGL sometimes, check carefully
    # GL_TEXTURE_CUBE_MAP_POSITIVE_X, Negative_X, Positive_Y, Negative_Y, Positive_Z, Negative_Z
    suffixes = ["px", "nx", "py", "ny", "pz", "nz"]
    targets = [
        GL_TEXTURE_CUBE_MAP_POSITIVE_X, GL_TEXTURE_CUBE_MAP_NEGATIVE_X,
        GL_TEXTURE_CUBE_MAP_POSITIVE_Y, GL_TEXTURE_CUBE_MAP_NEGATIVE_Y,
        GL_TEXTURE_CUBE_MAP_POSITIVE_Z, GL_TEXTURE_CUBE_MAP_NEGATIVE_Z
    ]

    all_loaded = True
    for i in range(6):
        filename = f"{base_name}_{suffixes[i]}.png" # Assuming PNG format
        filepath = os.path.join("textures", filename)
        print(f"載入 Skybox 面: {filepath}")
        if not os.path.exists(filepath):
            print(f"警告: Skybox 紋理檔案 '{filepath}' 不存在。")
            all_loaded = False
            break # Stop loading if one face is missing

        try:
            surface = pygame.image.load(filepath)
            # Cubemaps often don't need alpha, but loading as RGBA is safer
            # Some tutorials suggest flipping Y for certain faces depending on tool,
            # but let's try without flipping first.
            texture_data = pygame.image.tostring(surface, "RGBA", False) # Try without Y-flip first

            glTexImage2D(targets[i], 0, GL_RGBA, surface.get_width(), surface.get_height(),
                         0, GL_RGBA, GL_UNSIGNED_BYTE, texture_data)
        except Exception as e:
            print(f"載入 Skybox 紋理 '{filepath}' 時發生錯誤: {e}")
            all_loaded = False
            break

    if all_loaded:
        glTexParameteri(GL_TEXTURE_CUBE_MAP, GL_TEXTURE_MAG_FILTER, GL_LINEAR)
        glTexParameteri(GL_TEXTURE_CUBE_MAP, GL_TEXTURE_MIN_FILTER, GL_LINEAR)
        # Clamp to edge is essential for skyboxes to avoid seams at edges
        glTexParameteri(GL_TEXTURE_CUBE_MAP, GL_TEXTURE_WRAP_S, GL_CLAMP_TO_EDGE)
        glTexParameteri(GL_TEXTURE_CUBE_MAP, GL_TEXTURE_WRAP_T, GL_CLAMP_TO_EDGE)
        glTexParameteri(GL_TEXTURE_CUBE_MAP, GL_TEXTURE_WRAP_R, GL_CLAMP_TO_EDGE) # WRAP_R for the 3rd dimension

        glBindTexture(GL_TEXTURE_CUBE_MAP, 0) # Unbind
        skybox_texture_cache[base_name] = texture_id
        print(f"Skybox 已載入並快取: '{base_name}' (ID: {texture_id})")
        return texture_id
    else:
        # Cleanup if loading failed
        glBindTexture(GL_TEXTURE_CUBE_MAP, 0)
        glDeleteTextures(1, [texture_id])
        print(f"Skybox '{base_name}' 載入失敗。")
        return None


def draw_skybox(base_name, size=1.0):
    """
    Draws a skybox cube centered around the origin.
    Requires the corresponding cubemap texture to be loaded via load_skybox.
    Assumes camera is at the origin for rendering skybox (or use matrix manipulation).
    Size parameter is mostly cosmetic, real 'distance' is handled by depth settings.
    """
    global skybox_texture_cache
    if base_name not in skybox_texture_cache:
        # Attempt to load it now if not cached? Or rely on preloading?
        # Let's try loading it dynamically.
        load_skybox(base_name)
        if base_name not in skybox_texture_cache: # Check again after trying to load
             print(f"警告: Skybox '{base_name}' 未載入，無法繪製。")
             return

    skybox_id = skybox_texture_cache[base_name]

    glPushAttrib(GL_ENABLE_BIT | GL_DEPTH_BUFFER_BIT | GL_POLYGON_BIT | GL_TEXTURE_BIT | GL_LIGHTING_BIT | GL_CURRENT_BIT) # Save more states
    glEnable(GL_TEXTURE_CUBE_MAP)
    glBindTexture(GL_TEXTURE_CUBE_MAP, skybox_id)

    glDisable(GL_LIGHTING)      # Skybox is not affected by scene lighting
    glDisable(GL_DEPTH_TEST)    # Draw behind everything (Method 1)
    # glDepthMask(GL_FALSE)     # Don't write to depth buffer (Alternative Method 2)
    glDisable(GL_CULL_FACE)     # Draw inside faces of the cube

    # Set color to white to avoid tinting the texture
    glColor3f(1.0, 1.0, 1.0)

    s = size / 2.0 # Half size

    # Draw the cube using texture coordinates suitable for cubemaps
    # Texture coordinates for cubemaps are 3D vectors pointing from the center
    # towards the vertex. OpenGL calculates the correct face lookup based on this.
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
    # Restore states
    # glEnable(GL_DEPTH_TEST) # Restore if disabled above
    # glDepthMask(GL_TRUE)    # Restore if set to FALSE above
    # glEnable(GL_CULL_FACE)  # Restore if needed
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
