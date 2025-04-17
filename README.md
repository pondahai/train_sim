# train_sim
  
![image](https://github.com/user-attachments/assets/446e975b-c758-465f-ba05-d5908dd373e6)
![image](https://github.com/user-attachments/assets/44cdd953-a60a-4787-abd1-b69d61718ced)

這是一個使用 Python 開發的簡易 3D 電車模擬器，包含兩個主要程式：
1. 電車模擬器 (`main.py`)
2. 場景編輯器 (`scene_editor.py`)
  
  
全程大多數用gemini-2.5-pro vibe coding完成  
片段程式可能由Qwen以及GPT協助  

# 簡易 3D 電車模擬器

這是一個使用 Python、Pygame 和 PyOpenGL 建立的基礎 3D 電車模擬器。使用者可以在一個由 `scene.txt` 文件定義的 3D 環境中駕駛電車。

## 功能特色

* **3D 環境渲染：** 使用 PyOpenGL 進行基本的 3D 場景渲染。
* **電車物理模擬：**
    * 包含加速度、煞車、自然摩擦力。
    * 最高速度限制。
    * 可沿預定軌道行駛。
* **自訂軌道與場景：**
    * 透過 `scene.txt` 文件定義軌道（直線、彎道）和場景物件。
    * 支援軌道坡度。
    * 可放置建築物（立方體）、圓柱體和樹木等靜態物件。
    * 支援物件紋理貼圖（需放置於 `textures` 資料夾）。
* **駕駛艙視角：**
    * 提供第一人稱駕駛視角。
    * 包含基本的儀表板顯示（速度表、操作桿）。
* **視角控制：** 使用滑鼠自由調整視角（可鎖定/解鎖）。
* **HUD 顯示：**
    * 可選的小地圖（顯示軌道、物件和電車位置/方向）。
    * 小地圖可套圖（預設檔名 map.png，一個像素等於模擬世界一個單位（公尺））。
    * 可選的座標顯示（顯示電車在世界中的 X, Y, Z 座標）。
* **動態場景載入：**
    * 可手動觸發（按 `R`）重新載入 `scene.txt`。
    * 自動偵測 `scene.txt` 的變更並重新載入。
* **其他控制：**
    * 可切換地面網格的顯示。
    * 可切換軌道是否循環。

## 系統需求

* Python 3.x
* Pygame
* PyOpenGL
* NumPy

---

## 根目錄 Python 檔案簡要功能說明表

| 檔案名稱              | 功能簡述                                               |
|----------------------|--------------------------------------------------------|
| main.py              | 主程式入口，負責初始化、主迴圈、整合各模組            |
| renderer.py          | 3D 場景、物件、電車駕駛艙、HUD 等繪製                 |
| tram.py              | 電車物理模擬與控制邏輯                                 |
| track.py             | 軌道資料結構，直線/彎道/坡度計算與 OpenGL 頂點生成      |
| scene_parser.py      | 解析 scene.txt，建立場景與物件，支援紋理載入           |
| camera.py            | 攝影機/第一人稱視角控制與計算                         |
| minimap_renderer.py  | 小地圖繪製、地圖圖層、座標轉換                         |
| scene_editor.py      | PyQt5 GUI 場景編輯器，可視化修改 scene.txt             |
| texture_loader.py    | 紋理圖片載入與 OpenGL 快取管理                         |

---

## 模組說明

### main.py
- 專案主程式，負責初始化 Pygame、OpenGL、各模組與主視窗。
- 控制主事件迴圈、場景載入、鍵盤與滑鼠操作、畫面更新與渲染。

### renderer.py
- 處理 3D 場景的所有繪製，包括地面、軌道、建築、樹木、電車駕駛艙、HUD 等。
- 提供多種物件繪圖函式，支援紋理貼圖與座標顯示。

### tram.py
- 定義 Tram 類別，模擬電車的物理行為（加速度、煞車、摩擦、循環行駛等）。
- 管理電車在軌道上的位置、速度、方向與狀態。

### track.py
- 定義軌道相關資料結構（直線、彎道、坡度），並負責軌道頂點與方向的計算。
- 支援軌道內插、OpenGL 線段生成與座標查詢。

### scene_parser.py
- 負責解析 `scene.txt` 場景檔案，建立軌道、建築、樹木等物件。
- 支援紋理載入、場景重載、座標與旋轉資訊管理。

### camera.py
- 控制攝影機（第一人稱視角）的位置、朝向、滑鼠鎖定與視角角度。
- 提供視角更新、滑鼠靈敏度與限制 Pitch/Yaw 功能。

### minimap_renderer.py
- 負責小地圖的繪製、地圖圖層、玩家/物件位置顯示。
- 支援地圖縮放、座標轉換、地圖圖像（map.png）疊加。

### scene_editor.py
- 提供 PyQt5 圖形化場景編輯器，可讀寫 scene.txt。
- 支援表格編輯、即時小地圖預覽、OpenGL 嵌入與檔案管理。

### texture_loader.py
- 處理紋理圖片載入、OpenGL 紋理快取與釋放。
- 支援 PNG 檔案載入、Mipmap 生成與快取管理。

---

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

## scene.txt 檔案格式說明（最新版）

每一行代表一個指令，空白行與 `#` 開頭為註解。主要支援以下指令：

### 1. map
```
map <file> <cx> <cz> <scale>
```
- file: 地圖影像檔名
- cx, cz: 影像中心對應的世界座標 (float)
- scale: 世界單位/像素 (float, 必須為正)

### 2. start
```
start <x> <y> <z> <angle°>
```
- x, y, z: 世界座標 (float)
- angle°: 起始角度（度，float）

### 3. straight
```
straight <length> [grad‰]
```
- length: 長度 (float)
- grad‰: 坡度（千分比，float, 選填，預設 0）

### 4. curve
```
curve <radius> <angle°> [grad‰]
```
- radius: 半徑 (float)
- angle°: 旋轉角度（度，float）
- grad‰: 坡度（千分比，float, 選填，預設 0）

### 5. building
```
building <rel_x> <rel_y> <rel_z> <rx°> <rel_ry°> <rz°> <w> <d> <h> [tex] [uOf] [vOf] [tAng°] [uvMd] [uSc] [vSc]
```
- rel_x, rel_y, rel_z: 物件座標。**物件座標的參考點規則如下：**
    - 如果物件指令出現在第一個軌道指令（如 straight/curve）之前，則以世界原點 (0,0,0) 為參考點。
    - 如果物件指令出現在某段軌道指令（如 straight/curve）之後，則以該段軌道的起點為參考點。
- rx°, rel_ry°, rz°: 旋轉角度（度，float）
- w, d, h: 寬、深、⾼ (float)
- tex: 紋理檔名（string, 預設 "building.png"）
- uOf, vOf: 紋理 U/V offset (float, 預設 0)
- tAng°: 紋理旋轉角度 (float, 預設 0)
- uvMd: 紋理模式 (int, 0 或 1，預設 1)
- uSc, vSc: 紋理縮放（float，uvMd=0 時有效，預設 1.0）

### 6. cylinder
```
cylinder <rel_x> <rel_y> <rel_z> <rx°> <rel_ry°> <rz°> <rad> <h> [tex] [uOf] [vOf] [tAng°] [uvMd] [uSc] [vSc]
```
- rel_x, rel_y, rel_z: 物件座標，參考點規則同 building
- rx°, rel_ry°, rz°: 旋轉角度（度，float）
- rad: 半徑 (float)
- h: 高度 (float)
- tex: 紋理檔名（string, 預設 "metal.png"）
- uOf, vOf, tAng°, uvMd, uSc, vSc: 同 building

### 7. tree
```
tree <rel_x> <rel_y> <rel_z> <height>
```
- rel_x, rel_y, rel_z: 物件座標，參考點規則同 building
- height: 樹高 (float)

---

#### 範例
```
map map.png 0 0 1.0
start 0 0 0 0
straight 100
curve 50 90 0
building 10 0 5 0 0 0 10 10 10 building.png
cylinder 15 0 5 0 0 0 2 10 metal.png
tree 20 0 5 8
```

---

## 紋理與地圖

* 所有紋理檔案（建議使用 `.png` 格式）應放置在名為 `textures` 的子資料夾中。
* 真實地圖檔案 map.png 同樣放置在名為 `textures` 的子資料夾中。
* 程式會自動載入 `scene.txt` 中指定的紋理，或使用預設紋理。

---




