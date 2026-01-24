"""
Графический интерфейс приложения
"""
import sys
import logging
from datetime import datetime
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QStackedWidget, QFrame, QTableWidget,
    QTableWidgetItem, QHeaderView, QMessageBox, QProgressDialog,
    QFileDialog, QGroupBox, QMenuBar
)
from PySide6.QtGui import QAction, QFont, QPalette, QColor
from PySide6.QtCore import Qt, QTimer, QDate
import matplotlib.pyplot as plt
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure

from database import DatabaseManager
from reports import ExcelExporter, PDFReportThread
from models import CollectorDialog, CollectionDialog, CatalogItemDialog
import config

logger = logging.getLogger(__name__)


class DashboardPySide6(QMainWindow):
    def __init__(self):
        super().__init__()
        self.db = DatabaseManager()
        self.excel_exporter = ExcelExporter(self.db)
        self.setWindowTitle(f"{config.APP_CONFIG['name']} - Дашборд")
        self.setGeometry(100, 100, 1400, 900)
        
        self.countries = []
        self.collection_types = []
        self.current_collectors = []
        self.current_collections = []
        self.current_catalog = []
        
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        
        main_layout = QHBoxLayout(main_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        self.create_menu()
        main_layout.addWidget(self.menu_frame)
        
        self.content_area = QStackedWidget()
        main_layout.addWidget(self.content_area)
        
        self.create_dashboard_page()
        self.create_collectors_page()
        self.create_collections_page()
        self.create_catalog_page()
        self.create_about_page()
        
        self.content_area.setCurrentIndex(0)
        
        self.db.data_loaded.connect(self.on_data_loaded)
        self.db.error_occurred.connect(self.on_database_error)
        self.db.connected.connect(self.on_database_connected)
        
        self.excel_exporter.progress_updated.connect(self.on_export_progress)
        self.excel_exporter.export_finished.connect(self.on_export_finished)
        self.excel_exporter.export_error.connect(self.on_export_error)
        
        self.db.start()
        
        QTimer.singleShot(100, self.db.connect)
        
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self.refresh_dashboard)
        self.update_timer.start(config.APP_CONFIG['update_interval'])
        
        self.export_progress = None
        self.pdf_progress = None

        # Создаем меню для PDF отчетов
        self.create_pdf_reports_menu()

    def create_pdf_reports_menu(self):
        """Создание меню для PDF отчетов"""
        pdf_menu = self.menuBar().addMenu("📊 PDF Отчеты")
        
        statistical_action = QAction("📈 Статистический отчет", self)
        statistical_action.triggered.connect(self.generate_statistical_report)
        statistical_action.setToolTip("Генерация отчета с общей статистикой системы")
        pdf_menu.addAction(statistical_action)
        
        detailed_action = QAction("📋 Детальный отчет", self)
        detailed_action.triggered.connect(self.generate_detailed_report)
        detailed_action.setToolTip("Генерация отчета с детальными таблицами данных")
        pdf_menu.addAction(detailed_action)

    def generate_statistical_report(self):
        """Генерация статистического отчета"""
        try:
            filename, _ = QFileDialog.getSaveFileName(
                self,
                "Сохранить статистический отчет PDF",
                f"статистика_коллекционеры_{datetime.now().strftime('%Y%m%d_%H%M')}.pdf",
                "PDF Files (*.pdf)"
            )
            
            if filename:
                self.show_pdf_export_progress("Подготовка к генерации статистического отчета...")
                
                # Запуск генерации в отдельном потоке с конфигурацией БД
                report_thread = PDFReportThread(
                    config.DB_CONFIG, 'statistical', filename, self
                )
                report_thread.finished.connect(self.on_pdf_report_finished)
                report_thread.error.connect(self.on_pdf_report_error)
                report_thread.progress.connect(self.on_pdf_report_progress)
                report_thread.start()
                
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Не удалось начать генерацию отчета: {e}")

    def generate_detailed_report(self):
        """Генерация детального отчета"""
        try:
            filename, _ = QFileDialog.getSaveFileName(
                self,
                "Сохранить детальный отчет PDF",
                f"детальный_отчет_{datetime.now().strftime('%Y%m%d_%H%M')}.pdf",
                "PDF Files (*.pdf)"
            )
            
            if filename:
                self.show_pdf_export_progress("Подготовка к генерации детального отчета...")
                
                report_thread = PDFReportThread(
                    config.DB_CONFIG, 'detailed', filename, self
                )
                report_thread.finished.connect(self.on_pdf_report_finished)
                report_thread.error.connect(self.on_pdf_report_error)
                report_thread.progress.connect(self.on_pdf_report_progress)
                report_thread.start()
                
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Не удалось начать генерацию отчета: {e}")

    def show_pdf_export_progress(self, message):
        """Показать диалог прогресса для PDF генерации"""
        self.pdf_progress = QProgressDialog(message, "Отмена", 0, 0, self)
        self.pdf_progress.setWindowTitle("Генерация PDF отчета")
        self.pdf_progress.setWindowModality(Qt.WindowModal)
        self.pdf_progress.setCancelButton(None)  # Отключаем кнопку отмены
        self.pdf_progress.show()

    def on_pdf_report_progress(self, message):
        """Обновление прогресса генерации PDF"""
        if self.pdf_progress:
            self.pdf_progress.setLabelText(message)

    def on_pdf_report_finished(self, filename):
        """Обработка завершения генерации PDF"""
        if self.pdf_progress:
            self.pdf_progress.close()
            self.pdf_progress = None
        
        QMessageBox.information(
            self, 
            "Отчет сгенерирован", 
            f"PDF отчет успешно сохранен:\n{filename}\n\n"
            f"Отчет содержит актуальные данные из базы данных."
        )

    def on_pdf_report_error(self, error_message):
        """Обработка ошибки генерации PDF"""
        if self.pdf_progress:
            self.pdf_progress.close()
            self.pdf_progress = None
        
        QMessageBox.critical(self, "Ошибка генерации отчета", 
                           f"Произошла ошибка при генерации PDF отчета:\n\n{error_message}")

    def create_menu(self):
        self.menu_frame = QFrame()
        self.menu_frame.setFixedWidth(250)
        self.menu_frame.setStyleSheet("""
            QFrame {
                background-color: #2c3e50;
                border: none;
            }
            QPushButton {
                background-color: #34495e;
                color: white;
                border: none;
                padding: 15px;
                text-align: left;
                font-size: 14px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #1abc9c;
            }
            QPushButton:pressed {
                background-color: #16a085;
            }
        """)
        
        menu_layout = QVBoxLayout(self.menu_frame)
        menu_layout.setContentsMargins(0, 0, 0, 0)
        menu_layout.setSpacing(0)
        
        title_label = QLabel(f"{config.APP_CONFIG['name']}")
        title_label.setStyleSheet("""
            QLabel {
                background-color: #1abc9c;
                color: white;
                font-size: 18px;
                font-weight: bold;
                padding: 20px;
                text-align: center;
            }
        """)
        title_label.setAlignment(Qt.AlignCenter)
        menu_layout.addWidget(title_label)
        
        menu_items = [
            ("📊 Дашборд", self.show_dashboard),
            ("👥 Коллекционеры", self.show_collectors),
            ("📚 Коллекции", self.show_collections),
            ("🗂️ Каталог", self.show_catalog),
            ("📊 Отчет в Excel", self.export_to_excel),
            ("ℹ️ О платформе", self.show_about)
        ]
        
        for text, slot in menu_items:
            btn = QPushButton(text)
            btn.setFixedHeight(60)
            btn.clicked.connect(slot)
            menu_layout.addWidget(btn)
        
        menu_layout.addStretch()

    def export_to_excel(self):
        try:
            filename, _ = QFileDialog.getSaveFileName(
                self,
                "Сохранить отчет Excel",
                f"отчет_коллекционеры_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx",
                "Excel Files (*.xlsx)"
            )
            
            if filename:
                self.export_progress = QProgressDialog("Создание Excel отчета...", "Отмена", 0, 100, self)
                self.export_progress.setWindowTitle("Экспорт в Excel")
                self.export_progress.setWindowModality(Qt.WindowModal)
                self.export_progress.setAutoClose(True)
                self.export_progress.show()
                
                self.excel_exporter.create_excel_report(filename)
                
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Не удалось начать экспорт: {e}")

    def on_export_progress(self, value):
        if self.export_progress:
            self.export_progress.setValue(value)

    def on_export_finished(self, filename):
        if self.export_progress:
            self.export_progress.close()
            self.export_progress = None
        
        QMessageBox.information(
            self, 
            "Экспорт завершен", 
            f"Отчет успешно сохранен в файл:\n{filename}"
        )

    def on_export_error(self, error_message):
        if self.export_progress:
            self.export_progress.close()
            self.export_progress = None
        
        QMessageBox.critical(self, "Ошибка экспорта", error_message)

    def create_dashboard_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setSpacing(20)
        layout.setContentsMargins(20, 20, 20, 20)
        
        title = QLabel("Аналитический Дашборд")
        title.setAlignment(Qt.AlignCenter)
        title.setFont(QFont("Arial", 20, QFont.Weight.Bold))
        title.setStyleSheet("color: #2c3e50; margin: 10px;")
        layout.addWidget(title)
        
        cards_section = self.create_cards_section()
        layout.addWidget(cards_section)
        
        content_layout = QHBoxLayout()
        content_layout.setSpacing(20)
        
        left_column = QVBoxLayout()
        left_column.setSpacing(20)
        
        type_chart = self.create_collection_types_chart()
        left_column.addWidget(type_chart)
        
        country_chart = self.create_country_chart()
        left_column.addWidget(country_chart)
        
        content_layout.addLayout(left_column, 2)
        
        right_column = QVBoxLayout()
        right_column.setSpacing(20)
        
        table_section = self.create_recent_collections_table()
        right_column.addWidget(table_section)
        
        content_layout.addLayout(right_column, 1)
        
        layout.addLayout(content_layout, 1)
        
        self.content_area.addWidget(page)

    def create_cards_section(self):
        section = QWidget()
        layout = QHBoxLayout(section)
        layout.setSpacing(15)
        layout.setContentsMargins(0, 0, 0, 0)
        
        cards_data = [
            {
                "title": "Коллекционеры",
                "value": "0",
                "icon": "👥",
                "color": "#3498db",
                "description": "Всего в базе"
            },
            {
                "title": "Коллекции",
                "value": "0",
                "icon": "📚",
                "color": "#2ecc71",
                "description": "Всего коллекций"
            },
            {
                "title": "Предметы в каталоге",
                "value": "0",
                "icon": "🗂️",
                "color": "#9b59b6",
                "description": "Всего предметов"
            },
            {
                "title": "Предметы в коллекциях",
                "value": "0",
                "icon": "📦",
                "color": "#e74c3c",
                "description": "Всего предметов"
            }
        ]
        
        self.stat_cards = []
        for card_data in cards_data:
            card = self.create_card(**card_data)
            self.stat_cards.append(card)
            layout.addWidget(card)
        
        return section

    def create_card(self, title, value, icon, color, description):
        card = QFrame()
        card.setFrameStyle(QFrame.Shape.StyledPanel)
        card.setStyleSheet(f"""
            QFrame {{
                background-color: white;
                border: 1px solid #ddd;
                border-radius: 10px;
                padding: 15px;
            }}
        """)
        
        layout = QVBoxLayout(card)
        layout.setSpacing(8)
        layout.setContentsMargins(15, 15, 15, 15)
        
        top_layout = QHBoxLayout()
        
        icon_label = QLabel(icon)
        icon_label.setFont(QFont("Arial", 16))
        top_layout.addWidget(icon_label)
        
        title_label = QLabel(title)
        title_label.setFont(QFont("Arial", 11, QFont.Weight.Bold))
        title_label.setStyleSheet("color: #7f8c8d;")
        top_layout.addWidget(title_label)
        
        top_layout.addStretch()
        layout.addLayout(top_layout)
        
        value_label = QLabel(value)
        value_label.setFont(QFont("Arial", 24, QFont.Weight.Bold))
        value_label.setStyleSheet(f"color: {color};")
        value_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(value_label)
        
        desc_label = QLabel(description)
        desc_label.setFont(QFont("Arial", 10))
        desc_label.setStyleSheet("color: #95a5a6;")
        desc_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(desc_label)
        
        return card

    def create_collection_types_chart(self):
        group_box = QGroupBox("Распределение по типам коллекций")
        group_box.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                font-size: 14px;
                border: 1px solid #ddd;
                border-radius: 8px;
                margin-top: 10px;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px 0 5px;
            }
        """)
        
        layout = QVBoxLayout(group_box)
        
        self.type_fig = Figure(figsize=(10, 6), facecolor='white')
        self.type_canvas = FigureCanvas(self.type_fig)
        
        layout.addWidget(self.type_canvas)
        
        return group_box

    def create_country_chart(self):
        group_box = QGroupBox("Коллекционеры по странам")
        group_box.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                font-size: 14px;
                border: 1px solid #ddd;
                border-radius: 8px;
                margin-top: 10px;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px 0 5px;
            }
        """)
        
        layout = QVBoxLayout(group_box)
        
        self.country_fig = Figure(figsize=(10, 6), facecolor='white')
        self.country_canvas = FigureCanvas(self.country_fig)
        
        layout.addWidget(self.country_canvas)
        
        return group_box

    def create_recent_collections_table(self):
        group_box = QGroupBox("Последние коллекции")
        group_box.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                font-size: 14px;
                border: 1px solid #ddd;
                border-radius: 8px;
                margin-top: 10px;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px 0 5px;
            }
        """)
        
        layout = QVBoxLayout(group_box)
        
        self.recent_table = QTableWidget()
        self.recent_table.setColumnCount(4)
        self.recent_table.setHorizontalHeaderLabels(["Название", "Автор", "Тип", "Предметы"])
        
        self.recent_table.setAlternatingRowColors(True)
        self.recent_table.setStyleSheet("""
            QTableWidget {
                gridline-color: #ddd;
                alternate-background-color: #f8f9fa;
            }
            QHeaderView::section {
                background-color: #34495e;
                color: white;
                font-weight: bold;
                padding: 5px;
                border: none;
            }
        """)
        
        header = self.recent_table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        
        layout.addWidget(self.recent_table)
        
        return group_box

    def create_collectors_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        
        title = QLabel("Коллекционеры")
        title.setStyleSheet("""
            QLabel {
                font-size: 24px;
                font-weight: bold;
                color: #2c3e50;
                padding: 20px;
                background-color: #ecf0f1;
                border-bottom: 2px solid #bdc3c7;
            }
        """)
        layout.addWidget(title)
        
        toolbar_layout = QHBoxLayout()
        
        self.add_collector_btn = QPushButton("➕ Добавить коллекционера")
        self.edit_collector_btn = QPushButton("✏️ Редактировать")
        self.delete_collector_btn = QPushButton("🗑️ Удалить")
        refresh_btn = QPushButton("🔄 Обновить")
        
        button_style = """
            QPushButton {
                background-color: #3498db;
                color: white;
                border: none;
                padding: 8px 15px;
                border-radius: 5px;
                font-weight: bold;
                margin: 5px;
            }
            QPushButton:hover {
                background-color: #2980b9;
            }
            QPushButton:disabled {
                background-color: #bdc3c7;
            }
        """
        
        delete_style = """
            QPushButton {
                background-color: #e74c3c;
                color: white;
                border: none;
                padding: 8px 15px;
                border-radius: 5px;
                font-weight: bold;
                margin: 5px;
            }
            QPushButton:hover {
                background-color: #c0392b;
            }
            QPushButton:disabled {
                background-color: #bdc3c7;
            }
        """
        
        self.add_collector_btn.setStyleSheet(button_style)
        self.edit_collector_btn.setStyleSheet(button_style)
        self.delete_collector_btn.setStyleSheet(delete_style)
        refresh_btn.setStyleSheet(button_style)
        
        self.add_collector_btn.clicked.connect(self.add_collector)
        self.edit_collector_btn.clicked.connect(self.edit_collector)
        self.delete_collector_btn.clicked.connect(self.delete_collector)
        refresh_btn.clicked.connect(self.refresh_collectors)
        
        toolbar_layout.addWidget(self.add_collector_btn)
        toolbar_layout.addWidget(self.edit_collector_btn)
        toolbar_layout.addWidget(self.delete_collector_btn)
        toolbar_layout.addStretch()
        toolbar_layout.addWidget(refresh_btn)
        
        layout.addLayout(toolbar_layout)
        
        self.collectors_table = QTableWidget()
        self.collectors_table.setColumnCount(6)
        self.collectors_table.setHorizontalHeaderLabels(["ID", "Фамилия", "Имя", "Отчество", "Email", "Страна"])
        self.collectors_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.collectors_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.collectors_table.setSelectionMode(QTableWidget.SingleSelection)
        
        self.collectors_table.setColumnHidden(0, True)
        
        layout.addWidget(self.collectors_table)
        
        self.content_area.addWidget(page)

    def create_collections_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        
        title = QLabel("Коллекции")
        title.setStyleSheet("""
            QLabel {
                font-size: 24px;
                font-weight: bold;
                color: #2c3e50;
                padding: 20px;
                background-color: #ecf0f1;
                border-bottom: 2px solid #bdc3c7;
            }
        """)
        layout.addWidget(title)
        
        toolbar_layout = QHBoxLayout()
        
        self.add_collection_btn = QPushButton("➕ Добавить коллекцию")
        self.edit_collection_btn = QPushButton("✏️ Редактировать")
        self.delete_collection_btn = QPushButton("🗑️ Удалить")
        refresh_btn = QPushButton("🔄 Обновить")
        
        button_style = """
            QPushButton {
                background-color: #3498db;
                color: white;
                border: none;
                padding: 8px 15px;
                border-radius: 5px;
                font-weight: bold;
                margin: 5px;
            }
            QPushButton:hover {
                background-color: #2980b9;
            }
            QPushButton:disabled {
                background-color: #bdc3c7;
            }
        """
        
        delete_style = """
            QPushButton {
                background-color: #e74c3c;
                color: white;
                border: none;
                padding: 8px 15px;
                border-radius: 5px;
                font-weight: bold;
                margin: 5px;
            }
            QPushButton:hover {
                background-color: #c0392b;
            }
            QPushButton:disabled {
                background-color: #bdc3c7;
            }
        """
        
        self.add_collection_btn.setStyleSheet(button_style)
        self.edit_collection_btn.setStyleSheet(button_style)
        self.delete_collection_btn.setStyleSheet(delete_style)
        refresh_btn.setStyleSheet(button_style)
        
        self.add_collection_btn.clicked.connect(self.add_collection)
        self.edit_collection_btn.clicked.connect(self.edit_collection)
        self.delete_collection_btn.clicked.connect(self.delete_collection)
        refresh_btn.clicked.connect(self.refresh_collections)
        
        toolbar_layout.addWidget(self.add_collection_btn)
        toolbar_layout.addWidget(self.edit_collection_btn)
        toolbar_layout.addWidget(self.delete_collection_btn)
        toolbar_layout.addStretch()
        toolbar_layout.addWidget(refresh_btn)
        
        layout.addLayout(toolbar_layout)
        
        self.collections_table = QTableWidget()
        self.collections_table.setColumnCount(7)
        self.collections_table.setHorizontalHeaderLabels(["ID", "Название", "Автор", "Тип", "Дата создания", "Предметов", "Описание"])
        self.collections_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.collections_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.collections_table.setSelectionMode(QTableWidget.SingleSelection)
        
        self.collections_table.setColumnHidden(0, True)
        
        layout.addWidget(self.collections_table)
        
        self.content_area.addWidget(page)

    def create_catalog_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        
        title = QLabel("Каталог")
        title.setStyleSheet("""
            QLabel {
                font-size: 24px;
                font-weight: bold;
                color: #2c3e50;
                padding: 20px;
                background-color: #ecf0f1;
                border-bottom: 2px solid #bdc3c7;
            }
        """)
        layout.addWidget(title)
        
        toolbar_layout = QHBoxLayout()
        
        self.add_catalog_btn = QPushButton("➕ Добавить предмет")
        self.edit_catalog_btn = QPushButton("✏️ Редактировать")
        self.delete_catalog_btn = QPushButton("🗑️ Удалить")
        refresh_btn = QPushButton("🔄 Обновить")
        
        button_style = """
            QPushButton {
                background-color: #3498db;
                color: white;
                border: none;
                padding: 8px 15px;
                border-radius: 5px;
                font-weight: bold;
                margin: 5px;
            }
            QPushButton:hover {
                background-color: #2980b9;
            }
            QPushButton:disabled {
                background-color: #bdc3c7;
            }
        """
        
        delete_style = """
            QPushButton {
                background-color: #e74c3c;
                color: white;
                border: none;
                padding: 8px 15px;
                border-radius: 5px;
                font-weight: bold;
                margin: 5px;
            }
            QPushButton:hover {
                background-color: #c0392b;
            }
            QPushButton:disabled {
                background-color: #bdc3c7;
            }
        """
        
        self.add_catalog_btn.setStyleSheet(button_style)
        self.edit_catalog_btn.setStyleSheet(button_style)
        self.delete_catalog_btn.setStyleSheet(delete_style)
        refresh_btn.setStyleSheet(button_style)
        
        self.add_catalog_btn.clicked.connect(self.add_catalog_item)
        self.edit_catalog_btn.clicked.connect(self.edit_catalog_item)
        self.delete_catalog_btn.clicked.connect(self.delete_catalog_item)
        refresh_btn.clicked.connect(self.refresh_catalog)
        
        toolbar_layout.addWidget(self.add_catalog_btn)
        toolbar_layout.addWidget(self.edit_catalog_btn)
        toolbar_layout.addWidget(self.delete_catalog_btn)
        toolbar_layout.addStretch()
        toolbar_layout.addWidget(refresh_btn)
        
        layout.addLayout(toolbar_layout)
        
        self.catalog_table = QTableWidget()
        self.catalog_table.setColumnCount(6)
        self.catalog_table.setHorizontalHeaderLabels(["ID", "Название", "Редкость", "Страна", "Дата выпуска", "Описание"])
        self.catalog_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.catalog_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.catalog_table.setSelectionMode(QTableWidget.SingleSelection)
        
        self.catalog_table.setColumnHidden(0, True)
        
        layout.addWidget(self.catalog_table)
        
        self.content_area.addWidget(page)

    def create_about_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        
        title = QLabel("О платформе")
        title.setStyleSheet("""
            QLabel {
                font-size: 24px;
                font-weight: bold;
                color: #2c3e50;
                padding: 20px;
                background-color: #ecf0f1;
                border-bottom: 2px solid #bdc3c7;
            }
        """)
        layout.addWidget(title)
        
        content = QLabel(
            f"{config.APP_CONFIG['name']} версия {config.APP_CONFIG['version']}\n\n"
            "Эта платформа позволяет вести учет коллекционеров марок и монет, "
            "их коллекций и предметов. В каталоге хранится информация обо всех "
            "возможных предметах с указанием года выпуска, страны, редкости и других свойств.\n\n"
            "Функциональность:\n"
            "• Просмотр статистики и аналитики\n"
            "• Управление коллекционерами\n"
            "• Управление коллекциями\n"
            "• Управление каталогом предметов\n"
            "• Полноценные формы редактирования\n"
            "• Визуализация данных\n"
            "• Экспорт отчетов в Excel\n"
            "• Генерация PDF отчетов\n"
        )
        content.setStyleSheet("font-size: 16px; padding: 20px;")
        content.setWordWrap(True)
        layout.addWidget(content)
        
        self.content_area.addWidget(page)

    def on_database_connected(self):
        logger.info("База данных подключена, загружаем начальные данные")
        self.refresh_all_data()

    def refresh_all_data(self):
        self.db.get_statistics()
        self.db.get_collectors()
        self.db.get_collections()
        self.db.get_catalog()
        self.db.get_collection_types_stats()
        self.db.get_country_stats()
        self.db.get_countries()
        self.db.get_collection_types()

    def on_data_loaded(self, data_type, data):
        logger.info(f"Данные получены: {data_type}")
        
        try:
            if data_type == 'statistics':
                self.update_statistics(data)
            elif data_type == 'collectors':
                self.update_collectors_table(data)
            elif data_type == 'collections':
                self.update_collections_table(data)
                self.update_recent_collections_table(data)
            elif data_type == 'catalog':
                self.update_catalog_table(data)
            elif data_type == 'collection_types':
                self.update_collection_types_chart(data)
            elif data_type == 'country_stats':
                self.update_country_chart(data)
            elif data_type == 'countries':
                self.countries = data or []
            elif data_type == 'collection_types_list':
                self.collection_types = data or []
            elif data_type in ['collector_added', 'collector_updated', 'collector_deleted',
                              'collection_added', 'collection_updated', 'collection_deleted',
                              'catalog_item_added', 'catalog_item_updated', 'catalog_item_deleted']:
                self.refresh_all_data()
                QMessageBox.information(self, "Успех", "Операция выполнена успешно!")
        except Exception as e:
            logger.error(f"Ошибка при обработке данных {data_type}: {e}")

    def on_database_error(self, error_message):
        logger.error(f"Ошибка БД: {error_message}")
        QMessageBox.critical(self, "Ошибка базы данных", error_message)

    def update_statistics(self, stats):
        if stats:
            card_data = [
                ("collectors_count", 0),
                ("collections_count", 1),
                ("catalog_count", 2),
                ("items_count", 3)
            ]
            
            for key, index in card_data:
                if index < len(self.stat_cards):
                    card = self.stat_cards[index]
                    value_label = card.layout().itemAt(1).widget()
                    if value_label and isinstance(value_label, QLabel):
                        value_label.setText(str(stats.get(key, 0)))

    def update_collection_types_chart(self, data):
        if data:
            self.type_fig.clear()
            ax = self.type_fig.add_subplot(111)
            
            types = []
            counts = []
            for item in data:
                collection_type = item.get('collection_type', 'Неизвестно')
                count = item.get('count', 0)
                if collection_type and count > 0:
                    types.append(collection_type)
                    counts.append(count)
            
            if types and counts:
                colors = ['#3498db', '#2ecc71', '#9b59b6', '#e74c3c', '#f39c12']
                
                wedges, texts, autotexts = ax.pie(
                    counts,
                    labels=types,
                    autopct='%1.1f%%',
                    colors=colors[:len(types)],
                    startangle=90
                )
                
                for autotext in autotexts:
                    autotext.set_color('white')
                    autotext.set_fontweight('bold')
                
                ax.set_title('Распределение по типам коллекций', fontweight='bold')
            else:
                ax.text(0.5, 0.5, 'Нет данных\nдля отображения', 
                       horizontalalignment='center', verticalalignment='center',
                       transform=ax.transAxes, fontsize=14)
                ax.set_title('Распределение по типам коллекций', fontweight='bold')
            
            self.type_canvas.draw()

    def update_country_chart(self, data):
        if data:
            self.country_fig.clear()
            ax = self.country_fig.add_subplot(111)
            
            countries = []
            counts = []
            for item in data:
                country = item.get('country', 'Неизвестно')
                count = item.get('collector_count', 0)
                if country and count > 0:
                    countries.append(country)
                    counts.append(count)
            
            if countries and counts:
                bars = ax.bar(countries, counts, color='#1abc9c', alpha=0.8)
                
                ax.set_title('Коллекционеры по странам', fontweight='bold')
                ax.set_ylabel('Количество коллекционеров')
                ax.tick_params(axis='x', rotation=45)
                
                for bar, count in zip(bars, counts):
                    height = bar.get_height()
                    ax.text(bar.get_x() + bar.get_width()/2., height,
                           f'{count}', ha='center', va='bottom')
            else:
                ax.text(0.5, 0.5, 'Нет данных\nдля отображения', 
                       horizontalalignment='center', verticalalignment='center',
                       transform=ax.transAxes, fontsize=14)
                ax.set_title('Коллекционеры по странам', fontweight='bold')
            
            self.country_fig.tight_layout()
            self.country_canvas.draw()

    def update_recent_collections_table(self, collections):
        if collections:
            recent_collections = collections[-8:] if len(collections) > 8 else collections
            self.recent_table.setRowCount(len(recent_collections))
            
            for row, collection in enumerate(recent_collections):
                name = collection.get('name', '')
                author = collection.get('author', '')
                collection_type = collection.get('collection_type', '')
                number_of_items = collection.get('number_of_items', 0)
                
                self.recent_table.setItem(row, 0, QTableWidgetItem(name))
                self.recent_table.setItem(row, 1, QTableWidgetItem(author))
                self.recent_table.setItem(row, 2, QTableWidgetItem(collection_type))
                self.recent_table.setItem(row, 3, QTableWidgetItem(str(number_of_items)))

    def update_collectors_table(self, collectors):
        self.current_collectors = collectors
        if collectors:
            self.collectors_table.setRowCount(len(collectors))
            for row, collector in enumerate(collectors):
                collector_id = collector.get('id', '')
                surname = collector.get('surname', '')
                name = collector.get('name', '')
                patronymic = collector.get('patronymic', '')
                email = collector.get('email', '')
                country = collector.get('country', '')

                self.collectors_table.setItem(row, 0, QTableWidgetItem(str(collector_id)))
                self.collectors_table.setItem(row, 1, QTableWidgetItem(surname))
                self.collectors_table.setItem(row, 2, QTableWidgetItem(name))
                self.collectors_table.setItem(row, 3, QTableWidgetItem(patronymic))
                self.collectors_table.setItem(row, 4, QTableWidgetItem(email))
                self.collectors_table.setItem(row, 5, QTableWidgetItem(country))

    def update_collections_table(self, collections):
        self.current_collections = collections
        if collections:
            self.collections_table.setRowCount(len(collections))
            for row, collection in enumerate(collections):
                collection_id = collection.get('id', '')
                name = collection.get('name', '')
                author = collection.get('author', '')
                collection_type = collection.get('collection_type', '')
                
                date_creation = collection.get('date_of_creation')
                if date_creation:
                    if isinstance(date_creation, str):
                        date_str = date_creation
                    else:
                        date_str = str(date_creation)
                else:
                    date_str = ""
                
                number_of_items = collection.get('number_of_items', 0)
                description = collection.get('description', '')
                
                self.collections_table.setItem(row, 0, QTableWidgetItem(str(collection_id)))
                self.collections_table.setItem(row, 1, QTableWidgetItem(name))
                self.collections_table.setItem(row, 2, QTableWidgetItem(author))
                self.collections_table.setItem(row, 3, QTableWidgetItem(collection_type))
                self.collections_table.setItem(row, 4, QTableWidgetItem(date_str))
                self.collections_table.setItem(row, 5, QTableWidgetItem(str(number_of_items)))
                self.collections_table.setItem(row, 6, QTableWidgetItem(description))

    def update_catalog_table(self, catalog):
        self.current_catalog = catalog
        if catalog:
            self.catalog_table.setRowCount(len(catalog))
            for row, item in enumerate(catalog):
                item_id = item.get('id', '')
                name = item.get('name', '')
                rare = item.get('rare', '')
                country = item.get('country', '')
                
                release_date = item.get('release_date')
                if release_date:
                    if isinstance(release_date, str):
                        date_str = release_date
                    else:
                        date_str = str(release_date)
                else:
                    date_str = ""
                
                description = item.get('description', '')
                
                self.catalog_table.setItem(row, 0, QTableWidgetItem(str(item_id)))
                self.catalog_table.setItem(row, 1, QTableWidgetItem(name))
                self.catalog_table.setItem(row, 2, QTableWidgetItem(rare))
                self.catalog_table.setItem(row, 3, QTableWidgetItem(country))
                self.catalog_table.setItem(row, 4, QTableWidgetItem(date_str))
                self.catalog_table.setItem(row, 5, QTableWidgetItem(description))

    def add_collector(self):
        dialog = CollectorDialog(self, countries=self.countries)
        if dialog.exec() == QDialog.Accepted:
            data = dialog.get_data()
            self.db.add_collector(data)

    def edit_collector(self):
        current_row = self.collectors_table.currentRow()
        if current_row < 0:
            QMessageBox.warning(self, "Предупреждение", "Выберите коллекционера для редактирования")
            return
        
        collector_id = int(self.collectors_table.item(current_row, 0).text())
        collector = next((c for c in self.current_collectors if c['id'] == collector_id), None)
        
        if collector:
            dialog = CollectorDialog(self, collector=collector, countries=self.countries)
            if dialog.exec() == QDialog.Accepted:
                data = dialog.get_data()
                self.db.update_collector(collector_id, data)

    def delete_collector(self):
        current_row = self.collectors_table.currentRow()
        if current_row < 0:
            QMessageBox.warning(self, "Предупреждение", "Выберите коллекционера для удаления")
            return
        
        collector_id = int(self.collectors_table.item(current_row, 0).text())
        collector_name = self.collectors_table.item(current_row, 1).text()
        
        reply = QMessageBox.question(
            self, "Подтверждение удаления", 
            f"Вы уверены, что хотите удалить коллекционера {collector_name}?",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            self.db.delete_collector(collector_id)

    def add_collection(self):
        dialog = CollectionDialog(self, collection_types=self.collection_types)
        if dialog.exec() == QDialog.Accepted:
            data = dialog.get_data()
            self.db.add_collection(data)

    def edit_collection(self):
        current_row = self.collections_table.currentRow()
        if current_row < 0:
            QMessageBox.warning(self, "Предупреждение", "Выберите коллекцию для редактирования")
            return
        
        collection_id = int(self.collections_table.item(current_row, 0).text())
        collection = next((c for c in self.current_collections if c['id'] == collection_id), None)
        
        if collection:
            dialog = CollectionDialog(self, collection=collection, collection_types=self.collection_types)
            if dialog.exec() == QDialog.Accepted:
                data = dialog.get_data()
                self.db.update_collection(collection_id, data)

    def delete_collection(self):
        current_row = self.collections_table.currentRow()
        if current_row < 0:
            QMessageBox.warning(self, "Предупреждение", "Выберите коллекцию для удаления")
            return
        
        collection_id = int(self.collections_table.item(current_row, 0).text())
        collection_name = self.collections_table.item(current_row, 1).text()
        
        reply = QMessageBox.question(
            self, "Подтверждение удаления", 
            f"Вы уверены, что хотите удалить коллекцию '{collection_name}'?",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            self.db.delete_collection(collection_id)

    def add_catalog_item(self):
        dialog = CatalogItemDialog(self, countries=self.countries)
        if dialog.exec() == QDialog.Accepted:
            data = dialog.get_data()
            self.db.add_catalog_item(data)

    def edit_catalog_item(self):
        current_row = self.catalog_table.currentRow()
        if current_row < 0:
            QMessageBox.warning(self, "Предупреждение", "Выберите предмет каталога для редактирования")
            return
        
        item_id = int(self.catalog_table.item(current_row, 0).text())
        item = next((i for i in self.current_catalog if i['id'] == item_id), None)
        
        if item:
            dialog = CatalogItemDialog(self, item=item, countries=self.countries)
            if dialog.exec() == QDialog.Accepted:
                data = dialog.get_data()
                self.db.update_catalog_item(item_id, data)

    def delete_catalog_item(self):
        current_row = self.catalog_table.currentRow()
        if current_row < 0:
            QMessageBox.warning(self, "Предупреждение", "Выберите предмет каталога для удаления")
            return
        
        item_id = int(self.catalog_table.item(current_row, 0).text())
        item_name = self.catalog_table.item(current_row, 1).text()
        
        reply = QMessageBox.question(
            self, "Подтверждение удаления", 
            f"Вы уверены, что хотите удалить предмет '{item_name}'?",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            self.db.delete_catalog_item(item_id)

    def refresh_dashboard(self):
        self.db.get_statistics()
        self.db.get_collection_types_stats()
        self.db.get_country_stats()
        self.db.get_collections()

    def refresh_collectors(self):
        self.db.get_collectors()

    def refresh_collections(self):
        self.db.get_collections()

    def refresh_catalog(self):
        self.db.get_catalog()

    def show_dashboard(self):
        self.content_area.setCurrentIndex(0)
        self.refresh_dashboard()

    def show_collectors(self):
        self.content_area.setCurrentIndex(1)
        self.refresh_collectors()

    def show_collections(self):
        self.content_area.setCurrentIndex(2)
        self.refresh_collections()

    def show_catalog(self):
        self.content_area.setCurrentIndex(3)
        self.refresh_catalog()

    def show_about(self):
        self.content_area.setCurrentIndex(4)

    def closeEvent(self, event):
        logger.info("Закрытие приложения...")
        self.update_timer.stop()
        self.db.stop()
        event.accept()
