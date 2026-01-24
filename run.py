#!/usr/bin/env python3
"""
Точка входа для запуска приложения
"""
import sys
import os

# Добавляем src в путь для импорта
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

try:
    from main import main
    sys.exit(main())
except ImportError as e:
    print(f"Ошибка импорта: {e}")
    print("Проверьте установку зависимостей: pip install -r requirements.txt")
    sys.exit(1)
except Exception as e:
    print(f"Ошибка при запуске: {e}")
    sys.exit(1)
