# Crypto Backtester - 專案狀態與任務記錄

## 當前狀態 (2026-03-13)

### Git 提交狀態
- **分支**: `main`
- **最新提交**: `7d637e2`
- **狀態**: 開發中

### 最新提交內容
```
docs: Update AGENTS.md with latest fixes and status

- Document latest strategy-generation fixes
- Record test status and model defaults
- Refresh project state summary
```

---

## 近期修復記錄

### 2026-03-13
1. **Agentic loop 接線完成**
   - `conversation.py` 已改為呼叫 `StrategyRDWorkflow`
   - 流程為 Engineer codegen -> validation -> smoke backtest -> evaluation -> feedback -> revise

2. **Engineer Agent 結構化輸出強化**
   - 新增 `EngineerCodeResult`
   - 支援 `summary / assumptions / code / raw_response`
   - 不再只依賴 JSON，改用區塊式回應並加上 Python 抽取清洗

3. **代碼驗證與 artifacts**
   - 每輪保存 `.py` artifact
   - 每輪保存 `.raw.txt` 原始 LLM 回應
   - 驗證包含 syntax、BaseStrategy subclass、instantiation、smoke backtest

4. **對話式流程修復**
   - 修正既有 MD 策略載入後未同步 `current_strategy` 的問題
   - 修正 symbol 抽取，避免誤找 `BTCUSDT_MA_1h.csv`
   - loop 失敗時不再嘗試載入最後一個未驗證通過的壞檔

5. **Optuna 修復**
   - `short_window < long_window` 約束只對均線交叉策略生效
   - 避免 BBand 策略被錯誤 prune

6. **測試與自測**
   - 新增 `scripts/debug_agentic_loop.py`，可在不打 API 的情況下驗證閉環流程
   - 補充 `tests/test_strategy_developer_agent.py`
   - 補充 `tests/test_strategy_rd_workflow.py`
   - 補充 `tests/test_conversation_md.py`

### 已知問題
1. **Gemini codegen 穩定性仍不足**
   - 真實 API 執行時，Engineer Agent 仍可能回傳半截 class 或缺少 `generate_signals`
   - 目前已可保存 raw response 以便精確比對模型輸出

2. **測試環境依賴不一致**
   - 目前本機 `pytest` 會被 `pandas` / `numpy` binary incompatibility 卡住
   - 錯誤為 `numpy.dtype size changed`

---

## 專案架構願景

### 目標
建立一個結合 VSS (Video/Signal/State) 概念的加密貨幣交易系統，實現即時市場分析與人機對齊。

### 多智能體系統規劃
模擬真實量化交易團隊，包含以下角色：
1. **市場監控 Agent** - 提供最新市場資訊
2. **風險管理 Agent** - 做出交易決策
3. **策略開發 Agent** - 創建新策略
4. **回測 Agent** - 測試策略、開發指標
5. **程式碼/工程 Agent** - 實作程式碼
6. **彙報 Agent** - 向人類經理人報告

### 技術選型
- **多智能體框架**: LangGraph
- **LLM API**: Google Gemini (gemini-3-flash-preview)
- **現有系統**: OpenHands + MiniMax

---

## 待完成任務

### P0 - ✅ 已完成
1. ✅ 代碼生成與加載修復
2. ✅ 語法錯誤自動修復
3. ✅ 模型統一

### P1 - ✅ 完成
4. ✅ 研究 LangGraph + OpenRouter 整合

### P2 - 功能擴展
5. 完善 VSS 模組
6. 完善 Alignment 模組

### P1.5 - 進行中
7. 穩定 Engineer-driven strategy code loop
8. 收斂 structured output / revision prompt
9. 補齊 deterministic workflow smoke tests

---

## 討論要點

### LangGraph + OpenRouter 整合重點
1. 使用 LangGraph 的 StateGraph 定義 workflow
2. 每個節點代表一個 Agent
3. 使用 OpenRouter API 調用多種 LLM
4. 支持條件分支和循環

### 建議的 Agent 設計
- 每個 Agent 有明確的 role 和 responsibility
- 使用 structured output 確保輸出格式一致
- 實現 feedback loop 持續優化

---

## 檔案位置參考

### 核心模組
- `vss/` - VSS 市場分析
- `alignment/` - 人機對齊
- `backtest/` - 回測引擎
- `strategies/` - 交易策略

### Agent
- `agents/conversation.py` - 對話式策略開發
- `agents/strategy_developer_agent.py` - 策略開發 Agent
- `agents/strategy_evaluator_agent.py` - 策略評估 Agent
- `agents/reporter_agent.py` - 報告生成 Agent
- `agents/strategy_rd_workflow.py` - Agentic 策略研發閉環

### 測試
- `tests/` - 單元測試
- `scripts/debug_agentic_loop.py` - 不打 API 的閉環自測腳本

### 配置文件
- `pyproject.toml`
- `requirements.txt`

---

## 下次啟動時的初始化命令

```bash
cd /media/nexcom/data/alan/crypto-backtester
git status
git log --oneline -3
```
