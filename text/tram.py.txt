# tram.py
import numpy as np


class Tram:
    def __init__(self, track):
        
        self.track = track
        self.distance_on_track = 0.0
        self.current_speed = 0.0 # m/s
        self.max_speed = 60.0    # m/s
        self.acceleration = 2.0  # m/s^2
        self.braking = 3.0       # m/s^2 (煞車減速度)
        self.friction = 0.2      # m/s^2 (自然減速度)

        # 電車在軌道上的狀態
        self.position = np.array([0.0, 0.0, 0.0])
        self.forward_vector_xz = (1.0, 0.0) # (x, z)

        # 控制狀態
        self.is_accelerating = False
        self.is_braking = False

        # 是否循環
        self.looping = True

    def update(self, dt):
        """更新電車狀態"""
        # 應用摩擦力
        if not self.is_accelerating and not self.is_braking:
            if self.current_speed > 0:
                self.current_speed -= self.friction * dt
                if self.current_speed < 0: self.current_speed = 0
            elif self.current_speed < 0: # 如果允許倒車
                 self.current_speed += self.friction * dt
                 if self.current_speed > 0: self.current_speed = 0


        # 應用加速和煞車
        if self.is_accelerating:
            self.current_speed += self.acceleration * dt
        elif self.is_braking:
            if self.current_speed > 0:
                self.current_speed -= self.braking * dt
                if self.current_speed < 0: self.current_speed = 0
            elif self.current_speed < 0: # 煞車也會使倒車減速
                 self.current_speed += self.braking * dt
                 if self.current_speed > 0: self.current_speed = 0


        # 限制速度
        self.current_speed = max(-self.max_speed, min(self.max_speed, self.current_speed))

        # 更新在軌道上的距離
        self.distance_on_track += self.current_speed * dt

        # 處理軌道循環
        if self.track.total_length > 0:
            if self.looping:
                # 處理正向循環
                if self.distance_on_track >= self.track.total_length:
                   self.distance_on_track -= self.track.total_length
                # 處理反向循環 (如果速度為負)
                elif self.distance_on_track < 0:
                   self.distance_on_track += self.track.total_length
            else:
                # 不循環則限制在軌道範圍內
                self.distance_on_track = max(0.0, min(self.distance_on_track, self.track.total_length))
                # 如果到達終點且不循環，停止電車
                if self.distance_on_track == 0.0 or self.distance_on_track == self.track.total_length:
                    if abs(self.current_speed) > 0.1: # 如果是因為撞到邊界停下，給一點反彈或直接停止
                        self.current_speed = 0


        # 獲取當前位置和朝向
        if self.track.total_length > 0:
             self.position, self.forward_vector_xz = self.track.get_position_orientation(self.distance_on_track)
        else:
             # 如果沒有軌道，保持在原地
             self.position = np.array([0.0, 0.0, 0.0])
             self.forward_vector_xz = (1.0, 0.0)


        # 重置控制狀態 (按鍵按下時會重新設置)
        self.is_accelerating = False
        self.is_braking = False

    def accelerate(self):
        self.is_accelerating = True
        self.is_braking = False # 加速時不能同時煞車

    def brake(self):
        self.is_braking = True
        self.is_accelerating = False # 煞車時不能同時加速

    def adjust_speed(self, delta):
        """通過滾輪調整速度"""
        new_speed = self.current_speed + delta * 0.5 # 調整滾輪靈敏度
        self.current_speed = max(-self.max_speed, min(self.max_speed, new_speed))

    def toggle_looping(self):
        self.looping = not self.looping
        print(f"軌道循環: {'啟用' if self.looping else '禁用'}")

    def get_speed_kmh(self):
        """獲取以 km/h 為單位的速度"""
        return self.current_speed * 3.6

    def get_control_state(self):
        """獲取控制桿狀態 (-1: 後退/煞車, 0: 空檔, 1: 前進)"""
        if self.is_accelerating:
            return 1
        elif self.is_braking:
            return -1
        elif abs(self.current_speed) < 0.1 and not self.is_accelerating and not self.is_braking : #接近靜止且沒操作
            return 0
        elif self.current_speed > 0: # 滑行前進
            return 0.5 # 可以用中間狀態表示滑行
        elif self.current_speed < 0: # 滑行後退
            return -0.5
        return 0 # 預設空檔