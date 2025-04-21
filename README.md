# train_sim
  
![image](https://github.com/user-attachments/assets/446e975b-c758-465f-ba05-d5908dd373e6)
![image](https://github.com/user-attachments/assets/44cdd953-a60a-4787-abd1-b69d61718ced)

這是一個使用 Python 開發的簡易 3D 電車模擬器，包含兩個主要程式：
1. 電車模擬器 (`main.py`)
2. 場景編輯器 (`scene_editor.py`)
  
  
全程大多數用gemini-2.5-pro vibe coding完成  
片段程式可能由Qwen以及GPT協助  

# 簡易 3D 電車模擬器

這是一個使用 Python、Pygame 和 PyOpenGL 建立的基礎 3D 電車模擬器。使用者可以在 `scene.txt` 文件定義的 3D 環境中駕駛電車。

## 功能特色

- **3D 環境渲染：** 使用 PyOpenGL 進行基本的 3D 場景渲染。
- **電車物理模擬：**
  - 包含加速度、煞車、自然摩擦力。
  - 最高速度限制。
  - 可沿預定軌道行駛。
- **自訂軌道與場景：**
  - 透過 `scene.txt` 文件定義軌道（直線、彎道）和場景物件。
  - 支援軌道坡度。
  - 可放置建築物（立方體）、圓柱體和樹木等靜態物件。
  - 支援物件紋理貼圖（需放置於 `textures` 資料夾）。
- **駕駛艙視角：**
  - 提供第一人稱駕駛視角。
  - 包含基本的儀表板顯示（速度表、操作桿）。
- **視角控制：** 使用滑鼠自由調整視角（可鎖定/解鎖）。
- **HUD 顯示：**
  - 可選小地圖（顯示軌道、物件和電車位置/方向）。
  - 小地圖可套圖（預設檔名 map.png，一個像素等於模擬世界一個單位（公尺））。
  - 可選座標顯示（顯示電車在世界中的 X, Y, Z 座標）。
- **動態場景載入：**
  - 可手動觸發（按 `R`）重新載入 `scene.txt`。
  - 自動偵測 `scene.txt` 的變更並重新載入。
- **其他控制：**
  - 可切換地面網格的顯示。
  - 可切換軌道是否循環。

---

## ABOUT

用 AI 協助 Python 程式設計的簡單電車模擬器。  
A simple train simulator for Python, created with AI assistance.

### 專案緣起

這個專案其實沒有什麼遠大的目標，純粹是因為我想測試 AI 協助程式設計的流程，再加上我本身很喜歡模擬類遊戲，所以就誕生了這個 3D 電車模擬器。希望這個小作品能帶給同樣喜歡模擬遊戲或學習 Python 的朋友一些樂趣或啟發。

---

### About This Project

This project doesn't have a grand vision—it's simply a result of my curiosity about how AI can assist in programming, combined with my love for simulation games. That's how this 3D train simulator came to life. I hope this little project brings some fun or inspiration to others who enjoy simulation games or are learning Python.

---

## 系統需求

- Python 3.x
- Pygame
- PyOpenGL
- NumPy
- Numba

---

## 根目錄 Python 檔案簡要功能說明表

| 檔案名稱             | 功能簡述                                              |
|----------------------|------------------------------------------------------|
| main.py              | 主程式入口，負責初始化、主迴圈、整合各模組           |
| renderer.py          | 3D 場景、物件、電車駕駛艙、HUD 等繪製                |
| tram.py              | 電車物理模擬與控制邏輯                                |
| track.py             | 軌道資料結構，直線/彎道/坡度計算與 OpenGL 頂點生成     |
| scene_parser.py      | 解析 scene.txt，建立場景與物件，支援紋理載入          |
| camera.py            | 攝影機/第一人稱視角控制與計算                        |
| minimap_renderer.py  | 小地圖繪製、地圖圖層、座標轉換                        |
| scene_editor.py      | PyQt5 GUI 場景編輯器，可視化修改 scene.txt            |
| texture_loader.py    | 紋理圖片載入與 OpenGL 快取管理                        |

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

## 操作控制說明

### 基本駕駛
- **W / ↑（向上箭頭）**：加速電車
- **S / ↓（向下箭頭）**：煞車
- **滑鼠滾輪上下**：微調增加/減少當前速度

### 視角與滑鼠
- **滑鼠移動**（滑鼠鎖定時）：調整視角方向（第一人稱）
- **Tab**：切換滑鼠鎖定/解鎖狀態（解鎖時滑鼠可自由移動指標，鎖定時控制視角）
- **點擊滑鼠左鍵**（滑鼠未鎖定時）：立即鎖定滑鼠並進入第一人稱視角
- **Esc**：退出模擬器

### 顯示與功能切換
- **G**：切換地面網格顯示/隱藏
- **L**：切換軌道循環模式（到達終點是否自動回到起點）
- **R**：手動重新載入 scene.txt 檔案
- **M**：切換小地圖顯示/隱藏
- **I**：切換左上角座標/資訊顯示
- **C**：切換顯示駕駛室

### 小地圖縮放
- **Page Up**：放大（Zoom In）小地圖
- **Page Down**：縮小（Zoom Out）小地圖

---

#### 備註
- 滑鼠預設鎖定於視窗中，按 Tab 或左鍵可切換鎖定狀態。
- 駕駛艙視角（C 鍵）僅於支援的場景有效。
- 重新載入 scene.txt（R 鍵）可即時反映場景檔案的變更。

## scene.txt 檔案格式說明（最新版）

scene.txt 每一行代表一個指令，空白行與 `#` 開頭為註解。下方為完整格式與參數說明範例：

```plain
# scene.txt 指令格式說明

# 1. 地圖底圖
map <file> <cx> <cz> <scale>
# 參數說明：
#   <file>   ：底圖檔名（如 map.png）
#   <cx>     ：地圖中心 X 座標
#   <cz>     ：地圖中心 Z 座標
#   <scale>  ：地圖縮放比例

# 2. 軌道起點
start <x> <y> <z> <angle°>
# 參數說明：
#   <x>      ：起點 X 座標
#   <y>      ：起點 Y 座標
#   <z>      ：起點 Z 座標
#   <angle°> ：起始朝向角度（度，0=+Z方向，順時針）

# 3. 天空盒
skybox <base_name>
# 參數說明：
#   <base_name> ：天空盒貼圖前綴（會自動尋找 *_ft.png, *_bk.png 等六面）

# 4. 天空圓頂
skydome <texture_file>
# 參數說明：
#   <texture_file> ：天空圓頂貼圖檔名

# 5. 直線軌道
straight <length> [<grad‰>]
# 參數說明：
#   <length>  ：直線長度
#   <grad‰>   ：坡度（千分比，預設 0，可省略）

# 6. 彎道軌道
curve <radius> <angle°> [<grad‰>]
# 參數說明：
#   <radius>  ：彎道半徑
#   <angle°>  ：彎道角度（度，正值左彎，負值右彎）
#   <grad‰>   ：坡度（千分比，預設 0，可省略）

# 7. 建築物
building <rel_x> <rel_y> <rel_z> <rx°> <rel_ry°> <rz°> <w> <d> <h> [<tex>] [<uOf>] [<vOf>] [<tAng°>] [<uvMd>] [<uSc>] [<vSc>]
# 參數說明：
#   <rel_x/y/z> ：相對座標（以當前起點為原點）
#   <rx°>       ：X 軸旋轉角度
#   <rel_ry°>   ：Y 軸旋轉角度（相對於軌道方向）
#   <rz°>       ：Z 軸旋轉角度
#   <w/d/h>     ：寬/深/高
#   <tex>       ：貼圖檔名（可省略）
#   <uOf/vOf>   ：UV 偏移量（可省略）
#   <tAng°>     ：貼圖旋轉角度（可省略）
#   <uvMd>      ：UV 模式（可省略）
#   <uSc/vSc>   ：UV 縮放（可省略）

# 8. 圓柱體
cylinder <rel_x> <rel_y> <rel_z> <rx°> <rel_ry°> <rz°> <rad> <h> [<tex>] [<uOf>] [<vOf>] [<tAng°>] [<uvMd>] [<uSc>] [<vSc>]
# 參數說明：
#   <rel_x/y/z> ：相對座標
#   <rx°>       ：X 軸旋轉角度
#   <rel_ry°>   ：Y 軸旋轉角度（相對於軌道方向）
#   <rz°>       ：Z 軸旋轉角度
#   <rad>       ：半徑
#   <h>         ：高度
#   <tex>       ：貼圖檔名（可省略，其餘同 building）

# 9. 樹木
tree <rel_x> <rel_y> <rel_z> <height>
# 參數說明：
#   <rel_x/y/z> ：相對座標
#   <height>    ：樹高

# 備註：
# - 所有 rel_x/y/z 皆為相對於目前「起點」或上一段軌道結束點的座標。
# - 帶 [] 的參數代表可省略。
# - 指令順序會影響物件擺放與軌道結構。
```

---

#### 範例
```plain
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





