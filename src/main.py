"""
Точка входа в приложение
"""
import sys
import logging
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QPalette, QColor
from ui import DashboardPySide6

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def main():
    """Основная функция запуска приложения"""
    app = QApplication(sys.argv)
    
    app.setStyle('Fusion')
    
    # Настройка цветовой палитры
    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, QColor(240, 240, 240))
    app.setPalette(palette)
    
    try:
        window = DashboardPySide6()
        window.show()
        logger.info("Приложение успешно запущено")
        
        return app.exec()
    except Exception as e:
        logger.error(f"Ошибка при запуске приложения: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
