"""
Модуль для работы с базой данных
"""
import asyncio
import aiomysql
import threading
import time
import logging
from PySide6.QtCore import QObject, Signal
import config

logger = logging.getLogger(__name__)


class DatabaseManager(QObject):
    data_loaded = Signal(str, object)
    error_occurred = Signal(str)
    connected = Signal()
    
    def __init__(self, db_config=None):
        super().__init__()
        self.db_config = db_config or config.DB_CONFIG
        self.pool = None
        self.loop = None
        self.thread = None
        self._is_loop_ready = False

    def start(self):
        """Запуск event loop в отдельном потоке"""
        self.thread = threading.Thread(target=self._run_event_loop, daemon=True)
        self.thread.start()

    def _run_event_loop(self):
        """Запуск event loop"""
        try:
            self.loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.loop)
            self._is_loop_ready = True
            logger.info("Event loop запущен")
            self.loop.run_forever()
        except Exception as e:
            logger.error(f"Ошибка в event loop: {e}")
            self.error_occurred.emit(str(e))

    def wait_for_loop(self, timeout=5):
        """Ожидание инициализации event loop"""
        start_time = time.time()
        while not self._is_loop_ready and time.time() - start_time < timeout:
            time.sleep(0.1)
        return self._is_loop_ready

    async def _connect(self):
        """Подключение к базе данных"""
        try:
            logger.info("Подключение к базе данных...")
            self.pool = await aiomysql.create_pool(
                host=self.db_config['host'],
                user=self.db_config['user'],
                password=self.db_config['password'],
                db=self.db_config['db'],
                autocommit=True,
                minsize=1,
                maxsize=10
            )
            logger.info("✅ Успешное подключение к базе данных")
            self.connected.emit()
            return True
        except Exception as e:
            logger.error(f"❌ Ошибка подключения к базе данных: {e}")
            self.error_occurred.emit(str(e))
            return False

    async def _execute_query(self, query, params=None):
        """Выполнение запроса"""
        if not self.pool:
            return None
            
        try:
            async with self.pool.acquire() as conn:
                async with conn.cursor(aiomysql.DictCursor) as cursor:
                    await cursor.execute(query, params)
                    if query.strip().upper().startswith('SELECT'):
                        return await cursor.fetchall()
                    else:
                        return cursor.lastrowid
        except Exception as e:
            logger.error(f"Ошибка выполнения запроса: {e}")
            return None

    def connect(self):
        """Запуск подключения к БД"""
        if self.wait_for_loop():
            asyncio.run_coroutine_threadsafe(self._connect(), self.loop)
        else:
            logger.error("Event loop не запущен")
            self.error_occurred.emit("Event loop не запущен")

    # Методы для получения данных
    def get_collectors(self):
        if not self.pool: return
        future = asyncio.run_coroutine_threadsafe(self._get_collectors(), self.loop)
        future.add_done_callback(lambda f: self._on_data_loaded(f, 'collectors'))

    def get_collections(self):
        if not self.pool: return
        future = asyncio.run_coroutine_threadsafe(self._get_collections(), self.loop)
        future.add_done_callback(lambda f: self._on_data_loaded(f, 'collections'))

    def get_catalog(self):
        if not self.pool: return
        future = asyncio.run_coroutine_threadsafe(self._get_catalog(), self.loop)
        future.add_done_callback(lambda f: self._on_data_loaded(f, 'catalog'))

    def get_statistics(self):
        if not self.pool: return
        future = asyncio.run_coroutine_threadsafe(self._get_statistics(), self.loop)
        future.add_done_callback(lambda f: self._on_data_loaded(f, 'statistics'))

    def get_collection_types_stats(self):
        if not self.pool: return
        future = asyncio.run_coroutine_threadsafe(self._get_collection_types_stats(), self.loop)
        future.add_done_callback(lambda f: self._on_data_loaded(f, 'collection_types'))

    def get_country_stats(self):
        if not self.pool: return
        future = asyncio.run_coroutine_threadsafe(self._get_country_stats(), self.loop)
        future.add_done_callback(lambda f: self._on_data_loaded(f, 'country_stats'))

    def get_countries(self):
        if not self.pool: return
        future = asyncio.run_coroutine_threadsafe(self._get_countries(), self.loop)
        future.add_done_callback(lambda f: self._on_data_loaded(f, 'countries'))

    def get_collection_types(self):
        if not self.pool: return
        future = asyncio.run_coroutine_threadsafe(self._get_collection_types(), self.loop)
        future.add_done_callback(lambda f: self._on_data_loaded(f, 'collection_types_list'))

    # Асинхронные методы для выполнения запросов
    async def _get_collectors(self):
        return await self._execute_query("""
            SELECT c.*, co.country 
            FROM collector c 
            LEFT JOIN country co ON c.id_country = co.id
        """)

    async def _get_collections(self):
        return await self._execute_query("""
            SELECT col.*, ct.collection_type 
            FROM collection col 
            LEFT JOIN collection_type ct ON col.id_collection_type = ct.id
        """)

    async def _get_catalog(self):
        return await self._execute_query("""
            SELECT cat.*, co.country 
            FROM catalog cat 
            LEFT JOIN country co ON cat.id_country = co.id
        """)

    async def _get_statistics(self):
        result = await self._execute_query("""
            SELECT 
                (SELECT COUNT(*) FROM collector) as collectors_count,
                (SELECT COUNT(*) FROM collection) as collections_count,
                (SELECT COUNT(*) FROM catalog) as catalog_count,
                (SELECT COUNT(*) FROM collection_item) as items_count
        """)
        return result[0] if result else {}

    async def _get_collection_types_stats(self):
        return await self._execute_query("""
            SELECT ct.collection_type, COUNT(c.id) as count
            FROM collection c
            LEFT JOIN collection_type ct ON c.id_collection_type = ct.id
            GROUP BY ct.collection_type
        """)

    async def _get_country_stats(self):
        return await self._execute_query("""
            SELECT co.country, COUNT(c.id) as collector_count
            FROM collector c
            LEFT JOIN country co ON c.id_country = co.id
            GROUP BY co.country
            ORDER BY collector_count DESC
            LIMIT 10
        """)

    async def _get_countries(self):
        return await self._execute_query("SELECT * FROM country")

    async def _get_collection_types(self):
        return await self._execute_query("SELECT * FROM collection_type")

    # Методы для добавления/обновления/удаления данных
    def add_collector(self, data):
        if not self.pool: return
        future = asyncio.run_coroutine_threadsafe(self._add_collector(data), self.loop)
        future.add_done_callback(lambda f: self._on_modify_complete(f, 'collector_added'))

    def update_collector(self, collector_id, data):
        if not self.pool: return
        future = asyncio.run_coroutine_threadsafe(self._update_collector(collector_id, data), self.loop)
        future.add_done_callback(lambda f: self._on_modify_complete(f, 'collector_updated'))

    def delete_collector(self, collector_id):
        if not self.pool: return
        future = asyncio.run_coroutine_threadsafe(self._delete_collector(collector_id), self.loop)
        future.add_done_callback(lambda f: self._on_modify_complete(f, 'collector_deleted'))

    def add_collection(self, data):
        if not self.pool: return
        future = asyncio.run_coroutine_threadsafe(self._add_collection(data), self.loop)
        future.add_done_callback(lambda f: self._on_modify_complete(f, 'collection_added'))

    def update_collection(self, collection_id, data):
        if not self.pool: return
        future = asyncio.run_coroutine_threadsafe(self._update_collection(collection_id, data), self.loop)
        future.add_done_callback(lambda f: self._on_modify_complete(f, 'collection_updated'))

    def delete_collection(self, collection_id):
        if not self.pool: return
        future = asyncio.run_coroutine_threadsafe(self._delete_collection(collection_id), self.loop)
        future.add_done_callback(lambda f: self._on_modify_complete(f, 'collection_deleted'))

    def add_catalog_item(self, data):
        if not self.pool: return
        future = asyncio.run_coroutine_threadsafe(self._add_catalog_item(data), self.loop)
        future.add_done_callback(lambda f: self._on_modify_complete(f, 'catalog_item_added'))

    def update_catalog_item(self, item_id, data):
        if not self.pool: return
        future = asyncio.run_coroutine_threadsafe(self._update_catalog_item(item_id, data), self.loop)
        future.add_done_callback(lambda f: self._on_modify_complete(f, 'catalog_item_updated'))

    def delete_catalog_item(self, item_id):
        if not self.pool: return
        future = asyncio.run_coroutine_threadsafe(self._delete_catalog_item(item_id), self.loop)
        future.add_done_callback(lambda f: self._on_modify_complete(f, 'catalog_item_deleted'))

    # Асинхронные методы для модификации данных
    async def _add_collector(self, data):
        query = """
            INSERT INTO collector (surname, name, patronymic, email, id_country, description)
            VALUES (%s, %s, %s, %s, %s, %s)
        """
        params = (data['surname'], data['name'], data['patronymic'], data['email'], 
                 data['id_country'], data['description'])
        return await self._execute_query(query, params)

    async def _update_collector(self, collector_id, data):
        query = """
            UPDATE collector 
            SET surname=%s, name=%s, patronymic=%s, email=%s, id_country=%s, description=%s
            WHERE id=%s
        """
        params = (data['surname'], data['name'], data['patronymic'], data['email'],
                 data['id_country'], data['description'], collector_id)
        return await self._execute_query(query, params)

    async def _delete_collector(self, collector_id):
        """Удаление коллекционера с учетом внешних ключей через транзакцию"""
        conn = None
        try:
            conn = await aiomysql.connect(
                host=self.db_config['host'],
                user=self.db_config['user'],
                password=self.db_config['password'],
                db=self.db_config['db'],
                autocommit=False
            )
            
            async with conn.cursor(aiomysql.DictCursor) as cursor:
                try:
                    # Сначала находим все коллекции этого коллекционера
                    find_collections_query = "SELECT id FROM collection WHERE author = %s"
                    await cursor.execute(find_collections_query, (collector_id,))
                    collections = await cursor.fetchall()
                    
                    # Для каждой коллекции удаляем зависимые записи в collection_item
                    for collection in collections:
                        collection_id = collection['id']
                        delete_items_query = "DELETE FROM collection_item WHERE id_collection = %s"
                        await cursor.execute(delete_items_query, (collection_id,))
                    
                    # Теперь удаляем все коллекции коллекционера
                    delete_collections_query = "DELETE FROM collection WHERE author = %s"
                    await cursor.execute(delete_collections_query, (collector_id,))
                    
                    # Наконец, удаляем самого коллекционера
                    delete_collector_query = "DELETE FROM collector WHERE id = %s"
                    await cursor.execute(delete_collector_query, (collector_id,))
                    
                    await conn.commit()
                    logger.info(f"Коллекционер {collector_id} и все его коллекции успешно удалены")
                    return True
                    
                except Exception as e:
                    await conn.rollback()
                    logger.error(f"Ошибка в транзакции удаления коллекционера {collector_id}: {e}")
                    raise
                    
        except Exception as e:
            logger.error(f"Ошибка подключения или удаления коллекционера {collector_id}: {e}")
            raise
            
        finally:
            if conn:
                conn.close()

    async def _add_collection(self, data):
        try:
            query = """
                INSERT INTO collection (name, author, id_collection_type, date_of_creation, number_of_items, description)
                VALUES (%s, %s, %s, %s, %s, %s)
            """
            id_collection_type = data['id_collection_type'] if data['id_collection_type'] else 1
            params = (data['name'], data['author'], id_collection_type,
                     data['date_of_creation'], data['number_of_items'], data['description'])
            return await self._execute_query(query, params)
        except Exception as e:
            logger.error(f"Ошибка добавления коллекции: {e}")
            raise

    async def _update_collection(self, collection_id, data):
        query = """
            UPDATE collection 
            SET name=%s, author=%s, id_collection_type=%s, date_of_creation=%s, number_of_items=%s, description=%s
            WHERE id=%s
        """
        params = (data['name'], data['author'], data['id_collection_type'],
                 data['date_of_creation'], data['number_of_items'], data['description'], collection_id)
        return await self._execute_query(query, params)

    async def _delete_collection(self, collection_id):
        """Удаление коллекции с учетом внешних ключей через транзакцию"""
        conn = None
        try:
            conn = await aiomysql.connect(
                host=self.db_config['host'],
                user=self.db_config['user'],
                password=self.db_config['password'],
                db=self.db_config['db'],
                autocommit=False
            )
            
            async with conn.cursor(aiomysql.DictCursor) as cursor:
                try:
                    # Проверяем, есть ли зависимые записи в collection_item
                    check_query = """
                        SELECT COUNT(*) as count 
                        FROM collection_item 
                        WHERE id_collection = %s
                    """
                    await cursor.execute(check_query, (collection_id,))
                    result = await cursor.fetchone()
                    
                    if result and result['count'] > 0:
                        # Удаляем зависимые записи
                        delete_items_query = "DELETE FROM collection_item WHERE id_collection = %s"
                        await cursor.execute(delete_items_query, (collection_id,))
                        logger.info(f"Удалено {result['count']} предметов из коллекции {collection_id}")
                    
                    # Удаляем саму коллекцию
                    delete_collection_query = "DELETE FROM collection WHERE id = %s"
                    await cursor.execute(delete_collection_query, (collection_id,))
                    
                    await conn.commit()
                    logger.info(f"Коллекция {collection_id} успешно удалена")
                    return True
                    
                except Exception as e:
                    await conn.rollback()
                    logger.error(f"Ошибка в транзакции удаления коллекции {collection_id}: {e}")
                    raise
                    
        except Exception as e:
            logger.error(f"Ошибка подключения или удаления коллекции {collection_id}: {e}")
            raise
            
        finally:
            if conn:
                conn.close()

    async def _add_catalog_item(self, data):
        try:
            query = """
                INSERT INTO catalog (name, rare, id_country, release_date, description)
                VALUES (%s, %s, %s, %s, %s)
            """
            id_country = data['id_country'] if data['id_country'] else 1
            params = (data['name'], data['rare'], id_country,
                     data['release_date'], data['description'])
            return await self._execute_query(query, params)
        except Exception as e:
            logger.error(f"Ошибка добавления предмета каталога: {e}")
            raise

    async def _update_catalog_item(self, item_id, data):
        query = """
            UPDATE catalog 
            SET name=%s, rare=%s, id_country=%s, release_date=%s, description=%s
            WHERE id=%s
        """
        params = (data['name'], data['rare'], data['id_country'],
                 data['release_date'], data['description'], item_id)
        return await self._execute_query(query, params)

    async def _delete_catalog_item(self, item_id):
        """Удаление предмета каталога с учетом внешних ключей через транзакцию"""
        conn = None
        try:
            conn = await aiomysql.connect(
                host=self.db_config['host'],
                user=self.db_config['user'],
                password=self.db_config['password'],
                db=self.db_config['db'],
                autocommit=False
            )
            
            async with conn.cursor(aiomysql.DictCursor) as cursor:
                try:
                    # Проверяем, есть ли зависимые записи
                    check_query = """
                        SELECT COUNT(*) as count 
                        FROM collection_item 
                        WHERE id_catalog = %s
                    """
                    await cursor.execute(check_query, (item_id,))
                    result = await cursor.fetchone()
                    
                    if result and result['count'] > 0:
                        # Если есть зависимые записи, удаляем их сначала
                        delete_links_query = "DELETE FROM collection_item WHERE id_catalog = %s"
                        await cursor.execute(delete_links_query, (item_id,))
                        logger.info(f"Удалено {result['count']} зависимых записей из collection_item")
                    
                    # Теперь удаляем сам предмет из каталога
                    delete_item_query = "DELETE FROM catalog WHERE id = %s"
                    await cursor.execute(delete_item_query, (item_id,))
                    
                    await conn.commit()
                    logger.info(f"Предмет каталога {item_id} успешно удален")
                    return True
                    
                except Exception as e:
                    await conn.rollback()
                    logger.error(f"Ошибка в транзакции удаления предмета {item_id}: {e}")
                    raise
                    
        except Exception as e:
            logger.error(f"Ошибка подключения или удаления предмета каталога {item_id}: {e}")
            raise
            
        finally:
            if conn:
                conn.close()

    def _on_data_loaded(self, future, data_type):
        try:
            result = future.result()
            self.data_loaded.emit(data_type, result)
        except Exception as e:
            self.error_occurred.emit(f"Ошибка загрузки {data_type}: {e}")

    def _on_modify_complete(self, future, operation_type):
        try:
            result = future.result()
            self.data_loaded.emit(operation_type, result)
        except Exception as e:
            self.error_occurred.emit(f"Ошибка операции {operation_type}: {e}")

    def stop(self):
        """Остановка event loop"""
        if self.loop and self.loop.is_running():
            try:
                close_future = asyncio.run_coroutine_threadsafe(self._close(), self.loop)
                close_future.result(timeout=5)
            except Exception as e:
                logger.warning(f"Ошибка при закрытии соединений: {e}")
            finally:
                self.loop.call_soon_threadsafe(self.loop.stop)
                logger.info("Event loop остановлен")

    async def _close(self):
        """Закрытие подключения"""
        if self.pool:
            self.pool.close()
            await self.pool.wait_closed()
            logger.info("Соединение с базой данных закрыто")
