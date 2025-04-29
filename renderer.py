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
CYLINDER_SLICES = 16 # Keep (maybe reduce default slightly?)

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
    grass_tex = texture_loader.load_texture("grass.png")
    tree_bark_tex = texture_loader.load_texture("tree_bark.png")
    tree_leaves_tex = texture_loader.load_texture("tree_leaves.png")
    cab_metal_tex = texture_loader.load_texture("metal.png") # Assuming cab uses metal texture

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
        if segment.ballast_vao and segment.ballast_vertices:
            glColor3fv(BALLAST_COLOR)
            glBindVertexArray(segment.ballast_vao)
            vertex_count = len(segment.ballast_vertices) // 3
            glDrawArrays(GL_TRIANGLES, 0, vertex_count)
            glBindVertexArray(0)
        glLineWidth(2.0); glColor3fv(RAIL_COLOR)
        if segment.rail_left_vao and segment.rail_left_vertices:
            glBindVertexArray(segment.rail_left_vao)
            vertex_count = len(segment.rail_left_vertices) // 3
            glDrawArrays(GL_LINE_STRIP, 0, vertex_count)
            glBindVertexArray(0)
        if segment.rail_right_vao and segment.rail_right_vertices:
            glBindVertexArray(segment.rail_right_vao)
            vertex_count = len(segment.rail_right_vertices) // 3
            glDrawArrays(GL_LINE_STRIP, 0, vertex_count)
            glBindVertexArray(0)
    glEnable(GL_TEXTURE_2D)


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
def draw_cube(width, depth, height, texture_id=None,
              u_offset=0.0, v_offset=0.0, tex_angle_deg=0.0, uv_mode=1,
              uscale=1.0, vscale=1.0):
    # (Logic unchanged)
    if texture_id is not None and glIsTexture(texture_id):
        glBindTexture(GL_TEXTURE_2D, texture_id); glEnable(GL_TEXTURE_2D)
        wrap_mode = GL_REPEAT if uv_mode == 0 else GL_REPEAT # Or GL_CLAMP_TO_EDGE
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, wrap_mode)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, wrap_mode)
    else: glDisable(GL_TEXTURE_2D)
    w, d, h = width / 2.0, depth / 2.0, height
    angle_rad = math.radians(tex_angle_deg)
    glBegin(GL_QUADS)
    # Bottom face
    face_w, face_h = width, depth; cur_usc, cur_vsc = uscale, vscale
    if uv_mode == 1: bc = [(1, 0), (0, 0), (0, 1), (1, 1)]; cu, cv = 0.5, 0.5
    else: bc = [(width, 0), (0, 0), (0, depth), (width, depth)]; cu, cv = width / 2.0, depth / 2.0
    glNormal3f(0, -1, 0)
    uv = _calculate_uv(*bc[0], cu, cv, u_offset, v_offset, angle_rad, uv_mode, cur_usc, cur_vsc); glTexCoord2f(*uv); glVertex3f( w, 0,  d)
    uv = _calculate_uv(*bc[1], cu, cv, u_offset, v_offset, angle_rad, uv_mode, cur_usc, cur_vsc); glTexCoord2f(*uv); glVertex3f(-w, 0,  d)
    uv = _calculate_uv(*bc[2], cu, cv, u_offset, v_offset, angle_rad, uv_mode, cur_usc, cur_vsc); glTexCoord2f(*uv); glVertex3f(-w, 0, -d)
    uv = _calculate_uv(*bc[3], cu, cv, u_offset, v_offset, angle_rad, uv_mode, cur_usc, cur_vsc); glTexCoord2f(*uv); glVertex3f( w, 0, -d)
    # Top face
    face_w, face_h = width, depth; cur_usc, cur_vsc = uscale, vscale
    if uv_mode == 1: bc = [(1, 1), (0, 1), (0, 0), (1, 0)]; cu, cv = 0.5, 0.5
    else: bc = [(width, depth), (0, depth), (0, 0), (width, 0)]; cu, cv = width / 2.0, depth / 2.0
    glNormal3f(0, 1, 0)
    uv = _calculate_uv(*bc[0], cu, cv, u_offset, v_offset, angle_rad, uv_mode, cur_usc, cur_vsc); glTexCoord2f(*uv); glVertex3f( w, h, -d)
    uv = _calculate_uv(*bc[1], cu, cv, u_offset, v_offset, angle_rad, uv_mode, cur_usc, cur_vsc); glTexCoord2f(*uv); glVertex3f(-w, h, -d)
    uv = _calculate_uv(*bc[2], cu, cv, u_offset, v_offset, angle_rad, uv_mode, cur_usc, cur_vsc); glTexCoord2f(*uv); glVertex3f(-w, h,  d)
    uv = _calculate_uv(*bc[3], cu, cv, u_offset, v_offset, angle_rad, uv_mode, cur_usc, cur_vsc); glTexCoord2f(*uv); glVertex3f( w, h,  d)
    # Front face
    face_w, face_h = width, height; cur_usc, cur_vsc = uscale, vscale
    if uv_mode == 1: bc = [(1, 0), (0, 0), (0, 1), (1, 1)]; cu, cv = 0.5, 0.5
    else: bc = [(width, 0), (0, 0), (0, height), (width, height)]; cu, cv = width / 2.0, height / 2.0
    glNormal3f(0, 0, 1)
    uv = _calculate_uv(*bc[0], cu, cv, u_offset, v_offset, angle_rad, uv_mode, cur_usc, cur_vsc); glTexCoord2f(*uv); glVertex3f( w, 0, d)
    uv = _calculate_uv(*bc[1], cu, cv, u_offset, v_offset, angle_rad, uv_mode, cur_usc, cur_vsc); glTexCoord2f(*uv); glVertex3f(-w, 0, d)
    uv = _calculate_uv(*bc[2], cu, cv, u_offset, v_offset, angle_rad, uv_mode, cur_usc, cur_vsc); glTexCoord2f(*uv); glVertex3f(-w, h, d)
    uv = _calculate_uv(*bc[3], cu, cv, u_offset, v_offset, angle_rad, uv_mode, cur_usc, cur_vsc); glTexCoord2f(*uv); glVertex3f( w, h, d)
    # Back face
    face_w, face_h = width, height; cur_usc, cur_vsc = uscale, vscale
    if uv_mode == 1: bc = [(0, 1), (1, 1), (1, 0), (0, 0)]; cu, cv = 0.5, 0.5
    else: bc = [(width, height), (0, height), (0, 0), (width, 0)]; cu, cv = width / 2.0, height / 2.0
    glNormal3f(0, 0, -1)
    uv = _calculate_uv(*bc[0], cu, cv, u_offset, v_offset, angle_rad, uv_mode, cur_usc, cur_vsc); glTexCoord2f(*uv); glVertex3f( w, h, -d)
    uv = _calculate_uv(*bc[1], cu, cv, u_offset, v_offset, angle_rad, uv_mode, cur_usc, cur_vsc); glTexCoord2f(*uv); glVertex3f(-w, h, -d)
    uv = _calculate_uv(*bc[2], cu, cv, u_offset, v_offset, angle_rad, uv_mode, cur_usc, cur_vsc); glTexCoord2f(*uv); glVertex3f(-w, 0, -d)
    uv = _calculate_uv(*bc[3], cu, cv, u_offset, v_offset, angle_rad, uv_mode, cur_usc, cur_vsc); glTexCoord2f(*uv); glVertex3f( w, 0, -d)
    # Left face
    face_w, face_h = depth, height; cur_usc, cur_vsc = uscale, vscale
    if uv_mode == 1: bc = [(1, 0), (0, 0), (0, 1), (1, 1)]; cu, cv = 0.5, 0.5
    else: bc = [(depth, 0), (0, 0), (0, height), (depth, height)]; cu, cv = depth / 2.0, height / 2.0
    glNormal3f(-1, 0, 0)
    uv = _calculate_uv(*bc[0], cu, cv, u_offset, v_offset, angle_rad, uv_mode, cur_usc, cur_vsc); glTexCoord2f(*uv); glVertex3f(-w, 0, -d)
    uv = _calculate_uv(*bc[1], cu, cv, u_offset, v_offset, angle_rad, uv_mode, cur_usc, cur_vsc); glTexCoord2f(*uv); glVertex3f(-w, 0,  d)
    uv = _calculate_uv(*bc[2], cu, cv, u_offset, v_offset, angle_rad, uv_mode, cur_usc, cur_vsc); glTexCoord2f(*uv); glVertex3f(-w, h,  d)
    uv = _calculate_uv(*bc[3], cu, cv, u_offset, v_offset, angle_rad, uv_mode, cur_usc, cur_vsc); glTexCoord2f(*uv); glVertex3f(-w, h, -d)
    # Right face
    face_w, face_h = depth, height; cur_usc, cur_vsc = uscale, vscale
    if uv_mode == 1: bc = [(0, 0), (1, 0), (1, 1), (0, 1)]; cu, cv = 0.5, 0.5
    else: bc = [(0, 0), (depth, 0), (depth, height), (0, height)]; cu, cv = depth / 2.0, height / 2.0
    glNormal3f(1, 0, 0)
    uv = _calculate_uv(*bc[0], cu, cv, u_offset, v_offset, angle_rad, uv_mode, cur_usc, cur_vsc); glTexCoord2f(*uv); glVertex3f( w, 0,  d)
    uv = _calculate_uv(*bc[1], cu, cv, u_offset, v_offset, angle_rad, uv_mode, cur_usc, cur_vsc); glTexCoord2f(*uv); glVertex3f( w, 0, -d)
    uv = _calculate_uv(*bc[2], cu, cv, u_offset, v_offset, angle_rad, uv_mode, cur_usc, cur_vsc); glTexCoord2f(*uv); glVertex3f( w, h, -d)
    uv = _calculate_uv(*bc[3], cu, cv, u_offset, v_offset, angle_rad, uv_mode, cur_usc, cur_vsc); glTexCoord2f(*uv); glVertex3f( w, h,  d)
    glEnd()
    glBindTexture(GL_TEXTURE_2D, 0)
    glEnable(GL_TEXTURE_2D)


# --- draw_cylinder (unchanged) ---
def draw_cylinder(radius, height, texture_id=None,
                  u_offset=0.0, v_offset=0.0, tex_angle_deg=0.0, uv_mode=1,
                  uscale=1.0, vscale=1.0):
    # (Logic unchanged)
    if texture_id is not None and glIsTexture(texture_id):
        glBindTexture(GL_TEXTURE_2D, texture_id); glEnable(GL_TEXTURE_2D)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_REPEAT)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_REPEAT)
    else: glDisable(GL_TEXTURE_2D)
    quadric = gluNewQuadric()
    if quadric:
        gluQuadricTexture(quadric, GL_TRUE);
        gluQuadricNormals(quadric, GLU_SMOOTH)
        glMatrixMode(GL_TEXTURE);
        glPushMatrix();
        glLoadIdentity()
        glTranslatef(u_offset, v_offset, 0)
        if uv_mode == 0:
            safe_uscale = uscale if uscale > 1e-6 else 1e-6
            safe_vscale = vscale if vscale > 1e-6 else 1e-6
            glScalef(1.0 / safe_uscale, 1.0 / safe_vscale, 1.0)
        glMatrixMode(GL_MODELVIEW)
        gluCylinder(quadric, radius, radius, height, CYLINDER_SLICES, 1)
        glMatrixMode(GL_TEXTURE);
        glLoadIdentity();
        glMatrixMode(GL_MODELVIEW) # Reset texture matrix for caps
        glPushMatrix();
        glRotatef(180, 1, 0, 0);
        gluDisk(quadric, 0, radius, CYLINDER_SLICES, 1);
        glPopMatrix()
        glPushMatrix();
        glTranslatef(0, 0, height);
        gluDisk(quadric, 0, radius, CYLINDER_SLICES, 1);
        glPopMatrix()
        gluDeleteQuadric(quadric)
        glMatrixMode(GL_TEXTURE);
        glPopMatrix();
        glMatrixMode(GL_MODELVIEW) # Restore texture matrix
    else: print("Error creating GLU quadric object for cylinder.")
    glBindTexture(GL_TEXTURE_2D, 0)
    glEnable(GL_TEXTURE_2D)

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

def draw_hill(center_x, peak_height, center_z, base_radius, resolution=20, texture_id=None, uscale=10.0, vscale=10.0):
    """
    繪製一個基於餘弦插值的山丘。

    Args:
        center_x, center_z: 山峰中心的 XZ 座標。
        peak_height: 山峰相對於基底 (y=0) 的高度。
        base_radius: 山丘基底的半徑。
        resolution: 山丘網格的精細度 (例如 20x20 個四邊形)。
        texture_id: 應用於山丘的紋理 ID (如果為 None 則不使用紋理)。
        uscale, vscale: 紋理在 U 和 V 方向上的重複次數。
    """
    # --- 參數驗證 ---
    if peak_height <= 0 or base_radius <= 0 or resolution < 2:
        return

    # --- 紋理設定 ---
    if texture_id is not None and glIsTexture(texture_id):
        glBindTexture(GL_TEXTURE_2D, texture_id)
        glEnable(GL_TEXTURE_2D)
        # 設置紋理環繞方式，REPEAT 比較常用於地形
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_REPEAT)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_REPEAT)
        glColor4f(1.0, 1.0, 1.0, 1.0) # 確保紋理顏色不受glColor影響
    else:
        glDisable(GL_TEXTURE_2D)
        # 如果沒有紋理，可以設置一個預設顏色，例如棕色或綠色
        glColor3f(0.4, 0.5, 0.3) # 示例：深綠色

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

                # 計算高度 (使用餘弦插值)
                height = 0.0
                if distance <= base_radius:
                    height = peak_height * 0.5 * (math.cos(math.pi * distance / base_radius) + 1.0)

                # 計算實際世界座標
                world_x = center_x + world_dx
                world_z = center_z + world_dz
                world_y = height # 高度直接是 Y 座標 (假設基底在 Y=0)

                # --- 計算近似法向量 ---
                # 為了簡化，我們先給一個朝上的法向量，之後可以改進
                # 更精確的方法是計算數值導數或使用解析導數（如果插值函數可導）
                # 這裡使用一個簡單的近似：根據坡度稍微傾斜法向量
                normal_x = 0.0
                normal_y = 1.0
                normal_z = 0.0
                if distance > 1e-6 and distance <= base_radius:
                     # 導數的近似值 (未歸一化)
                     slope_factor = -peak_height * 0.5 * math.pi / base_radius * math.sin(math.pi * distance / base_radius)
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
    glBindTexture(GL_TEXTURE_2D, 0) # 解綁紋理
    # 繪製結束後不需要禁用 GL_TEXTURE_2D，交給調用者管理
    
# --- draw_scene_objects (unchanged) ---
def draw_scene_objects(scene):
#     glEnable(GL_BLEND)
    # (Logic unchanged)
    glColor3f(1.0, 1.0, 1.0)
    # Buildings
    for item in scene.buildings:
        line_num, obj_data = item # 先解包出 行號 和 原始數據元組
        # 再從原始數據元組解包出繪製所需變數
        (obj_type, x, y, z, rx, abs_ry, rz, w, d, h, tex_id, u_offset, v_offset, tex_angle_deg, uv_mode, uscale, vscale, tex_file) = obj_data
        glPushMatrix(); glTranslatef(x, y, z); glRotatef(abs_ry, 0, 1, 0); glRotatef(rx, 1, 0, 0); glRotatef(rz, 0, 0, 1)
        draw_cube(w, d, h, tex_id, u_offset, v_offset, tex_angle_deg, uv_mode, uscale, vscale)
        glPopMatrix()
    # Cylinders
    for item in scene.cylinders:
        line_num, obj_data = item # 先解包出 行號 和 原始數據元組
        # 再從原始數據元組解包出繪製所需變數
        (obj_type, x, y, z, rx, abs_ry, rz, radius, h, tex_id, u_offset, v_offset, tex_angle_deg, uv_mode, uscale, vscale, tex_file) = obj_data
        glPushMatrix();
        glTranslatef(x, y, z);
        glRotatef(abs_ry, 0, 1, 0);
        glRotatef(rz, 0, 0, 1)
        glRotatef(rx, 1, 0, 0);
        glPushMatrix();
        glRotatef(-90, 1, 0, 0)
        draw_cylinder(radius, h, tex_id, u_offset, v_offset, tex_angle_deg, uv_mode, uscale, vscale)
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
            (cx, height, cz, radius, tex_id, uscale, vscale, tex_file) = hill_data
        except ValueError:
             print(f"警告: 解包 hill 數據時出錯 (來源行: {line_num})")
             continue # 跳過這個物件

        # 不需要 Push/Pop Matrix，因為 draw_hill 使用絕對座標
        # 可以直接調用繪製函數
        draw_hill(cx, height, cz, radius,
                  resolution=10, # 可以將解析度設為可配置或常數
                  texture_id=tex_id,
                  uscale=uscale, vscale=vscale)
        
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
                    loaded_id = texture_loader.load_texture(file_name)
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