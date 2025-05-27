
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
    - 可定義**視覺化軌道分岔 (`vbranch`)**，在不影響主軌道邏輯的情況下增加視覺豐富度。
    - 可放置建築物（立方體）、圓柱體、**球體**、**山丘**、**人字形屋頂 (Gableroof)** 和樹木 (**使用 Billboard 方式渲染，支援 Alpha Testing**) 等靜態物件。
    - 支援物件紋理貼圖（需放置於 `textures` 資料夾），包含 **Alpha Testing** (例如樹木、帶透明通道的建築紋理)。
    - 支援 **UV 佈局模式**，允許單個紋理圖集用於複雜物件（如立方體、人字形屋頂）的不同表面。
    - 支援使用 `import` 指令將外部場景片段導入主場景。
- **背景系統：**
    - 支援 **天空盒 (Skybox)** 和 **天空圓頂 (Skydome)** 作為背景。
    - 可根據電車行駛里程 **觸發背景切換**。
- **駕駛艙視角：**
    - 提供第一人稱駕駛視角，包含可設定的攝影機偏移。
    - 包含基本的儀表板顯示（速度表、操作桿）。
- **視角控制：** 使用滑鼠自由調整視角（可鎖定/解鎖）。
- **HUD 顯示：**
    - 可選小地圖（顯示軌道、物件輪廓和電車位置/方向）。
    - 小地圖可載入指定底圖 (`map` 指令)，並根據指定比例縮放。**模擬器模式下，靜態元素烘焙後的內部紋理為 1 世界單位/像素**。
    - 可選座標/速度資訊顯示。
- **動態場景載入：**
    - 可手動觸發（按 `R`）重新載入 `scene.txt`。
    - 自動偵測 `scene.txt` 的變更並重新載入。
    - 支援透過主選單（滑鼠右鍵）載入不同的場景檔案。
- **場景編輯器 (`scene_editor.py`)：**
    - 提供 **圖形化介面 (PyQt5)** 編輯 `scene.txt`。
    - **即時 2D 小地圖預覽**：
        - 動態繪製場景所有元素（軌道、物件標記、網格、標籤）。
        - 高亮顯示表格中選中的物件/軌道段。
        - 支援 **F7 模式**，用於微調物件座標時在小地圖上提供額外視覺輔助（如局部座標軸）。
        - 雙擊小地圖可將 3D 預覽視角中心定位到對應世界座標。
    - **即時 3D 預覽窗口**：
        - 支援自由飛行相機（WASDQE移動，滑鼠控制視角）。
        - 根據表格選中行，動態顯示對應的天空盒/天空圓頂背景。
    - **表格編輯功能**：
        - 支援多行複製/貼上/刪除。
        - 根據選中行的指令類型，**動態更新表頭參數提示**。
        - 支援 **F7 座標微調模式**：選中物件後按 F7，可使用方向鍵和 PageUp/Down 精細調整物件的 X, Y, Z 座標。
    - **檔案管理**：支援開啟、儲存、另存為場景檔案。
    - **設定持久化**：自動儲存和載入編輯器視窗狀態、小地圖和 3D 預覽視角、最後開啟的檔案路徑等。
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
- **PyQt5** (用於 `scene_editor.py`)
- **Pillow (PIL)** (用於 `minimap_renderer.py` 載入編輯器背景圖和小地圖烘焙時的圖片處理)


---

## 根目錄 Python 檔案簡要功能說明表

| 檔案名稱             | 功能簡述                                                                 |
|----------------------|-------------------------------------------------------------------------|
| main.py              | 主程式入口，負責初始化、主迴圈、整合各模組，包含右鍵選單載入場景功能。          |
| renderer.py          | 3D 場景、物件（含**球體、山丘、人字形屋頂**）、電車駕駛艙、HUD、**天空盒/天空圓頂背景** 等繪製，支援 Alpha Testing 和 UV 佈局。 |
| tram.py              | 電車物理模擬與控制邏輯。                                                   |
| track.py             | 軌道資料結構，直線/彎道/坡度計算，OpenGL 頂點生成，支援**視覺化分岔 (`vbranch`)**。 |
| scene_parser.py      | 解析 scene.txt，建立場景與物件，支援紋理載入、**`import` 指令**、**`gableroof` 指令**。 |
| camera.py            | 攝影機/第一人稱視角控制與計算，支援攝影機偏移。                              |
| minimap_renderer.py  | 小地圖繪製，模擬器模式下靜態元素烘焙 (1:1)，編輯器模式下動態繪製所有元素。       |
| scene_editor.py      | PyQt5 GUI 場景編輯器，可視化修改 scene.txt，含即時 2D/3D 預覽、**F7 微調模式**。 |
| texture_loader.py    | 紋理圖片載入與 OpenGL 快取管理，支援 Alpha 通道檢測。                       |

---

## 模組說明

### main.py
- 專案主程式，負責初始化 Pygame、OpenGL、各模組與主視窗。
- 控制主事件迴圈、場景載入（含**右鍵選單載入**）、鍵盤與滑鼠操作、畫面更新與渲染。
- 實現基於電車里程的**背景觸發切換**邏輯。

### renderer.py
- 處理 3D 場景的所有繪製，包括地面、軌道、建築、**球體**、**山丘**、**人字形屋頂 (Gableroof)**、樹木 (**Billboard 方式，支援 Alpha Testing**)、電車駕駛艙、HUD、**天空盒/天空圓頂背景** 等。
- 提供多種物件繪圖函式，支援紋理貼圖、**Alpha Testing**、**UV 佈局模式** (如立方體、人字形屋頂使用紋理圖集) 與座標顯示。

### tram.py
- 定義 Tram 類別，模擬電車的物理行為（加速度、煞車、摩擦、循環行駛等）。
- 管理電車在軌道上的位置、速度、方向與狀態。

### track.py
- 定義軌道相關資料結構（直線、彎道、坡度），並負責軌道頂點與方向的計算。
- 支援軌道內插、OpenGL 線段生成與座標查詢。
- 新增支援**視覺化軌道分岔 (`vbranch`)** 的數據結構和相關頂點生成。
- 包含 `is_buffer_ready` 標誌，用於判斷軌道段的 OpenGL 緩衝區是否準備就緒。

### scene_parser.py
- 負責解析 `scene.txt` 場景檔案，建立軌道、建築、圓柱、**球體**、**山丘**、樹木、**人字形屋頂 (Gableroof)** 等物件。
- 新增支援 `skybox`、`skydome` 指令，管理背景觸發器。
- 新增支援 **`import <filepath>` 指令**，允許將其他場景檔案的內容導入當前場景，並處理相對路徑和循環導入。
- 支援紋理載入（包含 Alpha 通道檢測資訊）、場景重載、座標與旋轉資訊管理（包含物件相對於父原點的 Y 旋轉）。
- 更新 `COMMAND_HINTS` 以包含新指令和參數。

### camera.py
- 控制攝影機（第一人稱視角）的位置、朝向、滑鼠鎖定與視角角度。
- 提供視角更新、滑鼠靈敏度與限制 Pitch/Yaw 功能。
- 支援攝影機相對於電車中心的**偏移量設定 (X, Y, Z)**。

### minimap_renderer.py
- 負責小地圖繪製。
- **模擬器模式：** 烘焙靜態地圖紋理（含軌道、物件輪廓如建築物的凸包、**山丘基底**、**人字形屋頂凸包**），**強制 1 世界單位/像素比例**，動態疊加電車。
- **編輯器模式：** 動態繪製所有元素（軌道、物件標記含**局部座標軸**、**山丘標記/輪廓/高度**、**人字形屋頂輪廓/屋脊線**、網格、標籤），支援高亮和 **F7 微調目標的特殊高亮**。
- 支援地圖縮放、座標轉換、地圖圖像疊加，使用 **Pillow** 載入編輯器背景圖以支援更廣泛格式。
- 包含用於計算物件（如建築物、人字形屋頂）2D 凸包投影的輔助函數。

### scene_editor.py
- 提供 PyQt5 圖形化場景編輯器，可讀寫 scene.txt。
- 支援表格編輯（含**複製/貼上/刪除行**）、即時 **2D 小地圖預覽**（含高亮、**F7 座標軸**、雙擊定位 3D 視角）、**3D 自由飛行預覽**（含對應背景顯示、WASDQE 移動、Shift 加速）、**動態參數提示**與檔案管理（開啟、儲存、另存為）。
- **F7 模式**：選中物件後按 F7，進入座標微調模式，可用方向鍵和 PageUp/Down 精細調整選中物件的 X, Y, Z 座標，並在小地圖上顯示該物件的局部座標軸。
- 自動儲存和載入編輯器視窗佈局、小地圖和 3D 預覽視角、最後開啟的檔案路徑等設定到 `editor_settings.json`。

### texture_loader.py
- 處理紋理圖片載入、OpenGL 紋理快取與釋放。
- 支援 PNG 檔案載入、Mipmap 生成與快取管理。
- 快取中包含紋理是否有 Alpha 通道的標記。

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
pip install pygame PyOpenGL numpy Numba PyQt5 Pillow
```

## 如何執行

1.  確保 `scene.txt` 檔案和 `textures` 資料夾（包含所需的 `.png` 紋理檔）與 `main.py` / `scene_editor.py` 在同一目錄下。
2.  開啟終端機或命令提示字元，進入專案目錄。
3.  執行主程式：

    ```bash
    python main.py
    ```
4.  執行場景編輯器：
    ```bash
    python scene_editor.py
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
- **Esc**：
    - 若滑鼠已鎖定：解鎖滑鼠。
    - 若滑鼠未鎖定：退出模擬器。
- **滑鼠右鍵**：開啟選單 (目前僅 "載入場景" 和 "離開" 功能)

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

### 場景編輯器 (`scene_editor.py`) 操作
- **表格操作：**
    - **點擊儲存格：** 開始編輯。
    - **方向鍵：** 在儲存格間移動。
    - **Enter (在選中行或儲存格時，非編輯狀態)：** 在當前選中行的下方插入新行。
    - **Ctrl + Enter (Windows/Linux) / Cmd + Enter (macOS)：** 在當前行下方插入新行。
    - **Ctrl + C / Cmd + C：** 複製選中的一行或多行。
    - **Ctrl + V / Cmd + V：** 在當前選中行的下方貼上複製的行。
    - **Delete：** 刪除選中的**整行**。若僅選中單元格，則清空單元格內容。
    - **點擊行號：** 選取整行。按住 Ctrl/Shift 點擊可多選。
    - **雙擊表格行：** 小地圖預覽視窗會嘗試定位到該行物件的中心。
    - **F7 (當焦點在表格某一行時)：** 進入/退出該行物件的**座標微調模式**。
        - 在微調模式下：
            - **方向鍵 左/右：** 微調 X 座標 (-/+ 0.1，Shift加速為 1.0)。
            - **方向鍵 上/下：** 微調 Z 座標 (-/+ 0.1，Shift加速為 1.0)。
            - **PageUp/PageDown：** 微調 Y 座標 (+/- 0.1，Shift加速為 1.0)。
            - **Esc：** 退出微調模式。
            - 小地圖上會顯示目標物件的局部座標軸。
- **小地圖預覽 (Minimap)：**
    - **滑鼠左鍵拖曳：** 平移地圖視角。
    - **滑鼠滾輪：** 縮放地圖視角。
    - **點擊表格行：** 對應的物件或軌道段會在小地圖上高亮顯示。
    - **雙擊小地圖任意位置：** 3D 預覽視窗的攝影機會移動到該世界座標點 (保持 Y 高度不變)。
- **3D 預覽 (3D Preview)：**
    - **滑鼠左鍵點擊視窗：** 鎖定滑鼠以控制視角（如果未鎖定）。
    - **Tab：** 切換滑鼠鎖定/解鎖狀態。
    - **滑鼠移動 (鎖定時)：** 控制視角方向。
    - **W / A / S / D：** 前後左右移動相機。
    - **空格 / Q：** 上升 / 下降相機。
    - **Shift (按住)：** 加速移動。
    - **G：** 切換 3D 預覽中的地面網格顯示。
    - **Esc (鎖定時)：** 解鎖滑鼠。
- **選單：**
    - **File > Open (Ctrl+O)：** 開啟新的 `scene.txt` 檔案。
    - **File > Save (Ctrl+S)：** 儲存當前 `scene.txt`。若無當前路徑則觸發另存為。
    - **File > Save As (Ctrl+Shift+S)：** 將當前內容另存為新的 `scene.txt` 檔案。
    - **File > Reload (F5)：** 從磁碟重新載入當前 `scene.txt`（會提示是否放棄未儲存的修改）。
    - **File > Exit (Ctrl+Q)：** 退出編輯器（會提示是否儲存未儲存的修改）。
    - **Edit > Copy Rows (Ctrl+C)：** 複製選中行。
    - **Edit > Paste Rows (Ctrl+V)：** 貼上行。
    - **View > ...：** 顯示/隱藏各個面板（表格、小地圖、3D預覽）。

---

#### 備註
- 滑鼠預設鎖定於視窗中，按 Tab 或左鍵可切換鎖定狀態。
- 駕駛艙視角（C 鍵）僅於支援的場景有效。
- 重新載入 scene.txt（R 鍵）可即時反映場景檔案的變更。

## scene.txt 檔案格式說明（最新版）

scene.txt 每一行代表一個指令，空白行與 `#` 開頭為註解。下方為完整格式與參數說明範例：

```plain
# scene.txt 指令格式說明 (版本：加入 Sphere, Hill, Gableroof, Import, vbranch, 背景系統)

# 1. 地圖底圖 (用於小地圖)
map <file> <cx> <cz> <scale>
# 參數說明：
#   <file>   ：底圖檔名（如 map.png），放置於 textures 資料夾。
#   <cx>     ：地圖中心點在世界座標系中的 X 座標。
#   <cz>     ：地圖中心點在世界座標系中的 Z 座標。
#   <scale>  ：地圖縮放比例 (世界單位 / 像素)。例如 0.5 表示 1 像素代表 0.5 世界單位。

# 2. 軌道起點 (定義電車初始位置和相對座標系原點)
start <x> <y> <z> <angle°>
# 參數說明：
#   <x>, <y>, <z> ：起點的世界座標。
#   <angle°>      ：起始朝向角度（度）。0 度朝向世界 +Z 軸，90 度朝向世界 +X 軸。

# 3. 天空盒背景 (同一時間場景中只有一個背景有效)
skybox <base_name>
# 參數說明：
#   <base_name> ：天空盒貼圖的基礎名稱。程式會自動尋找 `textures/<base_name>_px.png`, `..._nx.png`, `..._py.png`, `..._ny.png`, `..._pz.png`, `..._nz.png` 這六個檔案。

# 4. 天空圓頂背景 (同一時間場景中只有一個背景有效)
skydome <texture_file>
# 參數說明：
#   <texture_file> ：用於天空圓頂的單張貼圖檔名（建議是等距柱狀投影圖），放置於 textures 資料夾。

# --- 軌道指令 (會更新當前位置和相對座標系原點) ---

# 5. 直線軌道
straight <length> [<grad‰>]
# 參數說明：
#   <length>  ：直線的水平投影長度。
#   <grad‰>   ：坡度（千分比，正值上坡，負值下坡），可選，預設 0。

# 6. 彎道軌道
curve <radius> <angle°> [<grad‰>]
# 參數說明：
#   <radius>  ：彎道半徑 (必須為正)。
#   <angle°>  ：彎道角度（度）。正值向左轉，負值向右轉。
#   <grad‰>   ：坡度（千分比），可選，預設 0。

# 7. 視覺化軌道分岔 (Visual Branch - 不影響電車主路徑，僅供視覺)
vbranch <type> <param1> <param2> [<grad‰>] [<direction_modifier>]
# 參數說明：
#   <type>    ：分岔類型，"straight" 或 "curve"。
#   --- 若 type 為 "straight" ---
#   <param1>  ：角度偏移 (度)，相對於父軌道末端切線方向。正值向左偏，負值向右偏。
#   <param2>  ：直線分岔的長度。
#   <grad‰>   ：(可選) 分岔的坡度，預設 0。
#   <direction_modifier> ：(可選，通常不用於 straight)
#   --- 若 type 為 "curve" ---
#   <param1>  ：彎道半徑。
#   <param2>  ：彎道掃過的角度 (度)。正值左轉，負值右轉 (基於 <direction_modifier>)。
#   <grad‰>   ：(可選) 分岔的坡度，預設 0。
#   <direction_modifier> ：(可選) "forward" (預設，基於父軌道末端切線向前延伸) 或 "backward" (基於父軌道末端切線向後延伸)。

# --- 物件指令 (座標相對於上一個 start 或軌道段的結束點) ---

# 8. 建築物 (立方體)
building <rel_x> <rel_y> <rel_z> <rx°> <rel_ry°> <rz°> <w> <d> <h> [<tex>] [<uOf>] [<vOf>] [<tAng°>] [<uvMd>] [<uSc>] [<vSc>]
# 參數說明：
#   <rel_x/y/z> ：相對於當前原點的座標 (x:左右, y:上下, z:前後)。
#   <rx°>       ：繞物件自身 X 軸旋轉角度。
#   <rel_ry°>   ：繞物件自身 Y 軸旋轉角度 (相對於當前軌道方向)。
#   <rz°>       ：繞物件自身 Z 軸旋轉角度。
#   <w/d/h>     ：寬(X) / 深(Z) / 高(Y)。
#   <tex>       ：貼圖檔名 (預設 "building.png")。
#   <uOf/vOf>   ：UV 座標偏移 (預設 0)。
#   <tAng°>     ：貼圖旋轉角度 (預設 0)。
#   <uvMd>      ：UV 模式 (0:世界單位, 1:物件比例貼滿各面, 2:使用預定義UV佈局如十字展開, 預設 1)。
#   <uSc/vSc>   ：UV 縮放 (模式 0 時為世界單位尺寸，模式 1 時為重複次數, 預設 1.0)。

# 9. 圓柱體
cylinder <rel_x> <rel_y> <rel_z> <rx°> <rel_ry°> <rz°> <rad> <h> [<tex>] [<uOf>] [<vOf>] [<tAng°>] [<uvMd>] [<uSc>] [<vSc>]
# 參數說明：(同 building，除了 <rad>/<h> 代表半徑/高度)
#   <tex> (預設 "metal.png")
#   <uvMd> (圓柱體通常不支援 uv_mode=2，預設 1)

# 10. 樹木 (使用交叉面片 Billboard，支援 Alpha Test)
tree <rel_x> <rel_y> <rel_z> <height> [<tex>]
# 參數說明：
#   <rel_x/y/z> ：相對於當前原點的座標。
#   <height>    ：樹的高度。
#   <tex>       ：樹木貼圖檔名 (建議使用帶 Alpha 通道的 PNG，預設 "tree_leaves.png")。

# 11. 球體
sphere <rel_x> <rel_y> <rel_z> <rx°> <rel_ry°> <rz°> <radius> [<tex>] [<uOf>] [<vOf>] [<tAng°>] [<uvMd>] [<uSc>] [<vSc>]
# 參數說明：(同 building，除了 <radius> 代表球體半徑)
#   <tex> (預設 "default_sphere.png")
#   <uvMd> (球體通常不支援 uv_mode=2，預設 1)

# 12. 山丘 (基於中心點生成)
hill <cx> <base_y> <cz> <radius> <peak_h_offset> [<tex>] [<uSc>] [<vSc>]
# 參數說明：
#   <cx>, <cz>      ：山峰最高點的世界座標 X, Z。
#   <base_y>        ：山丘基底的 Y 座標。
#   <radius>        ：山丘基底的半徑。
#   <peak_h_offset> ：山峰相對於 <base_y> 的高度偏移。
#   <tex>           ：應用於山坡的貼圖檔名 (預設 "grass.png")。
#   <uSc/vSc>       ：貼圖重複比例 (預設 10.0)。
#   <uOf/vOf>       ：(可選) 紋理 UV 座標偏移量 (預設 0.0)。

# 13. 人字形屋頂 (Gableroof)
gableroof <rel_x> <rel_y> <rel_z> <abs_rx°> <abs_ry°> <abs_rz°> <base_w> <base_l> <ridge_h_off> [<ridge_x_off>] [<eave_x_oh>] [<eave_z_oh>] [<tex_atlas>]
# 參數說明：
#   <rel_x/y/z>     ：相對於當前原點的座標 (x:左右, y:屋簷底部/牆頂, z:前後)。
#   <abs_rx°>       ：絕對 X 軸旋轉 (俯仰 Pitch)，預設 0。
#   <abs_ry°>       ：相對於世界座標的 Y 軸旋轉 (朝向 Yaw)。
#   <abs_rz°>       ：絕對 Z 軸旋轉 (側滾 Roll)，預設 0。
#   <base_w>        ：屋頂基底寬度 (沿屋頂局部X軸，山牆方向)。
#   <base_l>        ：屋頂基底長度 (沿屋頂局部Z軸，屋脊方向)。
#   <ridge_h_off>   ：屋脊相對於屋簷 (<rel_y>) 的高度差。
#   <ridge_x_off>   ：(可選) 非對稱屋脊的X偏移 (相對於基底寬度中心)，預設 0。
#   <eave_x_oh>     ：(可選) X方向的屋簷懸挑，預設 0。
#   <eave_z_oh>     ：(可選) Z方向的屋簷懸挑，預設 0。
#   <tex_atlas>     ：(可選) 使用的紋理圖集檔名 (預設 "default_roof_atlas.png")。使用預定義UV佈局。

# 14. 導入外部場景檔案
import <filepath> [<rel_x>] [<rel_y>] [<rel_z>] [<rel_angle°>]
# 參數說明：
#   <filepath> ：要導入的場景檔路徑 (相對於包含此 import 指令的檔案)。
#                導入的檔案內容會在其位置被解析，就像直接寫在那裡一樣。
#                支援相對路徑。程式會處理循環導入。
#   <rel_x> <rel_y> <rel_z> <rel_angle> ：(可選)外部場景的臨時原點(相對於目前)

# 備註：
# - `skybox` 或 `skydome` 指令會設定其後的軌道段開始時的背景。第一個出現的背景指令也會作為初始背景。
# - 物件指令 (`building`, `cylinder`, `tree`, `sphere`, `gableroof`) 的座標 `rel_x/y/z` 和相對 Y 旋轉 `rel_ry` (對於 building/cylinder/sphere) 或絕對旋轉 (gableroof) 是相對於定義它們之前的最後一個 `start` 或軌道指令 (`straight`, `curve`) 的結束點和方向（作為原點）。
# - `hill` 指令使用絕對世界座標 `cx`, `cz` 定義中心點。
# - `vbranch` 指令的參數定義的分岔是從其父軌道段的末端開始延伸的。
# - 帶 [] 的參數代表可省略，將使用預設值。
# - 指令順序很重要。
```

---

#### 範例
```plain
map map.png 0 0 1.0
start 0 0 0 0

skybox mysky # 設置初始天空盒

straight 100
vbranch straight 10 30 # 從第一個直線段末端，向左偏10度，長30米的分岔
vbranch curve 20 -45 0 backward # 從第一個直線段末端，向右反向彎曲45度，半徑20米的分岔

curve 50 90 0

skydome another_sky.png # 在彎道結束後，背景切換為天空圓頂

straight 50 10 # 一段上坡10‰，長50米的直軌
building 10 0 5 0 0 0 10 10 10 building_texture.png 0 0 0 2 # 使用UV Mode 2 (圖集)
cylinder 15 0 5 0 0 0 2 10 metal.png
tree 20 0 5 8 tree_transparent.png
gableroof 0 10 0 0 90 0 10 15 3 # 在Y=10高，長15寬10，屋脊高3，朝向世界+X
hill 100 20 50 30 15 ground_texture.png 5 5

import common_objects/park_area.txt # 導入公園區域的場景定義
```

---

## 紋理與地圖 (更新)

*   所有紋理檔案（建議使用 `.png` 格式以支援透明度，特別是樹木和可能的 UI 元素）應放置在名為 `textures` 的子資料夾中。
*   **天空盒 (Skybox)** 需要六張圖片，命名格式為 `<base_name>_px.png`, `..._nx.png`, `..._py.png`, `..._ny.png`, `..._pz.png`, `..._nz.png`，同樣放置在 `textures` 中。
*   **天空圓頂 (Skydome)** 使用單張圖片（建議是等距柱狀投影格式），放置在 `textures` 中。
*   小地圖底圖檔 (`map` 指令指定) 同樣放置在 `textures` 中。
*   程式會自動載入 `scene.txt` 中指定的紋理，或使用預設紋理。
*   對於使用 UV 佈局模式 (如 `building` 的 `uvMd=2` 或 `gableroof`) 的物件，其紋理圖集也應放置在 `textures` 中。

---

## Support the Project! ❤️

This project is a labor of love, and I'm incredibly grateful for your use and feedback. If you appreciate what I'm building and want to help keep it going, any contribution would be greatly appreciated!  Your support allows me to dedicate more time to development, bug fixes, and new features.

You can support us in the following ways:  
[![paypal](https://www.paypalobjects.com/en_US/i/btn/btn_donateCC_LG.gif)](https://www.paypal.me/pondahai)

