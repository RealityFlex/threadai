import time
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from app.utils.logger import log_request, log_response

class LoggingMiddleware(BaseHTTPMiddleware):
    """Middleware для логирования запросов и ответов"""
    
    async def dispatch(self, request: Request, call_next):
        # Логирование запроса
        log_request(request)
        
        # Измерение времени выполнения запроса
        start_time = time.time()
        
        # Обработка запроса
        response = await call_next(request)
        
        # Вычисление времени выполнения
        execution_time = time.time() - start_time
        
        # Логирование ответа
        log_response(request, response, execution_time)
        
        return response 