# cabin.py
from OpenGL.GL import *
from OpenGL.GLU import *
import math

def draw_dashboard(width=1.8, height=0.6, depth=0.5):
    """在攝影機前方繪製一個簡單的儀表板"""
    glColor3f(0.2, 0.2, 0.25) # 深灰色儀表板
    glPushMatrix()
    # 稍微向下、向前移動，使其位於視角下方
    glTranslatef(0.0, -0.5, -0.8)
    glScalef(width, height, depth)

    # 繪製一個立方體作為儀表板基座
    vertices = [
        (-0.5, -0.5, -0.5), (0.5, -0.5, -0.5), (0.5, 0.5, -0.5), (-0.5, 0.5, -0.5), # 前
        (-0.5, -0.5, 0.5), (0.5, -0.5, 0.5), (0.5, 0.5, 0.5), (-0.5, 0.5, 0.5), # 後
        (-0.5, 0.5, -0.5), (0.5, 0.5, -0.5), (0.5, 0.5, 0.5), (-0.5, 0.5, 0.5), # 上
        (-0.5, -0.5, -0.5), (0.5, -0.5, -0.5), (0.5, -0.5, 0.5), (-0.5, -0.5, 0.5), # 下
        (-0.5, -0.5, -0.5), (-0.5, 0.5, -0.5), (-0.5, 0.5, 0.5), (-0.5, -0.5, 0.5), # 左
        (0.5, -0.5, -0.5), (0.5, 0.5, -0.5), (0.5, 0.5, 0.5), (0.5, -0.5, 0.5)  # 右
    ]
    indices = [
        0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23
    ]
    glBegin(GL_QUADS)
    for i in range(0, len(indices), 4):
         # 這裡為了簡單，省略了法線計算，效果可能不完美
        for j in range(4):
            glVertex3fv(vertices[indices[i + j]])
    glEnd()
    glPopMatrix()

def draw_control_lever(position_x=0.6, position_y=-0.4, position_z=-0.6, level=0.0):
    """繪製一個簡單的控制桿"""
    # level: -1 (後退) 到 1 (前進)
    max_angle = 45.0 # 控制桿最大傾斜角度
    angle = -level * max_angle

    glColor3f(0.8, 0.8, 0.8) # 銀灰色
    glPushMatrix()
    glTranslatef(position_x, position_y, position_z)

    # 底座 (小圓柱)
    quadric = gluNewQuadric()
    gluCylinder(quadric, 0.05, 0.05, 0.1, 8, 1)

    # 操縱桿
    glTranslatef(0, 0.1, 0) # 移到基座頂部
    glRotatef(angle, 0, 0, 1) # 繞 Z 軸旋轉 (前後傾斜)
    gluCylinder(quadric, 0.03, 0.02, 0.4, 8, 1) # 向上變細

    # 頂部球
    glTranslatef(0, 0.4, 0)
    # gluSphere(quadric, 0.05, 8, 8) # 如果需要球體

    gluDeleteQuadric(quadric)
    glPopMatrix()

def draw_window_frame():
    """繪製前景窗的邊框 (線條)"""
    # 這個比較 tricky，因為它應該固定在螢幕上
    # 方法1: 在世界座標系下繪製一個非常靠近攝影機的大框 (簡單但不完美)
    # 方法2: 切換到正交投影繪製 HUD (較好但複雜)
    # 這裡用方法1示意

    frame_dist = 0.1 # 邊框離攝影機多近
    frame_width = 1.9 * frame_dist # 根據視角和距離調整
    frame_height = 1.1 * frame_dist

    glColor3f(0.1, 0.1, 0.1)
    glLineWidth(5.0)
    glBegin(GL_LINE_LOOP)
    glVertex3f(-frame_width/2, -frame_height/2, -frame_dist)
    glVertex3f( frame_width/2, -frame_height/2, -frame_dist)
    glVertex3f( frame_width/2,  frame_height/2, -frame_dist)
    glVertex3f(-frame_width/2,  frame_height/2, -frame_dist)
    glEnd()
    glLineWidth(1.0)