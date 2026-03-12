# Crypto Backtester - 專案狀態與任務記錄

## 當前狀態 (2026-03-11)

### Git 提交狀態
- **分支**: `main`
- **最新提交**: `aa30411`
- **狀態**: 已同步

### 最新提交內容
```
fix: Add syntax repair during loading phase

- Extract _fix_syntax_errors as reusable method
- Apply fix when loading generated strategy files
- Auto-repair and save fixed code
```

---

## 近期修復記錄

### 2026-03-11
1. **語法錯誤修復**：增強對 LLM 生成代碼的語法修復
   - 修復未閉合的三引號（docstring）
   - 生成時和加載時都會自動修復

2. **抽象方法問題**：
   - 使用 `type()` 動態創建子類實現 `generate_signals`
   
3. **測試狀態**：305 個測試全部通過

4. **模型統一**：
   - 所有 Agent 預設模型改為 `gemini-3-flash-preview`

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

### 測試
- `tests/` - 單元測試

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
