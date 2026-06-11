# TODO — 待辦清單

## 第一部分:效能優化

2026-06-11 效能檢視後的待辦項目。已完成的部分:uniform location 快取、
`draw_track` 的 `glGetError` 改為除錯旗標(`DEBUG_TRACK_GL_CHECKS`)、
HUD 與小地圖格線標籤的文字紋理快取、`texture_loader.py` 的 PyQt5 import 改為可選。

驗證方式:打開 `main.py` 內已註解的 cProfile 程式碼實測,或比較標題列 FPS。

---

## 高優先:圓柱 / 球 / 樹改用 VBO(工程量較大)

目前這三類物件仍走即時模式,每幀重新計算幾何:

- `draw_cylinder`(renderer.py,`gluNewQuadric` 處)每個圓柱每幀
  `gluNewQuadric()` → 重新鑲嵌整個網格 → `gluDeleteQuadric()`。
- `draw_sphere`(renderer.py)同樣每幀重建 quadric。
- `draw_tree`(renderer.py)每棵樹每幀 `glPushAttrib`/`glPopAttrib`
  (極昂貴的狀態保存)加 `glBegin/glEnd` 即時模式。

做法:比照 buildings/hills 的模式,載入場景時建立 VBO/VAO
(`create_building_buffers` 可當範本),繪製時只綁 VAO + `glDrawArrays`。
樹只是兩個交叉面片,所有樹可合併成單一 VBO 一次 draw call 畫完,
alpha test 等狀態整批設定一次。

## 中優先:每幀矩陣讀回與重複求逆

- `glGetFloatv(GL_MODELVIEW_MATRIX / GL_PROJECTION_MATRIX)` 每幀讀回三次:
  視錐更新(frustum_culling.py `update()`)、建築區塊、山丘區塊
  (renderer.py `draw_scene_objects`)。`glGetFloatv` 會造成 pipeline 同步。
  應在 `draw_scene_objects` 開頭讀一次,傳給視錐與兩個 shader 區塊共用。
- 建築與山丘各自用 `np.linalg.inv` 從 modelview 反推相機位置,每幀兩次。
  相機位置 `camera_instance` 本來就有,從 main.py 傳進來即可,完全不必求逆。

## 中優先:每物件每幀的 `glIsTexture`

建築(`draw_scene_objects` 內)、山丘、圓柱(`draw_cylinder`)、
樹(`draw_tree`)、球(`draw_sphere`)每幀都對每個物件呼叫 `glIsTexture`
(driver 往返)。紋理有效與否在載入時就確定,應在 scene_parser 打包資料時
存一個布林旗標,繪製時直接用。

## 中優先:`draw_track` 的 draw call 合併

每段軌道分道碴/左軌/右軌三次 `glBindVertexArray` + `glDrawArrays`,
visual branches 再各三次。段數多時可把同類幾何合併成單一大 VBO,
一次畫完所有道碴、一次畫完所有軌條。

## 低優先(小項)

- **`glTexParameteri` 每幀重設**:`draw_sphere`、`draw_tree` 每次呼叫都設
  wrap mode。wrap mode 是紋理物件屬性,在 `texture_loader.load_texture`
  載入時設一次即可。
- **視錐剔除的 Python 迴圈與除錯碼**(frustum_culling.py):
  - 平面正規化用 Python 迴圈逐一處理,可向量化成一行 numpy
    (`np.linalg.norm(planes[:, :3], axis=1)`)。
  - `update()` 內每 120 幀做一次 `np.linalg.inv` + `print` 的 DEBUG 區塊,
    正式執行時應移除或加旗標(目前每 2 秒固定輸出 DEBUG 訊息)。
- **`import numpy as math`**(main.py、renderer.py 等):純量運算
  (`math.radians`、`math.cos`、`arctan2`…)走 numpy 比內建 `math` 慢數倍,
  熱路徑(每幀的小地圖角度計算等)受影響。改回內建 `math` 需逐一確認
  numpy 專有函數名(如 `arctan2` → `atan2`)。
- **小地圖軌道線每幀逐點轉換**(minimap_renderer.py
  `draw_simulator_minimap` 的 B.1 區塊):軌道是靜態的,每幀對每個點呼叫
  `_world_to_map_coords_adapted` + 即時模式頂點。可預先把點存成 numpy
  陣列做整批運算,或烘進 VBO 後只更新平移/縮放。
- **編輯器文字繪製尚未接上快取**:`minimap_renderer.py` 編輯器路徑
  (約 1556、1776、1813、1876、1974、2081、2329、2402、2478、2491 行)
  仍用舊的 `renderer._draw_text_texture`(每次重建紋理)。模擬器路徑已改用
  `renderer._get_cached_text_texture` + `_draw_text_quad`,編輯器可比照換掉。

---

# 第二部分:新功能研究 — OSM 自動生成沿線建物(2026-06-11)

目標:場景編輯器中設定經緯度,一鍵把真實地圖的建物(含樓層高度)
自動生成為沿線的 `building` 方塊,並可選擇把淡化地圖當背景。

**結論:可行,中等工程量,渲染端零修改** —— 因為產物直接落在現有
scene.txt 指令格式(`building x y z rx ry rz w d h ...`、
`map 圖檔 cx cz scale`)。

## 資料來源

- **首選:OpenStreetMap + Overpass API**
  - 建物輪廓(footprint 多邊形)全球涵蓋,台灣市區涵蓋率不錯
  - 高度資訊:`building:levels`(樓層數)、`height`(公尺)標籤
  - Overpass API 免費、免金鑰,HTTP 查詢回傳 JSON,Python 內建
    `urllib` 即可呼叫,不需 GIS 套件
  - **限制**:台灣很多建物輪廓有但樓層標籤沒填(市中心較完整,
    住宅區參差),必須有預設高度 fallback(如 2~4 層 × 3m/層)
  - 授權 ODbL,需標示「© OpenStreetMap contributors」
- **第二階段選項:內政部國土測繪中心(NLSC)/ 縣市開放資料**
  - 台灣建物圖資含樓層數,品質比 OSM 完整
  - 格式為 SHP/GeoJSON,解析工作量較大
  - NLSC 的 WMTS「臺灣通用電子地圖」可當底圖圖磚來源

## 技術設計

1. **經緯度 → 世界座標**:編輯器設原點 (lat₀, lon₀) 對應世界 (0,0),
   等距圓柱近似:`x = (lon−lon₀)·cos(lat₀)·111320`、
   `z = (lat−lat₀)·110540`(公尺)。10km 範圍內誤差 < 0.1%。
2. **淡化地圖背景**:抓 XYZ 圖磚(OSM tiles 或 NLSC WMTS)拼成 PNG,
   拼圖時降飽和度/加白,存到 `textures/`,輸出
   `map 圖檔.png cx cz scale` 接上現有背景機制。
   注意 Web Mercator 的 scale(公尺/像素)隨緯度變化,取中心緯度計算。
3. **沿線生成建物**:
   - 取 `track.segments` 所有點算 bbox,外擴用戶設定範圍(50/100/300m)
   - Overpass 查詢 bbox 內建物多邊形
   - 每個多邊形算最小面積外接矩形(rotating calipers,numpy 約 50 行)
     → 得 `w`、`d`、旋轉角 `ry`;中心點 → `x, z`;
     高度 = `height` 標籤,否則 `levels × 3m`,否則預設值
   - 過濾:建物中心到軌道折線最短距離 ≤ 設定範圍
   - 輸出一批 `building` 行附加到 scene.txt,加標記註解(如 `# auto-osm`)
     以便「重新生成」時先刪舊的

## 風險與注意事項

- 不規則建物(L 形、口字形)壓成單一矩形會失真;第一版可接受,
  之後可凹多邊形切成多個方塊
- 市區沿線 300m 可能撈到上千棟:building 已走 VBO 路徑扛得住,
  但建議加數量上限或最小面積過濾(濾掉 < 20m² 的小棚子)
- Overpass 有流量限制,查詢結果應 cache 成本地 JSON,離線可重生成

## 建議實作順序

1. **先寫獨立命令列腳本**:輸入經緯度＋範圍 → 輸出 building 行。
   不碰編輯器 UI,先驗證資料品質與矩形擬合效果(風險最高的部分)
2. 底圖拼接＋淡化,輸出 `map` 行
3. 編輯器 UI:經緯度輸入框、範圍下拉、生成/清除按鈕
