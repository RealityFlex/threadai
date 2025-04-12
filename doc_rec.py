import ollama
from PIL import Image
import json
import os
import tempfile
from fastapi import APIRouter, UploadFile, File, HTTPException, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from app.db.database import get_db
from app.models.models import User, DocumentEvaluation
import math
import time
from typing import Optional
from dotenv import load_dotenv

# Загружаем переменные окружения
load_dotenv()

# Получаем URL API Ollama из переменных окружения или используем значение по умолчанию
OLLAMA_API_URL = os.getenv("OLLAMA_API_URL", "http://localhost:11434")

# Настраиваем клиент Ollama
ollama.set_host(OLLAMA_API_URL)

router = APIRouter()

def evaluate_document(image_path):
    """
    Оценивает документ по фотографии.
    
    Args:
        image_path (str): Путь к изображению документа
        
    Returns:
        dict: Словарь с оценкой и описанием документа
    """
    # Проверяем существование файла
    if not os.path.exists(image_path):
        return {"error": "Файл не найден"}
    
    try:
        # Логируем адрес API для отладки
        print(f"Отправляем запрос к Ollama API по адресу: {OLLAMA_API_URL}")
        
        # Отправляем запрос к модели
        res = ollama.chat(
            model="gemma3",
            messages=[
                {
                    'role': 'user',
                    'content': '''Проанализируй документ на изображении и верни ответ в формате JSON:
                    {
                        "type": "тип документа (сертификат/диплом/грамота/благодарность)",
                        "score": "оценка от 0 до 10",
                        "recipient": "кому выдан документ",
                        "reason": "за что выдан документ",
                        "issuer": "кто выдал документ",
                        "date": "дата выдачи",
                        "details": "дополнительные детали"
                    }
                    Оценивай документы по следующей шкале:
                    - Сертификат участника: 2 балла
                    - Грамота/благодарность: 3 балла
                    - Диплом 3 степени: 5 баллов
                    - Диплом 2 степени: 7 баллов
                    - Диплом 1 степени: 10 баллов
                    - Диплом с отличием: 10 баллов
                    ''',
                    'images': [image_path]
                }
            ]
        )
        
        # Парсим ответ
        try:
            result = json.loads(res['message']['content'].split('```json')[1].split('```')[0])
            return result
        except json.JSONDecodeError:
            print(res['message']['content'])
            return {"error": "Не удалось распознать ответ модели"}
            
    except Exception as e:
        return {"error": f"Ошибка при обработке изображения: {str(e)}"}

def process_documents(directory):
    """
    Обрабатывает все документы в указанной директории.
    
    Args:
        directory (str): Путь к директории с документами
        
    Returns:
        list: Список результатов оценки документов
    """
    results = []
    supported_extensions = ('.jpg', '.jpeg', '.png')
    
    # Проверяем существование директории
    if not os.path.exists(directory):
        return [{"error": "Директория не найдена"}]
    
    # Обрабатываем все изображения в директории
    for filename in os.listdir(directory):
        if filename.lower().endswith(supported_extensions):
            image_path = os.path.join(directory, filename)
            result = evaluate_document(image_path)
            result['filename'] = filename
            results.append(result)
    
    return results

def calculate_rating(db: Session, user_id: int, new_score: int) -> float:
    """
    Вычисляет новый рейтинг пользователя на основе оценки загруженного документа.
    
    Формула рейтинга:
    - Рейтинг увеличивается нелинейно с каждым новым документом
    - Более высокий score даёт больший прирост рейтинга
    - Учитывается общее количество загруженных документов
    - Более значимые документы дают больший вклад в рейтинг
    
    Args:
        db (Session): Сессия базы данных
        user_id (int): ID пользователя
        new_score (int): Оценка нового документа
        
    Returns:
        float: Новый рейтинг пользователя
    """
    # Получаем текущий рейтинг пользователя
    user = db.query(User).filter(User.user_id == user_id).first()
    if not user:
        return 0.0
    
    current_rating = user.rating
    
    # Получаем количество документов, которые пользователь уже загрузил
    doc_count = db.query(DocumentEvaluation).filter(DocumentEvaluation.user_id == user_id).count()
    
    # Базовый прирост рейтинга сильно зависит от оценки документа
    # Оценка 10 даёт максимальный прирост, оценка меньше 5 даёт малый прирост
    # Нелинейная шкала, которая отдает предпочтение высоким оценкам
    if new_score >= 8:  # Дипломы 1-2 степени и с отличием
        base_increment = 1.0 + (new_score - 8) * 0.5  # От 1.0 до 2.0
    elif new_score >= 5:  # Диплом 3 степени
        base_increment = 0.5 + (new_score - 5) * 0.167  # От 0.5 до ~1.0
    else:  # Сертификаты участника, грамоты
        base_increment = 0.1 + (new_score / 5) * 0.4  # От 0.1 до ~0.5
    
    # Множитель, учитывающий количество документов 
    # Первые несколько документов дают больший эффект
    if doc_count < 5:
        docs_factor = 1.0 - (doc_count * 0.1)  # От 1.0 до 0.6
    else:
        docs_factor = 0.5  # Стабилизируется на уровне 0.5
    
    # Вычисляем итоговое изменение рейтинга
    rating_change = base_increment * docs_factor
    
    # Вычисляем новый рейтинг
    new_rating = current_rating + rating_change
    
    # Округляем до одного знака после запятой
    new_rating = round(new_rating, 1)
    
    return new_rating

def save_document_evaluation(db: Session, user_id: int, evaluation: dict):
    """
    Сохраняет результат оценки документа в базу данных.
    
    Args:
        db (Session): Сессия базы данных
        user_id (int): ID пользователя
        evaluation (dict): Результат оценки документа
    
    Returns:
        DocumentEvaluation: Созданная запись в базе данных
    """
    # Преобразуем score из строки в целое число
    try:
        score = int(evaluation.get("score", "0"))
    except (ValueError, TypeError):
        score = 0
    
    # Создаем запись об оценке документа
    doc_eval = DocumentEvaluation(
        user_id=user_id,
        document_type=evaluation.get("type", "неизвестно"),
        score=score,
        recipient=evaluation.get("recipient", "неизвестно"),
        reason=evaluation.get("reason", "неизвестно"),
        issuer=evaluation.get("issuer", "неизвестно"),
        document_date=evaluation.get("date", "неизвестно"),
        details=evaluation.get("details", ""),
        filename=evaluation.get("filename", "")
    )
    
    db.add(doc_eval)
    db.commit()
    db.refresh(doc_eval)
    
    return doc_eval

@router.post("/api/document/evaluate", tags=["Документы"])
async def evaluate_document_api(
    file: UploadFile = File(...),
    user_id: Optional[int] = None,
    db: Session = Depends(get_db)
):
    """
    Оценивает значимость диплома или сертификата по загруженной фотографии
    и обновляет рейтинг пользователя.
    
    Args:
        file: Загруженный файл изображения (JPEG, PNG)
        user_id: ID пользователя, если не указан - не обновляет рейтинг
        db: Сессия базы данных
        
    Returns:
        JSONResponse: Результат оценки документа и обновленный рейтинг пользователя
    """
    # Проверяем тип файла
    if not file.filename.lower().endswith(('.jpg', '.jpeg', '.png')):
        raise HTTPException(
            status_code=400, 
            detail="Поддерживаются только изображения форматов JPG, JPEG и PNG"
        )
    
    # Создаем временный файл для сохранения загруженного изображения
    with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(file.filename)[1]) as temp_file:
        temp_file_path = temp_file.name
        # Читаем содержимое загруженного файла и записываем во временный файл
        content = await file.read()
        temp_file.write(content)
    
    try:
        # Оцениваем документ
        result = evaluate_document(temp_file_path)
        
        # Добавляем имя файла в результат
        result['filename'] = file.filename
        
        # Если указан ID пользователя, обновляем рейтинг
        if user_id is not None:
            # Проверяем существование пользователя
            user = db.query(User).filter(User.user_id == user_id).first()
            if not user:
                raise HTTPException(status_code=404, detail=f"Пользователь с ID {user_id} не найден")
            
            # Преобразуем score в целое число для расчета рейтинга
            try:
                # Проверяем, является ли score строкой или числом
                if isinstance(result.get("score"), str):
                    score = int(result.get("score", "0"))
                else:
                    score = int(result.get("score", 0))
            except (ValueError, TypeError):
                score = 0
            
            old_rating = user.rating
            
            # Пытаемся сохранить документ в базу данных
            try:
                doc_eval = save_document_evaluation(db, user_id, result)
                result['document_saved'] = True
            except Exception as e:
                # Если не удалось сохранить документ, все равно обновляем рейтинг
                db.rollback()  # Откатываем транзакцию в случае ошибки
                result['document_saved'] = False
                result['document_error'] = str(e)
                print(f"Ошибка при сохранении документа: {str(e)}")
            
            # Вычисляем и обновляем рейтинг пользователя в любом случае
            try:
                new_rating = calculate_rating(db, user_id, score)
                
                # Обновляем рейтинг пользователя
                user.rating = new_rating
                db.commit()
                
                # Добавляем информацию о рейтинге в результат
                result['previous_rating'] = old_rating
                result['new_rating'] = new_rating
                result['rating_change'] = new_rating - old_rating
                result['rating_updated'] = True
                
                print(f"Пользователь ID {user_id}: обновлен рейтинг с {old_rating} до {new_rating}")
            except Exception as e:
                db.rollback()
                result['rating_updated'] = False
                result['rating_error'] = str(e)
                print(f"Ошибка при обновлении рейтинга: {str(e)}")
        
        # Возвращаем результат оценки документа
        return JSONResponse(content=result)
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Ошибка при обработке документа: {str(e)}"
        )
    finally:
        # Удаляем временный файл
        if os.path.exists(temp_file_path):
            os.unlink(temp_file_path)

# Пример использования
if __name__ == "__main__":
    # Оценка одного документа
    result = evaluate_document("./diploms/hakatom_0.png")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    
    # Обработка всех документов в директории
    # results = process_documents("./diploms")
    # print(json.dumps(results, ensure_ascii=False, indent=2))