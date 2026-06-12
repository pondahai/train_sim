# TODO — 待辦清單

## 第一部分:效能優化

2026-06-11 效能檢視後的待辦項目。已完成的部分:uniform location 快取、
`draw_track` 的 `glGetError` 改為除錯旗標(`DEBUG_TRACK_GL_CHECKS`)、
HUD 與小地圖格線標籤的文字紋理快取、`texture_loader.py` 的 PyQt5 import 改為可選。

驗證方式:打開 `main.py` 內已註解的 cProfile 程式碼實測,或比較標題列 FPS。

---

## ~~高優先:球改用 VBO~~(2026-06-12 完成)

圓柱、樹於合流時完成;球體已比照圓柱模式改 VBO+著色器
(`generate_sphere_mesh_data` / `create_sphere_buffers`,與圓柱共用著色器),
無 VBO 的條目自動退回立即模式。著色器路徑不支援 sphere 的
`tex_angle_deg` 紋理旋轉(與圓柱相同限制),需要時走 fallback。

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
- ~~**小地圖軌道線每幀逐點轉換**~~ 已於 2026-06-12 合流時完成:
  軌道改烘進靜態 FBO 紋理(畫在建築之上),模擬器小地圖不再每幀重畫。
- **編輯器文字繪製尚未接上快取**:`minimap_renderer.py` 編輯器路徑
  (約 1556、1776、1813、1876、1974、2081、2329、2402、2478、2491 行)
  仍用舊的 `renderer._draw_text_texture`(每次重建紋理)。模擬器路徑已改用
  `renderer._get_cached_text_texture` + `_draw_text_quad`,編輯器可比照換掉。

---

# 第二部分:新功能

## OSM 自動生成沿線建物

編輯器設定經緯度,自動從開源地圖(OSM/Overpass API)抓取建物輪廓與
樓層高度,沿線生成 `building` 方塊;另可把淡化地圖當背景。
評估結論:可行,渲染端零修改。

詳細研究與技術設計見 [docs/osm_buildings_research.md](docs/osm_buildings_research.md)。

實作順序:
1. ~~獨立驗證腳本(經緯度＋範圍 → building 行)~~
   2026-06-12 完成:`tools/osm_buildings.py`(含 `--selftest` 離線測試、
   Overpass 查詢快取)。士林站半徑 150m 實測 118 棟可正常解析載入。
2. ~~底圖拼接＋淡化(輸出 `map` 行)~~
   2026-06-12 完成:`tools/osm_basemap.py`(圖磚拼接、降飽和+白化、
   自動 zoom、圖磚快取)。重要發現:遊戲世界 +X=西、+Z=北
   (由 scene.txt 淡水線實景校準驗證),兩支腳本的座標慣例已對齊。
   合併測試場景:`scene_osm士林測試.txt`。
### 2026-06-12 後續:OSM 子場景嵌入(完成)

- `import 檔名 緯度 經度`:經緯度形式 import(需母場景 latlon 在前),
  子場景原點由錨點換算、北對齊不旋轉、y=0;舊形式不變。
- `map` 改第一張生效:母場景底圖優先;母場景無底圖時子場景底圖
  補位並套用嵌入平移。多底圖同時顯示是未來工程(map 需改清單)。
- 編輯器 OSM 對話框新增「輸出到子場景檔」:整檔覆寫、
  import 行自動進剪貼簿。

### 2026-06-12 後續:latlon 經緯度錨點(完成)

- 新場景指令 `latlon 緯度 經度`:把「軌道目前端點」錨定到該經緯度,
  一個場景只取第一個錨點(後續忽略+警告);**可以沒有**
  (建築庫等內嵌用場景檔不受影響)。
- 編輯器小地圖:滑鼠指標顯示世界座標,場景有錨點時加顯經緯度。
- OSM 生成對話框:有錨點時自動帶入指標所指經緯度,
  且生成的建物/底圖用錨點換算世界座標,直接對齊既有軌道。
- 同日修復:編輯器小地圖樹/圓柱/球/山丘的固定長度解包
  在 VBO 擴充元組後失敗,樹的未捕獲例外讓整個動態繪製
  (含軌道)中斷——「小地圖軌道消失」的根因。

3. ~~編輯器 UI(經緯度輸入、範圍選擇、生成/清除按鈕)~~
   2026-06-12 完成:scene_editor.py Tools 選單 →「OSM 沿線建物…」
   (`OsmImportDialog` + `_run_osm_import`,直接 import tools/ 模組)。
   區塊插在檔首、重新生成自動清舊區塊。待改進:網路查詢目前會
   暫時凍結 UI(只有等待游標)、auto-osm 區塊放在 start/track 之後
   會被相對原點再轉一次(見研究筆記)。
