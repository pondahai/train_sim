# train_sim

# 簡易 3D 電車模擬器
![image](https://github.com/user-attachments/assets/446e975b-c758-465f-ba05-d5908dd373e6)
![image](https://github.com/user-attachments/assets/44cdd953-a60a-4787-abd1-b69d61718ced)


這是一個使用 Python、Pygame 和 PyOpenGL 建立的基礎 3D 電車模擬器。  
使用者可以在一個由 `scene.txt` 文件定義的 3D 環境中駕駛電車。  
全程用gemini-2.5-pro vibe coding完成  

## 主要功能

*   **3D 環境渲染:** 使用 PyOpenGL 進行基本的 3D 場景繪製。
*   **電車物理模擬:** 包含加速度、煞車、自然摩擦力和最高速度限制。
*   **可自訂軌道:** 透過 `scene.txt` 定義直線、彎道，並支援坡度設定。
*   **可自訂場景:** 在 `scene.txt` 中定義建築、圓柱體、樹木等物件，支援紋理、相對位置、旋轉和縮放。
*   **紋理映射:** 支援為物體（建築、圓柱體、地面、樹木等）應用紋理，並可進行 UV 偏移、旋轉、平鋪/拉伸模式設定。
*   **第一人稱視角:** 提供基於滑鼠控制的自由視角（Mouse Look）。
*   **駕駛艙儀表:** 顯示速度表和模擬的操作桿狀態。
*   **小地圖 (Minimap):**
    *   顯示軌道、場景物件和玩家位置/方向。
    *   可縮放 (PageUp/PageDown)。
    *   可選網格線和坐標標籤。
    *   可載入場景定義的背景圖片。
*   **HUD 資訊:** 可選顯示電車在世界中的即時坐標。
*   **動態場景重載:** 自動檢測 `scene.txt` 檔案的變更並重新載入場景，或透過 'R' 鍵手動觸發。
*   **軌道循環:** 可切換電車到達軌道終點時是否循環回到起點。
*   **性能優化:** 軌道繪製採用 VBO (Vertex Buffer Objects) 以提高效率。部分計算函數使用 Numba (`@jit`) 加速。

## 需求 / Dependencies

*   Python 3.8 或更高版本
*   Pygame (`pip install pygame`)
*   PyOpenGL (`pip install PyOpenGL PyOpenGL_accelerate`)
*   NumPy (`pip install numpy`)
*   Numba (`pip install numba`)

建議將依賴項放入 `requirements.txt` 文件中：
```
pygame
PyOpenGL
PyOpenGL_accelerate
numpy
numba
```
然後使用 `pip install -r requirements.txt` 安裝。

## 安裝

1.  確保已安裝 Python 和 pip。
2.  克隆此儲存庫：
    ```bash
    git clone <your-repository-url>
    cd <repository-directory>
    ```
3.  安裝所需的依賴項：
    ```bash
    pip install -r requirements.txt
    ```

## 使用方法

1.  直接運行主程式：
    ```bash
    python main.py
    ```
2.  **控制:**
    *   **滑鼠移動:** 控制視角方向 (需要點擊視窗鎖定滑鼠)。
    *   **W / ↑ (上箭頭):** 加速電車。
    *   **S / ↓ (下箭頭):** 煞車。
    *   **滑鼠滾輪:** 微調電車速度。
    *   **ESC:** 解鎖滑鼠 / 再次按下退出程式。
    *   **TAB:** 手動切換滑鼠鎖定狀態。
    *   **G:** 切換地面網格的顯示。
    *   **L:** 切換軌道循環模式。
    *   **R:** 手動重新載入 `scene.txt`。
    *   **M:** 切換小地圖的顯示。
    *   **I:** 切換坐標顯示。
    *   **PageUp:** 放大地圖。
    *   **PageDown:** 縮小地圖。

## 場景文件格式 (`scene.txt`)

`scene.txt` 文件定義了軌道的佈局和場景中的物件。

*   以 `#` 開頭的行是註解，會被忽略。
*   命令不區分大小寫。
*   物件（building, cylinder, tree）的位置 (`rel_x`, `rel_y`, `rel_z`) 和 Y 軸旋轉 (`rel_ry_deg`) 是 **相對於其前方最近的軌道段起點和起始方向** 的。
    *   `rel_x`: 沿軌道段起始方向的右側 (+X) 或左側 (-X) 的距離。
    *   `rel_y`: 相對於軌道段起點的高度偏移。
    *   `rel_z`: 沿軌道段起始方向的前方 (+Z) 或後方 (-Z) 的距離。
    *   `rel_ry_deg`: 相對於軌道段起始方向的額外 Y 軸旋轉角度（度）。
*   如果在任何軌道段之前定義物件，則其坐標和旋轉相對於世界原點 (0,0,0) 和 X 軸正方向 (0 度)。

**可用命令:**

*   `start <x> <y> <z> <angle_deg>`
    *   設定電車和軌道的起始位置 (`x`, `y`, `z`) 和初始水平朝向角度 (`angle_deg`)。角度 0 沿 X 軸正方向，90 沿 Z 軸正方向。如果省略，則從 (0,0,0) 角度 0 開始。
*   `straight <length> [gradient_permille]`
    *   從當前軌道末端添加一段直線軌道。
    *   `length`: 直線的水平長度。
    *   `gradient_permille` (可選): 坡度，單位千分比 (‰)。正值上坡，負值下坡。預設為 0。
*   `curve <radius> <angle_deg> [gradient_permille]`
    *   從當前軌道末端添加一段彎曲軌道。
    *   `radius`: 彎道的半徑。
    *   `angle_deg`: 彎道的角度（度）。正角度向左轉 (逆時針)，負角度向右轉 (順時針)。
    *   `gradient_permille` (可選): 坡度，單位千分比 (‰)。預設為 0。
*   `building <rx> <ry> <rz> <rot_x> <rot_y> <rot_z> <width> <depth> <height> [texture] [uoff] [voff] [tang] [umode] [usca] [vsca]`
    *   添加一個建築物（立方體）。
    *   `<rx> <ry> <rz>`: 相對位置。
    *   `<rot_x> <rot_y> <rot_z>`: 相對 Y 軸旋轉後的額外 X, Y, Z 軸旋轉角度（度）。
    *   `<width> <depth> <height>`: 建築物的尺寸。
    *   `texture` (可選): 紋理檔名 (在 `textures/` 資料夾下)。預設 "building.png"。
    *   `uoff`, `voff` (可選): 紋理 UV 坐標偏移。預設 0.0。
    *   `tang` (可選): 紋理旋轉角度（度）。預設 0.0。
    *   `umode` (可選): UV 模式。1=拉伸填滿 (預設)，0=按單位平鋪。
    *   `usca`, `vsca` (可選): 當 `umode=0` 時，紋理在 U 和 V 方向的縮放比例（每個紋理單位對應多少世界單位）。預設 1.0。
*   `cylinder <rx> <ry> <rz> <rot_x> <rot_y> <rot_z> <radius> <height> [texture] [uoff] [voff] [tang] [umode] [usca] [vsca]`
    *   添加一個圓柱體。參數與 `building` 類似。
    *   `texture` 預設 "metal.png"。
*   `tree <rx> <ry> <rz> <height>`
    *   添加一棵樹。
    *   `<rx> <ry> <rz>`: 相對位置。
    *   `<height>`: 樹的高度。
*   `map <filename> <center_world_x> <center_world_z> <scale>`
    *   設定小地圖使用的背景圖片。
    *   `filename`: 背景圖片檔名 (在 `textures/` 資料夾下)。
    *   `center_world_x`, `center_world_z`: 背景圖片 **中心點** 對應的世界坐標 X 和 Z。
    *   `scale`: 比例尺，表示 **每個像素** 對應多少世界單位長度。

## 程式運作原理 / 架構

本模擬器採用模塊化設計，主要由以下幾個部分組成：

1.  **主程式 (`main.py`):**
    *   初始化 Pygame 和 OpenGL。
    *   設置視窗和基本渲染狀態。
    *   載入字體、場景。
    *   創建電車 (`Tram`) 和攝影機 (`Camera`) 實例。
    *   **主循環:**
        *   處理使用者輸入（鍵盤、滑鼠）。
        *   更新遊戲狀態（計算每幀時間 `dt`）。
        *   調用 `tram.update(dt)` 更新電車物理狀態和位置。
        *   調用 `camera.update_position_orientation()` 和 `camera.update_angles()` 更新攝影機。
        *   定期檢查 `scene.txt` 是否更新並觸發 `scene_parser.load_scene()`。
        *   **渲染:**
            *   清空緩衝區。
            *   設置 3D 投影 (`gluPerspective`)。
            *   設置視圖矩陣 (`gluLookAt`，由 `camera.apply_view()` 控制)。
            *   調用 `renderer` 模組繪製地面、軌道、場景物件和電車駕駛艙。
            *   切換到 2D 正交投影繪製 HUD（小地圖、坐標）。
            *   交換緩衝區顯示畫面 (`pygame.display.flip()`)。
    *   退出時進行清理。

2.  **電車 (`tram.py`):**
    *   `Tram` 類負責模擬電車的物理行為。
    *   儲存電車狀態：在軌道上的距離 (`distance_on_track`)、目前速度 (`current_speed`)、最大速度、加速度、煞車力、摩擦力等。
    *   `update(dt)` 方法根據時間間隔 `dt` 和控制狀態 (`is_accelerating`, `is_braking`) 更新速度和距離。
    *   處理軌道邊界（循環或停止）。
    *   根據 `distance_on_track` 從 `track` 物件獲取當前的 3D 世界坐標 (`position`) 和水平朝向向量 (`forward_vector_xz`)。

3.  **攝影機 (`camera.py`):**
    *   `Camera` 類管理第一人稱視角。
    *   根據滑鼠輸入更新視角的偏航角 (`yaw`) 和俯仰角 (`pitch`)。
    *   `update_position_orientation()` 方法根據電車的 `position` 和 `forward_vector_xz`，以及預設的偏移量，計算攝影機在世界中的基礎位置 (`base_position`) 和基礎朝向 (`base_forward`)。
    *   `apply_view()` 方法結合基礎位置/朝向和滑鼠控制的 yaw/pitch，計算最終的 `eye_pos`, `look_at_pos`, `final_up` 向量，並調用 `gluLookAt` 設置 OpenGL 的視圖矩陣。

4.  **場景解析器 (`scene_parser.py`):**
    *   負責讀取和解析 `scene.txt` 文件。
    *   `Scene` 類用於存儲解析後的場景數據，包括 `Track` 物件和包含 **絕對世界坐標** 的物件列表（建築、圓柱體、樹木）以及地圖背景資訊。
    *   `parse_scene_file()` 函數逐行讀取文件，根據命令創建軌道段或計算物件的絕對世界坐標和旋轉，並將其添加到 `Scene` 物件中。
    *   `load_scene()` 函數檢查文件修改時間，只在需要時重新解析文件，並觸發相關資源（紋理、軌道 VBO）的清理和重新載入。

5.  **軌道 (`track.py`):**
    *   `TrackSegment` 基類及其子類 `StraightTrack` 和 `CurveTrack` 定義了軌道的幾何形狀和屬性（長度、坡度、點、朝向）。
    *   **核心優化：** 在軌道段初始化時 (`__init__`)，會計算出一系列內插點 (`points`) 和朝向 (`orientations`)，並基於這些點生成用於繪製道碴和軌道的頂點數據，創建 VBO 和 VAO (`setup_buffers`)。這避免了在渲染循環中進行大量計算和 OpenGL 調用。
    *   `get_position_orientation()` 方法根據在段上的距離進行插值，返回精確的 3D 位置和 2D 朝向。
    *   `Track` 類管理多個 `TrackSegment`，計算總長度，並提供根據總距離查找位置和朝向的方法。它也負責在清理時釋放所有段的 VBO/VAO 資源。

6.  **渲染器 (`renderer.py`):**
    *   包含繪製場景中各種元素的函數。
    *   `init_renderer()`: 初始化 OpenGL 光照、狀態等。
    *   `draw_ground()`: 繪製地面（可選紋理）。
    *   `draw_track()`: **使用 VBO/VAO 高效繪製軌道和道碴。** 遍歷 `Track` 中的 `TrackSegment`，綁定預先計算好的 VAO，並使用 `glDrawArrays` 繪製。
    *   `draw_cube()`, `draw_cylinder()`, `draw_tree()`: **目前使用 OpenGL 立即模式 (Immediate Mode)** 繪製這些基本形狀，支援紋理和 `scene.txt` 中定義的各種 UV 變換參數。雖然比 VBO 慢，但實現了靈活的紋理控制。
    *   `draw_scene_objects()`: 遍歷 `Scene` 中的物件列表，設置變換（平移、旋轉）並調用相應的繪製函數。
    *   `draw_tram_cab()`: 在電車的局部坐標系中繪製駕駛艙模型和儀表。
    *   `draw_minimap()`, `draw_coordinates()`: 切換到 2D 正交投影模式繪製 HUD 元素，涉及坐標轉換和文字渲染。
    *   管理小地圖背景紋理的載入和更新。

7.  **紋理載入器 (`texture_loader.py`):**
    *   提供 `load_texture()` 函數，負責從文件載入圖片、創建 OpenGL 紋理對象、生成 Mipmap，並進行快取以避免重複載入。
    *   提供 `clear_texture_cache()` 函數，在場景重載時釋放舊紋理。

---

