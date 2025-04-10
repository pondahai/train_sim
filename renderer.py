# renderer.py
from OpenGL.GL import *
from OpenGL.GLU import *
import numpy as np
import math
from track import TRACK_WIDTH, BALLAST_WIDTH, BALLAST_HEIGHT # 引入軌道寬度等常數
import texture_loader # 假設紋理載入器可用
import pygame # <-- 新增：導入 Pygame
import os

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
MINIMAP_SIZE = 200  # 小地圖的像素大小 (正方形)
MINIMAP_PADDING = 10 # 離螢幕邊緣的距離
# MINIMAP_RANGE = 300.0 # 小地圖顯示的世界單位範圍 (以此距離為半徑的正方形區域)
DEFAULT_MINIMAP_RANGE = 300.0 # 小地圖預設顯示的世界單位範圍
MINIMAP_MIN_RANGE = 50.0      # <-- 新增：最小縮放範圍 (放大極限)
MINIMAP_MAX_RANGE = 1000.0    # <-- 新增：最大縮放範圍 (縮小極限)
MINIMAP_ZOOM_FACTOR = 1.1     # <-- 新增：每次縮放的比例因子
MINIMAP_BG_FALLBACK_COLOR = (0.2, 0.2, 0.2, 0.7) # Use if no map image specified or fails to load
MINIMAP_BG_COLOR = (0.2, 0.2, 0.2, 0.7) # 背景顏色 (RGBA)
MINIMAP_TRACK_COLOR = (1.0, 0.0, 0.0) # 軌道顏色 ()
MINIMAP_BUILDING_COLOR = (0.6, 0.4, 0.2) # 建築顏色 (棕色)
MINIMAP_CYLINDER_COLOR = (0.6, 0.4, 0.2) # Use same color for cylinders for now
MINIMAP_TILTED_CYLINDER_BOX_SIZE_FACTOR = 1.0 # Factor to scale the tilted box size (relative to max(radius, height/2))
MINIMAP_TREE_COLOR = (0.1, 0.8, 0.1) # 樹木顏色 (綠色)
MINIMAP_PLAYER_COLOR = (1.0, 0.0, 0.0) # 玩家顏色 (紅色)
MINIMAP_PLAYER_SIZE = 5 # 玩家標記的大小 (像素)
# --- 新增：網格線參數 ---
MINIMAP_GRID_SCALE = 50.0 # 世界單位中每格的大小
MINIMAP_GRID_COLOR = (1.0, 1.0, 1.0, 0.3) # 網格線顏色 (淡白色)
MINIMAP_GRID_LABEL_COLOR = (255, 255, 255, 180) # 網格標籤顏色 (稍亮的白色)
MINIMAP_GRID_LABEL_FONT_SIZE = 12 # 網格標籤字體大小
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
    """繪製軌道和道碴"""
    glDisable(GL_TEXTURE_2D) # 軌道和道碴不用紋理

    half_track_width = TRACK_WIDTH / 2.0
    half_ballast_width = BALLAST_WIDTH / 2.0

    for segment in track_obj.segments:
        if not segment.points or len(segment.points) < 2:
            continue

        # 繪製道碴 (使用 Triangle Strip 提高效率)
        glColor3fv(BALLAST_COLOR)
        glBegin(GL_TRIANGLE_STRIP)
        for i in range(len(segment.points)):
            pos = segment.points[i]
            orient_xz = segment.orientations[i]
            # 計算垂直於軌道的向量 (right vector)
            right_vec_xz = np.array([-orient_xz[1], 0, orient_xz[0]]) # Assumes orient_xz is normalized

            # 在點 pos 處計算左右道碴點 (高度基於 pos[1])
            p_ballast_left = pos + right_vec_xz * half_ballast_width
            p_ballast_right = pos - right_vec_xz * half_ballast_width

            glNormal3f(0, 1, 0) # 道碴頂面法線向上
            glVertex3f(p_ballast_left[0], pos[1] + BALLAST_HEIGHT, p_ballast_left[2])
            glVertex3f(p_ballast_right[0], pos[1] + BALLAST_HEIGHT, p_ballast_right[2])
        glEnd()
        # 可以選擇性繪製道碴側面

        # 繪製兩條軌道 (使用 Line Strip)
        glColor3fv(RAIL_COLOR)
        glLineWidth(2.0) # 設定線寬
        rail_height_offset = BALLAST_HEIGHT + 0.05 # 軌道在道碴之上

        # 左軌道
        glBegin(GL_LINE_STRIP)
        for i in range(len(segment.points)):
            pos = segment.points[i]
            orient_xz = segment.orientations[i]
            right_vec_xz = np.array([-orient_xz[1], 0, orient_xz[0]])
            p_rail_left = pos + right_vec_xz * half_track_width
            # *** 使用點的 Y 坐標加上軌道偏移 ***
            glVertex3f(p_rail_left[0], pos[1] + rail_height_offset, p_rail_left[2])
        glEnd()

        # 右軌道
        glBegin(GL_LINE_STRIP)
        for i in range(len(segment.points)):
            pos = segment.points[i]
            orient_xz = segment.orientations[i]
            right_vec_xz = np.array([-orient_xz[1], 0, orient_xz[0]])
            p_rail_right = pos - right_vec_xz * half_track_width
             # *** 使用點的 Y 坐標加上軌道偏移 ***
            glVertex3f(p_rail_right[0], pos[1] + rail_height_offset, p_rail_right[2])
        glEnd()

    glEnable(GL_TEXTURE_2D) # 恢復紋理狀態

def draw_cube(width, depth, height, texture_id=None):
    """繪製一個立方體，可選紋理"""
    if texture_id is not None and glIsTexture(texture_id): # Check if texture ID is valid
        glBindTexture(GL_TEXTURE_2D, texture_id)
        glEnable(GL_TEXTURE_2D)
    else:
        glDisable(GL_TEXTURE_2D)

    w, d, h = width / 2.0, depth / 2.0, height # 中心在底部 (0, 0, 0), 頂部在 Y=h

    # glColor3f(0.8, 0.8, 0.8) # Set color outside if needed

    glBegin(GL_QUADS)
    # Bottom face (Y=0)
    glNormal3f(0, -1, 0)
    glTexCoord2f(1, 0); glVertex3f( w, 0,  d) # Texture coords might need adjustment depending on image
    glTexCoord2f(0, 0); glVertex3f(-w, 0,  d)
    glTexCoord2f(0, 1); glVertex3f(-w, 0, -d)
    glTexCoord2f(1, 1); glVertex3f( w, 0, -d)

    # Top face (Y=h)
    glNormal3f(0, 1, 0)
    glTexCoord2f(1, 1); glVertex3f( w, h, -d)
    glTexCoord2f(0, 1); glVertex3f(-w, h, -d)
    glTexCoord2f(0, 0); glVertex3f(-w, h,  d)
    glTexCoord2f(1, 0); glVertex3f( w, h,  d)

    # Front face  (Z=d)
    glNormal3f(0, 0, 1)
    glTexCoord2f(1, 0); glVertex3f( w, 0, d)
    glTexCoord2f(0, 0); glVertex3f(-w, 0, d)
    glTexCoord2f(0, 1); glVertex3f(-w, h, d)
    glTexCoord2f(1, 1); glVertex3f( w, h, d)

    # Back face (Z=-d)
    glNormal3f(0, 0, -1)
    glTexCoord2f(1, 0); glVertex3f( w, h, -d)
    glTexCoord2f(0, 0); glVertex3f(-w, h, -d)
    glTexCoord2f(0, 1); glVertex3f(-w, 0, -d)
    glTexCoord2f(1, 1); glVertex3f( w, 0, -d)

    # Left face (X=-w)
    glNormal3f(-1, 0, 0)
    glTexCoord2f(1, 0); glVertex3f(-w, 0, -d)
    glTexCoord2f(0, 0); glVertex3f(-w, 0,  d)
    glTexCoord2f(0, 1); glVertex3f(-w, h,  d)
    glTexCoord2f(1, 1); glVertex3f(-w, h, -d)

    # Right face (X=w)
    glNormal3f(1, 0, 0)
    glTexCoord2f(1, 0); glVertex3f( w, 0,  d)
    glTexCoord2f(0, 0); glVertex3f( w, 0, -d)
    glTexCoord2f(0, 1); glVertex3f( w, h, -d)
    glTexCoord2f(1, 1); glVertex3f( w, h,  d)
    glEnd()

    glBindTexture(GL_TEXTURE_2D, 0) # Unbind
    glEnable(GL_TEXTURE_2D) # Ensure it's enabled afterwards


def draw_cylinder(radius, height, texture_id=None):
    """繪製圓柱體，可選紋理. Assumes it's drawn along Z-axis, needs external rotation for Y-up."""
    if texture_id is not None and glIsTexture(texture_id):
        glBindTexture(GL_TEXTURE_2D, texture_id)
        glEnable(GL_TEXTURE_2D)
    else:
        glDisable(GL_TEXTURE_2D)

    quadric = gluNewQuadric()
    if quadric: # Check if quadric creation succeeded
        gluQuadricTexture(quadric, GL_TRUE) # Enable texture coordinates
        gluQuadricNormals(quadric, GLU_SMOOTH) # Smooth normals

        # Draw cylinder body (along Z from 0 to height)
        gluCylinder(quadric, radius, radius, height, CYLINDER_SLICES, 1)

        # Draw bottom cap (at Z=0)
        glPushMatrix()
        glRotatef(180, 1, 0, 0) # Flip to face inwards for standard culling
        gluDisk(quadric, 0, radius, CYLINDER_SLICES, 1)
        glPopMatrix()

        # Draw top cap (at Z=height)
        glPushMatrix()
        glTranslatef(0, 0, height)
        gluDisk(quadric, 0, radius, CYLINDER_SLICES, 1)
        glPopMatrix()

        gluDeleteQuadric(quadric)
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
        obj_type, x, y, z, rx, ry, rz, w, d, h, tex_id = obj_data
        glPushMatrix()
        glTranslatef(x, y, z) # Move to position
        # Apply rotations: Y (yaw), then X (pitch), then Z (roll) - common order
        glRotatef(ry, 0, 1, 0)
        glRotatef(rx, 1, 0, 0)
        glRotatef(rz, 0, 0, 1)
        draw_cube(w, d, h, tex_id) # Draws cube with base at current origin
        glPopMatrix()

    # 繪製圓柱體
    for obj_data in scene.cylinders:
        # Order from parser: type, x, y, z, rx, rz, ry, radius, h, tex_id
        obj_type, x, y, z, rx, rz, ry, radius, h, tex_id = obj_data
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
        draw_cylinder(radius, h, tex_id) # Draw the cylinder along the (now rotated) Z-axis
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
    lever_base_x = cab_width * 0.25
    lever_base_y = dash_pos_y + dash_height * 0.2
    lever_base_z = dash_pos_z - dash_depth * 0.4 + 0.5
    lever_length = 0.4
    lever_max_angle = 40.0 # 向前或向後的最大角度

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
    render_angle_y = math.degrees(math.atan2(tram.forward_vector_xz[0], tram.forward_vector_xz[1]))
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
    
    
def _world_to_map_coords(world_x, world_z, player_x, player_z, map_center_x, map_center_y, scale):
    """內部輔助函數：將世界XZ坐標轉換為小地圖2D屏幕坐標"""
    # 計算相對於玩家的偏移量
    delta_x = world_x - player_x
    delta_z = world_z - player_z # 注意：通常地圖Y對應世界Z

    # 應用縮放並計算在小地圖上的坐標
    # 假設地圖 X+ 對應世界 X+, 地圖 Y+ 對應世界 Z+
    # 這裡改成map_center_x - delta_x * scale 不然minimap會左右顛倒
    map_x = map_center_x - delta_x * scale
    map_y = map_center_y + delta_z * scale

    return map_x, map_y

# 這裡引數必須排列成rx_deg, rz_deg, ry_deg 才可以讓旋轉正確
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


# --- Modified draw_minimap ---
def draw_minimap(scene, tram, screen_width, screen_height):
    """繪製 HUD 小地圖 (使用場景定義的背景圖或純色)"""
    global grid_label_font, current_minimap_range
    # Use cached texture ID and dimensions
    global minimap_bg_texture_id, minimap_bg_image_width_px, minimap_bg_image_height_px

    # --- Calculate Map Position on Screen ---
    map_left = screen_width - MINIMAP_SIZE - MINIMAP_PADDING
    map_right = screen_width - MINIMAP_PADDING
    map_bottom = screen_height - MINIMAP_SIZE - MINIMAP_PADDING # Y=0 is bottom in ortho
    map_top = screen_height - MINIMAP_PADDING
    map_center_x = map_left + MINIMAP_SIZE / 2
    map_center_y = map_bottom + MINIMAP_SIZE / 2

    # --- Player and Viewport Info ---
    player_x = tram.position[0]
    player_z = tram.position[2] # 使用 Z 坐標

    # 縮放比例：世界單位範圍映射到地圖像素大小
    if current_minimap_range <= 0: current_minimap_range = MINIMAP_MIN_RANGE # 防止除零
    scale = MINIMAP_SIZE / current_minimap_range
    world_half_range = current_minimap_range / 2.0
    #
    world_view_left = player_x - world_half_range
    world_view_right = player_x + world_half_range
    world_view_bottom_z = player_z - world_half_range # Bottom of map = smaller Z
    world_view_top_z = player_z + world_half_range   # Top of map = larger Z

    # --- 切換到 2D 正交投影 ---
    glMatrixMode(GL_PROJECTION)
    glPushMatrix()          # 保存透視投影矩陣
    glLoadIdentity()
    gluOrtho2D(0, screen_width, 0, screen_height) # 設置屏幕像素坐標系

    glMatrixMode(GL_MODELVIEW)
    glPushMatrix()          # 保存 3D 視圖矩陣
    glLoadIdentity()        # 重置模型視圖矩陣

    # --- 關閉 3D 相關狀態 ---
    glPushAttrib(GL_ENABLE_BIT | GL_CURRENT_BIT | GL_LINE_BIT | GL_POINT_BIT) # 保存狀態
    glDisable(GL_DEPTH_TEST)
    glDisable(GL_LIGHTING)
    glEnable(GL_BLEND)
    glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
    glDisable(GL_TEXTURE_2D) # Default to disabled

    # --- Draw Minimap Background ---
    use_texture = (minimap_bg_texture_id is not None and
                   minimap_bg_image_width_px > 0 and
                   minimap_bg_image_height_px > 0 and
                   scene.map_filename is not None and # Ensure scene specified a map
                   abs(scene.map_world_scale) > 1e-6) # Ensure valid scale

    if use_texture:
        glEnable(GL_TEXTURE_2D)
        glBindTexture(GL_TEXTURE_2D, minimap_bg_texture_id)
        glColor4f(1.0, 1.0, 1.0, 1.0)

        # --- Calculate World Extent of the Loaded Image ---
        # Scale is world units per pixel
        image_world_width = minimap_bg_image_width_px * scene.map_world_scale
        image_world_height = minimap_bg_image_height_px * scene.map_world_scale

        img_world_x_min = scene.map_world_center_x - image_world_width / 2.0
        img_world_x_max = scene.map_world_center_x + image_world_width / 2.0
        # Assuming image (0,0) is top-left, and world Z increases upwards on map (map_y increases upwards)
        # Texture V=0 is bottom (due to pygame flip), V=1 is top.
        # World Z corresponding to image bottom (V=0)
        img_world_z_min = scene.map_world_center_z - image_world_height / 2.0
        # World Z corresponding to image top (V=1)
        img_world_z_max = scene.map_world_center_z + image_world_height / 2.0

        # --- Calculate Texture Coordinates for the Visible Viewport ---
        # Avoid division by zero if width/height are somehow zero
        if abs(image_world_width) < 1e-6 or abs(image_world_height) < 1e-6:
            u_min, u_max, v_min, v_max = 0.0, 1.0, 0.0, 1.0 # Fallback UVs
            print("Warning: Calculated image world width/height is near zero.")
        else:
            # 以下兩行是修改過的  因為要讓圖片跟著同方向移動
            u_min = (-world_view_left + img_world_x_max) / image_world_width
            u_max = (-world_view_right + img_world_x_max) / image_world_width
            v_min = (world_view_bottom_z - img_world_z_min) / image_world_height # Z_min corresponds to V=0 (bottom)
            v_max = (world_view_top_z - img_world_z_min) / image_world_height    # Z_max corresponds to V=1 (top)

        # Clamp texture coordinates to [0, 1] if using CLAMP_TO_EDGE wasn't enough
        # u_min, u_max = max(0.0, u_min), min(1.0, u_max)
        # v_min, v_max = max(0.0, v_min), min(1.0, v_max)

        # --- Draw Textured Quad ---
        glBegin(GL_QUADS)
        # 以下 glTexCoord2f 內的u_max u_min  因為要把圖片左右相反
        glTexCoord2f(u_max, v_min); glVertex2f(map_left, map_bottom)   # Bottom Left
        glTexCoord2f(u_min, v_min); glVertex2f(map_right, map_bottom)  # Bottom Right
        glTexCoord2f(u_min, v_max); glVertex2f(map_right, map_top)     # Top Right
        glTexCoord2f(u_max, v_max); glVertex2f(map_left, map_top)      # Top Left
        glEnd()

        glBindTexture(GL_TEXTURE_2D, 0)
        glDisable(GL_TEXTURE_2D)
    else:
        # --- Fallback: Draw Solid Color Background ---
        glDisable(GL_TEXTURE_2D)
        glColor4fv(MINIMAP_BG_FALLBACK_COLOR)
        glBegin(GL_QUADS)
        glVertex2f(map_left, map_bottom); glVertex2f(map_right, map_bottom)
        glVertex2f(map_right, map_top); glVertex2f(map_left, map_top)
        glEnd()
        
    # --- 設置裁剪區域 (只在小地圖範圍內繪製) ---
    # 注意：glScissor 的 Y 是從左下角算的
    glEnable(GL_SCISSOR_TEST)
    glScissor(int(map_left), int(map_bottom), int(MINIMAP_SIZE), int(MINIMAP_SIZE))

    # --- Draw Grid Lines ---
    # (Grid drawing code - check world_view boundaries vs grid scale)
    draw_grid = current_minimap_range < DEFAULT_MINIMAP_RANGE * 1.5 # Show grid when zoomed in
    if draw_grid:
        glColor4fv(MINIMAP_GRID_COLOR)
        glLineWidth(1.0)
        start_grid_x = math.floor(world_view_left / MINIMAP_GRID_SCALE) * MINIMAP_GRID_SCALE
        start_grid_z = math.floor(world_view_bottom_z / MINIMAP_GRID_SCALE) * MINIMAP_GRID_SCALE
        # ... (垂直線繪製) ...
        current_grid_x = start_grid_x
        while current_grid_x <= world_view_right:
            map_x, _ = _world_to_map_coords(current_grid_x, player_z, player_x, player_z, map_center_x, map_center_y, scale)
            # Draw line only if it's potentially visible within the map bounds
            if map_left - 1 <= map_x <= map_right + 1:
                glBegin(GL_LINES); glVertex2f(map_x, map_bottom); glVertex2f(map_x, map_top); glEnd()
            current_grid_x += MINIMAP_GRID_SCALE
        # ... (水平線繪製) ...
        current_grid_z = start_grid_z
        while current_grid_z <= world_view_top_z:
             _, map_y = _world_to_map_coords(player_x, current_grid_z, player_x, player_z, map_center_x, map_center_y, scale)
             if map_bottom - 1 <= map_y <= map_top + 1:
                 glBegin(GL_LINES); glVertex2f(map_left, map_y); glVertex2f(map_right, map_y); glEnd()
             current_grid_z += MINIMAP_GRID_SCALE


    # --- 繪製軌道 ---
    glColor3fv(MINIMAP_TRACK_COLOR)
    glLineWidth(2.0)
    for segment in scene.track.segments:
        if not segment.points or len(segment.points) < 2:
            continue
        
        map_x, map_y = _world_to_map_coords(segment.points[0][0], segment.points[0][2],
                                            player_x, player_z,
                                            map_center_x, map_center_y, scale)
        glPointSize(8)
        glBegin(GL_POINTS)
        glColor3fv(MINIMAP_TRACK_COLOR)
        glVertex2f(map_x, map_y)  # 
        glEnd()
        
        
        glBegin(GL_LINE_STRIP)
        
        for point_world in segment.points:
            # 將世界坐標轉換為地圖坐標
            map_x, map_y = _world_to_map_coords(point_world[0], point_world[2],
                                                player_x, player_z,
                                                map_center_x, map_center_y, scale)
            
            # 在此處進行簡單的邊界檢查 (可選，glScissor 已做裁剪)
            # if map_left <= map_x <= map_right and map_bottom <= map_y <= map_top:
            glVertex2f(map_x, map_y)
            
        glEnd()

    # --- 繪製建築物 (簡單方塊) ---
    glColor3fv(MINIMAP_BUILDING_COLOR)
    glLineWidth(1.0) # 使用線條繪製輪廓
    for bldg in scene.buildings:
        b_type, wx, wy, wz, rx, ry, rz, ww, wd, wh, tid = bldg
        # 獲取建築物在世界坐標系中的四個底角 (忽略高度 wy)
        half_w = ww / 2.0
        half_d = wd / 2.0
        # 局部坐標系下的四個角 (Y=0 平面)
        corners_local = [
            np.array([-half_w, 0, -half_d]), # 後左
            np.array([ half_w, 0, -half_d]), # 後右
            np.array([ half_w, 0,  half_d]), # 前右
            np.array([-half_w, 0,  half_d])  # 前左
        ]

        # 應用旋轉 (只考慮 Y 軸旋轉 ry，因為是俯視圖)
        angle_y_rad = -math.radians(ry)
        cos_y = math.cos(angle_y_rad)
        sin_y = math.sin(angle_y_rad)

        corners_world_xz = []
        for corner in corners_local:
            # 應用 Y 軸旋轉
            rotated_x = corner[0] * cos_y - corner[2] * sin_y
            rotated_z = corner[0] * sin_y + corner[2] * cos_y
            # 平移到世界位置
            world_corner_x = wx + rotated_x
            world_corner_z = wz + rotated_z
            corners_world_xz.append((world_corner_x, world_corner_z))

        # 將世界坐標轉換為地圖坐標並繪製矩形輪廓
        map_coords = []
        in_map = True # 檢查是否有任何角點在圖內
        for wcx, wcz in corners_world_xz:
            map_x, map_y = _world_to_map_coords(wcx, wcz, player_x, player_z, map_center_x, map_center_y, scale)
            map_coords.append((map_x, map_y))
            if not (map_left <= map_x <= map_right and map_bottom <= map_y <= map_top):
                 # 如果需要嚴格裁剪，可以在這裡跳過繪製完全在外的物體
                 # pass
                 pass # 依賴 glScissor

        # 繪製輪廓 (GL_LINE_LOOP)
        glBegin(GL_LINE_LOOP)
        for mx, my in map_coords:
            glVertex2f(mx, my)
        glEnd()

    # --- 繪製圓柱體 (根據旋轉選擇圓形或矩形) ---
    # 圓柱體也用相同顏色
    num_circle_segments = 128 # 用幾條線段近似圓形
    for cyl in scene.cylinders:
        c_type, wx, wy, wz, rx, ry, rz, cr, ch, tid = cyl # cr=radius, ch=height

        # 檢查是否有 X 或 Y 軸的傾斜
        is_tilted = abs(rx) > 0.1 or abs(ry) > 0.1

        if is_tilted:
            # --- 繪製傾斜圓柱體的投影矩形 (方案 2：以原點投影定位) ---

            # 1. 計算旋轉後的軸心線端點 (仍然需要計算投影軸以確定角度)
            p_bottom_local_rel = np.array([0, -ch/2.0, 0])
            p_top_local_rel = np.array([0, ch/2.0, 0])
            p_bottom_rotated_rel = _rotate_point_3d(p_bottom_local_rel, rx, ry, rz)
            p_top_rotated_rel = _rotate_point_3d(p_top_local_rel, rx, ry, rz)
            p_bottom_world = np.array([wx, wy, wz]) + p_bottom_rotated_rel
            p_top_world = np.array([wx, wy, wz]) + p_top_rotated_rel
            p_bottom_xz = np.array([p_bottom_world[0], p_bottom_world[2]])
            p_top_xz = np.array([p_top_world[0], p_top_world[2]])

            # 2. 計算投影軸向量和角度 (用於旋轉)
            axis_proj_xz = p_top_xz - p_bottom_xz
            length_proj = np.linalg.norm(axis_proj_xz)
            # Angle of the projected axis on the map (relative to +X axis)
            angle_map_rad = math.atan2(axis_proj_xz[1], axis_proj_xz[0]) if length_proj > 1e-6 else 0

            # 3. 計算矩形在地圖上的尺寸
            rect_length = length_proj + 2 * cr # Approximation of projected length
            rect_width = 2 * cr

            # --- *** START CHANGE (方案 2) *** ---
            # 4. 計算 *原點* (wx, wz) 在地圖上的坐標，用於定位
            origin_map_x, origin_map_y = _world_to_map_coords(wx, wz, # 使用原始的 wx, wz
                                                            player_x, player_z,
                                                            map_center_x, map_center_y, scale)
            # --- *** END CHANGE *** ---

            # 5. 繪製旋轉的矩形
            glPushMatrix()
            # --- *** START CHANGE (方案 2) *** ---
            # 平移到 *原點* 的地圖坐標
            glTranslatef(origin_map_x, origin_map_y, 0)
            # --- *** END CHANGE *** ---
            # 旋轉 (使用投影軸計算出的角度)
            glRotatef(math.degrees(angle_map_rad), 0, 0, 1)
            # 繪製相對於旋轉後 *原點* 的矩形 (尺寸需要縮放)
            half_len = (rect_length * scale) / 2.0
            half_wid = (rect_width * scale) / 2.0
            glBegin(GL_LINE_LOOP)
            glVertex2f(-half_len, -half_wid)
            glVertex2f( half_len, -half_wid)
            glVertex2f( half_len,  half_wid)
            glVertex2f(-half_len,  half_wid)
            glEnd()
            glPopMatrix()

        else:
            # --- 繪製未傾斜圓柱體的圓形輪廓 (保持不變) ---
            center_map_x, center_map_y = _world_to_map_coords(wx, wz, player_x, player_z, map_center_x, map_center_y, scale)
            radius_map = cr * scale

            if map_left - radius_map <= center_map_x <= map_right + radius_map and \
               map_bottom - radius_map <= center_map_y <= map_top + radius_map:
                glBegin(GL_LINE_LOOP)
                for i in range(num_circle_segments):
                    angle = 2 * math.pi * i / num_circle_segments
                    offset_x = radius_map * math.cos(angle)
                    offset_y = radius_map * math.sin(angle)
                    glVertex2f(center_map_x + offset_x, center_map_y + offset_y)
                glEnd()


    # Adjust point size based on zoom? Optional.
    min_point_size, max_point_size = 1.0, 5.0
    # Map range from min_range to default_range to max_point_size to min_point_size
    point_size_ratio = (DEFAULT_MINIMAP_RANGE - current_minimap_range) / (DEFAULT_MINIMAP_RANGE - MINIMAP_MIN_RANGE) if DEFAULT_MINIMAP_RANGE != MINIMAP_MIN_RANGE else 1.0
    point_size = min_point_size + (max_point_size - min_point_size) * max(0, min(1, point_size_ratio)) # Clamp ratio
    point_size = max(min_point_size, min(max_point_size, point_size)) # Ensure within bounds

    # --- 繪製樹木 (簡單點) ---
    glColor3fv(MINIMAP_TREE_COLOR)
    glPointSize(max(3.0, point_size))
    glBegin(GL_POINTS)
    for tree in scene.trees:
        tx, ty, tz, th = tree
        map_x, map_y = _world_to_map_coords(tx, tz, player_x, player_z, map_center_x, map_center_y, scale)
        if map_left <= map_x <= map_right and map_bottom <= map_y <= map_top:
            glVertex2f(map_x, map_y)
    glEnd()

    # --- 繪製玩家標記 (紅色三角形指示方向) ---
    glColor3fv(MINIMAP_PLAYER_COLOR)
    # 計算玩家朝向角度 (從 X 軸正方向算，逆時針為正)
    # tram.forward_vector_xz 是 (x, z)
    player_angle_rad = -math.atan2(tram.forward_vector_xz[1], tram.forward_vector_xz[0]) # atan2(y, x) -> atan2(z, x)

    # 計算三角形的三個頂點 (相對於地圖中心)
    # 頂點 (指向前方)
    tip_x = map_center_x + math.cos(player_angle_rad - math.pi) * MINIMAP_PLAYER_SIZE * 3
    tip_y = map_center_y + math.sin(player_angle_rad - math.pi) * MINIMAP_PLAYER_SIZE * 3
    # 左後點
    left_angle = player_angle_rad - math.pi * .75 # 往後 135 度
    left_x = map_center_x + math.cos(left_angle) * MINIMAP_PLAYER_SIZE * 1
    left_y = map_center_y + math.sin(left_angle) * MINIMAP_PLAYER_SIZE * 1
    # 右後點
    right_angle = player_angle_rad + math.pi * .75 # 往後 135 度 (順時針)
    right_x = map_center_x + math.cos(right_angle) * MINIMAP_PLAYER_SIZE * 1
    right_y = map_center_y + math.sin(right_angle) * MINIMAP_PLAYER_SIZE * 1

    glBegin(GL_TRIANGLES)
    glVertex2f(tip_x, tip_y)
    glVertex2f(left_x, left_y)
    glVertex2f(right_x, right_y)
    glEnd()

    # --- *** 關閉裁剪，準備繪製標籤 (標籤在裁剪區域外) *** ---
    glDisable(GL_SCISSOR_TEST)

    # --- 繪製網格標籤 ---
    draw_labels = current_minimap_range < DEFAULT_MINIMAP_RANGE * 1.2
    if grid_label_font and draw_labels:
        glEnable(GL_TEXTURE_2D) # 啟用紋理繪製文字

        # 繪製 X 坐標標籤 (在地圖底部)
        current_grid_x = start_grid_x
        while current_grid_x <= world_view_right:
            map_x, _ = _world_to_map_coords(current_grid_x, player_z, player_x, player_z, map_center_x, map_center_y, scale)
            if map_left <= map_x <= map_right:
                label_text = f"{current_grid_x:.0f}"
                try:
                    text_surface = grid_label_font.render(label_text, True, MINIMAP_GRID_LABEL_COLOR)
                    text_width, text_height = text_surface.get_size()
                    # 繪製在底部，稍微外移
                    draw_label_x = map_x - text_width / 2 # 居中
                    draw_label_y = map_bottom - MINIMAP_GRID_LABEL_OFFSET - text_height
                    _draw_text_texture(text_surface, draw_label_x, draw_label_y)
                except Exception as e:
                    print(f"渲染 X 標籤時出錯: {e}") # 避免崩潰
            current_grid_x += MINIMAP_GRID_SCALE

        # 繪製 Z 坐標標籤 (在地圖左側)
        current_grid_z = start_grid_z
        while current_grid_z <= world_view_top_z:
             _, map_y = _world_to_map_coords(player_x, current_grid_z, player_x, player_z, map_center_x, map_center_y, scale)
             if map_bottom <= map_y <= map_top:
                label_text = f"{current_grid_z:.0f}"
                try:
                    text_surface = grid_label_font.render(label_text, True, MINIMAP_GRID_LABEL_COLOR)
                    text_width, text_height = text_surface.get_size()
                    # 繪製在左側，稍微外移
                    draw_label_x = map_left - MINIMAP_GRID_LABEL_OFFSET - text_width
                    draw_label_y = map_y - text_height / 2 # 垂直居中
                    _draw_text_texture(text_surface, draw_label_x, draw_label_y)
                except Exception as e:
                    print(f"渲染 Z 標籤時出錯: {e}") # 避免崩潰
             current_grid_z += MINIMAP_GRID_SCALE

        glDisable(GL_TEXTURE_2D) # 完成文字繪製後禁用

    # --- 恢復 OpenGL 狀態 ---
    glDisable(GL_SCISSOR_TEST) # 關閉裁剪
    glDisable(GL_BLEND)
    glPopAttrib()           # 恢復之前保存的狀態 (Enable/Color/Line/Point)

    # --- 恢復矩陣 ---
    glMatrixMode(GL_PROJECTION)
    glPopMatrix()           # 恢復透視投影矩陣
    glMatrixMode(GL_MODELVIEW)
    glPopMatrix()           # 恢復 3D 視圖矩陣

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
    
