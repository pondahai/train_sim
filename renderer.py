# renderer.py
from OpenGL.GL import *
from OpenGL.GLU import *
import numpy as np
import numpy as math
# import math
from track import TRACK_WIDTH, BALLAST_WIDTH, BALLAST_HEIGHT  # 引入軌道寬度等常數
import texture_loader # 假設紋理載入器可用
import pygame # <-- 新增：導入 Pygame
import os

from numba import jit, njit

# --- 一些繪圖參數 ---
GROUND_SIZE = 200.0
TREE_TRUNK_RADIUS = 0.2
TREE_LEAVES_RADIUS = 1.5
RAIL_COLOR = (0.4, 0.4, 0.5) # 軌道顏色
BALLAST_COLOR = (0.6, 0.55, 0.5) # 道碴顏色
CAB_COLOR = (0.2, 0.3, 0.7) # 駕駛艙顏色
DASHBOARD_COLOR = (0.8, 0.8, 0.85) # 儀表板顏色
LEVER_COLOR = (0.8, 0.1, 0.1) # 操作桿顏色
NEEDLE_COLOR = (0.0, 0.0, 0.0) # 指針顏色
CYLINDER_SLICES = 128 # 圓柱體側面數

# --- 小地圖參數 ---  <-- 新增
MINIMAP_SIZE = 500  # 小地圖的像素大小 (正方形)
MINIMAP_PADDING = 10 # 離螢幕邊緣的距離
# MINIMAP_RANGE = 300.0 # 小地圖顯示的世界單位範圍 (以此距離為半徑的正方形區域)
DEFAULT_MINIMAP_RANGE = 500.0 # 小地圖預設顯示的世界單位範圍
MINIMAP_MIN_RANGE = 10.0      # <-- 新增：最小縮放範圍 (放大極限)
MINIMAP_MAX_RANGE = 1000.0    # <-- 新增：最大縮放範圍 (縮小極限)
MINIMAP_ZOOM_FACTOR = 1.1     # <-- 新增：每次縮放的比例因子
MINIMAP_BG_FALLBACK_COLOR = (0.2, 0.2, 0.2, 0.7) # Use if no map image specified or fails to load
EDITOR_BG_COLOR = (0.15, 0.15, 0.18, 1.0) # Different BG for editor view <--- ADD THIS LINE
MINIMAP_BG_COLOR = (0.2, 0.2, 0.2, 0.7) # 背景顏色 (RGBA)
MINIMAP_TRACK_COLOR = (1.0, 0.0, 0.0) # 軌道顏色 ()
MINIMAP_BUILDING_COLOR = (0.6, 0.4, 0.2) # 建築顏色 (棕色)
MINIMAP_CYLINDER_COLOR = (0.6, 0.4, 0.2) # Use same color for cylinders for now
MINIMAP_TILTED_CYLINDER_BOX_SIZE_FACTOR = 1.0 # Factor to scale the tilted box size (relative to max(radius, height/2))
MINIMAP_TREE_COLOR = (0.1, 0.8, 0.1) # 樹木顏色 (綠色)
MINIMAP_PLAYER_COLOR = (1.0, 0.0, 0.0) # 玩家顏色 (紅色)
MINIMAP_PLAYER_SIZE = 36 # 玩家標記的大小 (像素)
# --- 新增：網格線參數 ---
MINIMAP_GRID_SCALE = 50.0 # 世界單位中每格的大小
MINIMAP_GRID_COLOR = (1.0, 1.0, 1.0, 0.3) # 網格線顏色 (淡白色)
MINIMAP_GRID_LABEL_COLOR = (255, 255, 255, 180) # 網格標籤顏色 (稍亮的白色)
MINIMAP_GRID_LABEL_FONT_SIZE = 24 # 網格標籤字體大小
MINIMAP_GRID_LABEL_OFFSET = 2 # 標籤離地圖邊緣的像素距離

# --- REMOVED Hardcoded map file and world coordinate constants ---
# MINIMAP_BACKGROUND_IMAGE_FILE = "map.png"
# MAP_IMAGE_WORLD_X_MIN = -500.0
# ... and others ...

# --- NEW: Globals for managing the current map texture ---
current_map_filename_rendered = None # Keep track of the filename associated with the texture ID
minimap_bg_texture_id = None # Store the loaded texture ID
minimap_bg_image_width_px = 0 # Store loaded image pixel width
minimap_bg_image_height_px = 0 # Store loaded image pixel height

# --- 全域 HUD 字體 ---
hud_display_font = None
# --- 新增：網格標籤字體 ---
grid_label_font = None

# --- 坐標顯示參數 ---
COORD_PADDING_X = 10 # 左邊距
COORD_PADDING_Y = 10 # 上邊距 (從頂部算)
COORD_TEXT_COLOR = (255, 255, 255, 255) # 文字顏色 (RGBA - 白色)

# --- 紋理 ID 緩存 (避免重複載入) ---
grass_tex = None
tree_bark_tex = None
tree_leaves_tex = None
cab_metal_tex = None # 駕駛艙紋理 (可選)

# --- 新增：當前小地圖範圍變數 ---
current_minimap_range = DEFAULT_MINIMAP_RANGE

# --- 新增：縮放小地圖函數 ---
def zoom_minimap(factor):
    """
    根據因子縮放小地圖範圍。
    factor > 1: 縮小 (範圍變大)
    factor < 1: 放大 (範圍變小)
    """
    global current_minimap_range
    current_minimap_range *= factor
    # 限制縮放範圍
    current_minimap_range = max(MINIMAP_MIN_RANGE, min(current_minimap_range, MINIMAP_MAX_RANGE))
    print(f"Minimap range set to: {current_minimap_range:.1f}")

def set_hud_font(font):
    """從 main.py 接收 Pygame 字體物件"""
    global hud_display_font, grid_label_font
    hud_display_font = font

    # 重置 grid_label_font
    grid_label_font = None
    # 為網格標籤創建一個較小的字體
    if hud_display_font: # 確保主字體已成功傳入
        # 直接嘗試創建網格標籤字體，使用系統默認字體和指定大小
        try:
            grid_label_font = pygame.font.SysFont(None, MINIMAP_GRID_LABEL_FONT_SIZE)
            print(f"網格標籤字體已創建 (大小: {MINIMAP_GRID_LABEL_FONT_SIZE}).")
        except Exception as e:
            # 如果創建失敗，則 grid_label_font 保持為 None
            print(f"警告: 無法加載系統默認字體作為網格標籤字體 (大小: {MINIMAP_GRID_LABEL_FONT_SIZE}): {e}")
            grid_label_font = None
    else:
        # 如果主字體就沒傳過來，那網格字體也無法創建
        print("警告: 主 HUD 字體未設置，網格標籤字體無法創建。")

# --- 紋理載入輔助函數 (用於載入地圖背景) ---
def _load_minimap_texture(filename):
    """載入 Minimap 背景紋理，並根據其解析度計算世界座標範圍"""
    global minimap_bg_texture_id, minimap_bg_image_width_px, minimap_bg_image_height_px

    # Clear previous texture info first
    if minimap_bg_texture_id is not None and glIsTexture(minimap_bg_texture_id):
        glDeleteTextures(1, [minimap_bg_texture_id])
    minimap_bg_texture_id = None
    minimap_bg_image_width_px = 0
    minimap_bg_image_height_px = 0

    if filename is None:
        return None # No filename provided

    filepath = os.path.join("textures", filename)
    if not os.path.exists(filepath):
        print(f"警告: Minimap 背景圖檔案 '{filepath}' 不存在。")
        return None

    try:
        surface = pygame.image.load(filepath).convert_alpha()
        texture_data = pygame.image.tostring(surface, "RGBA", True)
        width_px, height_px = surface.get_width(), surface.get_height()

        if width_px <= 0 or height_px <= 0:
             print(f"警告: Minimap 背景圖 '{filepath}' 寬度或高度無效 ({width_px}x{height_px})。")
             return None

        # Store dimensions
        minimap_bg_image_width_px = width_px
        minimap_bg_image_height_px = height_px

        # --- 載入紋理到 OpenGL ---
        tex_id = glGenTextures(1)
        glBindTexture(GL_TEXTURE_2D, tex_id)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_CLAMP_TO_EDGE) # Clamp prevents repeating edge pixels
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_CLAMP_TO_EDGE)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR) # Linear filtering for zoom
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR) # Linear filtering for shrink
        glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA, width_px, height_px, 0,
                     GL_RGBA, GL_UNSIGNED_BYTE, texture_data)
        glBindTexture(GL_TEXTURE_2D, 0) # Unbind

        minimap_bg_texture_id = tex_id # Store the valid texture ID
        print(f"Minimap 背景圖已載入: {filename} (ID: {tex_id}, {width_px}x{height_px}px)")
        return tex_id

    except Exception as e:
        print(f"載入 Minimap 背景圖 '{filepath}' 時發生錯誤: {e}")
        minimap_bg_texture_id = None # Ensure ID is None on error
        minimap_bg_image_width_px = 0
        minimap_bg_image_height_px = 0
        return None

# --- NEW: Functions to manage map texture based on scene changes ---
def clear_cached_map_texture():
    """Called by scene_parser before reloading to reset state."""
    global current_map_filename_rendered, minimap_bg_texture_id
    global minimap_bg_image_width_px, minimap_bg_image_height_px

    if minimap_bg_texture_id is not None and glIsTexture(minimap_bg_texture_id):
         # This deletion might be redundant if texture_loader.clear_texture_cache covers it,
         # but explicit cleanup here is safer.
         # glDeleteTextures(1, [minimap_bg_texture_id]) # Let texture_loader handle deletion via cache
         pass # Assume texture_loader cache clear handles GL deletion

    minimap_bg_texture_id = None
    current_map_filename_rendered = None
    minimap_bg_image_width_px = 0
    minimap_bg_image_height_px = 0
    print("已清除快取的小地圖紋理狀態。")


def update_map_texture(scene):
    """Loads/unloads the minimap texture based on the current scene's map settings."""
    global current_map_filename_rendered, minimap_bg_texture_id
    global minimap_bg_image_width_px, minimap_bg_image_height_px

    target_filename = scene.map_filename # Get filename from the scene object

    if target_filename != current_map_filename_rendered:
        print(f"偵測到小地圖檔案變更: 從 '{current_map_filename_rendered}' 到 '{target_filename}'")
        # Load the new texture (or unload if target is None)
        _load_minimap_texture(target_filename) # This function now handles cleanup and loading

        # Update the cached filename *after* attempting to load
        current_map_filename_rendered = target_filename
    #else:
        #print(f"Minimap file unchanged ('{target_filename}'), skipping texture load.")
        #pass # No change needed


def init_renderer():
    """初始化渲染器，載入常用紋理"""
    global grass_tex, tree_bark_tex, tree_leaves_tex, cab_metal_tex
    # Load common non-map textures
    grass_tex = texture_loader.load_texture("grass.png")
    tree_bark_tex = texture_loader.load_texture("tree_bark.png")
    tree_leaves_tex = texture_loader.load_texture("tree_leaves.png")
    cab_metal_tex = texture_loader.load_texture("metal.png") # Assuming cab uses metal texture

    # --- REMOVED: Hardcoded loading of minimap background ---
    # _load_minimap_texture(MINIMAP_BACKGROUND_IMAGE_FILE) # Now handled by update_map_texture

    # 設置一些 OpenGL 狀態
    glEnable(GL_DEPTH_TEST)
    glEnable(GL_TEXTURE_2D)
    glEnable(GL_LIGHTING)
    glEnable(GL_LIGHT0)
    glEnable(GL_COLOR_MATERIAL) # 允許 glColor 影響材質
    glColorMaterial(GL_FRONT_AND_BACK, GL_AMBIENT_AND_DIFFUSE)

    # 設置光照
    glLightfv(GL_LIGHT0, GL_AMBIENT, [0.3, 0.3, 0.3, 1.0])
    glLightfv(GL_LIGHT0, GL_DIFFUSE, [0.8, 0.8, 0.8, 1.0])
    glLightfv(GL_LIGHT0, GL_SPECULAR, [0.5, 0.5, 0.5, 1.0])
    glLightfv(GL_LIGHT0, GL_POSITION, [100.0, 150.0, 100.0, 1.0]) # 定位光源

    glEnable(GL_NORMALIZE) # 自動標準化法線

# --- draw_ground, draw_track, draw_cube, draw_cylinder, draw_tree remain the same ---
# ... (Keep existing drawing functions for ground, track, cube, cylinder, tree) ...
def draw_ground(show_ground):
    """繪製地面"""
    if not show_ground:
        return

    if grass_tex:
        glBindTexture(GL_TEXTURE_2D, grass_tex)
    else:
        glDisable(GL_TEXTURE_2D) # 如果沒有紋理則禁用

    glColor3f(0.3, 0.7, 0.3) # 草地顏色 (備用)
    glBegin(GL_QUADS)
    # 計算紋理坐標使紋理重複
    tex_repeat = GROUND_SIZE / 10.0 # 每 10 個單位重複一次紋理
    glNormal3f(0, 1, 0) # 地面法線朝上
    glTexCoord2f(0, 0); glVertex3f(-GROUND_SIZE, 0, -GROUND_SIZE)
    glTexCoord2f(tex_repeat, 0); glVertex3f(GROUND_SIZE, 0, -GROUND_SIZE)
    glTexCoord2f(tex_repeat, tex_repeat); glVertex3f(GROUND_SIZE, 0, GROUND_SIZE)
    glTexCoord2f(0, tex_repeat); glVertex3f(-GROUND_SIZE, 0, GROUND_SIZE)
    glEnd()

    glEnable(GL_TEXTURE_2D) # 確保紋理啟用狀態恢復
    glBindTexture(GL_TEXTURE_2D, 0) # 解除綁定

def draw_track(track_obj):
    """使用 VBO/VAO 繪製軌道和道碴"""
    if not track_obj or not track_obj.segments:
        return
    
    """繪製軌道和道碴"""
    glDisable(GL_TEXTURE_2D) # 軌道和道碴不用紋理
    glEnableClientState(GL_VERTEX_ARRAY) # (如果你沒有使用 location=0 的 VAO，可能需要這個，但 VAO 是推薦方式)

    half_track_width = TRACK_WIDTH / 2.0
    half_ballast_width = BALLAST_WIDTH / 2.0

    for segment in track_obj.segments:
        # --- 繪製道碴 (使用 VAO) ---
        if segment.ballast_vao and segment.ballast_vertices:
            glColor3fv(BALLAST_COLOR)
            glBindVertexArray(segment.ballast_vao)
            # 頂點數量 = 列表長度 / 3 (因為每個頂點有 x,y,z 三個浮點數)
            vertex_count = len(segment.ballast_vertices) // 3
            glDrawArrays(GL_TRIANGLES, 0, vertex_count) # 使用 GL_TRIANGLES
            glBindVertexArray(0) # 解綁

        # --- 繪製軌道 (使用 VAO) ---
        glLineWidth(2.0) # 設定線寬
        glColor3fv(RAIL_COLOR)

        # 左軌道
        if segment.rail_left_vao and segment.rail_left_vertices:
            glBindVertexArray(segment.rail_left_vao)
            vertex_count = len(segment.rail_left_vertices) // 3
            glDrawArrays(GL_LINE_STRIP, 0, vertex_count)
            glBindVertexArray(0)

        # 右軌道
        if segment.rail_right_vao and segment.rail_right_vertices:
            glBindVertexArray(segment.rail_right_vao)
            vertex_count = len(segment.rail_right_vertices) // 3
            glDrawArrays(GL_LINE_STRIP, 0, vertex_count)
            glBindVertexArray(0)

    glDisableClientState(GL_VERTEX_ARRAY) # (如果之前啟用了)
    glEnable(GL_TEXTURE_2D) # 恢復紋理狀態
#     for segment in track_obj.segments:
#         if not segment.points or len(segment.points) < 2:
#             continue
# 
#         # 繪製道碴 (使用 Triangle Strip 提高效率)
#         glColor3fv(BALLAST_COLOR)
#         glBegin(GL_TRIANGLE_STRIP)
#         for i in range(len(segment.points)):
#             pos = segment.points[i]
#             orient_xz = segment.orientations[i]
#             # 計算垂直於軌道的向量 (right vector)
#             right_vec_xz = np.array([-orient_xz[1], 0, orient_xz[0]]) # Assumes orient_xz is normalized
# 
#             # 在點 pos 處計算左右道碴點 (高度基於 pos[1])
#             p_ballast_left = pos + right_vec_xz * half_ballast_width
#             p_ballast_right = pos - right_vec_xz * half_ballast_width
# 
#             glNormal3f(0, 1, 0) # 道碴頂面法線向上
#             glVertex3f(p_ballast_left[0], pos[1] + BALLAST_HEIGHT, p_ballast_left[2])
#             glVertex3f(p_ballast_right[0], pos[1] + BALLAST_HEIGHT, p_ballast_right[2])
#         glEnd()
#         # 可以選擇性繪製道碴側面
# 
#         # 繪製兩條軌道 (使用 Line Strip)
#         glColor3fv(RAIL_COLOR)
#         glLineWidth(2.0) # 設定線寬
#         rail_height_offset = BALLAST_HEIGHT + 0.05 # 軌道在道碴之上
# 
#         # 左軌道
#         glBegin(GL_LINE_STRIP)
#         for i in range(len(segment.points)):
#             pos = segment.points[i]
#             orient_xz = segment.orientations[i]
#             right_vec_xz = np.array([-orient_xz[1], 0, orient_xz[0]])
#             p_rail_left = pos + right_vec_xz * half_track_width
#             # *** 使用點的 Y 坐標加上軌道偏移 ***
#             glVertex3f(p_rail_left[0], pos[1] + rail_height_offset, p_rail_left[2])
#         glEnd()
# 
#         # 右軌道
#         glBegin(GL_LINE_STRIP)
#         for i in range(len(segment.points)):
#             pos = segment.points[i]
#             orient_xz = segment.orientations[i]
#             right_vec_xz = np.array([-orient_xz[1], 0, orient_xz[0]])
#             p_rail_right = pos - right_vec_xz * half_track_width
#              # *** 使用點的 Y 坐標加上軌道偏移 ***
#             glVertex3f(p_rail_right[0], pos[1] + rail_height_offset, p_rail_right[2])
#         glEnd()
# 
#     glEnable(GL_TEXTURE_2D) # 恢復紋理狀態

@njit
def _calculate_uv(u_base, v_base, center_u, center_v, u_offset, v_offset, angle_rad, uv_mode, uscale=1.0, vscale=1.0):
    """Helper function to calculate final UV coordinates for a vertex."""
    # Apply scaling *before* rotation if uv_mode is 0 (Tile)
    if uv_mode == 0:
        # Scale relative to the base coordinates (which are 0 to size)
        # Scaling should probably happen around the center? Or just scale the final range?
        # Let's scale the raw size-based coords first.
        # Example: if base is (width, 0), scale to (width/uscale, 0)
        # Check for zero scale to prevent division errors
        if uscale == 0: uscale = 1e-6
        if vscale == 0: vscale = 1e-6
        u_scaled = u_base / uscale
        v_scaled = v_base / vscale
        # Recalculate center based on scaled range if needed? No, center is geometric.
        # The range is now [0, face_w/uscale] and [0, face_h/vscale]
        # Let's keep the base coords and apply scale *after* rotation/offset?
        # Or apply scale to the *result* of rotation?
        # Let's try scaling the *base* coordinates before doing anything else.
        u_base = u_scaled
        v_base = v_scaled
        # Adjust center for rotation if scaling is done first? Center remains geometric center.
        center_u_scaled = center_u / uscale
        center_v_scaled = center_v / vscale
        center_u = center_u_scaled # Use scaled center for rotation origin? Makes sense.
        center_v = center_v_scaled


    cos_t = math.cos(angle_rad)
    sin_t = math.sin(angle_rad)

    # Translate to origin (using potentially scaled center if mode is 0)
    u_trans = u_base - center_u
    v_trans = v_base - center_v

    # Rotate
    u_rot = u_trans * cos_t - v_trans * sin_t
    v_rot = u_trans * sin_t + v_trans * cos_t

    # Translate back and apply offset
    final_u = u_rot + center_u + u_offset
    final_v = v_rot + center_v + v_offset

    # --- Alternative scaling approach: Scale *after* rotation ---
    # if uv_mode == 0:
    #     if uscale == 0: uscale = 1e-6
    #     if vscale == 0: vscale = 1e-6
    #     # Scale the final coordinate relative to the offset origin
    #     final_u = (final_u - u_offset) / uscale + u_offset
    #     final_v = (final_v - v_offset) / vscale + v_offset
    # This might be simpler but could interact weirdly with rotation center.
    # Let's stick with scaling the base first.

    return final_u, final_v


def draw_cube(width, depth, height, texture_id=None,
              u_offset=0.0, v_offset=0.0, tex_angle_deg=0.0, uv_mode=1,
              uscale=1.0, vscale=1.0):
    """
    繪製一個立方體，可選紋理，支援紋理偏移、旋轉和平鋪/拉伸模式。
    基於底部中心 (0,0,0)，頂部在 Y=height。
    uv_mode=1: 拉伸填滿 (0-1 範圍) (忽略 pixels_per_unit)
    uv_mode=0: 單位平鋪 (範圍 0-尺寸) ，使用 uscale, vscale
    """
    if texture_id is not None and glIsTexture(texture_id): # Check if texture ID is valid
        glBindTexture(GL_TEXTURE_2D, texture_id)
        glEnable(GL_TEXTURE_2D)
        # Set texture wrap mode based on uv_mode
        if uv_mode == 0: # Tile mode needs GL_REPEAT
            glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_REPEAT)
            glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_REPEAT)
        else: # Stretch mode might use GL_CLAMP_TO_EDGE or GL_REPEAT, REPEAT is often fine
             glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_REPEAT) # Or GL_CLAMP_TO_EDGE
             glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_REPEAT) # Or GL_CLAMP_TO_EDGE
    else:
        glDisable(GL_TEXTURE_2D)

    w, d, h = width / 2.0, depth / 2.0, height # 中心在底部 (0, 0, 0), 頂部在 Y=h
    angle_rad = math.radians(tex_angle_deg)

    # glColor3f(0.8, 0.8, 0.8) # Set color outside if needed

    glBegin(GL_QUADS)
    
    # --- Bottom face (Y=0) ---
    # Dimensions: width (X) maps to U, depth (Z) maps to V
    face_w, face_h = width, depth
    current_uscale, current_vscale = uscale, vscale # Use specific scales for this face
    if uv_mode == 1:
        base_coords = [(1, 0), (0, 0), (0, 1), (1, 1)]
        center_u, center_v = 0.5, 0.5
    else:
        base_coords = [(width, 0), (0, 0), (0, depth), (width, depth)] # U=[0,w], V=[0,d]
        center_u, center_v = width / 2.0, depth / 2.0
    glNormal3f(0, -1, 0)
    uv = _calculate_uv(*base_coords[0], center_u, center_v, u_offset, v_offset, angle_rad, uv_mode, current_uscale, current_vscale); glTexCoord2f(*uv); glVertex3f( w, 0,  d)
    uv = _calculate_uv(*base_coords[1], center_u, center_v, u_offset, v_offset, angle_rad, uv_mode, current_uscale, current_vscale); glTexCoord2f(*uv); glVertex3f(-w, 0,  d)
    uv = _calculate_uv(*base_coords[2], center_u, center_v, u_offset, v_offset, angle_rad, uv_mode, current_uscale, current_vscale); glTexCoord2f(*uv); glVertex3f(-w, 0, -d)
    uv = _calculate_uv(*base_coords[3], center_u, center_v, u_offset, v_offset, angle_rad, uv_mode, current_uscale, current_vscale); glTexCoord2f(*uv); glVertex3f( w, 0, -d)

    # --- Top face (Y=h) ---
    # Dimensions: width (X) -> U, depth (Z) -> V
    face_w, face_h = width, depth
    current_uscale, current_vscale = uscale, vscale
    if uv_mode == 1:
        base_coords = [(1, 1), (0, 1), (0, 0), (1, 0)]
        center_u, center_v = 0.5, 0.5
    else:
        base_coords = [(width, depth), (0, depth), (0, 0), (width, 0)] # U=[0,w], V=[0,d]
        center_u, center_v = width / 2.0, depth / 2.0
    glNormal3f(0, 1, 0)
    uv = _calculate_uv(*base_coords[0], center_u, center_v, u_offset, v_offset, angle_rad, uv_mode, current_uscale, current_vscale); glTexCoord2f(*uv); glVertex3f( w, h, -d)
    uv = _calculate_uv(*base_coords[1], center_u, center_v, u_offset, v_offset, angle_rad, uv_mode, current_uscale, current_vscale); glTexCoord2f(*uv); glVertex3f(-w, h, -d)
    uv = _calculate_uv(*base_coords[2], center_u, center_v, u_offset, v_offset, angle_rad, uv_mode, current_uscale, current_vscale); glTexCoord2f(*uv); glVertex3f(-w, h,  d)
    uv = _calculate_uv(*base_coords[3], center_u, center_v, u_offset, v_offset, angle_rad, uv_mode, current_uscale, current_vscale); glTexCoord2f(*uv); glVertex3f( w, h,  d)

    # --- Front face (Z=d) ---
    # Dimensions: width (X) -> U, height (Y) -> V
    face_w, face_h = width, height
    current_uscale, current_vscale = uscale, vscale # Or maybe specific scales for vertical faces?
    if uv_mode == 1:
        base_coords = [(1, 0), (0, 0), (0, 1), (1, 1)]
        center_u, center_v = 0.5, 0.5
    else:
        base_coords = [(width, 0), (0, 0), (0, height), (width, height)] # U=[0,w], V=[0,h]
        center_u, center_v = width / 2.0, height / 2.0
    glNormal3f(0, 0, 1)
    uv = _calculate_uv(*base_coords[0], center_u, center_v, u_offset, v_offset, angle_rad, uv_mode, current_uscale, current_vscale); glTexCoord2f(*uv); glVertex3f( w, 0, d)
    uv = _calculate_uv(*base_coords[1], center_u, center_v, u_offset, v_offset, angle_rad, uv_mode, current_uscale, current_vscale); glTexCoord2f(*uv); glVertex3f(-w, 0, d)
    uv = _calculate_uv(*base_coords[2], center_u, center_v, u_offset, v_offset, angle_rad, uv_mode, current_uscale, current_vscale); glTexCoord2f(*uv); glVertex3f(-w, h, d)
    uv = _calculate_uv(*base_coords[3], center_u, center_v, u_offset, v_offset, angle_rad, uv_mode, current_uscale, current_vscale); glTexCoord2f(*uv); glVertex3f( w, h, d)

    # --- Back face (Z=-d) ---
    # Dimensions: width (X) -> U, height (Y) -> V
    face_w, face_h = width, height
    current_uscale, current_vscale = uscale, vscale
    if uv_mode == 1:
        base_coords = [(0, 1), (1, 1), (1, 0), (0, 0)] # Flipped U
        center_u, center_v = 0.5, 0.5
    else:
        base_coords = [(width, height), (0, height), (0, 0), (width, 0)] # U=[0,w], V=[0,h]
        center_u, center_v = width / 2.0, height / 2.0
    glNormal3f(0, 0, -1)
    uv = _calculate_uv(*base_coords[0], center_u, center_v, u_offset, v_offset, angle_rad, uv_mode, current_uscale, current_vscale); glTexCoord2f(*uv); glVertex3f( w, h, -d)
    uv = _calculate_uv(*base_coords[1], center_u, center_v, u_offset, v_offset, angle_rad, uv_mode, current_uscale, current_vscale); glTexCoord2f(*uv); glVertex3f(-w, h, -d)
    uv = _calculate_uv(*base_coords[2], center_u, center_v, u_offset, v_offset, angle_rad, uv_mode, current_uscale, current_vscale); glTexCoord2f(*uv); glVertex3f(-w, 0, -d)
    uv = _calculate_uv(*base_coords[3], center_u, center_v, u_offset, v_offset, angle_rad, uv_mode, current_uscale, current_vscale); glTexCoord2f(*uv); glVertex3f( w, 0, -d)

    # --- Left face (X=-w) ---
    # Dimensions: depth (Z) -> U, height (Y) -> V
    face_w, face_h = depth, height
    current_uscale, current_vscale = uscale, vscale # Use the main scales? Or allow different scales for sides? Assuming main scales for now.
    if uv_mode == 1:
        base_coords = [(1, 0), (0, 0), (0, 1), (1, 1)]
        center_u, center_v = 0.5, 0.5
    else:
        base_coords = [(depth, 0), (0, 0), (0, height), (depth, height)] # U=[0,d], V=[0,h]
        center_u, center_v = depth / 2.0, height / 2.0
    glNormal3f(-1, 0, 0)
    uv = _calculate_uv(*base_coords[0], center_u, center_v, u_offset, v_offset, angle_rad, uv_mode, current_uscale, current_vscale); glTexCoord2f(*uv); glVertex3f(-w, 0, -d)
    uv = _calculate_uv(*base_coords[1], center_u, center_v, u_offset, v_offset, angle_rad, uv_mode, current_uscale, current_vscale); glTexCoord2f(*uv); glVertex3f(-w, 0,  d)
    uv = _calculate_uv(*base_coords[2], center_u, center_v, u_offset, v_offset, angle_rad, uv_mode, current_uscale, current_vscale); glTexCoord2f(*uv); glVertex3f(-w, h,  d)
    uv = _calculate_uv(*base_coords[3], center_u, center_v, u_offset, v_offset, angle_rad, uv_mode, current_uscale, current_vscale); glTexCoord2f(*uv); glVertex3f(-w, h, -d)

    # --- Right face (X=w) ---
    # Dimensions: depth (Z) -> U, height (Y) -> V
    face_w, face_h = depth, height
    current_uscale, current_vscale = uscale, vscale
    if uv_mode == 1:
        base_coords = [(0, 0), (1, 0), (1, 1), (0, 1)] # Flipped U
        center_u, center_v = 0.5, 0.5
    else:
        base_coords = [(0, 0), (depth, 0), (depth, height), (0, height)] # U=[0,d], V=[0,h]
        center_u, center_v = depth / 2.0, height / 2.0
    glNormal3f(1, 0, 0)
    uv = _calculate_uv(*base_coords[0], center_u, center_v, u_offset, v_offset, angle_rad, uv_mode, current_uscale, current_vscale); glTexCoord2f(*uv); glVertex3f( w, 0,  d)
    uv = _calculate_uv(*base_coords[1], center_u, center_v, u_offset, v_offset, angle_rad, uv_mode, current_uscale, current_vscale); glTexCoord2f(*uv); glVertex3f( w, 0, -d)
    uv = _calculate_uv(*base_coords[2], center_u, center_v, u_offset, v_offset, angle_rad, uv_mode, current_uscale, current_vscale); glTexCoord2f(*uv); glVertex3f( w, h, -d)
    uv = _calculate_uv(*base_coords[3], center_u, center_v, u_offset, v_offset, angle_rad, uv_mode, current_uscale, current_vscale); glTexCoord2f(*uv); glVertex3f( w, h,  d)


    glEnd()

    glBindTexture(GL_TEXTURE_2D, 0) # Unbind
    glEnable(GL_TEXTURE_2D) # Ensure it's enabled afterwards


def draw_cylinder(radius, height, texture_id=None,
                  u_offset=0.0, v_offset=0.0, tex_angle_deg=0.0, uv_mode=1,
                  uscale=1.0, vscale=1.0):
    """
    繪製圓柱體，可選紋理.
    uv_mode=0: 和 tex_angle_deg 在此基礎實現中可能效果不佳。
    
    
    """
    if texture_id is not None and glIsTexture(texture_id):
        glBindTexture(GL_TEXTURE_2D, texture_id)
        glEnable(GL_TEXTURE_2D)
        # Set wrap mode (REPEAT is usually desired for cylinders)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_REPEAT)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_REPEAT)
    else:
        glDisable(GL_TEXTURE_2D)

    quadric = gluNewQuadric()
    if quadric: # Check if quadric creation succeeded
        gluQuadricTexture(quadric, GL_TRUE) # Enable texture coordinates
        gluQuadricNormals(quadric, GLU_SMOOTH) # Smooth normals

        # --- Apply Texture Matrix Transformation (for offset) ---
        glMatrixMode(GL_TEXTURE)
        glPushMatrix() # Save current texture matrix
        glLoadIdentity() # Reset texture matrix
        # 1. Apply Offset (Translate texture lookup)
        glTranslatef(u_offset, v_offset, 0)

        # 2. Apply Rotation (around texture origin 0,0? Or center?) - Tricky!
        # Rotating here might not produce intuitive results with cylindrical mapping.
        # Let's skip rotation via matrix for GLU cylinder for now.
        # if tex_angle_deg != 0.0:
        #     # Translate to rotation center (e.g., 0.5, 0.5 if mode 1, or scaled center if mode 0?)
        #     # Rotate
        #     # Translate back
        #     pass # Complex to get right

        # 3. Apply Scaling (if mode is 0 - Tile/Scale)
        if uv_mode == 0:
            # Ensure scales are positive
            safe_uscale = uscale if uscale > 1e-6 else 1e-6
            safe_vscale = vscale if vscale > 1e-6 else 1e-6
            # Scale the texture coordinate system.
            # Dividing by scale makes texture appear larger (fewer repetitions).
            glScalef(1.0 / safe_uscale, 1.0 / safe_vscale, 1.0)
            # Note: This scales around the texture origin (0,0) after the translate.

        # --- Switch back to ModelView matrix ---
        glMatrixMode(GL_MODELVIEW)

        # --- Draw Cylinder using GLU ---
        # Body
        gluCylinder(quadric, radius, radius, height, CYLINDER_SLICES, 1)

        # --- Draw Caps (Reset Texture Matrix for Caps) ---
        # We reset the matrix for caps because their mapping is planar and likely
        # shouldn't inherit the scaling/offset applied for the cylindrical body.
        glMatrixMode(GL_TEXTURE)
        glLoadIdentity() # Reset texture matrix for caps
        glMatrixMode(GL_MODELVIEW)

        # Bottom cap
        glPushMatrix()
        glRotatef(180, 1, 0, 0)
        gluDisk(quadric, 0, radius, CYLINDER_SLICES, 1)
        glPopMatrix()

        # Top cap
        glPushMatrix()
        glTranslatef(0, 0, height)
        gluDisk(quadric, 0, radius, CYLINDER_SLICES, 1)
        glPopMatrix()

        gluDeleteQuadric(quadric)

        # --- Restore Texture Matrix ---
        glMatrixMode(GL_TEXTURE)
        glPopMatrix() # Restore previous texture matrix (before translate/scale)
        glMatrixMode(GL_MODELVIEW)

    else:
        print("Error creating GLU quadric object for cylinder.")


    glBindTexture(GL_TEXTURE_2D, 0) # Unbind
    glEnable(GL_TEXTURE_2D) # Re-enable


def draw_tree(x, y, z, height):
    """繪製一棵簡單的樹 (圓柱體+圓錐體)"""
    trunk_height = height * 0.6
    leaves_height = height * 0.4
    # leaves_y = y + trunk_height # Base of leaves

    glPushMatrix()
    glTranslatef(x, y, z) # Move to tree base position

    # --- Draw Trunk ---
    # glColor3f(0.5, 0.35, 0.05) # Trunk color
    if tree_bark_tex and glIsTexture(tree_bark_tex):
        glBindTexture(GL_TEXTURE_2D, tree_bark_tex)
        glEnable(GL_TEXTURE_2D)
        glColor3f(1.0, 1.0, 1.0) # Use white color when texturing
    else:
        glDisable(GL_TEXTURE_2D)
        glColor3f(0.5, 0.35, 0.05) # Fallback color

    quadric = gluNewQuadric()
    if quadric:
        gluQuadricTexture(quadric, GL_TRUE)
        gluQuadricNormals(quadric, GLU_SMOOTH)
        glPushMatrix()
        glRotatef(-90, 1, 0, 0) # Rotate cylinder to be Y-up
        # Draw trunk from y=0 to y=trunk_height
        gluCylinder(quadric, TREE_TRUNK_RADIUS, TREE_TRUNK_RADIUS * 0.8, trunk_height, CYLINDER_SLICES//2, 1) # Fewer slices for trunk
        glPopMatrix()
        gluDeleteQuadric(quadric)
    else: print("Error creating quadric for tree trunk.")

    # --- Draw Leaves ---
    # glColor3f(0.1, 0.5, 0.1) # Leaves color
    if tree_leaves_tex and glIsTexture(tree_leaves_tex):
        glBindTexture(GL_TEXTURE_2D, tree_leaves_tex)
        glEnable(GL_TEXTURE_2D)
        glColor3f(1.0, 1.0, 1.0) # Use white color when texturing
    else:
        glDisable(GL_TEXTURE_2D)
        glColor3f(0.1, 0.5, 0.1) # Fallback color

    glPushMatrix()
    glTranslatef(0, trunk_height, 0) # Move to the base of the leaves

    # 使用圓錐體代替球體可能更像樹
    quadric = gluNewQuadric()
    if quadric:
        gluQuadricTexture(quadric, GL_TRUE)
        gluQuadricNormals(quadric, GLU_SMOOTH)
        glPushMatrix()
        glRotatef(-90, 1, 0, 0) # Rotate cone to be Y-up
        # Draw cone from current position (base) upwards
        gluCylinder(quadric, TREE_LEAVES_RADIUS, 0, leaves_height * 1.5, CYLINDER_SLICES, 5) # Cone
        glPopMatrix()
        gluDeleteQuadric(quadric)
    else: print("Error creating quadric for tree leaves.")

    glPopMatrix() # Restore from leaves translation
    glPopMatrix() # Restore from tree base translation

    glBindTexture(GL_TEXTURE_2D, 0) # Unbind texture
    glEnable(GL_TEXTURE_2D) # Ensure texture is enabled
    glColor3f(1.0, 1.0, 1.0) # Reset color to white


def draw_scene_objects(scene):
    """繪製場景中的所有物件"""
    glColor3f(1.0, 1.0, 1.0) # Default to white, let textures/colors override

    # 繪製建築物
    for obj_data in scene.buildings:
        (obj_type, x, y, z, rx, ry, rz, w, d, h, tex_id,
         u_offset, v_offset, tex_angle_deg, uv_mode,
         uscale, vscale, tex_file) = obj_data
        glPushMatrix()
        glTranslatef(x, y, z) # Move to position
        # Apply rotations: Y (yaw), then X (pitch), then Z (roll) - common order
        glRotatef(ry, 0, 1, 0)
        glRotatef(rx, 1, 0, 0)
        glRotatef(rz, 0, 0, 1)
        draw_cube(w, d, h, tex_id, u_offset, v_offset, tex_angle_deg, uv_mode, uscale, vscale) # Draws cube with base at current origin
        glPopMatrix()

    # 繪製圓柱體
    for obj_data in scene.cylinders:
        # Order from parser: type, x, y, z, rx, rz, ry, radius, h, tex_id
        (obj_type, x, y, z, rx, rz, ry, radius, h, tex_id,
         u_offset, v_offset, tex_angle_deg, uv_mode,
         uscale, vscale, tex_file) = obj_data
        glPushMatrix()
        glTranslatef(x, y, z) # Move to position
        # Apply rotations specified in the file (rx, ry, rz order matters)
        # Typically, Y (yaw), X (pitch), Z (roll) is intuitive
        glRotatef(ry, 0, 1, 0) # Apply Yaw first
        glRotatef(rx, 1, 0, 0) # Then Pitch
        glRotatef(rz, 0, 0, 1) # Then Roll

        # Now, rotate the standard Z-aligned GLU cylinder to be Y-up *before* drawing
        glPushMatrix()
        glRotatef(-90, 1, 0, 0) # Rotate coordinate system so Z becomes Y
        draw_cylinder(radius, h, tex_id, u_offset, v_offset, tex_angle_deg, uv_mode, uscale, vscale) # Draw the cylinder along the (now rotated) Z-axis
        glPopMatrix() # Restore orientation before rotations

        glPopMatrix() # Restore position


    # 繪製樹木
    glColor3f(1.0, 1.0, 1.0) # Reset color for trees
    for tree_data in scene.trees:
        x, y, z, height = tree_data
        draw_tree(x, y, z, height)


def draw_tram_cab(tram, camera):
    """繪製駕駛艙和儀表板 (固定在電車上)"""
    # ... (Cab drawing code remains largely the same, ensure correct transforms) ...
    # --- Cab Geometry ---
    cab_width = 3
    cab_height = 1 # Height above floor
    cab_depth = 2
    cab_floor_y = 1.5 # Floor level of the cab relative to tram's position.y

    # --- Dashboard ---
    dash_height = 0.6
    dash_depth = 0.3
    dash_pos_y = 1.5 # 儀表板離地高度
    dash_pos_z = -1 # 儀表板在駕駛艙內的前後位置 (相對於駕駛艙中心)

    # --- Speedo ---
    speedo_radius = 0.15
    speedo_center_x = -cab_width * 0.25
    speedo_center_y = dash_pos_y + dash_height * 0.6
    speedo_center_z = dash_pos_z - dash_depth * 0.5 + 0.51 # 稍微突出

    # --- Lever ---
    lever_base_x = cab_width * 0
    lever_base_y = dash_pos_y + dash_height * 0.2
    lever_base_z = dash_pos_z - dash_depth * 0.4 + 0.5
    lever_length = 0.4
    lever_max_angle = -40.0 # 向前或向後的最大角度

    # ----------------------------------------
    #  核心：應用電車的變換
    # ----------------------------------------
    glPushMatrix()

    # 1. 移動到電車當前位置
    glTranslatef(tram.position[0], tram.position[1], tram.position[2])

    # 2. 旋轉以匹配電車朝向
    #    計算旋轉角度 (從 Z+ 軸開始)
#     angle_y = math.degrees(math.atan2(tram.forward_vector_xz[1], tram.forward_vector_xz[0]))
    #    OpenGL glRotatef 是繞 Y 軸旋轉，但我們的角度是從 X 軸計算的 atan2(y,x)
    #    需要調整，或者直接使用 forward vector 構建矩陣。
    #    簡單方法：atan2 給出的是與 X 軸正方向的夾角。需要轉換為繞 Y 軸的旋轉。
    #    如果 forward = (1,0) -> angle = 0
    #    如果 forward = (0,1) -> angle = 90
    #    如果 forward = (-1,0) -> angle = 180
    #    如果 forward = (0,-1) -> angle = -90 or 270
    #    glRotatef 的 Y 軸旋轉：正角度是逆時針（從上往下看）
    #    我們需要從 Z+ (0,0,1) 旋轉到 (forward_x, 0, forward_z)
    #    角度應該是 atan2(forward_x, forward_z) -> 這是繞 Y 軸的正確角度
    render_angle_y = math.degrees(math.arctan2(tram.forward_vector_xz[0], tram.forward_vector_xz[1]))
    glRotatef(180.0, 0, 1, 0)
    glRotatef(render_angle_y, 0, 1, 0)

    # --- 在電車的局部坐標系中繪製 ---

    # 可選：繪製一個簡單的電車平台 (方便觀察)
    platform_width = cab_width + 0.2
    platform_length = cab_depth + 1.0
    platform_height = 0.2
    glColor3f(0.5, 0.5, 0.5)
    glPushMatrix()
    glTranslatef(0, -platform_height, -platform_length / 2 + cab_depth/2) # 平台中心稍微靠後
#     draw_cube_centered(platform_width, platform_length, platform_height)
    draw_cube(platform_width, platform_length, platform_height)
    
    # 修改為居中放置:
#     glTranslatef(0, -platform_height, 0) # 將平台中心 Z 設為 0 (與駕駛艙中心一致)
#     draw_cube(platform_width, platform_length, platform_height)


    glPopMatrix()


    # 繪製駕駛艙外殼 (一個簡單的盒子)
    glColor3fv(CAB_COLOR)
    if cab_metal_tex:
        glBindTexture(GL_TEXTURE_D, cab_metal_tex)
        glEnable(GL_TEXTURE_2D)
    else:
        glDisable(GL_TEXTURE_2D)

    # 繪製一個沒有頂部和前部的盒子作為基礎駕駛艙
    glBegin(GL_QUADS)
    # Floor
    glNormal3f(0, 1, 0);
    glVertex3f(-cab_width/2, 1, -cab_depth/2)
    glVertex3f( cab_width/2, 1, -cab_depth/2)
    glVertex3f( cab_width/2, 1,  cab_depth/2)
    glVertex3f(-cab_width/2, 1,  cab_depth/2)
    # head wall
    glNormal3f(0, 0, -1);
    glVertex3f(-cab_width/2, 1 + cab_height, -cab_depth/2)
    glVertex3f( cab_width/2, 1 + cab_height, -cab_depth/2)
    glVertex3f( cab_width/2, 1,          -cab_depth/2)
    glVertex3f(-cab_width/2, 1,          -cab_depth/2)
    # Left wall
    glNormal3f(-1, 0, 0);
    glVertex3f(-cab_width/2, 1 + cab_height,  cab_depth/2)
    glVertex3f(-cab_width/2, 1 + cab_height, -cab_depth/2)
    glVertex3f(-cab_width/2, 1,          -cab_depth/2)
    glVertex3f(-cab_width/2, 1,           cab_depth/2)
    # Right wall
    glNormal3f(1, 0, 0);
    glVertex3f( cab_width/2, 1 + cab_height, -cab_depth/2)
    glVertex3f( cab_width/2, 1 + cab_height,  cab_depth/2)
    glVertex3f( cab_width/2, 1,           cab_depth/2)
    glVertex3f( cab_width/2, 1,          -cab_depth/2)
    # back wall
    glNormal3f(0, 0, 1);
    glVertex3f(-cab_width/2, 1 + cab_height + 1, cab_depth/2)
    glVertex3f( cab_width/2, 1 + cab_height + 1, cab_depth/2)
    glVertex3f( cab_width/2, 1,          cab_depth/2)
    glVertex3f(-cab_width/2, 1,          cab_depth/2)
    # top 
    glNormal3f(0, -1, 0);
    glVertex3f(-cab_width/2, 1 + cab_height + 1, -cab_depth/2)
    glVertex3f( cab_width/2, 1 + cab_height + 1, -cab_depth/2)
    glVertex3f( cab_width/2, 1 + cab_height + 1,  cab_depth/2)
    glVertex3f(-cab_width/2, 1 + cab_height + 1,  cab_depth/2)
    # middle front wall
    glNormal3f(0, 0, -1);
    glVertex3f(-cab_width/5, 1 + cab_height + 1, -cab_depth/2)
    glVertex3f( cab_width/5, 1 + cab_height + 1, -cab_depth/2)
    glVertex3f( cab_width/5, 1 + cab_height,          -cab_depth/2)
    glVertex3f(-cab_width/5, 1 + cab_height,          -cab_depth/2)
    # left A-pillar
    glNormal3f(0, 0, -1);
    glVertex3f(-cab_width/2, 1 + cab_height + 1, -cab_depth/2)
    glVertex3f(-cab_width/2 + 0.1, 1 + cab_height + 1, -cab_depth/2)
    glVertex3f(-cab_width/2 + 0.1, 1 + cab_height, -cab_depth/2)
    glVertex3f(-cab_width/2, 1 + cab_height, -cab_depth/2)
    glNormal3f(-1, 0, 0);
    glVertex3f(-cab_width/2, 1 + cab_height + 1,  -cab_depth/2 + 0.5)
    glVertex3f(-cab_width/2, 1 + cab_height + 1, -cab_depth/2)
    glVertex3f(-cab_width/2, 1 + cab_height, -cab_depth/2)
    glVertex3f(-cab_width/2, 1 + cab_height, -cab_depth/2 + 0.5)
    
    # right B-pillar
    glNormal3f(0, 0, -1);
    glVertex3f(cab_width/2, 1 + cab_height + 1, -cab_depth/2)
    glVertex3f(cab_width/2 - 0.1, 1 + cab_height + 1, -cab_depth/2)
    glVertex3f(cab_width/2 - 0.1, 1 + cab_height, -cab_depth/2)
    glVertex3f(cab_width/2, 1 + cab_height, -cab_depth/2)    
    glNormal3f(1, 0, 0);
    glVertex3f( cab_width/2, 1 + cab_height + 1, -cab_depth/2 + 0.5)
    glVertex3f( cab_width/2, 1 + cab_height + 1,  -cab_depth/2)
    glVertex3f( cab_width/2, 1 + cab_height,           -cab_depth/2)
    glVertex3f( cab_width/2, 1 + cab_height,          -cab_depth/2 + 0.5)

    glEnd()

    # 繪製儀表板
    glColor3fv(DASHBOARD_COLOR)
    glDisable(GL_TEXTURE_2D) # 儀表板不用紋理
    glPushMatrix()
    glTranslatef(0, dash_pos_y, dash_pos_z)
    # 稍微傾斜一點方便觀看
    glRotatef(-15, 1, 0, 0)
#     draw_cube_centered(cab_width * 0.95, dash_depth, dash_height) # 畫儀表板方塊
    draw_cube(cab_width * 0.95, dash_depth, dash_height) # 畫儀表板方塊
    
    glPopMatrix() # 恢復儀表板變換

    # --- 繪製儀表和操作桿 (在儀表板表面) ---
    glDisable(GL_LIGHTING) # 儀表和指針通常不受光照影響，顏色固定
    glLineWidth(2.0)

    # 繪製速度表盤
    glColor3f(0.9, 0.9, 0.9) # 表盤背景色
    glPushMatrix()
    # 移動到儀表板表面，考慮傾斜
    glTranslatef(0, dash_pos_y, dash_pos_z)
    glRotatef(-15, 1, 0, 0)
    glTranslatef(speedo_center_x, speedo_center_y - dash_pos_y , speedo_center_z - dash_pos_z ) # 相對儀表板中心

    # 畫圓盤背景
    glBegin(GL_TRIANGLE_FAN)
    glVertex3f(0, 0, 0.01) # 中心點稍微突出
    for i in range(33): # 32 段 + 回到起點
        angle = math.radians(i * 360 / 32)
        glVertex3f(math.cos(angle) * speedo_radius, math.sin(angle) * speedo_radius, 0.01)
    glEnd()

    # 畫刻度
    glColor3f(0.1, 0.1, 0.1) # 刻度顏色
    glBegin(GL_LINES)
    for speed_kmh in range(0, int(tram.max_speed * 3.6) + 1, 10): # 每 10km/h 一個長刻度
        angle_rad = math.radians(90 - (speed_kmh / (tram.max_speed * 3.6)) * 180) # 假設 0 在頂部, 180度範圍
        if tram.max_speed == 0: angle_rad = math.radians(90)
        x1 = math.cos(angle_rad) * speedo_radius * 0.8
        y1 = math.sin(angle_rad) * speedo_radius * 0.8
        x2 = math.cos(angle_rad) * speedo_radius
        y2 = math.sin(angle_rad) * speedo_radius
        glVertex3f(x1, y1, 0.02)
        glVertex3f(x2, y2, 0.02)
    glEnd()

    # 繪製速度指針
    current_kmh = tram.get_speed_kmh()
    speed_ratio = current_kmh / (tram.max_speed * 3.6)
    if tram.max_speed == 0: speed_ratio = 0
    needle_angle_rad = math.radians(90 - speed_ratio * 180) # 90度是0km/h, -90度是最大速度

    glColor3fv(NEEDLE_COLOR)
    glBegin(GL_TRIANGLES)
    # 指針根部
    glVertex3f(0, 0, 0.03)
    # 指針尖端
    needle_x = math.cos(needle_angle_rad) * speedo_radius * 0.9
    needle_y = math.sin(needle_angle_rad) * speedo_radius * 0.9
    glVertex3f(needle_x, needle_y, 0.03)
    # 指針側面的一個點，使其有寬度
    side_angle = needle_angle_rad + math.pi / 2
    glVertex3f(math.cos(side_angle) * 0.01, math.sin(side_angle) * 0.01, 0.03)
    glEnd()

    glPopMatrix() # 恢復速度表變換


    # 繪製操作桿
    glColor3fv(LEVER_COLOR)
    glPushMatrix()
    # 移動到操作桿基座，考慮儀表板傾斜
    glTranslatef(0, dash_pos_y, dash_pos_z)
    glRotatef(-15, 1, 0, 0)
    glTranslatef(lever_base_x, lever_base_y - dash_pos_y, lever_base_z - dash_pos_z)

    # 計算操作桿角度
    control_state = tram.get_control_state() # -1 (煞車/後退), 0 (空檔), 1 (前進)
    lever_angle = control_state * lever_max_angle # 簡單線性映射

    glRotatef(lever_angle, 1, 0, 0) # 繞 X 軸傾斜 (向前/後)

    # 畫操作桿 (一個細長的方塊)
    lever_width = 0.05
    glBegin(GL_QUADS)
    # Front
    glNormal3f(0,0,1); glVertex3f(-lever_width/2, lever_length, lever_width/2); glVertex3f(lever_width/2, lever_length, lever_width/2); glVertex3f(lever_width/2, 0, lever_width/2); glVertex3f(-lever_width/2, 0, lever_width/2)
    # Back
    glNormal3f(0,0,-1); glVertex3f(-lever_width/2, 0, -lever_width/2); glVertex3f(lever_width/2, 0, -lever_width/2); glVertex3f(lever_width/2, lever_length, -lever_width/2); glVertex3f(-lever_width/2, lever_length, -lever_width/2)
    # Top
    glNormal3f(0,1,0); glVertex3f(-lever_width/2, lever_length, -lever_width/2); glVertex3f(lever_width/2, lever_length, -lever_width/2); glVertex3f(lever_width/2, lever_length, lever_width/2); glVertex3f(-lever_width/2, lever_length, lever_width/2)
    # Bottom
    glNormal3f(0,-1,0); glVertex3f(-lever_width/2, 0, lever_width/2); glVertex3f(lever_width/2, 0, lever_width/2); glVertex3f(lever_width/2, 0, -lever_width/2); glVertex3f(-lever_width/2, 0, -lever_width/2)
    # Left
    glNormal3f(-1,0,0); glVertex3f(-lever_width/2, lever_length, lever_width/2); glVertex3f(-lever_width/2, 0, lever_width/2); glVertex3f(-lever_width/2, 0, -lever_width/2); glVertex3f(-lever_width/2, lever_length, -lever_width/2)
    # Right
    glNormal3f(1,0,0); glVertex3f(lever_width/2, lever_length, -lever_width/2); glVertex3f(lever_width/2, 0, -lever_width/2); glVertex3f(lever_width/2, 0, lever_width/2); glVertex3f(lever_width/2, lever_length, lever_width/2)
    glEnd()

    glPopMatrix() # 恢復操作桿變換

    glEnable(GL_LIGHTING) # 恢復光照
    glEnable(GL_TEXTURE_2D) # 恢復紋理
    glPopMatrix() # 恢復電車世界變換
    
# @njit    
# def _world_to_map_coords(world_x, world_z, player_x, player_z, map_center_x, map_center_y, scale):
#     """內部輔助函數：將世界XZ坐標轉換為小地圖2D屏幕坐標"""
#     # 計算相對於玩家的偏移量
#     delta_x = world_x - player_x
#     delta_z = world_z - player_z # 注意：通常地圖Y對應世界Z
# 
#     # 應用縮放並計算在小地圖上的坐標
#     # 假設地圖 X+ 對應世界 X+, 地圖 Y+ 對應世界 Z+
#     # 這裡改成map_center_x - delta_x * scale 不然minimap會左右顛倒
#     map_x = map_center_x - delta_x * scale
#     map_y = map_center_y + delta_z * scale
# 
#     return map_x, map_y

# 這裡引數必須排列成rx_deg, rz_deg, ry_deg 才可以讓旋轉正確
@njit
def _rotate_point_3d(point, rx_deg, rz_deg, ry_deg):
    """Applies rotations (in degrees) to a 3D point."""
    rad_x = math.radians(rx_deg)
    rad_y = math.radians(ry_deg)
    rad_z = math.radians(rz_deg)
    cos_x, sin_x = math.cos(rad_x), math.sin(rad_x)
    cos_y, sin_y = math.cos(rad_y), math.sin(rad_y)
    cos_z, sin_z = math.cos(rad_z), math.sin(rad_z)

    x, y, z = point

    # Apply Z rotation
    x1 = x * cos_z - y * sin_z
    y1 = x * sin_z + y * cos_z
    z1 = z

    # Apply Y rotation
    x2 = x1 * cos_y + z1 * sin_y
    y2 = y1
    z2 = -x1 * sin_y + z1 * cos_y

    # Apply X rotation
    x3 = x2
    y3 = y2 * cos_x - z2 * sin_x
    z3 = y2 * sin_x + z2 * cos_x

    return np.array([x3, y3, z3])




# --- 新增：繪製文字紋理的輔助函數 ---
def _draw_text_texture(text_surface, x, y):
    """將 Pygame Surface 繪製為 OpenGL 紋理"""
    text_width, text_height = text_surface.get_size()
    texture_data = pygame.image.tostring(text_surface, "RGBA", True)

    tex_id = glGenTextures(1)
    glBindTexture(GL_TEXTURE_2D, tex_id)
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR)
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR)
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_CLAMP_TO_EDGE)
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_CLAMP_TO_EDGE)
    glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA, text_width, text_height, 0,
                 GL_RGBA, GL_UNSIGNED_BYTE, texture_data)

    glEnable(GL_TEXTURE_2D)
    glColor4f(1.0, 1.0, 1.0, 1.0) # 確保紋理顏色不被污染
    glBegin(GL_QUADS)
    glTexCoord2f(0, 0); glVertex2f(x, y)
    glTexCoord2f(1, 0); glVertex2f(x + text_width, y)
    glTexCoord2f(1, 1); glVertex2f(x + text_width, y + text_height)
    glTexCoord2f(0, 1); glVertex2f(x, y + text_height)
    glEnd()

    glBindTexture(GL_TEXTURE_2D, 0)
    glDeleteTextures(1, [tex_id])
    
def draw_coordinates(tram_position, screen_width, screen_height):
    """在 HUD 左上角繪製電車坐標"""
    global hud_display_font
    if not hud_display_font: # 如果字體未成功載入，則不繪製
        return

    # --- 格式化坐標文字 ---
    coord_text = f"X: {tram_position[0]:.2f}  Y: {tram_position[1]:.2f}  Z: {tram_position[2]:.2f}"

    # --- 渲染文字到 Pygame Surface ---
    try:
        text_surface = hud_display_font.render(coord_text, True, COORD_TEXT_COLOR) # True for anti-aliasing
        text_width, text_height = text_surface.get_size()
    except Exception as e:
        print(f"渲染 HUD 文字時出錯: {e}")
        return # 避免後續錯誤

    # --- 切換到 2D 正交投影 ---
    glMatrixMode(GL_PROJECTION)
    glPushMatrix()
    glLoadIdentity()
    gluOrtho2D(0, screen_width, 0, screen_height) # Y 軸從底部到頂部

    glMatrixMode(GL_MODELVIEW)
    glPushMatrix()
    glLoadIdentity()

    # --- 關閉/設置 2D 繪圖所需狀態 ---
    glPushAttrib(GL_ENABLE_BIT | GL_TEXTURE_BIT | GL_COLOR_BUFFER_BIT) # 保存狀態
    glDisable(GL_DEPTH_TEST)
    glDisable(GL_LIGHTING)
    glEnable(GL_TEXTURE_2D) # 需要紋理來繪製文字
    glEnable(GL_BLEND)      # 啟用混合以獲得平滑字體邊緣
    glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)

    # --- 將 Pygame Surface 轉換為 OpenGL 紋理 ---
    texture_data = pygame.image.tostring(text_surface, "RGBA", True) # 翻轉 Y 軸

    # --- 創建並綁定 OpenGL 紋理 ---
    tex_id = glGenTextures(1)
    glBindTexture(GL_TEXTURE_2D, tex_id)
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR)
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR)
    # 使用 GL_CLAMP_TO_EDGE 避免邊緣偽影
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_CLAMP_TO_EDGE)
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_CLAMP_TO_EDGE)

    # --- 上傳紋理數據 ---
    glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA, text_width, text_height, 0,
                 GL_RGBA, GL_UNSIGNED_BYTE, texture_data)

    # --- 計算繪製位置 (左上角) ---
    draw_x = COORD_PADDING_X
    # gluOrtho2D 的 Y=0 在底部，所以要從屏幕高度減去
    draw_y = screen_height - COORD_PADDING_Y - text_height

    # --- 繪製帶有文字紋理的四邊形 ---
    glColor4f(1.0, 1.0, 1.0, 1.0) # 使用白色，紋理顏色將覆蓋它
    glBegin(GL_QUADS)
    glTexCoord2f(0, 0); glVertex2f(draw_x, draw_y) # 左下
    glTexCoord2f(1, 0); glVertex2f(draw_x + text_width, draw_y) # 右下
    glTexCoord2f(1, 1); glVertex2f(draw_x + text_width, draw_y + text_height) # 右上
    glTexCoord2f(0, 1); glVertex2f(draw_x, draw_y + text_height) # 左上
    glEnd()

    # --- 清理紋理 ---
    glBindTexture(GL_TEXTURE_2D, 0) # 解除綁定
    glDeleteTextures(1, [tex_id])   # 刪除紋理，避免洩漏

    # --- 恢復 OpenGL 狀態 ---
    glPopAttrib() # 恢復 Enable/Texture/Color Blend 狀態

    # --- 恢復矩陣 ---
    glMatrixMode(GL_PROJECTION)
    glPopMatrix()
    glMatrixMode(GL_MODELVIEW)
    glPopMatrix()
    
def test_draw_cube_centered(width, depth, height, texture_id=None):
    """繪製一個以原點 (0,0,0) 為中心的立方體"""
    if texture_id is not None:
        glBindTexture(GL_TEXTURE_2D, texture_id)
        glEnable(GL_TEXTURE_2D)
    else:
        glDisable(GL_TEXTURE_2D)

    w2, d2, h2 = width / 2.0, depth / 2.0, height / 2.0 # 半尺寸

    # glColor3f(0.8, 0.8, 0.8) # 顏色可以在外部設置

    glBegin(GL_QUADS)
    # Bottom face (Y=-h2)
    glNormal3f(0, -1, 0)
    glTexCoord2f(1, 1); glVertex3f( w2, -h2, -d2)
    glTexCoord2f(0, 1); glVertex3f(-w2, -h2, -d2)
    glTexCoord2f(0, 0); glVertex3f(-w2, -h2,  d2)
    glTexCoord2f(1, 0); glVertex3f( w2, -h2,  d2)
    # Top face (Y=h2)
    glNormal3f(0, 1, 0)
    glTexCoord2f(1, 1); glVertex3f( w2, h2,  d2)
    glTexCoord2f(0, 1); glVertex3f(-w2, h2,  d2)
    glTexCoord2f(0, 0); glVertex3f(-w2, h2, -d2)
    glTexCoord2f(1, 0); glVertex3f( w2, h2, -d2)
    # Front face (Z=d2)
    glNormal3f(0, 0, 1)
    glTexCoord2f(1, 1); glVertex3f( w2,  h2, d2)
    glTexCoord2f(0, 1); glVertex3f(-w2,  h2, d2)
    glTexCoord2f(0, 0); glVertex3f(-w2, -h2, d2)
    glTexCoord2f(1, 0); glVertex3f( w2, -h2, d2)
    # Back face (Z=-d2)
    glNormal3f(0, 0, -1)
    glTexCoord2f(1, 1); glVertex3f( w2, -h2, -d2)
    glTexCoord2f(0, 1); glVertex3f(-w2, -h2, -d2)
    glTexCoord2f(0, 0); glVertex3f(-w2,  h2, -d2)
    glTexCoord2f(1, 0); glVertex3f( w2,  h2, -d2)
    # Left face (X=-w2)
    glNormal3f(-1, 0, 0)
    glTexCoord2f(1, 1); glVertex3f(-w2,  h2,  d2)
    glTexCoord2f(0, 1); glVertex3f(-w2,  h2, -d2)
    glTexCoord2f(0, 0); glVertex3f(-w2, -h2, -d2)
    glTexCoord2f(1, 0); glVertex3f(-w2, -h2,  d2)
    # Right face (X=w2)
    glNormal3f(1, 0, 0)
    glTexCoord2f(1, 1); glVertex3f( w2,  h2, -d2)
    glTexCoord2f(0, 1); glVertex3f( w2,  h2,  d2)
    glTexCoord2f(0, 0); glVertex3f( w2, -h2,  d2)
    glTexCoord2f(1, 0); glVertex3f( w2, -h2, -d2)
    glEnd()

    glBindTexture(GL_TEXTURE_2D, 0)
    glEnable(GL_TEXTURE_2D) # 恢復默認啟用狀態

def test_draw_cylinder_y_up_centered(radius, height, texture_id=None, slices=CYLINDER_SLICES):
    """繪製一個以原點(0,0,0)為中心，沿 Y 軸的圓柱體"""
    if texture_id is not None:
         glBindTexture(GL_TEXTURE_2D, texture_id)
         glEnable(GL_TEXTURE_2D)
    else:
         glDisable(GL_TEXTURE_2D)

    quadric = gluNewQuadric()
    gluQuadricTexture(quadric, GL_TRUE)
    gluQuadricNormals(quadric, GLU_SMOOTH) # 使用平滑法線

    half_height = height / 2.0

    glPushMatrix()
    # GLU 圓柱體默認沿 Z 軸繪製，我們先將其旋轉使其沿 Y 軸
    glRotatef(-90, 1, 0, 0)
    # GLU 圓柱體底部在 z=0，頂部在 z=height。我們需要將其中心移到原點。
    # 因此，沿其自身 Z 軸（旋轉後的 Y 軸方向）平移 -half_height
    glTranslatef(0, 0, -half_height)

    # 繪製圓柱體側面 (現在從 z=-h/2 到 z=h/2 in rotated frame)
    gluCylinder(quadric, radius, radius, height, slices, 1)

    # 繪製底部圓盤 (在 z=-h/2 處)
    # GLU Disk 在 XY 平面繪製。由於我們繞 X 軸旋轉了 -90 度，
    # 原來的 XY 平面現在是這個坐標系的 XZ 平面，正好是我們需要的方向。
    gluDisk(quadric, 0, radius, slices, 1) # 在當前原點 (z=-h/2) 繪製

    # 繪製頂部圓盤 (在 z=+h/2 處)
    glPushMatrix()
    glTranslatef(0, 0, height) # 沿圓柱體軸移動到頂部 z=+h/2
    gluDisk(quadric, 0, radius, slices, 1) # 在頂部繪製
    glPopMatrix()

    glPopMatrix() # 恢復到應用旋轉和平移之前的狀態

    gluDeleteQuadric(quadric)
    glBindTexture(GL_TEXTURE_2D, 0)
    glEnable(GL_TEXTURE_2D) # 恢復    
    
# Consider njit for this if performance critical and only uses basic math/numpy
# @njit
def _world_to_map_coords_adapted(world_x, world_z, view_center_x, view_center_z, map_widget_center_x, map_widget_center_y, scale):
    """
    Internal helper: Converts world XZ to map widget coordinates.
    Assumes map X+ = world X+, map Y+ = world Z+.
    """
    delta_x = world_x - view_center_x
    delta_z = world_z - view_center_z
    # 軌道左右顛倒 因此修改成減號 
    map_x = map_widget_center_x - delta_x * scale
    map_y = map_widget_center_y + delta_z * scale
    return map_x, map_y

def _render_map_view(scene, view_center_x, view_center_z, view_range, target_widget_rect, draw_grid_labels=True, background_color=None):
    """
    Internal Helper: Renders the core content of a map view (track, objects, grid).
    This function assumes necessary OpenGL projection and states are set by the caller.
    It operates within the coordinate system defined by target_widget_rect.

    Args:
        scene: The Scene object.
        view_center_x, view_center_z: World coordinates to center the view on.
        view_range: World units defining the width/height of the view.
        target_widget_rect: (left, bottom, width, height) of the target drawing area in widget coordinates.
        draw_grid_labels: Whether to attempt drawing grid coordinate labels.
        background_color: The background color for this view.
    """
    widget_left, widget_bottom, widget_width, widget_height = target_widget_rect
    widget_center_x = widget_left + widget_width / 2.0
    widget_center_y = widget_bottom + widget_height / 2.0

    if view_range <= MINIMAP_MIN_RANGE / 10.0: view_range = MINIMAP_MIN_RANGE # Prevent extreme zoom / division issues
    # Calculate scale based on the available widget space and desired world range
    # Use the smaller dimension to ensure the full range fits
    scale = min(widget_width, widget_height) / view_range

    # --- World View Boundaries ---
    # Note: The actual visible range might be larger in one dimension if widget isn't square
    world_half_range_x = (widget_width / scale) / 2.0
    world_half_range_z = (widget_height / scale) / 2.0
    world_view_left = view_center_x - world_half_range_x
    world_view_right = view_center_x + world_half_range_x
    world_view_bottom_z = view_center_z - world_half_range_z
    world_view_top_z = view_center_z + world_half_range_z

    # --- Draw Background ---
    if background_color is not None:
#         glDisable(GL_TEXTURE_2D) # Ensure texturing is off unless specifically drawing texture
#         glColor4fv(background_color)
#         glBegin(GL_QUADS)
#         glVertex2f(widget_left, widget_bottom); glVertex2f(widget_left + widget_width, widget_bottom)
#         glVertex2f(widget_left + widget_width, widget_bottom + widget_height); glVertex2f(widget_left, widget_bottom + widget_height)
#         glEnd()
        pass
    
    # --- Draw Grid Lines ---
    if view_range < DEFAULT_MINIMAP_RANGE * 1.5: # Only draw grid when reasonably zoomed
        glColor4fv(MINIMAP_GRID_COLOR)
        glLineWidth(1.0)
        start_grid_x = math.floor(world_view_left / MINIMAP_GRID_SCALE) * MINIMAP_GRID_SCALE
        start_grid_z = math.floor(world_view_bottom_z / MINIMAP_GRID_SCALE) * MINIMAP_GRID_SCALE

        # Vertical lines
        current_grid_x = start_grid_x
        while current_grid_x <= world_view_right:
            map_x, _ = _world_to_map_coords_adapted(current_grid_x, view_center_z, view_center_x, view_center_z, widget_center_x, widget_center_y, scale)
            # Draw line slightly beyond boundaries to avoid gaps at edges
            glBegin(GL_LINES); glVertex2f(map_x, widget_bottom - 5); glVertex2f(map_x, widget_bottom + widget_height + 5); glEnd()
            current_grid_x += MINIMAP_GRID_SCALE
        # Horizontal lines
        current_grid_z = start_grid_z
        while current_grid_z <= world_view_top_z:
            _, map_y = _world_to_map_coords_adapted(view_center_x, current_grid_z, view_center_x, view_center_z, widget_center_x, widget_center_y, scale)
            glBegin(GL_LINES); glVertex2f(widget_left - 5, map_y); glVertex2f(widget_left + widget_width + 5, map_y); glEnd()
            current_grid_z += MINIMAP_GRID_SCALE

    # --- Draw Track ---
    if scene.track:
        glColor3fv(MINIMAP_TRACK_COLOR)
        glLineWidth(2.0)        
        for segment in scene.track.segments:
            if not segment.points or len(segment.points) < 2: continue
            
            #標記線段開頭
            map_x, map_y = _world_to_map_coords_adapted(segment.points[0][0], segment.points[0][2],
                                                view_center_x, view_center_z,
                                                widget_center_x, widget_center_y, scale)
            glPointSize(8)
            glBegin(GL_POINTS)
            glColor3fv(MINIMAP_TRACK_COLOR)
            glVertex2f(map_x, map_y)  # 
            glEnd()        
            
            glBegin(GL_LINE_STRIP)
            for point_world in segment.points:
                map_x, map_y = _world_to_map_coords_adapted(point_world[0], point_world[2],
                                                            view_center_x, view_center_z,
                                                            widget_center_x, widget_center_y, scale)
                glVertex2f(map_x, map_y)
            glEnd()

    # --- Draw Buildings (as Rectangles) ---
    glColor3fv(MINIMAP_BUILDING_COLOR)
    glLineWidth(1.0)
    for bldg in scene.buildings:
        b_type, wx, wy, wz, rx, ry, rz, ww, wd, wh, tid, uoff, voff, tang, uvmode, usca, vsca, tex_file = bldg
        half_w, half_d = ww / 2.0, wd / 2.0
        # Local corners (relative to object center wx,wy,wz) on XZ plane
        corners_local = [ np.array([-half_w, 0, -half_d]), np.array([ half_w, 0, -half_d]),
                          np.array([ half_w, 0,  half_d]), np.array([-half_w, 0,  half_d]) ]
        # Only apply world Y rotation for top-down minimap
        # 修改成 -ry 因為物件左右顛倒
        angle_y_rad = math.radians(-ry)
        cos_y, sin_y = math.cos(angle_y_rad), math.sin(angle_y_rad)
        map_coords = []
        for corner in corners_local:
            # Rotate around Y axis
            rotated_x = corner[0] * cos_y - corner[2] * sin_y
            rotated_z = corner[0] * sin_y + corner[2] * cos_y
            # Add world position
            world_corner_x = wx + rotated_x
            world_corner_z = wz + rotated_z
            # Convert to map coords
            map_x, map_y = _world_to_map_coords_adapted(world_corner_x, world_corner_z, view_center_x, view_center_z, widget_center_x, widget_center_y, scale)
            map_coords.append((map_x, map_y))
        # Draw the loop
        glBegin(GL_LINE_LOOP)
        for mx, my in map_coords: glVertex2f(mx, my)
        glEnd()

    # --- Draw Cylinders (Circle or Rotated Box) ---
    glColor3fv(MINIMAP_CYLINDER_COLOR)
    num_circle_segments = 12 # Fewer segments for minimap circles
    for cyl in scene.cylinders:
        c_type, wx, wy, wz, rx, ry, rz, cr, ch, tid, uoff, voff, tang, uvmode, usca, vsca, tex_file = cyl
        # 修改 檢查傾斜軸向為 rx ry
        is_tilted = abs(rx) > 0.1 or abs(ry) > 0.1 # 

        if is_tilted:
            # --- Draw Tilted Cylinder as a Rotated Bounding Box ---
            # Find major axis projection on XZ plane
            # Simplified: Use world Y rotation (ry) for box angle, size based on max(2*r, h) projected?
            # More accurate: calculate rotated endpoints, project onto XZ.
            # 修改為 [0, -ch / 2.0, 0]
            p_bottom_local = np.array([0, -ch / 2.0, 0]) # Assume cylinder is initially Z-aligned if using GLU standard
            p_top_local = np.array([0, ch / 2.0, 0])
            # Apply rotations (careful with order - e.g., Y, X, Z)
            # Need a consistent rotation function like _rotate_point_3d_numpy
            # For simplicity here, let's approximate using ry for angle and fixed size
            # 修改增加以下 用來旋轉傾斜的圓柱投影方塊
            p_bottom_rotated_rel = _rotate_point_3d(p_bottom_local, rx, ry, rz)
            p_top_rotated_rel = _rotate_point_3d(p_top_local, rx, ry, rz)
            p_bottom_world = np.array([wx, wy, wz]) + p_bottom_rotated_rel
            p_top_world = np.array([wx, wy, wz]) + p_top_rotated_rel
            p_bottom_xz = np.array([p_bottom_world[0], p_bottom_world[2]])
            p_top_xz = np.array([p_top_world[0], p_top_world[2]])
            axis_proj_xz = p_top_xz - p_bottom_xz
            length_proj = np.linalg.norm(axis_proj_xz)
            angle_map_rad = math.arctan2(axis_proj_xz[1], axis_proj_xz[0]) if length_proj > 1e-6 else 0
            
            map_center_x, map_center_y = _world_to_map_coords_adapted(wx, wz, view_center_x, view_center_z, widget_center_x, widget_center_y, scale)

            # Approximate projected size - crude, needs better projection logic if accuracy is vital
            proj_len = max(ch, 2*cr) * scale # Max dimension scaled
            proj_wid = min(ch, 2*cr) * scale # Min dimension scaled

            glPushMatrix()
            glTranslatef(map_center_x, map_center_y, 0)
            glRotatef(math.degrees(angle_map_rad), 0, 0, 1) # Rotate on screen Z
            glBegin(GL_LINE_LOOP)
            glVertex2f(-proj_len / 2, -proj_wid / 2)
            glVertex2f( proj_len / 2, -proj_wid / 2)
            glVertex2f( proj_len / 2,  proj_wid / 2)
            glVertex2f(-proj_len / 2,  proj_wid / 2)
            glEnd()
            glPopMatrix()
        else:
            # --- Draw Non-Tilted Cylinder as Circle ---
            center_map_x, center_map_y = _world_to_map_coords_adapted(wx, wz, view_center_x, view_center_z, widget_center_x, widget_center_y, scale)
            radius_map = cr * scale
            # Basic culling (optional, scissor test handles it)
            if widget_left - radius_map <= center_map_x <= widget_left + widget_width + radius_map and \
               widget_bottom - radius_map <= center_map_y <= widget_bottom + widget_height + radius_map:
                glBegin(GL_LINE_LOOP)
                for i in range(num_circle_segments):
                    angle = 2 * math.pi * i / num_circle_segments
                    glVertex2f(center_map_x + radius_map * math.cos(angle), center_map_y + radius_map * math.sin(angle))
                glEnd()

    # --- Draw Trees (as Points) ---
    glColor3fv(MINIMAP_TREE_COLOR)
    # Adjust point size based on zoom maybe?
    min_point_size, max_point_size = 2.0, 5.0
    zoom_ratio = max(0, min(1, (DEFAULT_MINIMAP_RANGE - view_range) / (DEFAULT_MINIMAP_RANGE - MINIMAP_MIN_RANGE))) if (DEFAULT_MINIMAP_RANGE - MINIMAP_MIN_RANGE) != 0 else 0
    point_size = min_point_size + (max_point_size - min_point_size) * zoom_ratio
    glPointSize(max(1.0, point_size)) # Ensure point size is at least 1
    glBegin(GL_POINTS)
    for tree in scene.trees:
        tx, ty, tz, th = tree
        map_x, map_y = _world_to_map_coords_adapted(tx, tz, view_center_x, view_center_z, widget_center_x, widget_center_y, scale)
        # Basic culling
        if widget_left <= map_x <= widget_left + widget_width and widget_bottom <= map_y <= widget_bottom + widget_height:
            glVertex2f(map_x, map_y)
    glEnd()
    glPointSize(1.0) # Reset point size

    # --- Draw Grid Labels ---
    # Labels are drawn outside the main map area typically, so handled after scissor usually
    if draw_grid_labels and grid_label_font and view_range < DEFAULT_MINIMAP_RANGE * 1.2:
        # This needs to be called *after* glDisable(GL_SCISSOR_TEST) by the caller
        # We'll add a flag or structure to return label info, or the caller handles labels
        pass # Label drawing logic moved to caller (draw_minimap or editor widget)

# --- ============================================= ---
# ---       SIMULATOR's draw_minimap Function       ---
# --- ============================================= ---

def draw_minimap(scene, tram, screen_width, screen_height):
    """
    Draws the HUD minimap for the SIMULATOR.
    Sets up projection, viewport, calls _render_map_view, and adds player marker.
    """
    global current_minimap_range, minimap_bg_texture_id # Use simulator's zoom and texture

    # --- Calculate Map Position on Screen (Simulator specific) ---
    map_draw_size = MINIMAP_SIZE
    map_left = screen_width - map_draw_size - MINIMAP_PADDING
    map_right = screen_width - MINIMAP_PADDING
    map_bottom = screen_height - map_draw_size - MINIMAP_PADDING # Y=0 screen bottom
    map_top = screen_height - MINIMAP_PADDING
    map_rect = (map_left, map_bottom, map_draw_size, map_draw_size)
    map_center_x = map_left + map_draw_size / 2.0
    map_center_y = map_bottom + map_draw_size / 2.0

    # --- Player Info ---
    player_x = tram.position[0]
    player_z = tram.position[2]
    view_range = current_minimap_range # Use the simulator's current zoom level

    # --- Setup 2D Projection for the whole screen ---
    glMatrixMode(GL_PROJECTION); glPushMatrix(); glLoadIdentity()
    # Use screen coordinates directly
    gluOrtho2D(0, screen_width, 0, screen_height)
    glMatrixMode(GL_MODELVIEW); glPushMatrix(); glLoadIdentity()

    # --- Save OpenGL State ---
    glPushAttrib(GL_ENABLE_BIT | GL_COLOR_BUFFER_BIT | GL_VIEWPORT_BIT | GL_SCISSOR_BIT | GL_LINE_BIT | GL_POINT_BIT | GL_TEXTURE_BIT)
    glDisable(GL_DEPTH_TEST)
    glDisable(GL_LIGHTING)
    glEnable(GL_BLEND)
    glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)


    # --- Set Viewport and Scissor for Minimap Area ---
    glViewport(int(map_left), int(map_bottom), int(map_draw_size), int(map_draw_size))
    glEnable(GL_SCISSOR_TEST)
    glScissor(int(map_left), int(map_bottom), int(map_draw_size), int(map_draw_size))

    # --- Choose Background: Texture or Fallback Color ---
    bg_color = MINIMAP_BG_FALLBACK_COLOR
    use_texture = (minimap_bg_texture_id is not None and
                   minimap_bg_image_width_px > 0 and
                   minimap_bg_image_height_px > 0 and
                   scene.map_filename is not None and
                   abs(scene.map_world_scale) > 1e-6)

    if use_texture:
         # --- Draw Textured Background (Simulator specific logic) ---
         glEnable(GL_TEXTURE_2D)
         glBindTexture(GL_TEXTURE_2D, minimap_bg_texture_id)
         glColor4f(1.0, 1.0, 1.0, 1.0) # White base for texture

         # Calculate texture coordinates based on player position and map settings
         image_world_width = minimap_bg_image_width_px * scene.map_world_scale
         image_world_height = minimap_bg_image_height_px * scene.map_world_scale
         img_world_x_min = scene.map_world_center_x - image_world_width / 2.0
         img_world_z_min = scene.map_world_center_z - image_world_height / 2.0
         # 以下兩行是修改添加過的 因為要讓圖片跟著同方向移動 見下方 u_min u_max的計算
         img_world_x_max = scene.map_world_center_x + image_world_width / 2.0
         img_world_z_max = scene.map_world_center_z + image_world_height / 2.0

         # Calculate world boundaries currently visible in the minimap square
         world_half = view_range / 2.0
         view_l, view_r = player_x - world_half, player_x + world_half
         view_b, view_t = player_z - world_half, player_z + world_half # Z maps to V

         # Calculate UVs
         if abs(image_world_width) < 1e-6 or abs(image_world_height) < 1e-6:
             u_min, u_max, v_min, v_max = 0.0, 1.0, 0.0, 1.0 # Fallback
         else:
             # Correct calculation: map world view coords to texture coords [0,1]
             # 以下兩行是修改過的 改成 +img_world_x_max 因為要讓圖片跟著同方向移動
             u_min = (-view_l + img_world_x_max) / image_world_width
             u_max = (-view_r + img_world_x_max) / image_world_width
             v_min = (view_b - img_world_z_min) / image_world_height # V=0 at bottom
             v_max = (view_t - img_world_z_min) / image_world_height # V=1 at top

         # Draw textured Quad for the minimap background
         # 修改以下 glTexCoord2f 內的u_max u_min  因為要把圖片左右相反
         glBegin(GL_QUADS)
         glTexCoord2f(u_max, v_min); glVertex2f(map_left, map_bottom)   # Bottom Left
         glTexCoord2f(u_min, v_min); glVertex2f(map_right, map_bottom)  # Bottom Right
         glTexCoord2f(u_min, v_max); glVertex2f(map_right, map_top)     # Top Right
         glTexCoord2f(u_max, v_max); glVertex2f(map_left, map_top)      # Top Left
         glEnd()
         glBindTexture(GL_TEXTURE_2D, 0)
         glDisable(GL_TEXTURE_2D)
         bg_color_to_use = None # IMPORTANT: Set to None if texture was drawn
         
    # --- Call the core rendering function ---
    # Pass player position as view center, simulator's zoom, and map rect
    _render_map_view(scene, player_x, player_z, view_range, map_rect,
                     draw_grid_labels=False, # Labels drawn outside scissor area later
                     background_color=bg_color_to_use) # Pass fallback if texture failed/off

    # --- Draw Player Marker (Simulator specific) ---
    glDisable(GL_TEXTURE_2D) # Marker is not textured
    glColor3fv(MINIMAP_PLAYER_COLOR)
    # Calculate angle from +X axis (counter-clockwise positive)
    # forward_vector_xz is (x, z)
    # 修改加負號 玩家方向顛倒
    player_angle_rad = -math.arctan2(tram.forward_vector_xz[1], tram.forward_vector_xz[0])

    # Triangle points relative to map center
    tip_angle = player_angle_rad - math.pi # Pointing forward
    left_angle = player_angle_rad - math.pi * 0.75 # Back left (~135 deg)
    right_angle = player_angle_rad + math.pi * 0.75 # Back right (~-135 deg)

    tip_x = map_center_x + math.cos(tip_angle) * MINIMAP_PLAYER_SIZE
    tip_y = map_center_y + math.sin(tip_angle) * MINIMAP_PLAYER_SIZE # sin(angle) corresponds to Z offset
    left_x = map_center_x + math.cos(left_angle) * MINIMAP_PLAYER_SIZE * 0.7
    left_y = map_center_y + math.sin(left_angle) * MINIMAP_PLAYER_SIZE * 0.7
    right_x = map_center_x + math.cos(right_angle) * MINIMAP_PLAYER_SIZE * 0.7
    right_y = map_center_y + math.sin(right_angle) * MINIMAP_PLAYER_SIZE * 0.7

    glBegin(GL_TRIANGLES)
    glVertex2f(tip_x, tip_y)
    glVertex2f(left_x, left_y)
    glVertex2f(right_x, right_y)
    glEnd()

    # --- Disable Scissor to Draw Labels Outside Map Area ---
    glDisable(GL_SCISSOR_TEST)

    # --- Draw Grid Labels (If enabled and font available) ---
    show_labels = grid_label_font and view_range < DEFAULT_MINIMAP_RANGE * 1.2
    if show_labels:
        # Calculate visible world boundaries again for label placement
        world_half_range_x = (map_draw_size / (min(map_draw_size, map_draw_size) / view_range)) / 2.0
        world_half_range_z = world_half_range_x # Assume square aspect for labels
        world_view_left = player_x - world_half_range_x
        world_view_right = player_x + world_half_range_x
        world_view_bottom_z = player_z - world_half_range_z
        world_view_top_z = player_z + world_half_range_z

        scale = min(map_draw_size, map_draw_size) / view_range # Recalculate scale used

        start_grid_x = math.floor(world_view_left / MINIMAP_GRID_SCALE) * MINIMAP_GRID_SCALE
        start_grid_z = math.floor(world_view_bottom_z / MINIMAP_GRID_SCALE) * MINIMAP_GRID_SCALE

        # Draw X labels below map
        current_grid_x = start_grid_x
        while current_grid_x <= world_view_right:
            map_x, _ = _world_to_map_coords_adapted(current_grid_x, player_z, player_x, player_z, map_center_x, map_center_y, scale)
            if map_left <= map_x <= map_right:
                label_text = f"{current_grid_x:.0f}"
                try:
                    text_surface = grid_label_font.render(label_text, True, MINIMAP_GRID_LABEL_COLOR)
                    draw_label_x = map_x - text_surface.get_width() / 2
                    draw_label_y = map_bottom - MINIMAP_GRID_LABEL_OFFSET - text_surface.get_height()
                    _draw_text_texture(text_surface, draw_label_x, draw_label_y)
                except Exception as e: print(f"渲染 X 標籤時出錯: {e}")
            current_grid_x += MINIMAP_GRID_SCALE

        # Draw Z labels left of map
        current_grid_z = start_grid_z
        while current_grid_z <= world_view_top_z:
            _, map_y = _world_to_map_coords_adapted(player_x, current_grid_z, player_x, player_z, map_center_x, map_center_y, scale)
            if map_bottom <= map_y <= map_top:
                label_text = f"{current_grid_z:.0f}"
                try:
                    text_surface = grid_label_font.render(label_text, True, MINIMAP_GRID_LABEL_COLOR)
                    draw_label_x = map_left - MINIMAP_GRID_LABEL_OFFSET - text_surface.get_width()
                    draw_label_y = map_y - text_surface.get_height() / 2
                    _draw_text_texture(text_surface, draw_label_x, draw_label_y)
                except Exception as e: print(f"渲染 Z 標籤時出錯: {e}")
            current_grid_z += MINIMAP_GRID_SCALE

    # --- Restore OpenGL State ---
    glPopAttrib() # Restore saved states

    # --- Restore Matrices ---
    glMatrixMode(GL_PROJECTION); glPopMatrix()
    glMatrixMode(GL_MODELVIEW); glPopMatrix()