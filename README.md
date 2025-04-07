# train_sim

# 簡易 3D 電車模擬器
![image](https://github.com/user-attachments/assets/62961ccb-aef0-4ac3-bd27-bc2bce40b4dc)

這是一個使用 Python、Pygame 和 PyOpenGL 建立的基礎 3D 電車模擬器。  
使用者可以在一個由 `scene.txt` 文件定義的 3D 環境中駕駛電車。  
全程用gemini-2.5-pro vibe coding完成  

## 功能特色

*   **3D 環境渲染:** 使用 PyOpenGL 進行基本的 3D 場景渲染。
*   **電車物理模擬:**
    *   包含加速度、煞車、自然摩擦力。
    *   最高速度限制。
    *   可沿預定軌道行駛。
*   **自訂軌道與場景:**
    *   透過 `scene.txt` 文件定義軌道（直線、彎道）和場景物件。
    *   支援軌道坡度。
    *   可放置建築物（立方體）、圓柱體和樹木等靜態物件。
    *   支援物件紋理貼圖（需放置於 `textures` 資料夾）。
*   **駕駛艙視角:**
    *   提供第一人稱駕駛視角。
    *   包含基本的儀表板顯示（速度表、操作桿）。
*   **視角控制:** 使用滑鼠自由調整視角（可鎖定/解鎖）。
*   **HUD 顯示:**
    *   可選的小地圖（顯示軌道、物件和電車位置/方向）。
	*   小地圖可套圖(預設檔名map.png，一個像素等於模擬世界一個單位(公尺))
    *   可選的座標顯示（顯示電車在世界中的 X, Y, Z 座標）。
*   **動態場景載入:**
    *   可手動觸發（按 `R`）重新載入 `scene.txt`。
    *   自動偵測 `scene.txt` 的變更並重新載入。
*   **其他控制:**
    *   可切換地面網格的顯示。
    *   可切換軌道是否循環。

## 系統需求

*   Python 3.x
*   Pygame
*   PyOpenGL
*   NumPy

## 安裝依賴

建議在虛擬環境中安裝：

```bash
# 建立虛擬環境 (可選)
python -m venv venv
# 啟用虛擬環境 (Windows)
.\venv\Scripts\activate
# 啟用虛擬環境 (macOS/Linux)
source venv/bin/activate

# 安裝必要的函式庫
pip install pygame PyOpenGL numpy
```

## 如何執行

1.  確保 `scene.txt` 檔案和 `textures` 資料夾（包含所需的 `.png` 紋理檔）與 `main.py` 在同一目錄下。
2.  開啟終端機或命令提示字元，進入專案目錄。
3.  執行主程式：

    ```bash
    python main.py
    ```

## 操作控制

*   **`W` / `↑` (向上箭頭):** 加速電車
*   **`S` / `↓` (向下箭頭):** 煞車
*   **`滑鼠滾輪向上/下`:** 微調增加/減少當前速度
*   **`滑鼠移動`:** (當滑鼠解鎖時) 調整視角方向
*   **`Tab`:** 切換滑鼠鎖定/解鎖狀態 (影響視角控制和滑鼠指標可見性)
*   **`Esc`:** 退出模擬器
*   **`G`:** 切換地面網格的顯示/隱藏
*   **`L`:** 切換軌道循環模式 (到達終點後是否回到起點)
*   **`R`:** 手動重新載入 `scene.txt` 檔案
*   **`M`:** 切換小地圖的顯示/隱藏
*   **`I`:** 切換左上角座標資訊的顯示/隱藏
*   **`Page Up`:** 放大 (Zoom In) 小地圖
*   **`Page Down`:** 縮小 (Zoom Out) 小地圖

## `scene.txt` 檔案格式說明

`scene.txt` 用於定義軌道路線和場景中的靜態物件。

*   以 `#` 開頭的行是註解，會被忽略。
*   空白行會被忽略。
*   指令不分大小寫。
*   座標系統：通常 X 和 Z 構成水平面，Y 軸代表垂直高度。
*   角度單位：度 (degrees)。

### 軌道指令 (依序定義路線)

軌道指令會基於上一段軌道的結束位置和角度繼續建立。

1.  **`straight <length> [gradient_permille]`**
    *   建立一段直線軌道。
    *   `length`: 直線軌道的水平長度。
    *   `gradient_permille` (可選): 軌道的坡度，單位是千分比 (‰)。正值表示上坡，負值表示下坡。預設為 0。

2.  **`curve <radius> <angle_deg> [gradient_permille]`**
    *   建立一段彎曲軌道。
    *   `radius`: 彎道的半徑。
    *   `angle_deg`: 彎道的角度（度）。正角度通常表示向左轉，負角度向右轉（相對於當前前進方向）。
    *   `gradient_permille` (可選): 軌道的坡度，單位是千分比 (‰)。預設為 0。

### 場景物件指令

1.  **`building <x> <y> <z> <rx> <ry> <rz> <width> <depth> <height> [texture_file]`**
    *   在指定位置放置一個立方體建築。
    *   `x`, `y`, `z`: 建築物底部中心的座標。
    *   `rx`, `ry`, `rz`: 分別繞 X, Y, Z 軸的旋轉角度（度）。
    *   `width`, `depth`, `height`: 建築物的寬度 (X軸方向)、深度 (Z軸方向)、高度 (Y軸方向)。
    *   `texture_file` (可選): 指定使用的紋理檔案名稱（位於 `textures` 資料夾內）。預設為 `building.png`。

2.  **`cylinder <x> <y> <z> <rx> <ry> <rz> <radius> <height> [texture_file]`**
    *   在指定位置放置一個圓柱體。
    *   `x`, `y`, `z`: 圓柱體底部中心的座標。
    *   `rx`, `ry`, `rz`: 分別繞 X, Y, Z 軸的旋轉角度（度）。注意：OpenGL 的 `gluCylinder` 預設沿 Z 軸繪製，渲染器內部會先旋轉使其豎直（沿 Y 軸），然後再應用這裡的旋轉。
    *   `radius`: 圓柱體的半徑。
    *   `height`: 圓柱體的高度。
    *   `texture_file` (可選): 指定使用的紋理檔案名稱（位於 `textures` 資料夾內）。預設為 `metal.png`。

3.  **`tree <x> <y> <z> <height>`**
    *   在指定位置放置一棵樹（由圓柱樹幹和圓錐/球體樹葉組成）。
    *   `x`, `y`, `z`: 樹根部的座標。
    *   `height`: 樹的總高度。

### 範例 `scene.txt`

```
# 這是一個範例場景檔案

# 軌道定義
straight 50 5     # 前進 50 單位，上坡 5‰
curve 20 90 -2    # 左轉 90 度，半徑 20，下坡 2‰
straight 30
curve 20 -90 0    # 右轉 90 度，半徑 20，水平
straight 50 -5    # 前進 50 單位，下坡 5‰

# 場景物件
building 10 0 20  0 45 0  5 8 10 building_brick.png
building -15 0 40 0 0 0   6 6 8
cylinder 5 0 5    0 0 0   1 5 pipe.png
tree 8 0 12 6
tree -10 0 30 7
```

## 紋理

*   所有紋理檔案（建議使用 `.png` 格式）應放置在名為 `textures` 的子資料夾中。
*   真實地圖檔案map.png同樣放置在名為 `textures` 的子資料夾中。
*   程式會自動載入 `scene.txt` 中指定的紋理，或使用預設紋理。

---

