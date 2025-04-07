# camera.py
import math
import numpy as np
from OpenGL.GLU import gluLookAt

# 攝影機相對於電車中心的位置 (駕駛艙視角)
CAMERA_OFFSET_Y = 2.6  # 高度
CAMERA_OFFSET_Z = 0.5  # 稍微向前一點

class Camera:
    def __init__(self):
        self.yaw = 0.0   # 水平角度 (繞 Y 軸)
        self.pitch = 0.0 # 垂直角度 (繞 X 軸)
        self.mouse_sensitivity = 0.1
        self.mouse_locked = True
        self.max_pitch = 89.0
        self.min_pitch = -89.0

        # 這些將由電車更新
        self.base_position = np.array([0.0, 0.0, 0.0])
        self.base_forward = np.array([0.0, 0.0, 1.0]) # 電車朝向 (X, Z) 平面
        self.base_up = np.array([0.0, 1.0, 0.0])      # 電車的上方向量

    def update_angles(self, dx, dy):
        """根據滑鼠移動更新視角角度"""
        if not self.mouse_locked:
            self.yaw -= dx * self.mouse_sensitivity
            self.pitch -= dy * self.mouse_sensitivity # Y 軸反轉

            # 限制 Pitch 角度
            self.pitch = max(self.min_pitch, min(self.max_pitch, self.pitch))

            # 限制 Yaw 角度在 0-360 或 -180-180 之間 (可選)
            self.yaw %= 360.0

    def set_mouse_lock(self, locked):
        self.mouse_locked = locked

    def update_position_orientation(self, tram_pos_3d, tram_forward_xz):
        """更新攝影機的基礎位置和朝向 (來自電車)"""
        # tram_forward_xz 是 (forward_x, forward_z)
        # 構建水平朝向的 3D 向量
        forward_3d_horizontal = np.array([tram_forward_xz[0], 0.0, tram_forward_xz[1]])
        forward_3d_horizontal /= np.linalg.norm(forward_3d_horizontal) # 確保單位化

        # 基礎 up 向量 (仍然是世界 Y 軸，假設相機平台不隨坡度傾斜)
        base_up = np.array([0.0, 1.0, 0.0])
        # 計算基礎位置 (考慮偏移量)
        # tram_pos_3d 是電車在軌道上的 3D 點
        # 垂直偏移應用 base_up
        # 水平偏移應用 forward_3d_horizontal
        self.base_position = tram_pos_3d + base_up * CAMERA_OFFSET_Y + forward_3d_horizontal * CAMERA_OFFSET_Z
        
        # 基礎朝向仍然是水平的 (除非你想讓相機隨坡度自動俯仰)
        self.base_forward = forward_3d_horizontal
        # 假設電車始終是水平的，基礎 up 向量總是 (0, 1, 0)
        # 如果需要支援軌道傾斜，這裡需要更複雜的計算
        self.base_up = base_up

    def apply_view(self):
        """計算最終的 LookAt 參數並應用到 OpenGL"""
        # --- 基礎向量 ---
        eye_pos = self.base_position
        tram_forward = self.base_forward # 已經是單位向量 (x, 0, z)
        # 穩定的基礎 up 向量 (假設電車不翻滾)
        world_up = np.array([0.0, 1.0, 0.0])
        
        yaw_rad = math.radians(self.yaw)
        pitch_rad = math.radians(self.pitch)

        # 1. 計算基礎的右向量
        right_vector = np.cross(self.base_forward, self.base_up)
        right_vector /= np.linalg.norm(right_vector)

        # 2. 圍繞基礎 up 向量旋轉 (Yaw)
        # 使用旋轉矩陣或四元數更精確，這裡用簡單三角函數近似
        # 先計算初始的 look_at 點 (未經滑鼠調整)
        initial_look_at = self.base_position + self.base_forward

        # 3. 圍繞基礎 right 向量旋轉 (Pitch)
        # 計算最終的視線方向向量
        # 從基礎 forward 開始
        direction = np.copy(self.base_forward)

        # 應用 Yaw 旋轉 (繞 Y 軸)
        # R_y = [[cos(y), 0, sin(y)], [0, 1, 0], [-sin(y), 0, cos(y)]]
        cy = math.cos(yaw_rad)
        sy = math.sin(yaw_rad)
        rotated_x = direction[0] * cy + direction[2] * sy
        rotated_z = -direction[0] * sy + direction[2] * cy
        direction[0] = rotated_x
        direction[2] = rotated_z

        # 應用 Pitch 旋轉 (繞計算出的 Right 軸)
        # R_axis = I + sin(p)*K + (1-cos(p))*K^2, K 是 right_vector 的反對稱矩陣
        # 簡化：直接在 YZ' 平面（旋轉後）或 XY' 平面（旋轉後）計算 pitch
        # 或者，更簡單的方式：計算球面坐標
        # 注意：這裡的 pitch 是相對於電車的水平面
        final_dir_x = math.cos(pitch_rad) * direction[0]
        final_dir_y = math.sin(pitch_rad) # 相對於局部水平面
        final_dir_z = math.cos(pitch_rad) * direction[2]

        final_direction = np.array([final_dir_x, final_dir_y, final_dir_z])
        # 確保向量被正確旋轉（需要考慮 base_forward 和 base_up）
        # --- 更可靠的方法：使用 look_at 點 ---
        # 計算相對於基礎方向的偏移量
        offset = np.array([
            math.cos(pitch_rad) * math.sin(yaw_rad), # X 分量受 Yaw 影響
            math.sin(pitch_rad),                    # Y 分量只受 Pitch 影響
            math.cos(pitch_rad) * math.cos(yaw_rad) # Z 分量受 Yaw 影響 (假設基礎朝向 Z+)
        ])

        # 需要將這個 offset 旋轉到電車的坐標系中
        # forward = base_forward
        # up = base_up
        # right = np.cross(forward, up)
        # 建立旋轉矩陣 T = [right, up, -forward] (OpenGL 視圖矩陣的逆)
        # final_direction = T * offset (矩陣向量乘法)
        # 這部分有點複雜，先用近似法：直接組合 look_at 點

        # --- 近似 look_at 點計算 ---
        # 1. 基礎 look_at (沿電車方向)
#         base_look_target = self.base_position + self.base_forward
        base_angle_y_rad = math.atan2(tram_forward[0], tram_forward[2]) # 繞 Y 軸從 +Z 到 tram_forward 的角度
        final_yaw_rad = base_angle_y_rad + yaw_rad # 疊加滑鼠 yaw
        
        # 2. 計算滑鼠控制的旋轉後的方向向量 (相對於世界坐標系，近似)
        # (這部分最容易出錯，精確計算需要四元數或旋轉矩陣)
#         look_dir = np.array([
#             math.cos(pitch_rad) * math.sin(yaw_rad + math.atan2(self.base_forward[2], self.base_forward[0])),
#             math.sin(pitch_rad),
#             math.cos(pitch_rad) * math.cos(yaw_rad + math.atan2(self.base_forward[2], self.base_forward[0]))
#         ])
#         look_dir /= np.linalg.norm(look_dir) # 標準化
        dir_x = math.cos(pitch_rad) * math.sin(final_yaw_rad)
        dir_y = math.sin(pitch_rad) # 垂直分量
        dir_z = math.cos(pitch_rad) * math.cos(final_yaw_rad)

        look_dir = np.array([dir_x, dir_y, dir_z])
        # 確保 look_dir 是單位向量 (理論上如果 pitch/yaw 正確計算就應該是)
        norm = np.linalg.norm(look_dir)
        if norm > 1e-6:
            look_dir /= norm
        else: # 防止零向量
            look_dir = tram_forward # 出錯時預設看前方

        # 計算最終 look_at 點
#         final_look_at_target = self.base_position + look_dir
        # 2. 計算最終觀察目標點
        look_at_pos = eye_pos + look_dir

        # 獲取最終的 up 向量 (也受 pitch 影響)
        # 簡單處理：只要 pitch 不是 +/- 90 度，世界 Y 軸通常可以作為 up
        # 為了更穩定，可以計算 right 向量，然後叉乘得到精確 up
#         final_right = np.cross(look_dir, self.base_up)
#         final_up = np.cross(final_right, look_dir)
#         if np.linalg.norm(final_up) < 1e-6: # 避免向量接近零
#              final_up = self.base_up # 備用
# 
#         final_up /= np.linalg.norm(final_up)
        # 3. 計算最終的 Up 向量
        #    一個常見且較穩定的方法：
        #    a) 計算右向量 (right = look_dir x world_up)
        #    b) 重新計算上向量 (up = right x look_dir)
        #    這可以處理 look_dir 接近 world_up 的情況 (萬向鎖問題)

        #    如果視線沒有接近正上方或正下方，可以直接用 world_up
        if abs(np.dot(look_dir, world_up)) < 0.99: # 檢查是否接近垂直
            final_right = np.cross(look_dir, world_up)
            final_up = np.cross(final_right, look_dir)
        else:
            # 如果看得太垂直，world_up 不穩定，改用電車前方作為參考來計算 right
            final_right = np.cross(world_up, look_dir) # 注意叉乘順序可能影響方向
            # 或者用電車前方計算 right
            # final_right = np.cross(tram_forward, look_dir) # 可能也不穩定

            # 備用策略：當看垂直時，強制 up 為電車的 Z 軸方向的反方向？
            # 或者簡單地使用一個固定的備用 up (如 [0, 0, 1] 或 [0, 0, -1] 取決於哪個更穩定)
            # 最簡單的處理：當垂直時，保持之前的 up 或使用 world_up (可能會跳一下)
            # 讓我們嘗試用 world_up 計算 right，再計算 up
            final_right = np.cross(look_dir, world_up) # 即使垂直，這個 right 應該還是有效的 (除了完全重合)
            if np.linalg.norm(final_right) < 1e-6: # 如果完全重合 (不太可能)
                 # 如果看向 Y+，right 可以是 X+
                 if look_dir[1] > 0: final_right = np.array([1.0, 0.0, 0.0])
                 # 如果看向 Y-，right 可以是 X- (或 X+?)
                 else: final_right = np.array([-1.0, 0.0, 0.0])

            final_up = np.cross(final_right, look_dir)


        # 確保 final_up 是單位向量
        norm_up = np.linalg.norm(final_up)
        if norm_up > 1e-6:
            final_up /= norm_up
        else:
            final_up = world_up # 極端情況下的回退


        # 應用 OpenGL 的 gluLookAt
#         gluLookAt(
#             self.base_position[0], self.base_position[1], self.base_position[2], # Eye position
#             final_look_at_target[0], final_look_at_target[1], final_look_at_target[2], # Look at point
#             final_up[0], final_up[1], final_up[2]             # Up vector
#         )
        # --- 應用 gluLookAt ---
        gluLookAt(
            eye_pos[0], eye_pos[1], eye_pos[2],         # Eye position
            look_at_pos[0], look_at_pos[1], look_at_pos[2], # Look at point
            final_up[0], final_up[1], final_up[2]       # Up vector
        )

