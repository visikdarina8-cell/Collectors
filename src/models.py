"""
Диалоговые окна и модели данных
"""
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QFormLayout, QLineEdit, 
    QComboBox, QTextEdit, QPushButton, QHBoxLayout,
    QDateEdit, QSpinBox, QMessageBox
)
from PySide6.QtCore import QDate
from datetime import datetime


class CollectorDialog(QDialog):
    def __init__(self, parent=None, collector=None, countries=None):
        super().__init__(parent)
        self.collector = collector
        self.countries = countries or []
        
        self.setWindowTitle("Редактировать коллекционера" if collector else "Добавить коллекционера")
        self.setModal(True)
        self.setFixedSize(500, 400)
        
        layout = QVBoxLayout(self)
        
        form_layout = QFormLayout()
        
        self.surname_edit = QLineEdit()
        self.name_edit = QLineEdit()
        self.patronymic_edit = QLineEdit()
        self.email_edit = QLineEdit()
        self.country_combo = QComboBox()
        self.description_edit = QTextEdit()
        
        self.country_combo.addItem("Не выбрано", None)
        for country in self.countries:
            self.country_combo.addItem(country['country'], country['id'])
        
        if collector:
            self.surname_edit.setText(collector.get('surname', ''))
            self.name_edit.setText(collector.get('name', ''))
            self.patronymic_edit.setText(collector.get('patronymic', ''))
            self.email_edit.setText(collector.get('email', ''))
            self.description_edit.setPlainText(collector.get('description', ''))
            
            country_id = collector.get('id_country')
            if country_id:
                for i in range(self.country_combo.count()):
                    if self.country_combo.itemData(i) == country_id:
                        self.country_combo.setCurrentIndex(i)
                        break
        
        form_layout.addRow("Фамилия:", self.surname_edit)
        form_layout.addRow("Имя:", self.name_edit)
        form_layout.addRow("Отчество:", self.patronymic_edit)
        form_layout.addRow("Email:", self.email_edit)
        form_layout.addRow("Страна:", self.country_combo)
        form_layout.addRow("Описание:", self.description_edit)
        
        layout.addLayout(form_layout)
        
        button_layout = QHBoxLayout()
        self.save_btn = QPushButton("Сохранить")
        self.cancel_btn = QPushButton("Отмена")
        
        self.save_btn.setStyleSheet("""
            QPushButton {
                background-color: #27ae60;
                color: white;
                border: none;
                padding: 8px 15px;
                border-radius: 5px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #219a52;
            }
        """)
        
        self.cancel_btn.setStyleSheet("""
            QPushButton {
                background-color: #95a5a6;
                color: white;
                border: none;
                padding: 8px 15px;
                border-radius: 5px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #7f8c8d;
            }
        """)
        
        self.save_btn.clicked.connect(self.accept)
        self.cancel_btn.clicked.connect(self.reject)
        
        button_layout.addWidget(self.save_btn)
        button_layout.addWidget(self.cancel_btn)
        layout.addLayout(button_layout)
    
    def get_data(self):
        return {
            'surname': self.surname_edit.text(),
            'name': self.name_edit.text(),
            'patronymic': self.patronymic_edit.text(),
            'email': self.email_edit.text(),
            'id_country': self.country_combo.currentData(),
            'description': self.description_edit.toPlainText()
        }


class CollectionDialog(QDialog):
    def __init__(self, parent=None, collection=None, collection_types=None):
        super().__init__(parent)
        self.collection = collection
        self.collection_types = collection_types or []
        
        self.setWindowTitle("Редактировать коллекцию" if collection else "Добавить коллекцию")
        self.setModal(True)
        self.setFixedSize(500, 450)
        
        layout = QVBoxLayout(self)
        
        form_layout = QFormLayout()
        
        self.name_edit = QLineEdit()
        self.author_edit = QLineEdit()
        self.type_combo = QComboBox()
        self.date_edit = QDateEdit()
        self.items_spin = QSpinBox()
        self.description_edit = QTextEdit()
        
        self.date_edit.setCalendarPopup(True)
        self.date_edit.setDate(QDate.currentDate())
        self.items_spin.setRange(0, 1000000)
        self.items_spin.setValue(0)
        
        self.type_combo.addItem("Не выбрано", None)
        for ct in self.collection_types:
            self.type_combo.addItem(ct['collection_type'], ct['id'])
        
        if collection:
            self.name_edit.setText(collection.get('name', ''))
            self.author_edit.setText(collection.get('author', ''))
            self.items_spin.setValue(collection.get('number_of_items', 0))
            self.description_edit.setPlainText(collection.get('description', ''))
            
            type_id = collection.get('id_collection_type')
            if type_id:
                for i in range(self.type_combo.count()):
                    if self.type_combo.itemData(i) == type_id:
                        self.type_combo.setCurrentIndex(i)
                        break
            
            date_str = collection.get('date_of_creation')
            if date_str:
                try:
                    date = QDate.fromString(date_str, 'yyyy-MM-dd')
                    if date.isValid():
                        self.date_edit.setDate(date)
                except:
                    pass
        
        form_layout.addRow("Название:", self.name_edit)
        form_layout.addRow("Автор:", self.author_edit)
        form_layout.addRow("Тип коллекции:", self.type_combo)
        form_layout.addRow("Дата создания:", self.date_edit)
        form_layout.addRow("Количество предметов:", self.items_spin)
        form_layout.addRow("Описание:", self.description_edit)
        
        layout.addLayout(form_layout)
        
        button_layout = QHBoxLayout()
        self.save_btn = QPushButton("Сохранить")
        self.cancel_btn = QPushButton("Отмена")
        
        self.save_btn.setStyleSheet("""
            QPushButton {
                background-color: #27ae60;
                color: white;
                border: none;
                padding: 8px 15px;
                border-radius: 5px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #219a52;
            }
        """)
        
        self.cancel_btn.setStyleSheet("""
            QPushButton {
                background-color: #95a5a6;
                color: white;
                border: none;
                padding: 8px 15px;
                border-radius: 5px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #7f8c8d;
            }
        """)
        
        self.save_btn.clicked.connect(self.accept)
        self.cancel_btn.clicked.connect(self.reject)
        
        button_layout.addWidget(self.save_btn)
        button_layout.addWidget(self.cancel_btn)
        layout.addLayout(button_layout)
    
    def accept(self):
        if not self.name_edit.text().strip():
            QMessageBox.warning(self, "Ошибка", "Название коллекции не может быть пустым")
            return
            
        if self.type_combo.currentData() is None:
            QMessageBox.warning(self, "Ошибка", "Необходимо выбрать тип коллекции")
            return
            
        super().accept()
    
    def get_data(self):
        return {
            'name': self.name_edit.text(),
            'author': self.author_edit.text(),
            'id_collection_type': self.type_combo.currentData(),
            'date_of_creation': self.date_edit.date().toString('yyyy-MM-dd'),
            'number_of_items': self.items_spin.value(),
            'description': self.description_edit.toPlainText()
        }


class CatalogItemDialog(QDialog):
    def __init__(self, parent=None, item=None, countries=None):
        super().__init__(parent)
        self.item = item
        self.countries = countries or []
        
        self.setWindowTitle("Редактировать предмет каталога" if item else "Добавить предмет каталога")
        self.setModal(True)
        self.setFixedSize(500, 400)
        
        layout = QVBoxLayout(self)
        
        form_layout = QFormLayout()
        
        self.name_edit = QLineEdit()
        self.rare_combo = QComboBox()
        self.country_combo = QComboBox()
        self.date_edit = QDateEdit()
        self.description_edit = QTextEdit()
        
        self.date_edit.setCalendarPopup(True)
        self.date_edit.setDate(QDate.currentDate())
        
        self.rare_combo.addItems(["Обычный", "Редкий", "Очень редкий", "Уникальный"])
        
        self.country_combo.addItem("Не выбрано", None)
        for country in self.countries:
            self.country_combo.addItem(country['country'], country['id'])
        
        if item:
            self.name_edit.setText(item.get('name', ''))
            self.description_edit.setPlainText(item.get('description', ''))
            
            rare = item.get('rare', '')
            if rare:
                index = self.rare_combo.findText(rare)
                if index >= 0:
                    self.rare_combo.setCurrentIndex(index)
            
            country_id = item.get('id_country')
            if country_id:
                for i in range(self.country_combo.count()):
                    if self.country_combo.itemData(i) == country_id:
                        self.country_combo.setCurrentIndex(i)
                        break
            
            date_str = item.get('release_date')
            if date_str:
                try:
                    date = QDate.fromString(date_str, 'yyyy-MM-dd')
                    if date.isValid():
                        self.date_edit.setDate(date)
                except:
                    pass
        
        form_layout.addRow("Название:", self.name_edit)
        form_layout.addRow("Редкость:", self.rare_combo)
        form_layout.addRow("Страна:", self.country_combo)
        form_layout.addRow("Дата выпуска:", self.date_edit)
        form_layout.addRow("Описание:", self.description_edit)
        
        layout.addLayout(form_layout)
        
        button_layout = QHBoxLayout()
        self.save_btn = QPushButton("Сохранить")
        self.cancel_btn = QPushButton("Отмена")
        
        self.save_btn.setStyleSheet("""
            QPushButton {
                background-color: #27ae60;
                color: white;
                border: none;
                padding: 8px 15px;
                border-radius: 5px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #219a52;
            }
        """)
        
        self.cancel_btn.setStyleSheet("""
            QPushButton {
                background-color: #95a5a6;
                color: white;
                border: none;
                padding: 8px 15px;
                border-radius: 5px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #7f8c8d;
            }
        """)
        
        self.save_btn.clicked.connect(self.accept)
        self.cancel_btn.clicked.connect(self.reject)
        
        button_layout.addWidget(self.save_btn)
        button_layout.addWidget(self.cancel_btn)
        layout.addLayout(button_layout)
    
    def accept(self):
        if not self.name_edit.text().strip():
            QMessageBox.warning(self, "Ошибка", "Название предмета не может быть пустым")
            return
            
        if self.country_combo.currentData() is None:
            QMessageBox.warning(self, "Ошибка", "Необходимо выбрать страну")
            return
            
        super().accept()
    
    def get_data(self):
        return {
            'name': self.name_edit.text(),
            'rare': self.rare_combo.currentText(),
            'id_country': self.country_combo.currentData(),
            'release_date': self.date_edit.date().toString('yyyy-MM-dd'),
            'description': self.description_edit.toPlainText()
        }
