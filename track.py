# track.py
# import math
import numpy as math
import numpy as np
from OpenGL.GL import * # 需要引入 OpenGL 函數

INTERPOLATION_STEPS = 3 # 每單位角度或長度的內插步數 (影響平滑度和效能)
TRACK_WIDTH = 1.5       # 軌道寬度
BALLAST_WIDTH = 2.5     # 道碴寬度
BALLAST_HEIGHT = 0.1    # 道碴高度

class TrackSegment:
    """軌道區段基類"""
    def __init__(self, start_pos_3d, start_angle_rad_xz, gradient_permille=0.0):
        # *** 確保 start_pos 是 3D numpy array ***
        self.start_pos = np.array(start_pos_3d, dtype=float)
#         self.start_angle_rad = start_angle_rad # Y 軸旋轉角度 (弧度)
        self.angle_deg = 0.0
        self.start_angle_rad = start_angle_rad_xz # 水平面上的起始角度 (Y 軸旋轉)
        self.gradient_factor = gradient_permille / 1000.0 # 轉換為每單位水平距離的垂直變化率
        
        self.length = 0 # 這將是軌道的 *實際* 長度 (包含坡度影響下的弧長)
        self.horizontal_length = 0 # 水平投影長度 (用於坡度計算)
        
        self.end_pos = np.copy(self.start_pos)
        self.end_angle_rad = self.start_angle_rad
        self.points = [] # 中心線上的內插點 [(x, y, z), ...]
        self.orientations = [] # 每個點的朝向向量 [(forward_x, forward_z), ...]
        
        # --- 新增：用於 VBO 的數據 ---
        self.ballast_vertices = [] # 稍後轉換為 NumPy 數組
        self.rail_left_vertices = []
        self.rail_right_vertices = []

        # --- 新增：VBO 和 VAO ID ---
        self.ballast_vbo = None
        self.rail_left_vbo = None
        self.rail_right_vbo = None
        self.ballast_vao = None
        self.rail_left_vao = None
        self.rail_right_vao = None
        # ---------------------------

    def _generate_render_vertices(self):
        """
        根據 self.points 和 self.orientations 生成繪製用的頂點。
        這個方法應該在 points 和 orientations 計算完成後被調用。
        """
        if not self.points or len(self.points) < 2:
            return

        self.ballast_vertices = []
        self.rail_left_vertices = []
        self.rail_right_vertices = []

        half_track_width = TRACK_WIDTH / 2.0
        half_ballast_width = BALLAST_WIDTH / 2.0
        rail_height_offset = BALLAST_HEIGHT + 0.05

        # --- 生成道碴頂面頂點 (使用 GL_TRIANGLES) ---
        # GL_TRIANGLE_STRIP 跨段組合比較麻煩，先用 GL_TRIANGLES 簡化
        for i in range(len(self.points) - 1):
            p1 = self.points[i]
            o1_xz = self.orientations[i]
            r1_xz = np.array([-o1_xz[1], 0, o1_xz[0]]) # Right vector at p1

            p2 = self.points[i+1]
            o2_xz = self.orientations[i+1]
            r2_xz = np.array([-o2_xz[1], 0, o2_xz[0]]) # Right vector at p2

            # 計算四個角點 (道碴頂面)
            bl1 = p1 + r1_xz * half_ballast_width + np.array([0, BALLAST_HEIGHT, 0])
            br1 = p1 - r1_xz * half_ballast_width + np.array([0, BALLAST_HEIGHT, 0])
            bl2 = p2 + r2_xz * half_ballast_width + np.array([0, BALLAST_HEIGHT, 0])
            br2 = p2 - r2_xz * half_ballast_width + np.array([0, BALLAST_HEIGHT, 0])

            # 第一個三角形 (bl1, br1, bl2)
            self.ballast_vertices.extend(bl1.tolist())
            self.ballast_vertices.extend(br1.tolist())
            self.ballast_vertices.extend(bl2.tolist())
            # 第二個三角形 (bl2, br1, br2)
            self.ballast_vertices.extend(bl2.tolist())
            self.ballast_vertices.extend(br1.tolist())
            self.ballast_vertices.extend(br2.tolist())

        # --- 生成軌道頂點 (使用 GL_LINE_STRIP) ---
        for i in range(len(self.points)):
            pos = self.points[i]
            orient_xz = self.orientations[i]
            right_vec_xz = np.array([-orient_xz[1], 0, orient_xz[0]])

            p_rail_left = pos + right_vec_xz * half_track_width + np.array([0, rail_height_offset, 0])
            p_rail_right = pos - right_vec_xz * half_track_width + np.array([0, rail_height_offset, 0])

            self.rail_left_vertices.extend(p_rail_left.tolist())
            self.rail_right_vertices.extend(p_rail_right.tolist())

    def setup_buffers(self):
        """創建並上傳 VBO/VAO 數據"""
        if not self.ballast_vertices: # 確保頂點已生成
             print("警告: setup_buffers 被調用，但頂點尚未生成。")
             return

        # 清理舊的緩衝區 (如果存在)
        self.cleanup_buffers()

        # --- Ballast VBO/VAO ---
        if self.ballast_vertices:
            ballast_data = np.array(self.ballast_vertices, dtype=np.float32)
            self.ballast_vbo = glGenBuffers(1)
            glBindBuffer(GL_ARRAY_BUFFER, self.ballast_vbo)
            glBufferData(GL_ARRAY_BUFFER, ballast_data.nbytes, ballast_data, GL_STATIC_DRAW)

            self.ballast_vao = glGenVertexArrays(1)
            glBindVertexArray(self.ballast_vao)
            glBindBuffer(GL_ARRAY_BUFFER, self.ballast_vbo)
            # 位置屬性 (location=0)
            glVertexAttribPointer(0, 3, GL_FLOAT, GL_FALSE, 3 * sizeof(GLfloat), ctypes.c_void_p(0))
            glEnableVertexAttribArray(0)
            # 可以添加法線屬性等，如果需要光照
            # glVertexAttribPointer(1, 3, GL_FLOAT, GL_FALSE, 6 * sizeof(GLfloat), ctypes.c_void_p(3 * sizeof(GLfloat))) # 假設數據是 [vx,vy,vz, nx,ny,nz, ...]
            # glEnableVertexAttribArray(1)
            glBindVertexArray(0) # 解綁 VAO
            glBindBuffer(GL_ARRAY_BUFFER, 0) # 解綁 VBO

        # --- Left Rail VBO/VAO ---
        if self.rail_left_vertices:
            rail_left_data = np.array(self.rail_left_vertices, dtype=np.float32)
            self.rail_left_vbo = glGenBuffers(1)
            glBindBuffer(GL_ARRAY_BUFFER, self.rail_left_vbo)
            glBufferData(GL_ARRAY_BUFFER, rail_left_data.nbytes, rail_left_data, GL_STATIC_DRAW)

            self.rail_left_vao = glGenVertexArrays(1)
            glBindVertexArray(self.rail_left_vao)
            glBindBuffer(GL_ARRAY_BUFFER, self.rail_left_vbo)
            glVertexAttribPointer(0, 3, GL_FLOAT, GL_FALSE, 3 * sizeof(GLfloat), ctypes.c_void_p(0))
            glEnableVertexAttribArray(0)
            glBindVertexArray(0)
            glBindBuffer(GL_ARRAY_BUFFER, 0)

        # --- Right Rail VBO/VAO ---
        if self.rail_right_vertices:
            rail_right_data = np.array(self.rail_right_vertices, dtype=np.float32)
            self.rail_right_vbo = glGenBuffers(1)
            glBindBuffer(GL_ARRAY_BUFFER, self.rail_right_vbo)
            glBufferData(GL_ARRAY_BUFFER, rail_right_data.nbytes, rail_right_data, GL_STATIC_DRAW)

            self.rail_right_vao = glGenVertexArrays(1)
            glBindVertexArray(self.rail_right_vao)
            glBindBuffer(GL_ARRAY_BUFFER, self.rail_right_vbo)
            glVertexAttribPointer(0, 3, GL_FLOAT, GL_FALSE, 3 * sizeof(GLfloat), ctypes.c_void_p(0))
            glEnableVertexAttribArray(0)
            glBindVertexArray(0)
            glBindBuffer(GL_ARRAY_BUFFER, 0)

        print(f"緩衝區已創建: Ballast VAO={self.ballast_vao}, Rail Left VAO={self.rail_left_vao}, Rail Right VAO={self.rail_right_vao}")

    def create_gl_buffers(self):
        self.setup_buffers()
        
    def cleanup_buffers(self):
        """刪除 OpenGL 緩衝區"""
        if self.ballast_vao: glDeleteVertexArrays(1, [self.ballast_vao])
        if self.rail_left_vao: glDeleteVertexArrays(1, [self.rail_left_vao])
        if self.rail_right_vao: glDeleteVertexArrays(1, [self.rail_right_vao])
        if self.ballast_vbo: glDeleteBuffers(1, [self.ballast_vbo])
        if self.rail_left_vbo: glDeleteBuffers(1, [self.rail_left_vbo])
        if self.rail_right_vbo: glDeleteBuffers(1, [self.rail_right_vbo])
        self.ballast_vao, self.rail_left_vao, self.rail_right_vao = None, None, None
        self.ballast_vbo, self.rail_left_vbo, self.rail_right_vbo = None, None, None

    def get_position_orientation(self, distance_on_segment):
        """根據在該段上的距離，獲取位置和朝向"""
        if not self.points or self.length == 0:
            return self.start_pos, (math.cos(self.start_angle_rad), math.sin(self.start_angle_rad))

        # 計算索引 (確保在範圍內)
        # 根據 *實際* 段長度計算比例
        ratio = distance_on_segment / self.length        
        index = int(ratio * (len(self.points) - 1))
        index = max(0, min(index, len(self.points) - 2)) # 確保至少有下一個點

        # 計算在兩個內插點之間的比例 t
        segment_len_per_point = self.length / (len(self.points) - 1)
        t = (distance_on_segment - index * segment_len_per_point) / segment_len_per_point
        t = max(0.0, min(1.0, t)) # 限制 t 在 0 到 1 之間

        # 線性內插 3D 位置
        pos1 = self.points[index]
        pos2 = self.points[index + 1]
        interpolated_pos = pos1 + t * (pos2 - pos1) # Numpy 會自動處理 3D 插值

        # 線性內插朝向 (簡單方法，對劇烈轉彎可能不完美，但適用於本例)
        # 可以考慮用球面線性內插 (Slerp) 獲取更平滑的旋轉
        orient1 = self.orientations[index]
        orient2 = self.orientations[index + 1]
        interpolated_orient = orient1 + t * (orient2 - orient1)
        norm = np.linalg.norm(interpolated_orient)
        if norm > 1e-6: # 避免除以零
             interpolated_orient /= norm # 重新標準化

        # 朝向向量 (forward_x, forward_z)
        forward_vector_xz  = (interpolated_orient[0], interpolated_orient[1])

        return interpolated_pos, forward_vector_xz

class StraightTrack(TrackSegment):
    """直軌道 (增加坡度支持)"""
    def __init__(self, start_pos_3d, start_angle_rad_xz, length, gradient_permille=0.0):
        super().__init__(start_pos_3d, start_angle_rad_xz, gradient_permille)
        self.horizontal_length = length # 直線的水平長度就是其定義的 length
        # 計算實際長度 (勾股定理)
        vertical_change = self.horizontal_length * self.gradient_factor
        self.length = math.sqrt(self.horizontal_length**2 + vertical_change**2)
        
        # 水平方向向量
        forward_vector_xz = np.array([math.cos(start_angle_rad_xz), math.sin(start_angle_rad_xz)])
        forward_vector_horizontal_3d = np.array([forward_vector_xz[0], 0, forward_vector_xz[1]])
        
#         self.end_pos = self.start_pos + forward_vector * length
#         self.end_angle_rad = start_angle_rad

        # 計算結束點 3D 坐標
        self.end_pos = self.start_pos + forward_vector_horizontal_3d * self.horizontal_length \
                      + np.array([0, vertical_change, 0])
        self.end_angle_rad = start_angle_rad_xz # 水平角度不變

        # 計算內插點 (包含 Y 坐標)
        num_steps = max(2, int(self.horizontal_length * INTERPOLATION_STEPS / 5))
        if num_steps < 2: num_steps = 2
        for i in range(num_steps):
            t = i / (num_steps - 1)
            current_horizontal_dist = t * self.horizontal_length
            current_vertical_change = current_horizontal_dist * self.gradient_factor
            point_pos = self.start_pos + forward_vector_horizontal_3d * current_horizontal_dist \
                       + np.array([0, current_vertical_change, 0])
            self.points.append(point_pos)
            self.orientations.append(forward_vector_xz) # 水平方向

        self.points = [] # 重置以確保從頭開始填充
        self.orientations = []
        forward_vector_xz = np.array([np.cos(start_angle_rad_xz), np.sin(start_angle_rad_xz)])
        forward_vector_horizontal_3d = np.array([forward_vector_xz[0], 0, forward_vector_xz[1]])
        vertical_change = self.horizontal_length * self.gradient_factor
        self.end_pos = self.start_pos + forward_vector_horizontal_3d * self.horizontal_length \
                       + np.array([0, vertical_change, 0])
        self.end_angle_rad = start_angle_rad_xz
        # --- 重新計算內插點 ---
        num_steps = max(2, int(self.horizontal_length * INTERPOLATION_STEPS / 5)) # 調整 INTERPOLATION_STEPS 值可能影響效能與平滑度
        if num_steps < 2: num_steps = 2
        for i in range(num_steps):
             t = i / (num_steps - 1)
             current_horizontal_dist = t * self.horizontal_length
             current_vertical_change = current_horizontal_dist * self.gradient_factor
             point_pos = self.start_pos + forward_vector_horizontal_3d * current_horizontal_dist \
                        + np.array([0, current_vertical_change, 0])
             self.points.append(point_pos)
             self.orientations.append(forward_vector_xz) # Orientation is constant
        # --- 生成繪圖頂點 ---
        self._generate_render_vertices()
        # --- 創建 VBO/VAO ---
#         self.setup_buffers() # 在初始化時就創建好

class CurveTrack(TrackSegment):
    """彎曲軌道 (增加坡度支持)"""
    def __init__(self, start_pos_3d, start_angle_rad_xz, radius, angle_deg, gradient_permille=0.0):
        super().__init__(start_pos_3d, start_angle_rad_xz, gradient_permille)
        self.radius = abs(radius) # 半徑始終為正
        self.angle_deg = angle_deg
        self.angle_rad = math.radians(angle_deg)
        # 水平弧長
        self.horizontal_length = self.radius * abs(self.angle_rad)
        # 計算實際弧長 (近似：將梯度應用於水平弧長，對於大多數情況足夠)
        # 更精確需要積分，但通常差異不大
        vertical_change = self.horizontal_length * self.gradient_factor
        # self.length = math.sqrt(self.horizontal_length**2 + vertical_change**2) # 這不對，弧長本身就是距離
        # 近似計算實際長度 (如果坡度很大，可以考慮更複雜的模型)
        # 簡單處理：假設實際長度約等於水平弧長，坡度主要影響 Y 坐標
        # 或者，使用一個小的修正因子，但我們先用水平弧長計算 Y
        self.length = self.horizontal_length # 假設行駛距離按水平弧長算 (用於 distance_on_segment)

        turn_direction = 1.0 if self.angle_rad > 0 else -1.0
        perp_angle = start_angle_rad_xz + turn_direction * math.pi / 2.0
        center_offset_xz = np.array([math.cos(perp_angle), math.sin(perp_angle)]) * self.radius
        # 計算圓心 (假設圓心在同一水平面上)
        self.center_xz = np.array([self.start_pos[0], self.start_pos[2]]) + center_offset_xz

        # 計算水平結束角度和位置
        self.end_angle_rad = start_angle_rad_xz + self.angle_rad
        end_offset_angle = start_angle_rad_xz - turn_direction * math.pi / 2.0 + self.angle_rad
        end_offset_xz = np.array([math.cos(end_offset_angle), math.sin(end_offset_angle)]) * self.radius
        end_pos_xz = self.center_xz + end_offset_xz

        # 計算結束點 Y 坐標
        end_pos_y = self.start_pos[1] + vertical_change
        self.end_pos = np.array([end_pos_xz[0], end_pos_y, end_pos_xz[1]])

        # 計算內插點
        num_steps = max(2, int(abs(angle_deg) * INTERPOLATION_STEPS / 5))
        if num_steps < 2: num_steps = 2
        start_angle_offset = start_angle_rad_xz - turn_direction * math.pi / 2.0

        for i in range(num_steps):
            t = i / (num_steps - 1)
            current_angle = start_angle_offset + t * self.angle_rad

            # 計算水平位置 (XZ平面)
            point_offset_xz = np.array([math.cos(current_angle), math.sin(current_angle)]) * self.radius
            current_pos_xz = self.center_xz + point_offset_xz

            # 計算 Y 坐標
            current_horizontal_arc_len = t * self.horizontal_length
            current_vertical_change = current_horizontal_arc_len * self.gradient_factor
            current_pos_y = self.start_pos[1] + current_vertical_change

            # 合成 3D 點
            self.points.append(np.array([current_pos_xz[0], current_pos_y, current_pos_xz[1]]))

            # 計算該點的水平切線方向 (朝前)
            tangent_angle = current_angle + turn_direction * math.pi / 2.0
            orientation_vec_xz = np.array([math.cos(tangent_angle), math.sin(tangent_angle)])
            self.orientations.append(orientation_vec_xz)

        self.points = [] # 重置
        self.orientations = []
        self.radius = abs(radius)
        self.angle_rad = np.radians(angle_deg)
        self.horizontal_length = self.radius * abs(self.angle_rad)
        vertical_change = self.horizontal_length * self.gradient_factor
        self.length = self.horizontal_length # Assume driving distance is horizontal arc length

        turn_direction = 1.0 if self.angle_rad > 0 else -1.0
        perp_angle = start_angle_rad_xz + turn_direction * np.pi / 2.0
        center_offset_xz = np.array([np.cos(perp_angle), np.sin(perp_angle)]) * self.radius
        self.center_xz = np.array([self.start_pos[0], self.start_pos[2]]) + center_offset_xz

        self.end_angle_rad = start_angle_rad_xz + self.angle_rad
        end_offset_angle = start_angle_rad_xz - turn_direction * np.pi / 2.0 + self.angle_rad
        end_offset_xz = np.array([np.cos(end_offset_angle), np.sin(end_offset_angle)]) * self.radius
        end_pos_xz = self.center_xz + end_offset_xz
        end_pos_y = self.start_pos[1] + vertical_change
        self.end_pos = np.array([end_pos_xz[0], end_pos_y, end_pos_xz[1]])

        # --- 重新計算內插點 ---
        num_steps = max(2, int(abs(angle_deg) * INTERPOLATION_STEPS / 5))
        if num_steps < 2: num_steps = 2
        start_angle_offset = start_angle_rad_xz - turn_direction * np.pi / 2.0

        for i in range(num_steps):
            t = i / (num_steps - 1)
            current_angle = start_angle_offset + t * self.angle_rad
            point_offset_xz = np.array([np.cos(current_angle), np.sin(current_angle)]) * self.radius
            current_pos_xz = self.center_xz + point_offset_xz
            current_horizontal_arc_len = t * self.horizontal_length
            current_vertical_change = current_horizontal_arc_len * self.gradient_factor
            current_pos_y = self.start_pos[1] + current_vertical_change
            self.points.append(np.array([current_pos_xz[0], current_pos_y, current_pos_xz[1]]))
            tangent_angle = current_angle + turn_direction * np.pi / 2.0
            orientation_vec_xz = np.array([np.cos(tangent_angle), np.sin(tangent_angle)])
            self.orientations.append(orientation_vec_xz)
        # --- 生成繪圖頂點 ---
        self._generate_render_vertices()
        # --- 創建 VBO/VAO ---
#         self.setup_buffers() # 在初始化時就創建好

class Track:
    """管理整個軌道"""
    def __init__(self):
        self.segments = []
        self.total_length = 0.0

    def add_segment(self, segment):
        self.segments.append(segment)
        self.total_length += segment.length

    def create_all_segment_buffers(self):
        """Creates OpenGL buffers for all segments in the track."""
        print(f"Creating GL buffers for {len(self.segments)} track segments...")
        for i, segment in enumerate(self.segments):
            # print(f"  Processing segment {i+1}/{len(self.segments)} ({type(segment).__name__})")
            if hasattr(segment, 'create_gl_buffers') and callable(segment.create_gl_buffers):
                segment.create_gl_buffers() # Call the method to create buffers
            else:
                print(f"  Warning: Segment {type(segment)} has no create_gl_buffers method.")

    def clear(self):
        # 在清除段之前，先清理它們的 OpenGL 資源
        for segment in self.segments:
            segment.cleanup_buffers()
        self.segments = []
        self.total_length = 0.0

    def get_position_orientation(self, distance_on_track):
        """根據在總軌道上的距離獲取位置和朝向"""
        if self.total_length == 0:
            return np.array([0.0, 0.0, 0.0]), (1.0, 0.0) # 預設位置和朝向

        current_dist = 0.0
        for segment in self.segments:
            if distance_on_track <= current_dist + segment.length + 1e-6: # 加一點容錯
                distance_on_segment = distance_on_track - current_dist
                return segment.get_position_orientation(distance_on_segment)
            current_dist += segment.length

        # 如果距離超出總長度 (理論上循環時不應到達這裡，除非不循環)
        # 返回最後一段的末端
        last_segment = self.segments[-1]
        end_forward_xz  = (math.cos(last_segment.end_angle_rad), math.sin(last_segment.end_angle_rad))
        return last_segment.end_pos, end_forward_xz
    
    def __del__(self):
        # 可選：確保在 Track 對象被垃圾回收時清理緩衝區
        self.clear()
    