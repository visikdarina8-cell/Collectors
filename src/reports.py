"""
Модуль для генерации отчетов (PDF и Excel)
"""
import asyncio
import aiomysql
import xlsxwriter
import pdfkit
import os
import logging
from datetime import datetime
from jinja2 import Environment, FileSystemLoader
from PySide6.QtCore import QObject, QThread, Signal
from PySide6.QtWidgets import QProgressDialog  # если используется
from PySide6.QtCore import Qt
import config

logger = logging.getLogger(__name__)


class BaseReporter(QObject):
    """Базовый класс для генерации PDF отчетов"""
    
    progress_updated = Signal(str)
    report_finished = Signal(str)
    report_error = Signal(str)
    
    def __init__(self, db_config):
        super().__init__()
        self.db_config = db_config
        
        # Настройка шаблонов
        template_dir = os.path.join(os.path.dirname(__file__), '..', 'templates')
        os.makedirs(template_dir, exist_ok=True)
        self.env = Environment(loader=FileSystemLoader(template_dir))
        
        # Настройка PDFKit
        try:
            if os.name == 'nt':  # Windows
                wkhtmltopdf_path = config.PDF_CONFIG['wkhtmltopdf_path']['windows']
            elif os.name == 'posix':  # Linux/Mac
                wkhtmltopdf_path = config.PDF_CONFIG['wkhtmltopdf_path']['linux']
            else:
                wkhtmltopdf_path = '/usr/bin/wkhtmltopdf'
            
            if os.path.exists(wkhtmltopdf_path):
                self.pdfkit_config = pdfkit.configuration(wkhtmltopdf=wkhtmltopdf_path)
            else:
                self.pdfkit_config = pdfkit.configuration()
                
            logger.info("PDFKit конфигурация успешно настроена")
        except Exception as e:
            logger.warning(f"Не удалось настроить PDFKit: {e}")
            self.pdfkit_config = None

    async def _execute_query(self, query, params=None):
        """Выполнение SQL запроса через прямое подключение"""
        try:
            conn = await aiomysql.connect(
                host=self.db_config['host'],
                user=self.db_config['user'],
                password=self.db_config['password'],
                db=self.db_config['db'],
                autocommit=True
            )
            
            async with conn.cursor(aiomysql.DictCursor) as cursor:
                await cursor.execute(query, params or {})
                if query.strip().upper().startswith('SELECT'):
                    result = await cursor.fetchall()
                else:
                    result = cursor.lastrowid
                
            conn.close()
            return result
            
        except Exception as e:
            logger.error(f"Ошибка выполнения запроса: {e}")
            raise

    def _format_date(self, date_str):
        """Форматирование даты для отображения"""
        try:
            if isinstance(date_str, str):
                date_obj = datetime.strptime(date_str, '%Y-%m-%d')
                return date_obj.strftime('%d.%m.%Y')
            return str(date_str)
        except:
            return str(date_str)

    def _render_template(self, template_name, context):
        """Рендеринг HTML шаблона"""
        try:
            template = self.env.get_template(template_name)
            return template.render(**context)
        except Exception as e:
            logger.error(f"Ошибка рендеринга шаблона {template_name}: {e}")
            raise

    def _generate_pdf(self, html_content, output_path):
        """Генерация PDF из HTML контента"""
        try:
            options = {
                'page-size': 'A4',
                'margin-top': '0.75in',
                'margin-right': '0.75in',
                'margin-bottom': '0.75in',
                'margin-left': '0.75in',
                'encoding': "UTF-8",
                'no-outline': None,
                'enable-local-file-access': None,
                'quiet': ''
            }
            
            if self.pdfkit_config:
                pdfkit.from_string(html_content, output_path, options=options, configuration=self.pdfkit_config)
            else:
                pdfkit.from_string(html_content, output_path, options=options)
                
            logger.info(f"PDF успешно сгенерирован: {output_path}")
            return True
            
        except Exception as e:
            logger.error(f"Ошибка генерации PDF: {e}")
            raise

    async def generate_report(self, output_path):
        """Абстрактный метод генерации отчета"""
        raise NotImplementedError("Метод должен быть реализован в дочернем классе")


class StatisticalReport(BaseReporter):
    """Генератор статистического отчета 'Общая статистика приложения'"""
    
    def __init__(self, db_config):
        super().__init__(db_config)
        self.report_name = "Общая статистика приложения"
        
    async def _collect_statistical_data(self):
        """Сбор статистических данных"""
        logger.info("Начало сбора статистических данных")
        
        data = {}
        
        try:
            self.progress_updated.emit("Сбор общей статистики...")
            
            # Общая статистика
            general_stats = await self._execute_query("""
                SELECT 
                    (SELECT COUNT(*) FROM collector) as total_collectors,
                    (SELECT COUNT(*) FROM collection) as total_collections,
                    (SELECT COUNT(*) FROM catalog) as total_catalog_items,
                    (SELECT COUNT(*) FROM collection_item) as total_items_in_collections,
                    (SELECT COUNT(*) FROM collection WHERE date_of_creation >= DATE_SUB(NOW(), INTERVAL 30 DAY)) as recent_collections,
                    (SELECT COUNT(*) FROM collector WHERE id IN (
                        SELECT DISTINCT c.id FROM collector c 
                        JOIN collection col ON c.id = col.author
                    )) as active_collectors
            """)
            data['general_stats'] = general_stats[0] if general_stats else {}
            
            self.progress_updated.emit("Анализ типов коллекций...")
            
            # Распределение по типам коллекций
            collection_types = await self._execute_query("""
                SELECT ct.collection_type, COUNT(c.id) as count
                FROM collection c
                LEFT JOIN collection_type ct ON c.id_collection_type = ct.id
                GROUP BY ct.collection_type
                ORDER BY count DESC
            """)
            data['collection_types'] = collection_types
            
            self.progress_updated.emit("Поиск самых активных коллекционеров...")
            
            # Топ коллекционеров
            top_collectors = await self._execute_query("""
                SELECT c.surname, c.name, COUNT(col.id) as collections_count
                FROM collector c
                LEFT JOIN collection col ON c.id = col.author
                GROUP BY c.id, c.surname, c.name
                ORDER BY collections_count DESC
                LIMIT 5
            """)
            data['top_collectors'] = top_collectors
            
            self.progress_updated.emit("Анализ месячной активности...")
            
            # Активность по месяцам
            monthly_activity = await self._execute_query("""
                SELECT 
                    DATE_FORMAT(date_of_creation, '%%Y-%%m') as month,
                    COUNT(*) as collections_created
                FROM collection
                WHERE date_of_creation >= DATE_SUB(NOW(), INTERVAL 6 MONTH)
                GROUP BY DATE_FORMAT(date_of_creation, '%%Y-%%m')
                ORDER BY month
            """)
            data['monthly_activity'] = monthly_activity
            
            # Расчет дополнительных метрик
            if data['general_stats']:
                stats = data['general_stats']
                total_collectors = stats.get('total_collectors', 0) or 0
                total_collections = stats.get('total_collections', 0) or 0
                total_items = stats.get('total_items_in_collections', 0) or 0
                recent_collections = stats.get('recent_collections', 0) or 0
                active_collectors = stats.get('active_collectors', 0) or 0
                
                active_percentage = (active_collectors / max(total_collectors, 1)) * 100
                data['additional_metrics'] = {
                    'active_collectors_percentage': round(active_percentage, 1),
                    'avg_items_per_collection': total_items / max(total_collections, 1),
                    'recent_collections_percentage': (recent_collections / max(total_collections, 1)) * 100
                }
            
            logger.info("Статистические данные успешно собраны")
            return data
            
        except Exception as e:
            logger.error(f"Ошибка сбора статистических данных: {e}")
            raise
    
    async def generate_report(self, output_path):
        """Генерация статистического отчета"""
        try:
            logger.info(f"Начало генерации статистического отчета: {output_path}")
            
            self.progress_updated.emit("Подготовка данных для отчета...")
            
            # Сбор данных
            data = await self._collect_statistical_data()
            
            # Подготовка контекста для шаблона
            context = {
                'report_name': self.report_name,
                'generation_date': datetime.now().strftime('%d.%m.%Y %H:%M'),
                'app_name': config.APP_CONFIG['name'],
                'data': data,
                'format_date': self._format_date
            }
            
            self.progress_updated.emit("Генерация PDF отчета...")
            
            # Рендеринг HTML
            html_content = self._render_template('statistical_report.html', context)
            
            # Генерация PDF
            self._generate_pdf(html_content, output_path)
            
            logger.info(f"Статистический отчет успешно сгенерирован: {output_path}")
            return output_path
            
        except Exception as e:
            logger.error(f"Ошибка генерации статистического отчета: {e}")
            raise


class DetailedReport(BaseReporter):
    """Генератор детального табличного отчета 'Детальная информация'"""
    
    def __init__(self, db_config):
        super().__init__(db_config)
        self.report_name = "Детальная информация по системе"
        
    async def _collect_detailed_data(self):
        """Сбор детальных данных для отчета"""
        logger.info("Начало сбора детальных данных")
        
        data = {}
        
        try:
            self.progress_updated.emit("Загрузка данных о коллекционерах...")
            
            # Коллекционеры с коллекциями
            collectors_data = await self._execute_query("""
                SELECT 
                    c.id,
                    c.surname,
                    c.name,
                    c.patronymic,
                    c.email,
                    co.country,
                    COUNT(col.id) as collections_count
                FROM collector c
                LEFT JOIN country co ON c.id_country = co.id
                LEFT JOIN collection col ON c.id = col.author
                GROUP BY c.id, c.surname, c.name, c.patronymic, c.email, co.country
                ORDER BY collections_count DESC
                LIMIT 50
            """)
            data['collectors'] = collectors_data or []
            
            self.progress_updated.emit("Загрузка данных о коллекциях...")
            
            # Коллекции с типами
            collections_data = await self._execute_query("""
                SELECT 
                    col.id,
                    col.name,
                    col.author,
                    ct.collection_type,
                    col.date_of_creation,
                    col.number_of_items,
                    col.description
                FROM collection col
                LEFT JOIN collection_type ct ON col.id_collection_type = ct.id
                ORDER BY col.date_of_creation DESC
                LIMIT 50
            """)
            data['collections'] = collections_data or []
            
            self.progress_updated.emit("Загрузка данных о предметах каталога...")
            
            # Предметы каталога
            catalog_data = await self._execute_query("""
                SELECT 
                    cat.id,
                    cat.name,
                    cat.rare,
                    co.country,
                    cat.release_date,
                    cat.description
                FROM catalog cat
                LEFT JOIN country co ON cat.id_country = co.id
                ORDER BY cat.release_date DESC
                LIMIT 50
            """)
            data['catalog'] = catalog_data or []
            
            logger.info("Детальные данные успешно собраны")
            return data
            
        except Exception as e:
            logger.error(f"Ошибка сбора детальных данных: {e}")
            raise
    
    async def generate_report(self, output_path):
        """Генерация детального отчета"""
        try:
            logger.info(f"Начало генерации детального отчета: {output_path}")
            
            self.progress_updated.emit("Подготовка данных для отчета...")
            
            # Сбор данных
            data = await self._collect_detailed_data()
            
            # Подготовка контекста для шаблона
            context = {
                'report_name': self.report_name,
                'generation_date': datetime.now().strftime('%d.%m.%Y %H:%M'),
                'app_name': config.APP_CONFIG['name'],
                'data': data,
                'format_date': self._format_date
            }
            
            self.progress_updated.emit("Генерация PDF отчета...")
            
            # Рендеринг HTML
            html_content = self._render_template('detailed_report.html', context)
            
            # Генерация PDF
            self._generate_pdf(html_content, output_path)
            
            logger.info(f"Детальный отчет успешно сгенерирован: {output_path}")
            return output_path
            
        except Exception as e:
            logger.error(f"Ошибка генерации детального отчета: {e}")
            raise


class PDFReportThread(QThread):
    """Поток для асинхронной генерации PDF отчетов"""
    
    finished = Signal(str)
    error = Signal(str)
    progress = Signal(str)
    
    def __init__(self, db_config, report_type, filename, parent=None):
        super().__init__(parent)
        self.db_config = db_config
        self.report_type = report_type
        self.filename = filename
    
    def run(self):
        try:
            # Создаем новую event loop для этого потока
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            if self.report_type == 'statistical':
                reporter = StatisticalReport(self.db_config)
            else:
                reporter = DetailedReport(self.db_config)
            
            # Подключаем сигналы прогресса
            reporter.progress_updated.connect(self.progress.emit)
            
            try:
                # Запускаем асинхронную генерацию
                result = loop.run_until_complete(reporter.generate_report(self.filename))
                self.finished.emit(result)
            except Exception as e:
                logger.error(f"Ошибка генерации отчета: {e}")
                self.error.emit(str(e))
            finally:
                loop.close()
                
        except Exception as e:
            logger.error(f"Ошибка в потоке генерации PDF: {e}")
            self.error.emit(str(e))


class ExcelExporter(QObject):
    """Класс для генерации Excel отчетов"""
    
    progress_updated = Signal(int)
    export_finished = Signal(str)
    export_error = Signal(str)
    
    def __init__(self, db_manager):
        super().__init__()
        self.db_manager = db_manager

    async def _get_all_data(self):
        """Получение всех данных для отчета"""
        try:
            collectors = await self.db_manager._get_collectors()
            collections = await self.db_manager._get_collections()
            catalog = await self.db_manager._get_catalog()
            statistics = await self.db_manager._get_statistics()
            collection_types_stats = await self.db_manager._get_collection_types_stats()
            country_stats = await self.db_manager._get_country_stats()
            countries = await self.db_manager._get_countries()
            collection_types = await self.db_manager._get_collection_types()
            
            return {
                'collectors': collectors or [],
                'collections': collections or [],
                'catalog': catalog or [],
                'statistics': statistics or {},
                'collection_types_stats': collection_types_stats or [],
                'country_stats': country_stats or [],
                'countries': countries or [],
                'collection_types': collection_types or []
            }
        except Exception as e:
            logger.error(f"Ошибка получения данных для Excel: {e}")
            raise

    def create_excel_report(self, filename):
        """Создание Excel отчета"""
        try:
            if self.db_manager.loop and self.db_manager.loop.is_running():
                future = asyncio.run_coroutine_threadsafe(self._create_report(filename), self.db_manager.loop)
                future.add_done_callback(self._on_export_complete)
            else:
                self.export_error.emit("Event loop не запущен")
        except Exception as e:
            self.export_error.emit(f"Ошибка запуска экспорта: {e}")

    async def _create_report(self, filename):
        """Асинхронное создание отчета"""
        try:
            self.progress_updated.emit(10)
            
            data = await self._get_all_data()
            self.progress_updated.emit(30)
            
            # Создаем словарь для связи ID коллекционера с его именем
            collector_name_map = {}
            for collector in data.get('collectors', []):
                collector_name = f"{collector.get('surname', '')} {collector.get('name', '')}".strip()
                if collector.get('patronymic'):
                    collector_name += f" {collector.get('patronymic', '')}"
                collector_name_map[collector.get('id')] = collector_name
            
            # Подсчитываем количество коллекций для каждого коллекционера
            collections_count_map = {}
            for collection in data.get('collections', []):
                author_id = collection.get('author')
                if author_id:
                    collections_count_map[author_id] = collections_count_map.get(author_id, 0) + 1
            
            workbook = xlsxwriter.Workbook(filename, {'default_date_format': 'dd.mm.yyyy'})
            
            # Форматы
            title_format = workbook.add_format({
                'bold': True,
                'font_size': 14,
                'fg_color': '#FF6B35',
                'font_color': 'white',
                'border': 1,
                'align': 'center',
                'valign': 'vcenter'
            })
            
            header_format = workbook.add_format({
                'bold': True,
                'font_size': 11,
                'fg_color': '#FFE0B2',
                'font_color': '#BF360C',
                'border': 1,
                'align': 'center',
                'valign': 'vcenter'
            })
            
            # Правильные числовые форматы
            id_format = workbook.add_format({'num_format': '0', 'border': 1, 'align': 'center'})
            date_format = workbook.add_format({'num_format': 'dd.mm.yyyy', 'border': 1, 'align': 'center'})
            number_format = workbook.add_format({'num_format': '#,##0', 'border': 1, 'align': 'center'})
            text_format = workbook.add_format({'border': 1, 'valign': 'top', 'text_wrap': True})
            center_format = workbook.add_format({'align': 'center', 'border': 1, 'valign': 'vcenter'})
            bold_format = workbook.add_format({'bold': True, 'border': 1})
            decimal_format = workbook.add_format({'num_format': '0.00', 'border': 1, 'align': 'center'})
            
            # ЛИСТ 1: ДАННЫЕ ПРОЕКТА
            worksheet_data = workbook.add_worksheet('Данные проекта')
            
            worksheet_data.merge_range('A1:I1', 'ОТЧЕТ ПЛАТФОРМЫ КОЛЛЕКЦИОНЕРОВ', title_format)
            worksheet_data.merge_range('A2:I2', 'Система управления коллекциями марок и монет', header_format)
            worksheet_data.set_row(0, 40)
            worksheet_data.set_row(1, 25)
            
            # Увеличиваем высоту строк для заголовков
            worksheet_data.set_row(3, 30)
            
            headers = [
                'ID', 'Фамилия', 'Имя', 'Отчество', 'Email', 'Страна', 
                'Описание', 'Кол-во коллекций', 'Сумма предметов'
            ]
            
            for col, header in enumerate(headers):
                worksheet_data.write(3, col, header, header_format)
            
            # Увеличиваем ширину колонок для лучшего отображения
            column_widths = [6, 15, 15, 15, 25, 15, 40, 15, 15]
            for col, width in enumerate(column_widths):
                worksheet_data.set_column(col, col, width)
            
            row = 4
            # Считаем общее количество предметов для каждого коллекционера
            collector_items_map = {}
            for collection in data.get('collections', []):
                author_id = collection.get('author')
                items_count = collection.get('number_of_items', 0)
                if author_id:
                    collector_items_map[author_id] = collector_items_map.get(author_id, 0) + items_count
            
            for collector in data.get('collectors', []):
                collector_id = collector.get('id')
                collections_count = collections_count_map.get(collector_id, 0)
                total_items = collector_items_map.get(collector_id, 0)
                
                worksheet_data.write_number(row, 0, collector_id, id_format)
                worksheet_data.write(row, 1, collector.get('surname', ''), text_format)
                worksheet_data.write(row, 2, collector.get('name', ''), text_format)
                worksheet_data.write(row, 3, collector.get('patronymic', ''), text_format)
                worksheet_data.write(row, 4, collector.get('email', ''), text_format)
                worksheet_data.write(row, 5, collector.get('country', ''), center_format)
                worksheet_data.write(row, 6, collector.get('description', ''), text_format)
                worksheet_data.write_number(row, 7, collections_count, number_format)
                worksheet_data.write_number(row, 8, total_items, number_format)
                
                # Увеличиваем высоту строк для длинных описаний
                description = collector.get('description', '')
                if len(description) > 100:
                    worksheet_data.set_row(row, 60)
                
                row += 1
            
            if data.get('collectors'):
                worksheet_data.autofilter(3, 0, row-1, len(headers)-1)
            
            # Пустая строка
            row += 2
            
            # КОЛЛЕКЦИИ
            worksheet_data.write(row, 0, 'Коллекции:', bold_format)
            row += 1
            
            collection_headers = [
                'ID', 'Название', 'Автор', 'Тип', 'Дата создания', 
                'Кол-во предметов', 'Описание'
            ]
            
            for col, header in enumerate(collection_headers):
                worksheet_data.write(row, col, header, header_format)
            
            row += 1
            collections_start_row = row
            
            for collection in data.get('collections', []):
                worksheet_data.write_number(row, 0, collection.get('id', 0), id_format)
                worksheet_data.write(row, 1, collection.get('name', ''), text_format)
                
                # Получаем имя автора из словаря
                author_id = collection.get('author')
                author_name = collector_name_map.get(author_id, str(author_id) if author_id else 'Неизвестно')
                worksheet_data.write(row, 2, author_name, text_format)
                
                worksheet_data.write(row, 3, collection.get('collection_type', ''), center_format)
                
                # Форматируем дату
                date_str = collection.get('date_of_creation')
                if date_str:
                    try:
                        if isinstance(date_str, str):
                            date_str = date_str.split(' ')[0]
                            try:
                                date = datetime.strptime(date_str, '%Y-%m-%d')
                                worksheet_data.write_datetime(row, 4, date, date_format)
                            except ValueError:
                                worksheet_data.write(row, 4, date_str, center_format)
                        else:
                            worksheet_data.write_datetime(row, 4, date_str, date_format)
                    except Exception:
                        worksheet_data.write(row, 4, str(date_str), center_format)
                else:
                    worksheet_data.write(row, 4, '', center_format)
                
                worksheet_data.write_number(row, 5, collection.get('number_of_items', 0), number_format)
                worksheet_data.write(row, 6, collection.get('description', ''), text_format)
                
                # Увеличиваем высоту строк для длинных описаний
                description = collection.get('description', '')
                if len(description) > 100:
                    worksheet_data.set_row(row, 60)
                
                row += 1
            
            if data.get('collections'):
                worksheet_data.autofilter(collections_start_row-1, 0, row-1, len(collection_headers)-1)
            
            # Пустая строка
            row += 2
            
            # КАТАЛОГ
            worksheet_data.write(row, 0, 'Каталог предметов:', bold_format)
            row += 1
            
            catalog_headers = [
                'ID', 'Название', 'Редкость', 'Страна', 'Дата выпуска', 'Описание'
            ]
            
            for col, header in enumerate(catalog_headers):
                worksheet_data.write(row, col, header, header_format)
            
            row += 1
            catalog_start_row = row
            
            for item in data.get('catalog', []):
                worksheet_data.write_number(row, 0, item.get('id', 0), id_format)
                worksheet_data.write(row, 1, item.get('name', ''), text_format)
                worksheet_data.write(row, 2, item.get('rare', ''), center_format)
                worksheet_data.write(row, 3, item.get('country', ''), center_format)
                
                # Форматируем дату выпуска
                release_date = item.get('release_date')
                if release_date:
                    try:
                        if isinstance(release_date, str):
                            release_date = release_date.split(' ')[0]
                            if release_date == '0000-00-00' or release_date.startswith('0000-'):
                                worksheet_data.write(row, 4, 'Неизвестно', center_format)
                            else:
                                try:
                                    date = datetime.strptime(release_date, '%Y-%m-%d')
                                    worksheet_data.write_datetime(row, 4, date, date_format)
                                except ValueError:
                                    worksheet_data.write(row, 4, release_date, center_format)
                        else:
                            worksheet_data.write_datetime(row, 4, release_date, date_format)
                    except Exception:
                        worksheet_data.write(row, 4, str(release_date), center_format)
                else:
                    worksheet_data.write(row, 4, '', center_format)
                
                worksheet_data.write(row, 5, item.get('description', ''), text_format)
                
                # Увеличиваем высоту строк для длинных описаний
                description = item.get('description', '')
                if len(description) > 100:
                    worksheet_data.set_row(row, 60)
                
                row += 1
            
            if data.get('catalog'):
                worksheet_data.autofilter(catalog_start_row-1, 0, row-1, len(catalog_headers)-1)
            
            worksheet_data.freeze_panes(4, 0)
            
            # ЛИСТ 2: АНАЛИТИКА
            worksheet_analytics = workbook.add_worksheet('Аналитика')
            worksheet_analytics.merge_range('A1:D1', 'АНАЛИТИКА ДАННЫХ', title_format)
            worksheet_analytics.set_row(0, 40)
            
            row = 3
            
            # 1. Общая статистика
            stats = data.get('statistics', {})
            worksheet_analytics.merge_range(f'A{row}:B{row}', 'ОБЩАЯ СТАТИСТИКА', title_format)
            row += 1
            
            stats_headers = ['Показатель', 'Значение']
            for col, header in enumerate(stats_headers):
                worksheet_analytics.write(row, col, header, header_format)
            row += 1
            
            stats_data = [
                ['Всего коллекционеров', stats.get('collectors_count', 0)],
                ['Всего коллекций', stats.get('collections_count', 0)],
                ['Предметов в каталоге', stats.get('catalog_count', 0)],
                ['Предметов в коллекциях', stats.get('items_count', 0)]
            ]
            
            for stat in stats_data:
                worksheet_analytics.write(row, 0, stat[0], text_format)
                worksheet_analytics.write_number(row, 1, stat[1], number_format)
                row += 1
            
            row += 2
            
            # 2. Распределение по типам коллекций
            worksheet_analytics.merge_range(f'A{row}:C{row}', 'РАСПРЕДЕЛЕНИЕ ПО ТИПАМ КОЛЛЕКЦИЙ', title_format)
            row += 1
            
            type_headers = ['Тип коллекции', 'Количество', 'Доля, %']
            for col, header in enumerate(type_headers):
                worksheet_analytics.write(row, col, header, header_format)
            row += 1
            
            type_stats = data.get('collection_types_stats', [])
            total_collections = sum(item.get('count', 0) for item in type_stats)
            
            type_table_start = row if type_stats else None
            for record in type_stats:
                count = record.get('count', 0)
                percentage = (count / total_collections * 100) if total_collections > 0 else 0
                
                worksheet_analytics.write(row, 0, record.get('collection_type', 'Не указан'), text_format)
                worksheet_analytics.write_number(row, 1, count, number_format)
                worksheet_analytics.write_number(row, 2, percentage, decimal_format)
                row += 1
            
            type_table_end = (row - 1) if type_table_start is not None else None
            
            # График 1: Круговая диаграмма типов коллекций
            if type_table_start is not None and type_table_end is not None and type_table_end >= type_table_start:
                chart1 = workbook.add_chart({'type': 'pie'})
                excel_start = type_table_start + 1
                excel_end = type_table_end + 1
                
                chart1.add_series({
                    'name': 'Типы коллекций',
                    'categories': f'=Аналитика!$A${excel_start}:$A${excel_end}',
                    'values': f'=Аналитика!$B${excel_start}:$B${excel_end}',
                })
                chart1.set_title({'name': 'Распределение коллекций по типам'})
                chart1.set_style(10)
                worksheet_analytics.insert_chart('E3', chart1)
            
            row += 20
            
            # 3. Коллекционеры по странам
            worksheet_analytics.merge_range(f'A{row}:C{row}', 'КОЛЛЕКЦИОНЕРЫ ПО СТРАНАМ', title_format)
            row += 1
            
            country_headers = ['Страна', 'Кол-во коллекционеров', 'Доля, %']
            for col, header in enumerate(country_headers):
                worksheet_analytics.write(row, col, header, header_format)
            row += 1
            
            country_stats = data.get('country_stats', [])
            total_collectors = sum(item.get('collector_count', 0) for item in country_stats)
            
            country_table_start = row if country_stats else None
            for record in country_stats:
                count = record.get('collector_count', 0)
                percentage = (count / total_collectors * 100) if total_collectors > 0 else 0
                
                worksheet_analytics.write(row, 0, record.get('country', 'Не указана'), text_format)
                worksheet_analytics.write_number(row, 1, count, number_format)
                worksheet_analytics.write_number(row, 2, percentage, decimal_format)
                row += 1
            
            country_table_end = (row - 1) if country_table_start is not None else None
            
            # График 2: Столбчатая диаграмма по странам
            if country_table_start is not None and country_table_end is not None and country_table_end >= country_table_start:
                chart2 = workbook.add_chart({'type': 'column'})
                excel_start = country_table_start + 1
                excel_end = country_table_end + 1
                
                chart2.add_series({
                    'name': 'Коллекционеры',
                    'categories': f'=Аналитика!$A${excel_start}:$A${excel_end}',
                    'values': f'=Аналитика!$B${excel_start}:$B${excel_end}',
                })
                chart2.set_title({'name': 'Коллекционеры по странам'})
                chart2.set_x_axis({'name': 'Страна'})
                chart2.set_y_axis({'name': 'Количество'})
                chart2.set_style(11)
                chart2.set_legend({'none': True})
                worksheet_analytics.insert_chart('E23', chart2)
            
            # Расчетные показатели
            row += 20
            worksheet_analytics.merge_range(f'A{row}:B{row}', 'РАСЧЕТНЫЕ ПОКАЗАТЕЛИ', title_format)
            row += 1
            
            total_collectors_val = stats.get('collectors_count', 0)
            total_collections_val = stats.get('collections_count', 0)
            total_items_val = stats.get('items_count', 0)
            
            metrics = [
                ['Всего коллекционеров:', total_collectors_val],
                ['Всего коллекций:', total_collections_val],
                ['Среднее коллекций на коллекционера:', 
                 round(total_collections_val / max(total_collectors_val, 1), 2)],
                ['Всего предметов в коллекциях:', total_items_val],
                ['Среднее предметов в коллекции:', 
                 round(total_items_val / max(total_collections_val, 1), 2)],
                ['Активных коллекционеров (имеющих коллекции):', 
                 sum(1 for collector_id, count in collections_count_map.items() if count > 0)]
            ]
            
            for metric_name, metric_value in metrics:
                worksheet_analytics.write(row, 0, metric_name, bold_format)
                if isinstance(metric_value, (int, float)):
                    if isinstance(metric_value, int):
                        worksheet_analytics.write_number(row, 1, metric_value, number_format)
                    else:
                        worksheet_analytics.write(row, 1, metric_value, decimal_format)
                row += 1
            
            # Устанавливаем ширину колонок
            worksheet_analytics.set_column('A:A', 35)
            worksheet_analytics.set_column('B:B', 20)
            worksheet_analytics.set_column('C:C', 15)
            
            # ЛИСТ 3: ВИЗУАЛИЗАЦИЯ
            worksheet_viz = workbook.add_worksheet('Визуализация')
            worksheet_viz.merge_range('A1:C1', 'ВИЗУАЛИЗАЦИЯ ДАННЫХ', title_format)
            worksheet_viz.set_row(0, 40)
            
            row = 3
            
            # Инфографика
            worksheet_viz.merge_range(f'A{row}:B{row}', 'ИНФОГРАФИКА ОСНОВНЫХ ПОКАЗАТЕЛЕЙ', title_format)
            row += 1
            
            info_headers = ['Показатель', 'Значение', 'Описание']
            for col, header in enumerate(info_headers):
                worksheet_viz.write(row, col, header, header_format)
            row += 1
            
            info_data = [
                ['Всего коллекционеров', total_collectors_val, 'Коллекционеров в системе'],
                ['Всего коллекций', total_collections_val, 'Коллекций создано'],
                ['Всего предметов', total_items_val, 'Предметов в коллекциях'],
                ['Предметов в каталоге', stats.get('catalog_count', 0), 'Предметов в общем каталоге'],
                ['Типов коллекций', len(type_stats), 'Различных типов коллекций'],
                ['Стран', len(country_stats), 'Стран представлено'],
                ['Активных коллекционеров', sum(1 for c in collections_count_map.values() if c > 0), 
                 'Коллекционеров с коллекциями']
            ]
            
            for info_row in info_data:
                worksheet_viz.write(row, 0, info_row[0], bold_format)
                worksheet_viz.write_number(row, 1, info_row[1], number_format)
                worksheet_viz.write(row, 2, info_row[2], text_format)
                row += 1
            
            # Выводы
            row += 2
            worksheet_viz.merge_range(f'A{row}:C{row}', 'ВЫВОДЫ ПО АНАЛИТИКЕ', title_format)
            row += 1
            
            active_collectors = sum(1 for c in collections_count_map.values() if c > 0)
            top_collector_id = max(collections_count_map.items(), key=lambda x: x[1])[0] if collections_count_map else None
            top_collector_name = collector_name_map.get(top_collector_id, 'Неизвестно') if top_collector_id else 'Неизвестно'
            top_collections_count = collections_count_map.get(top_collector_id, 0) if top_collector_id else 0
            
            conclusions = [
                f'1. В системе зарегистрировано {total_collectors_val} коллекционеров, из них {active_collectors} активных.',
                f'2. Создано {total_collections_val} коллекций различных типов.',
                f'3. В каталоге представлено {stats.get("catalog_count", 0)} предметов.',
                f'4. Всего в коллекциях содержится {total_items_val} предметов.',
            ]
            
            if type_stats:
                top_type = max(type_stats, key=lambda x: x.get('count', 0))
                conclusions.append(f'5. Наиболее популярный тип коллекций: {top_type.get("collection_type")} '
                                 f'({top_type.get("count")} коллекций).')
            
            if country_stats:
                top_country = max(country_stats, key=lambda x: x.get('collector_count', 0))
                conclusions.append(f'6. Больше всего коллекционеров в стране: {top_country.get("country")} '
                                 f'({top_country.get("collector_count")} человек).')
            
            if top_collections_count > 0:
                conclusions.append(f'7. Самый активный коллекционер: {top_collector_name} '
                                 f'({top_collections_count} коллекций).')
            
            for conclusion in conclusions:
                worksheet_viz.merge_range(row, 0, row, 2, conclusion, text_format)
                row += 1
            
            # Устанавливаем ширину колонок
            worksheet_viz.set_column('A:A', 30)
            worksheet_viz.set_column('B:B', 15)
            worksheet_viz.set_column('C:C', 45)
            
            workbook.close()
            self.progress_updated.emit(100)
            
            self.export_finished.emit(filename)
            
        except Exception as e:
            logger.error(f"Ошибка создания Excel отчета: {e}")
            self.export_error.emit(f"Ошибка создания отчета: {e}")

    def _on_export_complete(self, future):
        """Обработка завершения экспорта"""
        try:
            future.result()
        except Exception as e:
            logger.error(f"Ошибка при создании отчета: {e}")
            self.export_error.emit(f"Ошибка при создании отчета: {e}")
