from fastapi import Request, status
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError, IntegrityError
from pydantic import ValidationError
from app.utils.logger import log_error

async def sqlalchemy_exception_handler(request: Request, exc: SQLAlchemyError):
    """Обработчик исключений SQLAlchemy"""
    error_id = log_error(request, exc)
    
    if isinstance(exc, IntegrityError):
        # Обработка нарушения целостности данных (например, duplicate key, not null constraint)
        constraint_error = str(exc.orig)
        detail = "Ошибка целостности данных в базе данных"
        
        if "violates not-null constraint" in constraint_error:
            detail = "Отсутствует обязательное поле"
        elif "violates unique constraint" in constraint_error:
            detail = "Запись с такими данными уже существует"
        elif "violates foreign key constraint" in constraint_error:
            # Определяем, какое именно внешнее ограничение нарушено
            if "post_type_id" in constraint_error:
                detail = "Указан несуществующий тип поста"
            elif "user_id" in constraint_error:
                detail = "Указан несуществующий пользователь"
            elif "tag_type_id" in constraint_error:
                detail = "Указан несуществующий тип тега"
            else:
                detail = "Нарушение ссылочной целостности"
            
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={
                "detail": detail,
                "error_id": error_id,
                "error_type": "database_constraint",
                "error_message": str(exc),
                "help": "Проверьте корректность указанных ID. Используйте эндпоинт /system/init-db для инициализации базы и /system/create-test-user для создания тестового пользователя."
            }
        )
    else:
        # Общая ошибка базы данных
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "detail": "Ошибка базы данных",
                "error_id": error_id,
                "error_type": "database_error",
                "error_message": str(exc)
            }
        )

async def validation_exception_handler(request: Request, exc: ValidationError):
    """Обработчик ошибок валидации входных данных"""
    error_id = log_error(request, exc)
    
    # Формируем информативное сообщение об ошибке
    errors = exc.errors()
    detail = "Ошибка валидации данных"
    
    # Если ошибок немного, сделаем сообщение более понятным
    if len(errors) == 1:
        error = errors[0]
        loc = ".".join([str(l) for l in error.get("loc", [])])
        msg = error.get("msg", "")
        
        if "post_type_id" in loc:
            detail = f"Неверный тип поста: {msg}"
        elif "user_id" in loc:
            detail = f"Неверный ID пользователя: {msg}"
        elif "child_id" in loc:
            detail = f"Неверный ID родительского поста: {msg}"
        else:
            detail = f"Ошибка в поле {loc}: {msg}"
    
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "detail": detail,
            "error_id": error_id,
            "error_type": "validation_error",
            "errors": errors,
            "help": "Проверьте корректность всех полей запроса согласно документации API."
        }
    )

async def general_exception_handler(request: Request, exc: Exception):
    """Обработчик всех остальных исключений"""
    error_id = log_error(request, exc)
    
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "detail": "Внутренняя ошибка сервера",
            "error_id": error_id,
            "error_type": "server_error",
            "error_message": str(exc)
        }
    ) 