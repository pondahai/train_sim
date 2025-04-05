# shapes.py
import math
from OpenGL.GL import *
from OpenGL.GLU import *

# --- 標準紋理座標 (常用於 Front, Top, Bottom, Left, Right) ---
tex_coords_standard = [ (1.0, 0.0), (1.0, 1.0), (0.0, 1.0), (0.0, 0.0) ]
# --- 水平翻轉的紋理座標 (用於 Back Face，因為頂點順序是 BR, BL, TL, TR) ---
# 目標: 將 (0,0) 映射到 BL (vertex 1), (1,0) 映射到 BR (vertex 0)
#        將 (0,1) 映射到 TL (vertex 2), (1,1) 映射到 TR (vertex 3)
# 順序對應頂點 0, 1, 2, 3 (BR, BL, TL, TR):
tex_coords_flipped = [ (0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0)  ]
# tex_coords_flipped = [ (0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0) ]

# --- 繪圖輔助函式 ---
def draw_cube(x, y, z, width, depth, height, texture_id=None):
    """繪製一個以 (x, y, z) 為中心點的立方體"""
    w = width / 2.0
    d = depth / 2.0
    h = height # 高度從 y 開始向上

    vertices = [
        (x - w, y + h, z - d), (x + w, y + h, z - d), (x + w, y + h, z + d), (x - w, y + h, z + d), # 上
        (x - w, y,     z - d), (x + w, y,     z - d), (x + w, y,     z + d), (x - w, y,     z + d), # 下
        (x - w, y,     z - d), (x - w, y + h, z - d), (x - w, y + h, z + d), (x - w, y,     z + d), # 左
        (x + w, y,     z - d), (x + w, y + h, z - d), (x + w, y + h, z + d), (x + w, y,     z + d),  # 右
        (x - w, y,     z - d), (x + w, y,     z - d), (x + w, y + h, z - d), (x - w, y + h, z - d), # 前
        (x - w, y,     z + d), (x + w, y,     z + d), (x + w, y + h, z + d), (x - w, y + h, z + d), # 後
    ]
    normals = [
        (0, 0, -1), (0, 0, 1), (0, 1, 0), (0, -1, 0), (-1, 0, 0), (1, 0, 0)
    ]
    
    # 啟用/禁用紋理
    if texture_id is not None:
        glEnable(GL_TEXTURE_2D)
        glBindTexture(GL_TEXTURE_2D, texture_id)
        # 當使用紋理時，讓紋理顏色主導，但仍然受光照影響
        # 如果希望不受光照影響，可以使用 glTexEnvf(GL_TEXTURE_ENV, GL_TEXTURE_ENV_MODE, GL_REPLACE)
        # 但通常希望保留光照，使用預設的 GL_MODULATE
        glColor3f(1.0, 1.0, 1.0) # 設置基礎顏色為白色，避免影響紋理顏色
    else:
        # 如果沒有紋理，確保紋理是禁用的 (雖然 draw_scene 會處理，這裡多一層保險)
        glDisable(GL_TEXTURE_2D)
        # 顏色由外部的 glColor 設定 (在 main.py 的 draw_scene 中)

    glBegin(GL_QUADS)
    for face_index in range(6):
        glNormal3fv(normals[face_index])

        # --- 根據面選擇紋理座標 ---
        if face_index == 4: # Back face 
            current_face_tex_coords = tex_coords_flipped
        elif face_index == 5: # Back face
            current_face_tex_coords = tex_coords_flipped
        else: # All other faces (Front, Top, Bottom, Left, Right)
            current_face_tex_coords = tex_coords_standard
        # --------------------------

        for vertex_index in range(4):
            if texture_id is not None:
                # 使用選擇好的紋理座標
                glTexCoord2fv(current_face_tex_coords[vertex_index])
            # 繪製頂點
            glVertex3fv(vertices[face_index * 4 + vertex_index])
    glEnd()

    # 完成後解綁並禁用紋理
    if texture_id is not None:
        glBindTexture(GL_TEXTURE_2D, 0)
        glDisable(GL_TEXTURE_2D)
        
#     indices = [
#         0, 1, 2, 3,  # 前
#         4, 5, 6, 7,  # 後
#         8, 9, 10, 11, # 上
#         12, 13, 14, 15, # 下
#         16, 17, 18, 19, # 左
#         20, 21, 22, 23  # 右
#     ]
# 
#     glBegin(GL_QUADS)
#     for i in range(0, len(indices), 4):
#         face_normal = normals[i // 4]
#         glNormal3fv(face_normal)
#         for j in range(4):
#             glVertex3fv(vertices[indices[i + j]])
#     glEnd()

def draw_cylinder(x, y, z, radius, height, slices=16, texture_id=None):
    """繪製一個以 (x, y, z) 為底面中心點，沿 Y 軸正方向延伸 (站立) 的圓柱體"""
    quadric = gluNewQuadric()

    # --- Texture Setup ---
    if texture_id is not None:
        glEnable(GL_TEXTURE_2D)
        glBindTexture(GL_TEXTURE_2D, texture_id)
        glColor3f(1.0, 1.0, 1.0) # White base color for texture
        gluQuadricTexture(quadric, GL_TRUE) # Enable auto texture coords generation by GLU
    else:
        glDisable(GL_TEXTURE_2D)
        # Color is set by the caller (main.py) when no texture
        gluQuadricTexture(quadric, GL_FALSE) # Ensure texture coords aren't generated

    # Normals are important for lighting, whether textured or not
    gluQuadricNormals(quadric, GLU_SMOOTH)

    glPushMatrix()
    glTranslatef(x, y, z) # Move to the base center

    # Rotate so the cylinder Z-axis aligns with the world Y-axis
    glRotatef(-90.0, 1.0, 0.0, 0.0)

    # Draw cylinder side (along the new Z-axis, which is world Y)
    # Base radius, top radius, height, slices, stacks
    gluCylinder(quadric, radius, radius, height, slices, 1)

    # Draw top cap (at height along new Z / world Y)
    glPushMatrix()
    glTranslatef(0, 0, height)
    # Disk radius inner, outer, slices, loops
    gluDisk(quadric, 0, radius, slices, 1)
    glPopMatrix()

    # Draw bottom cap (at base Z=0 / world Y=y)
    # Need to flip the disk normals to face downwards (-Y)
    glPushMatrix()
    glRotatef(180, 0, 1, 0) # Rotate around new Y (world X?) to flip normal
    gluDisk(quadric, 0, radius, slices, 1)
    glPopMatrix()

    glPopMatrix() # Restore original matrix

    # --- Clean up texture state ---
    if texture_id is not None:
        glBindTexture(GL_TEXTURE_2D, 0)
        glDisable(GL_TEXTURE_2D)

    gluDeleteQuadric(quadric) # Release quadric object
    


def draw_tree(x, y, z, height, trunk_radius=0.5, foliage_radius=2.0, foliage_layers=3):
    """繪製一棵簡單的樹 (多個圓柱模擬)"""
    trunk_height = height * 0.6
    foliage_part_height = (height * 0.4) / foliage_layers

    # 樹幹
    glColor3f(0.5, 0.35, 0.05) # 棕色
    draw_cylinder(x, y, z, trunk_radius, trunk_height) # No texture for trunk

    # 樹葉 (多層圓柱/圓錐 - 這裡用圓柱簡化)
    glColor3f(0.0, 0.6, 0.2) # 綠色
    current_h = y + trunk_height
    current_r = foliage_radius
    for i in range(foliage_layers):
        layer_h = foliage_part_height + (foliage_layers - 1 - i) * 0.2 # 頂層稍高
        # No texture for foliage
        draw_cylinder(x, current_h, z, current_r * (1.0 - i*0.1), layer_h * (1.2 - i*0.1)) # Make layers slightly different
        # draw_cylinder(x, current_h, z, current_r, layer_h) # Original simple stack
        current_h += layer_h * 0.7 # 稍微重疊
        current_r *= 0.9 # 半徑遞減 slightly faster
        