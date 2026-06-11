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
