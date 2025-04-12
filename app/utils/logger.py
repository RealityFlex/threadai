import logging
import os
import json
from datetime import datetime
from fastapi import Request
import traceback

# Создаем директорию для логов, если она не существует
log_dir = "logs"
if not os.path.exists(log_dir):
    os.makedirs(log_dir)

# Настройка логгера для приложения
app_logger = logging.getLogger("app")
app_logger.setLevel(logging.INFO)

# Обработчик для записи в файл
file_handler = logging.FileHandler(f"{log_dir}/app.log")
file_handler.setLevel(logging.INFO)

# Создаем отдельный логгер для ошибок
error_logger = logging.getLogger("errors")
error_logger.setLevel(logging.ERROR)

# Обработчик для записи ошибок в отдельный файл
error_file_handler = logging.FileHandler(f"{log_dir}/errors.log")
error_file_handler.setLevel(logging.ERROR)

# Форматирование логов
log_format = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
file_handler.setFormatter(log_format)
error_file_handler.setFormatter(log_format)

# Добавляем обработчики к логгерам
app_logger.addHandler(file_handler)
error_logger.addHandler(error_file_handler)

# Функции для логирования
def log_request(request: Request):
    """Логирование входящего запроса"""
    app_logger.info(f"Request: {request.method} {request.url.path}")

def log_response(request: Request, response, execution_time: float):
    """Логирование ответа на запрос"""
    app_logger.info(f"Response: {request.method} {request.url.path} - Status: {response.status_code} - Time: {execution_time:.4f}s")

def log_error(request: Request, exc):
    """Подробное логирование ошибки"""
    error_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    client_host = request.client.host if request.client else "Unknown"
    
    error_info = {
        "timestamp": error_time,
        "client_ip": client_host,
        "method": request.method,
        "url": str(request.url),
        "headers": dict(request.headers),
        "error_type": str(type(exc).__name__),
        "error_message": str(exc),
        "traceback": traceback.format_exc()
    }
    
    # Логируем в файл
    error_logger.error(f"Error: {request.method} {request.url.path} - {type(exc).__name__}: {str(exc)}")
    error_logger.error(traceback.format_exc())
    
    # Также записываем подробную информацию в JSON
    error_id = datetime.now().strftime("%Y%m%d%H%M%S")
    with open(f"{log_dir}/error_{error_id}.json", "w") as error_file:
        json.dump(error_info, error_file, indent=4, default=str)
    
    return error_id 