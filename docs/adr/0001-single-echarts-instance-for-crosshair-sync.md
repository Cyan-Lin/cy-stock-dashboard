# 十字線聯動採單一 ECharts instance + axisPointer.link，不用 echarts.connect()

最初規劃（見 DECISIONS.md）是用多個獨立 ReactECharts instance，靠 `echarts.connect()` 同步主圖與各副圖的十字線。T09 實作時發現 `connect()` 只能同步 tooltip 顯示/隱藏，無法同步 crosshair 游標位置本身，也無法讓 `dataZoom` 真正跨圖同步。改為單一 ECharts instance、主圖與所有副圖各佔一個 `grid`，透過 `axisPointer.link: [{ xAxisIndex: 'all' }]` 與共用 `dataZoom`（`xAxisIndex: [0,1,2,3]`）達成十字線與縮放的真正同步。後續所有副圖（T10、T11...）都沿用此單一 instance + 多 grid 架構，不再拆成獨立 instance。
