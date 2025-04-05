# track.py
import math
from OpenGL.GL import *

# --- 軌道相關 ---
TRACK_WIDTH = 4.0  # 軌道範圍色塊寬度
RAIL_GAUGE = 1.435 # 標準軌距 (視覺用)
RAIL_OFFSET = RAIL_GAUGE / 2.0
SEGMENT_LENGTH = 1.0 # 直線和曲線的基礎分段長度，越小越平滑

class Track:
    def __init__(self):
        self.segments = [] # 原始定義: ('straight', length) or ('curve', radius, angle)
        self.points = []   # 預處理後的軌道中心點 [(x, y, z), ...]
        self.tangents = [] # 預處理後的軌道切線方向 [(dx, dy, dz), ...]
        self.cumulative_distances = [] # 每個點距離起點的累計距離 [dist, ...]
        self.total_length = 0.0
        self.filepath = None # Store filepath for reloading checks

    def add_segment(self, segment_type, *args):
        self.segments.append((segment_type, args))

    def reset(self):
        """Clears all track data."""
        self.segments.clear()
        self.points.clear()
        self.tangents.clear()
        self.cumulative_distances.clear()
        self.total_length = 0.0
        # Keep self.filepath
        
    def preprocess(self, start_pos=(0, 0, 0), start_dir=(0, 0, 1)):
        """根據 segments 生成詳細的 points, tangents 和 cumulative_distances"""
        self.points = [start_pos]
        
        # Ensure start tangent is normalized
        start_dir_len = math.sqrt(start_dir[0]**2 + start_dir[1]**2 + start_dir[2]**2)
        if start_dir_len > 1e-6:
             start_dir_norm = (start_dir[0]/start_dir_len, start_dir[1]/start_dir_len, start_dir[2]/start_dir_len)
        else:
             start_dir_norm = (0, 0, 1) # Default if zero vector provided
        self.tangents = [start_dir_norm]
        
        self.cumulative_distances = [0.0]
        self.total_length = 0.0 # Reset total length
        
        current_pos = list(start_pos)
        current_dir = list(start_dir) # 方向向量 (假設起始沿 Z 軸正方向)
        total_dist = 0.0

        if not self.segments:
            print("警告: 軌道定義為空，無法預處理。")
            return # Exit early if no segments

        for segment_type, args in self.segments:
            if segment_type == 'straight':
                length = args[0]
                num_segments = max(1, int(length / SEGMENT_LENGTH))
                segment_len = length / num_segments

                for _ in range(num_segments):
                    current_pos[0] += current_dir[0] * segment_len
                    current_pos[1] += current_dir[1] * segment_len # Y 保持不變 (除非有坡度)
                    current_pos[2] += current_dir[2] * segment_len
                    total_dist += segment_len

                    self.points.append(tuple(current_pos))
                    self.tangents.append(tuple(current_dir))
                    self.cumulative_distances.append(total_dist)

            elif segment_type == 'curve':
                radius = args[0]
                angle_deg = args[1]
                 # Ensure radius is not zero
                if abs(radius) < 1e-6:
                    print(f"警告: 曲線半徑接近零 ({radius})，跳過此段。")
                    continue
               
                angle_rad = math.radians(angle_deg)
                arc_length = abs(radius * angle_rad)
                num_segments = max(2, int(arc_length / SEGMENT_LENGTH)) # 曲線至少分2段
                segment_angle = angle_rad / num_segments
                # Calculate segment length based on chord length for better accuracy?
                # Or stick to arc length segment for simplicity? Sticking to arc length for now.
                segment_len = arc_length / num_segments # Each small segment's arc length
#                 segment_len = abs(radius * segment_angle) # 每小段的弧長

                # 計算圓心
                # 切線方向 (dx, dy, dz)
                # 法線方向 (指向圓心) - 假設在 XZ 平面
                # 左轉 (angle_deg > 0): 法線 = (-dz, 0, dx)
                # 右轉 (angle_deg < 0): 法線 = (dz, 0, -dx)
                # Normal vector points towards center: Left turn (+angle) -> (-dz, 0, dx), Right turn (-angle) -> (dz, 0, -dx)
                turn_sign = math.copysign(1.0, angle_rad)
                norm_dir = (-current_dir[2] * turn_sign, 0, current_dir[0] * turn_sign)
#                 norm_dir = ( -current_dir[2] * math.copysign(1, angle_rad),
#                              0,
#                              current_dir[0] * math.copysign(1, angle_rad) )
                center_x = current_pos[0] + norm_dir[0] * radius
                center_z = current_pos[2] + norm_dir[2] * radius

                # 迭代生成曲線上的點
                # Starting angle relative to center
                start_vec_x = current_pos[0] - center_x
                start_vec_z = current_pos[2] - center_z
                start_angle = math.atan2(start_vec_z, start_vec_x) # atan2(y, x)
#                 start_angle = math.atan2(current_pos[2] - center_z, current_pos[0] - center_x)

                for i in range(1, num_segments + 1):
                    current_angle = start_angle + i * segment_angle

                    # 新位置
                    new_x = center_x + radius * math.cos(current_angle)
                    new_z = center_z + radius * math.sin(current_angle)
                    current_pos = [new_x, current_pos[1], new_z] # Y 不變

                    # 新切線方向 (垂直於半徑方向)
                    # 半徑向量: (new_x - center_x, 0, new_z - center_z)
                    # 左轉切線: (-sin, 0, cos) -> (- (new_z-center_z)/radius, 0, (new_x-center_x)/radius)
                    # 右轉切線: (sin, 0, -cos) -> ( (new_z-center_z)/radius, 0, -(new_x-center_x)/radius)
                    radius_x = new_x - center_x
                    radius_z = new_z - center_z
                    tangent_x = -radius_z * turn_sign
                    tangent_z = radius_x * turn_sign
#                     tangent_x = -(new_z - center_z) / radius * math.copysign(1, angle_rad)
#                     tangent_z = (new_x - center_x) / radius * math.copysign(1, angle_rad)
                    # 歸一化 (理論上已經是單位向量)
                    # length = math.sqrt(tangent_x**2 + tangent_z**2)
                    # if length > 1e-6:
                    #     tangent_x /= length
                    #     tangent_z /= length
                    # Normalize the tangent
                    t_len = math.sqrt(tangent_x**2 + tangent_z**2)
                    if t_len > 1e-6:
                        tangent_x /= t_len
                        tangent_z /= t_len
                    else: # Should not happen if radius is non-zero
                        tangent_x = current_dir[0]
                        tangent_z = current_dir[2]
                    current_dir = [tangent_x, 0, tangent_z]

                    total_dist += segment_len
                    self.points.append(tuple(current_pos))
                    self.tangents.append(tuple(current_dir))
                    self.cumulative_distances.append(total_dist)

        self.total_length = total_dist
        if len(self.points) > 1 :
            print(f"Track preprocessed: {len(self.points)} points, total length: {self.total_length:.2f}m")
        else:
            print("Track preprocessing resulted in only the start point.")


    def get_position_and_tangent(self, distance):
        """根據距離軌道起點的距離，獲取插值後的位置和 *插值後的切線方向*"""
        # Handle edge cases: no points or outside track range
        if not self.points:
            return (0, 0.1, 0), (0, 0, 1) # Return default safe values
        if distance <= 0:
            return self.points[0], self.tangents[0]
        if distance >= self.total_length or len(self.points) < 2:
             # Check if points/tangents exist before accessing -1
             if self.points:
                  return self.points[-1], self.tangents[-1]
             else: # Should be caught by the first 'if' but as a safeguard
                  return (0, 0.1, 0), (0, 0, 1)

        # 使用二分查找或線性查找找到對應的線段索引
        # 這裡用線性查找簡化
        segment_index = 0
        while segment_index < len(self.cumulative_distances) - 1 and self.cumulative_distances[segment_index + 1] < distance:
            segment_index += 1

        # Ensure index doesn't go out of bounds for points/tangents lists
        if segment_index >= len(self.points) - 1:
             return self.points[-1], self.tangents[-1] # Already handled above, but safer

        # 在找到的線段內進行線性插值
        dist_start = self.cumulative_distances[segment_index]
        dist_end = self.cumulative_distances[segment_index + 1]
        segment_len = dist_end - dist_start

        if segment_len < 1e-6: # 避免除以零
             return self.points[segment_index], self.tangents[segment_index]

        t = (distance - dist_start) / segment_len # 插值因子 (0 到 1)

        # 插值位置
        p_start = self.points[segment_index]
        p_end = self.points[segment_index + 1]
        pos_x = p_start[0] + (p_end[0] - p_start[0]) * t
        pos_y = p_start[1] + (p_end[1] - p_start[1]) * t # Y 通常不變
        pos_z = p_start[2] + (p_end[2] - p_start[2]) * t

        # --- Interpolate tangent vector ---
        tan_start = self.tangents[segment_index]
        tan_end = self.tangents[segment_index + 1]

        # Linear interpolation of components
        interp_tx = tan_start[0] + (tan_end[0] - tan_start[0]) * t
        interp_ty = tan_start[1] + (tan_end[1] - tan_start[1]) * t # Should be 0
        interp_tz = tan_start[2] + (tan_end[2] - tan_start[2]) * t

        # Normalize the interpolated tangent
        interp_len = math.sqrt(interp_tx**2 + interp_ty**2 + interp_tz**2)
        if interp_len > 1e-6:
            final_tangent = (interp_tx / interp_len, interp_ty / interp_len, interp_tz / interp_len)
        else:
            # If interpolation results in zero vector (unlikely), fallback to start tangent
            final_tangent = tan_start

        return (pos_x, pos_y, pos_z), final_tangent


    def draw(self):
        """繪製軌道"""
        if not self.points:
            return

        # 1. 繪製軌道範圍 (色塊)
        glColor3f(0.6, 0.6, 0.5) # 軌道砂石顏色
        glBegin(GL_QUAD_STRIP)
        glNormal3f(0, 1, 0) # Normal points up
        for i in range(len(self.points)):
            pos = self.points[i]
            tangent = self.tangents[i]
            # 計算垂直於切線的偏移方向 (假設在XZ平面)
            perp_x = -tangent[2]
            perp_z = tangent[0]
            # 計算左右兩側的點
            offset_scale = TRACK_WIDTH / 2.0
            left_x = pos[0] + perp_x * offset_scale
            left_z = pos[2] + perp_z * offset_scale
            right_x = pos[0] - perp_x * offset_scale
            right_z = pos[2] - perp_z * offset_scale
            glVertex3f(left_x, pos[1] - 0.05, left_z) # 稍微抬高避免 Z-fighting
            glVertex3f(right_x, pos[1] - 0.05, right_z)
        glEnd()

        # 2. 繪製鐵軌 (兩條線)
        glColor3f(0.3, 0.3, 0.3) # 鐵軌深灰色
        glLineWidth(2.0) # 設定線寬

        # Calculate rail offsets based on perpendicular vector
        rail_offset_scale = RAIL_OFFSET

        # 左軌
        glBegin(GL_LINE_STRIP)
        for i in range(len(self.points)):
            pos = self.points[i]
            tangent = self.tangents[i]
            perp_x = -tangent[2]
            perp_z = tangent[0]
            rail_x = pos[0] + perp_x * rail_offset_scale
            rail_z = pos[2] + perp_z * rail_offset_scale
            glVertex3f(rail_x, pos[1], rail_z) # 比軌道範圍再高一點
        glEnd()

        # 右軌
        glBegin(GL_LINE_STRIP)
        for i in range(len(self.points)):
            pos = self.points[i]
            tangent = self.tangents[i]
            perp_x = -tangent[2]
            perp_z = tangent[0]
            rail_x = pos[0] - perp_x * rail_offset_scale
            rail_z = pos[2] - perp_z * rail_offset_scale
            glVertex3f(rail_x, pos[1], rail_z)
        glEnd()

        glLineWidth(1.0) # 恢復默認線寬