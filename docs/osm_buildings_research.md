# 研究筆記:OSM 自動生成沿線建物(2026-06-11)

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
   等距圓柱近似:`east = (lon−lon₀)·cos(lat₀)·111320`、
   `north = (lat−lat₀)·110540`(公尺)。10km 範圍內誤差 < 0.1%。
   **世界軸向(2026-06-12 由 scene.txt 淡水線實景校準驗證)**:
   遊戲世界 **+X=西、+Z=北**(圓山→石牌往北 z 增、往西 x 增),
   所以 `world_x = −east`、`world_z = north`;小地圖繪製時翻轉 X 顯示,
   `map` 底圖用正常北上、西左的圖即可,不需鏡像。
   預設原點角度(無 start 指令)下 scene_parser 的 rel→world 是恆等轉換,
   building 的 `ry = 長軸自東向逆時針角度`(矩形 180° 對稱,符號因此一致)。
   注意:auto-osm 區塊若放在 start/track 指令之後,rel 座標會被
   當時的相對原點再轉一次——編輯器 UI 階段需處理,驗證腳本先假設放檔首。
   **`latlon` 錨點指令(2026-06-12 新增)**:`latlon 緯度 經度` 把
   「軌道目前端點」(current_parse_pos) 綁定到經緯度,存在
   `Scene.geo_anchor`,換算函數 `Scene.world_to_latlon` /
   `latlon_to_world`。一個場景只取第一個錨點;可省略(建築庫場景)。
   有錨點時編輯器 OSM 生成會把產物換算到錨點對齊的世界座標
   (auto-osm 區塊仍插在檔首,識別字 `anchored` 記在 begin 註解)。
   **OSM 子場景嵌入(2026-06-12 新增)**:
   - `import 檔名 緯度 經度`(檔名後恰兩個數)= 經緯度形式:
     用母場景錨點換算世界座標當子場景原點,角度固定恆等(北對齊
     不旋轉),y=0。需要母場景的 `latlon` 寫在 import 行之前,
     否則警告並退回無偏移導入。舊形式 `import 檔 x y z angle` 不變。
   - `map` 改「第一張生效」:母場景底圖優先,後續(含子場景的)忽略;
     母場景沒底圖時,子場景底圖補位,且在經緯度 import 上下文中
     自動套用嵌入平移。
   - 編輯器對話框新增「輸出到子場景檔」:整檔覆寫(檔首 latlon＋
     import 註解行),import 行自動複製到剪貼簿,貼進母場景即嵌入。
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
