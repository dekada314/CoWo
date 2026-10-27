"""
Агент-аналитик (Analyst Agent) — РЕАЛЬНАЯ ВЕРСИЯ
Тестовый запуск локальной LLM через Ollama.
"""

from pydantic import BaseModel, Field
from typing import List
from langchain_ollama import ChatOllama
from langchain_core.prompts import ChatPromptTemplate

# 1. Строгая схема Карточки Знания
class KnowledgeCard(BaseModel):
    summary: str = Field(description="Краткое содержание документа (2-3 предложения)")
    theses: List[str] = Field(description="Ключевые тезисы документа (список строк)")
    concepts: List[str] = Field(description="Список извлеченных концепций (например, ['Chunking', 'Vector DB'])")
    domain: str = Field(description="Домен, к которому относится документ (например, 'RAG')")
    community: str = Field(description="Сообщество верхнего уровня (например, 'Программирование')")

# 2. Промпт для нейросети
ANALYST_PROMPT = """Ты — эксперт-аналитик. Проанализируй текст и извлеки карточку знания.
Верни ТОЛЬКО валидный JSON в формате KnowledgeCard, без markdown-тегов и лишних слов.

Текст документа:
{document_text}
"""

# 3. Главная функция
async def analyze_document_node(document_text: str) -> KnowledgeCard:
    print(f" Агент-аналитик: начинаю обработку ({len(document_text)} символов)...")
    
    # Инициализируем локальную нейросеть
    llm = ChatOllama(
        model="qwen2.5:3b",
        temperature=0.2,
        format="json",  # Заставляем Ollama возвращать чистый JSON
    )
    
    # Собираем цепочку: Промпт -> LLM -> Pydantic модель
    prompt = ChatPromptTemplate.from_template(ANALYST_PROMPT)
    chain = prompt | llm.with_structured_output(KnowledgeCard)
    
    print("🧠 Отправляю запрос в LLM (это может занять 10-20 секунд)...")
    
    try:
        # Вызываем нейросеть
        result = await chain.ainvoke({"document_text": document_text})
        print("✅ Агент-аналитик: успешно сформировал KnowledgeCard!")
        return result
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        raise

# 4. Тестовый запуск
if __name__ == "__main__":
    import asyncio
    
    async def main():
        test_text = """
        Документ описывает современные подходы к обработке больших языковых моделей.
        Рассматривается метод RAG (Retrieval-Augmented Generation), который позволяет 
        дополнять ответы модели актуальной информацией из внешней базы знаний.
        Ключевые компоненты: векторная база данных, эмбеддинги, чанкинг документов,
        реранкинг результатов поиска. Метод позволяет снизить галлюцинации модели.
        """
        
        result = await analyze_document_node(test_text)
        print("\n Результат работы агента:")
        print(result.model_dump_json(indent=2, ensure_ascii=False))

    asyncio.run(main())