# cy-stock-dashboard

個人台股儀表板：整合大盤 K 線、融資動向、警示系統，全部在單一 ECharts instance 內以多 grid 呈現。

## Language

**融資餘額（張）**：
`margin_data.margin_balance`，融資的股票張數（每張 1000 股）。目前圖表不使用這個欄位。
_Avoid_: 融資餘額（不加單位時容易跟金額搞混）

**融資金額**：
`margin_data.margin_balance_amount`，融資餘額對應的金額，DB 原始單位是千元。API 對外新增 `margin_amount_100m` 欄位換算為「億元」（÷ 100,000）供圖表顯示；刻意不叫 `margin_balance_*`，避免跟上面的張數欄位混淆。DECISIONS.md／T10 AC 寫的「融資餘額（億元）」語意上指的就是這個欄位，不是 `margin_balance`。
_Avoid_: 融資餘額

**融資維持率**：
`(現值 / 融資金額) * 100%`，衡量斷頭風險的比率，低於 140% 觸發斷頭風險警示。DB 與 `evaluator.py` 內部門檻（`Decimal("1.4")`）都用小數比率；`/api/margin` 在 API 邊界轉成百分比數字（× 100）回傳給前端圖表，欄位名維持 `margin_maintenance_ratio` 不變。

**籌碼洗淨指標**：
Rolling window（預設 20 個交易日，由 T06 的 Alert Evaluation Service 確認）內，融資餘額下降速率 ÷ 大盤跌幅。> 1 代表融資跌幅大於指數跌幅（籌碼洗淨充分，偏多訊號）；< 1 代表籌碼未洗淨（偏空訊號）。當該區間大盤未下跌時無法定義，該日不產生數值（時間序列上會出現資料缺口，前端畫圖時斷線、不用 `connectNulls` 硬接起來）。公式的唯一來源是 `backend/app/alerts/evaluator.py` 的 `chip_washout()` 純函數，且**永遠在日頻資料上以 window=20 個交易日計算**——週K/月K 顯示時是對這個算好的日頻序列取樣（每個 bucket 取最後一個交易日的值），不會在週/月聚合後的資料上重新套 20 期窗口（語意會從 20 個交易日變成 20 週/月，不對）。
_Avoid_: 融資減肥速度

**十字線聯動**：
主圖與所有副圖共用同一個 ECharts instance、多個 grid，透過 `axisPointer.link`（`{xAxisIndex: 'all'}`）讓游標停在任一 grid 時，十字線同步顯示在所有 grid 的同一天。不透過 `echarts.connect()`（多 instance 模式）——已驗證那個方式只能同步 tooltip 顯示/隱藏，無法同步游標位置。見 ADR-0001。
_Avoid_: echarts.connect() 多圖聯動

**副圖一 / 副圖二**：
單一 ECharts instance 內的 grid 2（融資動向面板：融資餘額＋融資維持率＋籌碼洗淨）與 grid 3（動態面板：資券比，月K 額外顯示 KD）。grid 0 是主圖 K 線，grid 1 是量能柱（附屬主圖，不算獨立副圖）。
