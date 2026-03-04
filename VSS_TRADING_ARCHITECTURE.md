# VSS 人機協作交易系統架構

## 核心理念

傳統程式交易像是黑盒子，只能事後從記錄中知道為什麼發生交易。本系統旨在實現**交易前的對齊机制**，讓人類與 VSS/Agent 在市場觀察期間持續校準判斷，確保雙方共識後才執行交易。

## 系統架構

```
┌─────────────────────────────────────────────────────────────┐
│                      市場數據流                               │
│                   (K線、訂單簿、成交量)                        │
└─────────────────────────┬───────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│                    即時市場觀察模組                            │
│              (每次新 K 棒產生時觸發分析)                       │
└────────┬──────────────────────────────┬────────────────────┘
         │                              │
         ▼                              ▼
┌──────────────────────┐      ┌──────────────────────────┐
│      人類判斷         │      │     VSS/Agent 分析        │
│  「看起來像多頭趨勢」 │      │   「價格處於上升趨勢」      │
└──────────┬───────────┘      └────────────┬─────────────┘
           │                                │
           └────────────┬───────────────────┘
                        ▼
              ┌─────────────────┐
              │   對齊評估模組   │
              └────────┬────────┘
                       │
         ┌─────────────┴─────────────┐
         │                           │
         ▼                           ▼
    [對齊]                      [不對齊]
         │                           │
         ▼                           ▼
    執行交易                   分析差異原因
         │                           │
         │                           ▼
         │                    ┌───────────────┐
         │                    │  更新/再訓練   │
         │                    │   Agent 能力   │
         │                    └───────────────┘
         │                           │
         └─────────────┬─────────────┘
                       ▼
                 記錄並持續監控
```

## 核心模組設計

### 1. 市場觀察器 (Market Observer)
- 即時監控市場數據流
- 每次新 K 棒產生時觸發 VSS 分析
- 可設定觀察頻率（每根 K 棒、每 N 根 K 棒）

### 2. VSS 分析引擎 (VSS Analysis Engine)
- 圖像辨識：分析 K 線圖形
- 模式搜尋：識別技術形態
- 異常偵測：發現異常波動
- 輸出：結構化市場狀態描述

### 3. 人類判斷輸入介面 (Human Judgment Interface)
- 快速輸入市場觀點
- 預設選項 + 自訂輸入
- 記錄時間戳與上下文

### 4. 對齊評估模組 (Alignment Evaluator)
- 比較人類與 Agent 判斷
- 計算對齊分數
- 記錄差異分析

### 5. 決策控制器 (Decision Controller)
- 對齊門檻判斷
- 交易執行閘門
- 風險控制檢查

### 6. 反饋學習系統 (Feedback Learning System)
- 收集人類確認/糾正
- 生成訓練數據
- 模型更新 pipeline

## 數據流設計

```
市場數據 ──▶ 觀察觸發 ──▶ VSS 分析 ──▶ 結構化輸出
                              │
                              ▼
                       人類判斷輸入
                              │
                              ▼
                       對齊評估 ──▶ [是] ──▶ 執行交易
                              │
                              ▼ [否]
                       差異分析 ──▶ 反饋記錄
                              │
                              ▼
                       模型更新 Queue
```

## 系統模組說明

### Alignment 模組 (alignment/)

人機對齊核心模組，實現人類判斷與 VSS 分析結果的對齊評估。

| 檔案 | 說明 |
|------|------|
| `types.py` | 決策相關類型定義 (`Decision`, `DecisionReason`) |
| `evaluator.py` | `AlignmentEvaluator` - 對齊評估器 |
| `recorder.py` | `JudgmentRecorder` - 判斷記錄器（持久化） |
| `controller.py` | `DecisionController` - 決策控制器 |

### VSS 模組 (vss/)

市場狀態視覺化分析模組。

| 檔案 | 說明 |
|------|------|
| `types.py` | 類型定義 (`MarketState`, `HumanJudgment`, `VSSAnalysisResult`, `AlignmentResult`) |
| `analyzer.py` | `VSSAnalyzer` - 市場分析器 |
| `observer.py` | `VSSObserver` - 市場觀察器 |

### 主要 API

```python
from alignment import AlignmentEvaluator, JudgmentRecorder, DecisionController
from vss.types import HumanJudgment, VSSAnalysisResult, AlignmentResult

# 1. 記錄人類判斷
recorder = JudgmentRecorder(storage_dir="./data/judgments")
recorder.record_judgment(human_judgment)

# 2. 執行對齊評估
evaluator = AlignmentEvaluator(misalignment_threshold=0.3)
result = evaluator.evaluate(human_judgment, vss_result)

# 3. 決策控制
controller = DecisionController(
    min_alignment_score=0.7,
    require_human_approval=True
)
decision = controller.make_decision(result)
```

## 關鍵設計原則

1. **共識優先** - 人類與 Agent 判斷不一致時，不執行交易
2. **持續校準** - 每次市場觀察都是對齊驗證的機會
3. **透明記錄** - 所有判斷、差異、決策皆需記錄
4. **安全閘門** - 可隨時暫停/介入中斷交易
5. **持續學習** - 將人類反饋轉化為訓練數據

## 預期效益

- 減少「黑盒子」帶來的不可控風險
- 結合人類經驗與 AI 處理能力
- 建立可解釋的交易決策過程
- 透過持續校準提升 Agent 判斷準確性

## 未來擴充方向

- 多時間框架對齊
- 多市場/多標的同時監控
- 團隊協作判斷聚合
- 歷史對齊率分析儀表板

---

*最後更新：2026-03-04 (新增 Alignment 模組文檔)*
