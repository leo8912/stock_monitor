from PyQt6.QtCore import QObject, pyqtSignal
from stock_monitor.core.container import container
from stock_monitor.config.manager import ConfigManager
from stock_monitor.data.stock.stocks import load_stock_data
from stock_monitor.utils.stock_utils import StockCodeProcessor
from stock_monitor.utils.logger import app_logger
from stock_monitor.utils.helpers import get_stock_emoji

class SettingsViewModel(QObject):
    """
    ViewModel for SettingsDialog
    Handles configuration loading/saving and stock search logic.
    """
    settings_loaded = pyqtSignal(dict)
    save_completed = pyqtSignal()
    search_results_updated = pyqtSignal(list)
    
    def __init__(self):
        super().__init__()
        self._container = container
        self._config_manager = self._container.get(ConfigManager)
        self._processor = StockCodeProcessor()
        
    def load_settings(self):
        """Load all settings"""
        settings = {
            "user_stocks": self._config_manager.get("user_stocks", []),
            "auto_start": self._config_manager.get("auto_start", False),
            "refresh_interval": self._config_manager.get("refresh_interval", 5),
            "font_size": self._config_manager.get("font_size", 13),
            "font_family": self._config_manager.get("font_family", "微软雅黑"),
            "transparency": self._config_manager.get("transparency", 80),
            "drag_sensitivity": self._config_manager.get("drag_sensitivity", 5),
        }
        self.settings_loaded.emit(settings)
        return settings

    def save_settings(self, settings: dict):
        """Save settings"""
        try:
            for key, value in settings.items():
                self._config_manager.set(key, value)
            self.save_completed.emit()
            return True
        except Exception as e:
            app_logger.error(f"Failed to save settings: {e}")
            return False

    def search_stocks(self, query: str):
        """Search stocks logic"""
        query = query.strip()
        if not query:
            self.search_results_updated.emit([])
            return

        try:
            # Load stock data
            all_stocks_list = load_stock_data()
            all_stocks = {stock["code"]: stock for stock in all_stocks_list}
            
            if not all_stocks:
                return

            # Filter and prioritize
            matched_stocks = []
            lower_query = query.lower()
            
            for code, stock in all_stocks.items():
                name = stock.get("name", "")
                if lower_query in code.lower() or lower_query in name.lower():
                    # Priority logic
                    priority = 0
                    if code.startswith(("sh", "sz")) and not code.startswith(("sh000", "sz399")):
                        priority = 10  # A shares
                    elif code.startswith(("sh000", "sz399")):
                        priority = 5   # Indices
                    elif code.startswith("hk"):
                        priority = 1   # HK shares
                    matched_stocks.append((priority, code, stock))

            # Sort by priority desc, then code asc
            matched_stocks.sort(key=lambda x: (-x[0], x[1]))

            # Format top 20 results
            results = []
            for _, code, stock in matched_stocks[:20]:
                emoji = get_stock_emoji(code, stock.get("name", ""))
                display_text = f"{emoji} {stock.get('name', '')} ({code})"
                # Return object or dict ideally, but keeping string for simple UI binding first? 
                # UI takes strings. Let's return dict with display text and code
                results.append({
                    "display": display_text,
                    "code": code,
                    "name": stock.get("name", "")
                })
            
            self.search_results_updated.emit(results)
            
        except Exception as e:
            app_logger.error(f"Search failed: {e}")
            self.search_results_updated.emit([])

    def get_stock_display_info(self, stock_code: str) -> str:
        """Get display text for a stock code (emoji + name + code)"""
        # Logic to reconstitute display string from saved code
        clean_code = self._processor.clean_code(stock_code)
        
        # We need current stock data to get name
        # Optimization: cache this or load on demand? load_stock_data is cached in module usually?
        all_stocks_list = load_stock_data()
        all_stocks_dict = {stock["code"]: stock for stock in all_stocks_list}
        
        stock_info = all_stocks_dict.get(clean_code)
        if stock_info:
            emoji = get_stock_emoji(clean_code, stock_info.get("name", ""))
            name = stock_info.get("name", "")
            if name:
                return f"{emoji} {name} ({clean_code})"
            else:
                return f"{emoji} {clean_code}"
        else:
            emoji = get_stock_emoji(clean_code, "")
            return f"{emoji} {clean_code}"
