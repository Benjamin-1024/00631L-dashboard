# 00631L 正二反彈交易 Dashboard（GitHub Pages 自動更新版）

## 一次性設定（約 10 分鐘）
1. GitHub 建立新 repo（建議 Public；私有 repo 使用 Pages 需付費方案），把本資料夾所有檔案推上去（含 `.github` 隱藏資料夾）。
2. Settings → Pages → Build and deployment → Source 選 **GitHub Actions**。
3. Actions 分頁 → `update-data-and-deploy` → Run workflow，手動跑第一次。
4. 完成後網址為 `https://<帳號>.github.io/<repo>/`，用手機或電腦開啟即可。
5. 點開該次 run 的 log 看每個來源是否成功；失敗訊息也會顯示在 Dashboard「數據與圖表」最上方。

## 排程
cron `0 0,2,4,10,14 * * *`（UTC）＝ 台灣時間 8:00、10:00、12:00、18:00、22:00。
GitHub 排程可能延遲，高峰時偶爾跳過；Public repo 若 60 天無活動會被停用排程（每次更新都會 commit，通常不受影響，仍建議偶爾檢查）。

## 資料來源與限制
| 指標 | 來源 | 備註 |
|---|---|---|
| 櫃買指數、60MA | 櫃買中心 OpenAPI（歷史資料） | 60MA 需 60 個交易日；可放 `docs/data/seed_otc.csv`（欄位 date,close）補歷史 |
| 外資台指期淨空單 | 期交所 OpenAPI（三大法人-區分各期貨契約-依日期） | 期交所 OpenAPI 僅提供最新一個交易日，歷史靠每天累積 |
| 美國 VIX | Cboe 公開 CSV | |
| 台灣融資金額 | 證交所信用交易統計 | 無融資維持率 |
| 韓國去槓桿、亞洲破線 | 無穩定公開來源 | 維持手動輸入 |

欄位名稱與路徑以官方 swagger 自動尋找、以關鍵字解析，**第一次執行請檢查 log 與 Dashboard 的來源狀態**；官方若改版，該來源會顯示失敗而不是補假數據，需要調整 `scripts/fetch_data.py`。

## 隱私
判斷、手動數據、交易紀錄只存在你瀏覽器的 localStorage，不會進 GitHub。
