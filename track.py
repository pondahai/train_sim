# track.py
# import math
import numpy as math
import numpy as np

INTERPOLATION_STEPS = 10 # 每單位角度或長度的內插步數 (影響平滑度和效能)
TRACK_WIDTH = 1.5       # 軌道寬度
BALLAST_WIDTH = 2.5     # 道碴寬度
BALLAST_HEIGHT = 0.1    # 道碴高度

class TrackSegment:
    """軌道區段基類"""
    def __init__(self, start_pos_3d, start_angle_rad_xz, gradient_permille=0.0):
        # *** 確保 start_pos 是 3D numpy array ***
        self.start_pos = np.array(start_pos_3d, dtype=float)
#         self.start_angle_rad = start_angle_rad # Y 軸旋轉角度 (弧度)
        self.start_angle_rad = start_angle_rad_xz # 水平面上的起始角度 (Y 軸旋轉)
        self.gradient_factor = gradient_permille / 1000.0 # 轉換為每單位水平距離的垂直變化率
        
        self.length = 0 # 這將是軌道的 *實際* 長度 (包含坡度影響下的弧長)
        self.horizontal_length = 0 # 水平投影長度 (用於坡度計算)
        
        self.end_pos = np.copy(self.start_pos)
        self.end_angle_rad = self.start_angle_rad
        self.points = [] # 中心線上的內插點 [(x, y, z), ...]
        self.orientations = [] # 每個點的朝向向量 [(forward_x, forward_z), ...]

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

class CurveTrack(TrackSegment):
    """彎曲軌道 (增加坡度支持)"""
    def __init__(self, start_pos_3d, start_angle_rad_xz, radius, angle_deg, gradient_permille=0.0):
        super().__init__(start_pos_3d, start_angle_rad_xz, gradient_permille)
        self.radius = abs(radius) # 半徑始終為正
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


class Track:
    """管理整個軌道"""
    def __init__(self):
        self.segments = []
        self.total_length = 0.0

    def add_segment(self, segment):
        self.segments.append(segment)
        self.total_length += segment.length

    def clear(self):
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