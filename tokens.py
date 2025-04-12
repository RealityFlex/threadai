from natasha import (
    Segmenter,
    MorphVocab,
    NewsEmbedding,
    NewsMorphTagger,
    Doc
)
from sklearn.feature_extraction.text import TfidfVectorizer
from collections import Counter
import numpy as np

# Инициализация компонентов Natasha
segmenter = Segmenter()
morph_vocab = MorphVocab()
emb = NewsEmbedding()
morph_tagger = NewsMorphTagger(emb)

def extract_topic_tokens(text, max_tokens=10):
    """
    Извлекает тематические токены из текста.
    
    Args:
        text (str): Исходный текст
        max_tokens (int): Максимальное количество возвращаемых токенов
        
    Returns:
        list: Список тематических токенов
    """
    # Создаем документ и применяем морфологический анализ
    doc = Doc(text)
    doc.segment(segmenter)
    doc.tag_morph(morph_tagger)
    
    # Извлекаем существительные и прилагательные
    tokens = []
    for token in doc.tokens:
        if token.pos in ['NOUN', 'ADJ']:  # существительные и прилагательные
            token.lemmatize(morph_vocab)
            tokens.append(token.lemma.lower())
    
    # Использование TF-IDF для определения важности слов
    if tokens:
        vectorizer = TfidfVectorizer(max_features=1000)
        try:
            tfidf_matrix = vectorizer.fit_transform([' '.join(tokens)])
            feature_names = vectorizer.get_feature_names_out()
            
            # Получение весов TF-IDF
            tfidf_scores = tfidf_matrix.toarray()[0]
            
            # Сортировка токенов по важности
            sorted_indices = np.argsort(tfidf_scores)[::-1]
            top_tokens = [feature_names[i] for i in sorted_indices[:max_tokens]]
            
            return top_tokens
        except ValueError:
            # Если не удалось создать матрицу TF-IDF, возвращаем самые частые токены
            return [token for token, _ in Counter(tokens).most_common(max_tokens)]
    
    return []

def process_post(posts):
    """
    Обрабатывает список постов и извлекает тематические токены для каждого.
    
    Args:
        posts (list): Список текстов постов
        
    Returns:
        dict: Словарь, где ключи - индексы постов, значения - списки токенов
    """
    tokens = {}
    for i, post in enumerate(posts):
        tokens = extract_topic_tokens(post)
    return tokens


posts = [
    "Сегодня я посетил интересную выставку современного искусства"
]

result = process_post(posts)
print(result)