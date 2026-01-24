"""
Конфигурация приложения
"""

# Конфигурация базы данных
DB_CONFIG = {
    'host': 'localhost',
    'user': 'darina',
    'password': '1308',
    'db': 'is21-08',
    'port': 3306,
    'charset': 'utf8mb4',
}

# Конфигурация PDF генерации
PDF_CONFIG = {
    'template_dir': 'templates',
    'wkhtmltopdf_path': {
        'windows': 'C:/Program Files/wkhtmltopdf/bin/wkhtmltopdf.exe',
        'linux': '/usr/bin/wkhtmltopdf',
        'mac': '/usr/local/bin/wkhtmltopdf'
    }
}

# Настройки приложения
APP_CONFIG = {
    'name': 'Платформа Коллекционеров',
    'version': '1.0.0',
    'author': 'Система отчетности',
    'update_interval': 30000  # ms
}
