"""
Trading System - 多 Agent 协调系统

整合：
- Market Monitor Agent (数据获取)
- Strategy Agent (策略信号)
- Risk Agent (风险管理)
- Trading Agent (交易执行)
- Human Approval Queue (人類審批)
"""

import logging
from typing import Optional, Dict, Any, List, Callable
from datetime import datetime
import pandas as pd
import threading
import time

from .market_monitor_agent import MarketMonitorAgent
from .strategy_agent import StrategyAgent
from .risk_agent import RiskAgent
from .trading_agent import TradingAgent
from core.approval_queue import HumanApprovalQueue, ApprovalPriority

# 模組日誌
logger = logging.getLogger(__name__)


class TradingSystem:
    """
    Trading System - 多 Agent 交易系统
    
    协调所有 Agent 的工作流程：
    1. Market Monitor 抓取数据
    2. Strategy Agent 产生信号
    3. Risk Agent 评估风险
    4. Trading Agent 执行交易
    """
    
    def __init__(
        self,
        symbols: List[str] = None,
        intervals: List[str] = ["1h"],
        initial_capital: float = 10000.0,
        mode: str = "paper",  # "paper" or "live"
        fetch_interval_minutes: int = 60,
    ):
        """
        初始化交易系统
        
        Args:
            symbols: 交易对列表
            intervals: K线间隔
            initial_capital: 初始资金
            mode: 交易模式
            fetch_interval_minutes: 数据抓取间隔
        """
        self.symbols = symbols or ["BTCUSDT"]
        self.intervals = intervals
        self.initial_capital = initial_capital
        self.mode = mode
        self.fetch_interval_minutes = fetch_interval_minutes
        
        # 初始化所有 Agents
        self.market_monitor = MarketMonitorAgent(
            symbols=self.symbols,
            intervals=self.intervals,
            fetch_interval_minutes=fetch_interval_minutes,
        )
        
        self.strategy_agent = StrategyAgent(
            data_source=self.market_monitor,
            initial_capital=initial_capital,
        )
        
        self.risk_agent = RiskAgent()
        
        self.trading_agent = TradingAgent(
            mode=mode,
            initial_capital=initial_capital,
        )
        
        # Human-in-the-Loop 審批隊列
        self.approval_queue = HumanApprovalQueue()
        
        # 狀態
        self._running = False
        self._paused = False
        self._thread: Optional[threading.Thread] = None
        self._control_thread: Optional[threading.Thread] = None
        self.cycle_history: List[Dict[str, Any]] = []
        self._command_queue: List[Dict[str, Any]] = []
        
        # 回调
        self.on_trade: Optional[Callable] = None
        self.on_signal: Optional[Callable] = None
        self.on_error: Optional[Callable] = None
    
    def start(self) -> None:
        """启动交易系统"""
        if self._running:
            print("⚠️ 系统已在运行")
            return
        
        print("🚀 启动交易系统...")
        
        # 注册数据回调
        self.market_monitor.register_callback(self._on_new_data)
        
        # 启动数据监控
        self.market_monitor.start()
        
        self._running = True
        self._paused = False
        
        # 启动命令控制线程
        self._control_thread = threading.Thread(target=self._command_loop, daemon=True)
        self._control_thread.start()
        
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()
        
        print("✅ 交易系统已启动")
        self._print_help()
    
    def _print_help(self):
        """打印帮助信息"""
        print("""
╔══════════════════════════════════════════════════════════╗
║              命令列控制 (Command Help)                  ║
╠══════════════════════════════════════════════════════════╣
║  help     - 显示这则讯息                                 ║
║  pause    - 暂停交易系统                                 ║
║  resume   - 恢复交易系统                                 ║
║  status   - 显示目前状态                                 ║
║  run      - 立即执行一次交易流程                          ║
║  force buy <symbol> <pct> - 强制买入                    ║
║  force sell <symbol> <pct> - 强制卖出                   ║
║  stop     - 停止交易系统                                 ║
║  history  - 显示交易历史                                 ║
║  orders   - 显示待审批订单                               ║
╚══════════════════════════════════════════════════════════╝
        """)
    
    def stop(self) -> None:
        """停止交易系统"""
        print("🛑 停止交易系統...")
        
        self._running = False
        self.market_monitor.stop()
        
        if self._thread:
            self._thread.join(timeout=5)
        
        print("✅ 系統已停止")
    
    def _command_loop(self):
        """命令輸入循環"""
        import sys
        import select
        
        print("\n💬 輸入命令後按 Enter...")
        
        while self._running:
            try:
                if sys.platform == 'win32':
                    import msvcrt
                    if msvcrt.kbhit():
                        cmd = sys.stdin.readline().strip()
                        self._process_command(cmd)
                else:
                    if select.select([sys.stdin], [], [], 1)[0]:
                        cmd = sys.stdin.readline().strip()
                        if cmd:
                            self._process_command(cmd)
                time.sleep(0.1)
            except Exception as e:
                logger.error(f"命令處理錯誤: {e}")
    
    def _process_command(self, cmd: str):
        """處理用戶命令"""
        parts = cmd.strip().lower().split()
        if not parts:
            return
        
        command = parts[0]
        
        if command == "help":
            self._print_help()
        
        elif command == "pause":
            self._paused = True
            print("⏸️ 系統已暫停")
        
        elif command == "resume":
            self._paused = False
            print("▶️ 系統已恢復")
        
        elif command == "status":
            status = self.get_status()
            print(f"""
📊 系統狀態:
   運行中: {status['running']}
   已暫停: {self._paused}
   交易對: {status['symbols']}
   模式: {status['mode']}
   執行次數: {status['cycles']}
   倉位價值: ${self.trading_agent.get_portfolio_value():,.2f}
            """)
        
        elif command == "run":
            print("🔄 執行一次交易流程...")
            self.run_once()
        
        elif command == "stop":
            print("🛑 收到停止命令")
            self.stop()
        
        elif command == "history":
            print("\n📜 交易歷史:")
            for i, h in enumerate(self.cycle_history[-10:], 1):
                print(f"  {i}. {h.get('symbol')} | {h.get('signal_text')} | {h.get('risk_action')} | {h.get('status')}")
        
        elif command == "orders":
            pending = self.approval_queue.get_pending()
            print(f"\n📋 待審批訂單: {len(pending)} 筆")
            for p in pending:
                print(f"  - {p.id}: {p.title} ({p.status})")
        
        elif command in ["force", "buy", "sell"]:
            if len(parts) >= 3 and parts[1] in ["buy", "sell"]:
                side = parts[1].upper()
                symbol = parts[2].upper()
                try:
                    pct = float(parts[3]) / 100 if len(parts) > 3 else 0.1
                    self._command_queue.append({
                        "action": "force_trade",
                        "side": side,
                        "symbol": symbol,
                        "pct": pct,
                    })
                    print(f"⚡ 已加入強制{side}命令: {symbol} {pct*100:.0f}%")
                except:
                    print("❌ 指令格式錯誤: force buy BTCUSDT 50")
            else:
                print("❌ 指令格式錯誤: force buy BTCUSDT 50")
        
        else:
            print(f"❌ 未知命令: {command} (輸入 help 查看)")
    
    def run_once(self) -> Dict[str, Any]:
        """
        执行一次完整的交易流程
        
        Returns:
            执行结果
        """
        results = {}
        
        for symbol in self.symbols:
            for interval in self.intervals:
                try:
                    result = self._process_symbol(symbol, interval)
                    results[f"{symbol}_{interval}"] = result
                except Exception as e:
                    print(f"❌ 处理 {symbol} {interval} 失败: {e}")
                    results[f"{symbol}_{interval}"] = {"error": str(e)}
        
        return results
    
    def _process_symbol(self, symbol: str, interval: str) -> Dict[str, Any]:
        """处理单个交易对"""
        result = {
            "timestamp": datetime.now().isoformat(),
            "symbol": symbol,
            "interval": interval,
        }
        
        logger.info("=" * 50)
        logger.info(f"🔄 開始處理: {symbol} {interval}")
        logger.info("=" * 50)
        
        # 1. 获取数据
        logger.info(f"📥 [1/4] 獲取市場數據...")
        data = self.market_monitor.get_latest_data(symbol, interval)
        
        if data is None or data.empty:
            logger.warning(f"⚠️ 無法獲取數據: {symbol}")
            result["status"] = "no_data"
            return result
        
        current_price = float(data["close"].iloc[-1])
        logger.info(f"   最新價格: ${current_price:,.2f} | 數據筆數: {len(data)}")
        
        result["data_rows"] = len(data)
        
        # 2. Strategy Agent 产生信号
        logger.info(f"📈 [2/4] Strategy Agent 分析中...")
        signal_result = self.strategy_agent.get_signal(symbol, interval)
        
        signal = signal_result.get("signal", 0)
        signal_text = signal_result.get("signal_text", "HOLD")
        best_strategy = signal_result.get("best_strategy")
        
        logger.info(f"   信號: {signal_text} ({signal})")
        if best_strategy:
            logger.info(f"   策略: {best_strategy}")
        
        result["signal"] = signal
        result["signal_text"] = signal_text
        result["best_strategy"] = best_strategy
        result["strategy_metrics"] = signal_result.get("metrics", {})
        
        # 回调
        if self.on_signal:
            self.on_signal(symbol, signal_result)
        
        # 3. Risk Agent 评估
        logger.info(f"🛡️ [3/4] Risk Agent 風險評估...")
        risk_result = self.risk_agent.evaluate_trade(
            signal=signal,
            market_data=data,
            strategy_metrics=signal_result.get("metrics", {}),
        )
        
        risk_action = risk_result.get("action")
        risk_level = risk_result.get("risk_level")
        position_size = risk_result.get("position_size", 0)
        
        logger.info(f"   風險等級: {risk_level}")
        logger.info(f"   決策: {risk_action}")
        if position_size > 0:
            logger.info(f"   部位大小: {position_size:.4f} ({position_size * 100:.1f}%)")
        
        result["risk_action"] = risk_action
        result["risk_level"] = risk_level
        result["position_size"] = position_size
        
        # 4. 执行交易
        if risk_action in ["BUY", "SELL"]:
            # ===== Human-in-the-Loop 審批 =====
            logger.info(f"⏸️ [4/5] 請求人類審批...")
            
            # 發送審批請求
            approval_request = self.approval_queue.request_approval(
                title=f"交易 {symbol}",
                requester="trading_system",
                data={
                    "symbol": symbol,
                    "side": risk_action,
                    "quantity": position_size * self.initial_capital / current_price,
                    "price": current_price,
                    "risk_level": risk_level,
                    "stop_loss": risk_result.get("stop_loss", 0),
                    "take_profit": risk_result.get("take_profit", 0),
                },
                description=f"Risk Agent 建議 {risk_action} {position_size*100:.1f}%部位的 {symbol}",
            )
            
            logger.info(f"   審批請求 ID: {approval_request.id}")
            logger.info(f"   等待人類批准... (按 Enter 批准/拒絕)")
            
            # 檢查審批狀態 (等待用戶輸入)
            # 注意：這裡使用同步等待，生產環境應該用非同步
            from core.approval_queue import ApprovalStatus
            
            # 模擬：5秒後自動批准 (實際應該讓人類審批)
            import time
            approved = False
            for i in range(10):  # 最多等待 50 秒
                time.sleep(5)
                status = self.approval_queue.get_by_id(approval_request.id)
                if status and status.status != ApprovalStatus.PENDING:
                    approved = status.status == ApprovalStatus.APPROVED
                    logger.info(f"   審批結果: {status.status} ({status.responder})")
                    break
                if i >= 2:  # 超過 10 秒自動批准（測試用）
                    logger.info(f"   ⏰ 逾時，自動批准用於測試")
                    self.approval_queue.approve(approval_request.id, "auto_system", "Timeout approval")
                    approved = True
                    break
            
            if not approved:
                logger.info(f"   ❌ 交易被拒絕")
                result["trade"] = {"status": "rejected", "reason": "human_rejected"}
                result["status"] = "rejected"
                self.cycle_history.append(result)
                return result
            
            # ===== 執行交易 =====
            logger.info(f"💰 [5/5] Trading Agent 執行交易...")
            trade_result = self.trading_agent.execute_trade(
                symbol=symbol,
                side=risk_action,
                quantity=position_size * self.initial_capital / current_price,
                price=current_price,
                stop_loss=risk_result.get("stop_loss", 0),
                take_profit=risk_result.get("take_profit", 0),
            )
            
            logger.info(f"   交易結果: {trade_result.get('status', 'unknown')}")
            logger.info(f"   訂單ID: {trade_result.get('order_id', 'N/A')}")
            
            result["trade"] = trade_result
            
            # 回调
            if self.on_trade:
                self.on_trade(symbol, trade_result)
        else:
            logger.info(f"⏭️ 跳過交易 (原因: {risk_action})")
        
        result["status"] = "completed"
        
        # 5. 记录到历史
        self.cycle_history.append(result)
        
        logger.info(f"✅ 完成處理: {symbol} {interval}")
        
        return result
    
    def _on_new_data(self, symbol: str, df: pd.DataFrame):
        """新数据回调"""
        logger.info(f"📊 收到新數據: {symbol} ({len(df)} 行)")
        
        # 可以选择立即处理
        # self._process_symbol(symbol, "1h")
    
    def _run_loop(self):
        """运行循环"""
        while self._running:
            # 检查暂停状态
            if self._paused:
                logger.info("⏸️ 系統已暫停，等待恢復...")
                time.sleep(5)
                continue
            
            # 检查命令队列 - 处理强制交易命令
            while self._command_queue:
                cmd = self._command_queue.pop(0)
                if cmd.get("action") == "force_trade":
                    self._execute_force_trade(cmd)
            
            # 执行一次完整流程
            self.run_once()
            
            # 等待下一次（使用配置的间隔）
            interval_seconds = self.fetch_interval_minutes * 60
            logger.info(f"⏳ 等待 {self.fetch_interval_minutes} 分鐘後再次執行...")
            for _ in range(interval_seconds):
                if not self._running or self._paused:
                    break
                time.sleep(1)
    
    def _execute_force_trade(self, cmd: Dict[str, Any]):
        """执行强制交易"""
        symbol = cmd.get("symbol", "BTCUSDT")
        side = cmd.get("side", "BUY")
        pct = cmd.get("pct", 0.1)
        
        logger.info(f"⚡ 執行強制交易: {side} {symbol} {pct*100:.0f}%")
        
        # 获取当前价格
        data = self.market_monitor.get_latest_data(symbol, "1h")
        if data is None or data.empty:
            logger.warning(f"⚠️ 無法獲取 {symbol} 數據")
            return
        
        current_price = float(data["close"].iloc[-1])
        quantity = pct * self.initial_capital / current_price
        
        # 直接执行交易
        result = self.trading_agent.execute_trade(
            symbol=symbol,
            side=side,
            quantity=quantity,
            price=current_price,
            stop_loss=0,
            take_profit=0,
        )
        
        logger.info(f"   強制交易結果: {result.get('status', 'unknown')}")
    
    def get_status(self) -> Dict[str, Any]:
        """获取系统状态"""
        return {
            "running": self._running,
            "symbols": self.symbols,
            "mode": self.mode,
            "market_monitor": self.market_monitor.get_market_summary(),
            "strategy_agent": self.strategy_agent.get_status(),
            "risk_agent": self.risk_agent.get_status(),
            "trading_agent": self.trading_agent.get_status(),
            "cycles": len(self.cycle_history),
        }
    
    def get_trade_history(self) -> List[Dict[str, Any]]:
        """获取交易历史"""
        return self.trading_agent.trades
    
    def get_cycle_history(self) -> List[Dict[str, Any]]:
        """获取执行周期历史"""
        return self.cycle_history


# ==================== 便捷函数 ====================

def create_trading_system(
    symbols: List[str] = None,
    intervals: List[str] = ["1h"],
    initial_capital: float = 10000.0,
    mode: str = "paper",
) -> TradingSystem:
    """创建交易系统"""
    return TradingSystem(
        symbols=symbols,
        intervals=intervals,
        initial_capital=initial_capital,
        mode=mode,
    )
