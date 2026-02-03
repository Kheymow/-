import asyncio
import json
import logging
import sys
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command, StateFilter
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
import os
import os
from dotenv import load_dotenv
# Импортируем базу знаний. 
# Если файла нет, используем минимальный словарь, чтобы код не падал.
try:
    from knowledge_base import knowledge
except ImportError:
    knowledge = {
        "cpu": {"title": "Процессор", "text": "Процессор — это сердце компьютера..."},
        "gpu": {"title": "Видеокарта", "text": "Видеокарта - отвечает за графику..."},
    }

load_dotenv()  # Загружает переменные из .env
TOKEN = os.getenv("BOT_TOKEN")

# Настройка логирования
logging.basicConfig(level=logging.INFO)

bot = Bot(token=TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

# --- FSM: Определяем состояния ---
class BuildStates(StatesGroup):
    waiting_for_budget = State()  # Состояние ожидания ввода суммы

# --- Загрузка сборок ---
def load_builds():
    """Загружает базу сборок из builds.json, обрабатывая возможные ошибки."""
    try:
        with open("builds.json", "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        # Возвращаем пустой список, если файл не найден или некорректен
        return []

builds = load_builds()

# --- Команда /start ---
@dp.message(Command("start"))
async def cmd_start(message: types.Message, state: FSMContext):
    """Обрабатывает команду /start и выводит главное меню."""
    await state.clear()
    
    builder = InlineKeyboardBuilder()
    builder.button(text="💻 Подобрать сборку", callback_data="start_build")
    builder.button(text="🧠 База знаний", callback_data="knowledge_menu")
    builder.adjust(1) 

    await message.answer(
        "Привет! 👋 Я бот, который подбирает ПК по бюджету.\nВыбери действие ниже:",
        reply_markup=builder.as_markup()
    )

# --- Начало подбора (кнопка) ---
@dp.callback_query(F.data == "start_build")
async def start_build(callback: types.CallbackQuery, state: FSMContext):
    """Переводит пользователя в режим ожидания бюджета."""
    await callback.message.edit_text("Введи свой бюджет (в рублях, минимум 45000₽):")
    await state.set_state(BuildStates.waiting_for_budget)

# --- Обработка бюджета (работает только в состоянии waiting_for_budget) ---
@dp.message(BuildStates.waiting_for_budget)
async def handle_budget(message: types.Message, state: FSMContext):
    """Обрабатывает введенный бюджет, ищет сборку и сбрасывает состояние."""
    try:
        # Очищаем текст от пробелов и знаков валюты
        clean_text = message.text.replace(" ", "").replace("₽", "")
        budget = int(clean_text)

        # Клавиатура для возврата в меню
        builder = InlineKeyboardBuilder()
        builder.button(text="🔙 В главное меню", callback_data="back_to_start")
        markup = builder.as_markup()

        if budget < 45000:
            await message.answer("Бюджет слишком мал. Минимальная сумма: 45 000 ₽. Попробуй еще раз.", reply_markup=markup)
            return

        # Логика поиска: ищем самую дорогую сборку, которая влезает в бюджет
        suitable = [b for b in builds if b.get("price", 0) <= budget]
        
        if suitable:
            build = sorted(suitable, key=lambda x: x.get("price", 0), reverse=True)[0]
            
            components_list = [f"- {key.upper()}: {value}" for key, value in build.items() if key not in ["name", "price"]] # <--- ИСПРАВЛЕНО: build.items()
            components_text = "\n".join(components_list)
            
            text = (
            f"💸 <b>Подходящая сборка:</b>\n"
            f"Название: {build.get('name', 'Нет имени')}\n"
            f"Цена: {build.get('price', 'Нет цены')} ₽\n\n"
            f"🔧 <b>Комплектующие:</b>\n{components_text}\n\n"
            "Если возникли вопросы, обратитесь в поддержку: @K_heymow"
            ) 
        else:
            text = "😔 К сожалению, на данный момент нет подходящих сборок под этот бюджет."# Отправляем сообщение С КЛАВИАТУРОЙ
        await message.answer(text, parse_mode="HTML", reply_markup=markup)
        await state.clear() # Сбрасываем состояние
        
    except ValueError:
        # В случае ошибки ввода
        builder = InlineKeyboardBuilder()
        builder.button(text="🔙 В главное меню", callback_data="back_to_start")
        await message.answer("❗️ Пожалуйста, введи корректное число.", reply_markup=builder.as_markup())


# --- Меню Базы знаний ---
@dp.callback_query(F.data == "knowledge_menu")
async def show_knowledge_base(callback: types.CallbackQuery):
    """Показывает главное меню Базы знаний."""
    builder = InlineKeyboardBuilder()
    
    # Главные темы
    builder.button(text="Процессор (CPU)", callback_data="cpu")
    builder.button(text="Видеокарта (GPU)", callback_data="gpu")
    builder.button(text="Материнская плата (Motherboard)", callback_data="motherboard")
    builder.button(text="Оперативная память (RAM)",callback_data="ram")
    builder.button(text="Охлаждение CPU",callback_data="cooling") 
    builder.button(text="Блок питания (PSU)",callback_data="psu")
    builder.button(text="Накопители",callback_data="storage")
    builder.button(text="Корпус (Case)", callback_data="case")
    builder.button(text="🔙 В меню", callback_data="back_to_start")
    
    builder.adjust(1)
    await callback.message.edit_text("📚 Выберите тему:", reply_markup=builder.as_markup())

# --- ХЕНДЛЕР: СУБ-МЕНЮ ДЛЯ CPU (Должен быть ДО универсального!) ---
@dp.callback_query(F.data == "cpu")
async def show_cpu_submenu(callback: types.CallbackQuery):
    """Показывает основную информацию о CPU и кнопки для перехода к подразделам."""
    # 1. Получаем основной текст про CPU из базы знаний
    cpu_data = knowledge.get("cpu", {"title": "Процессор", "text": "Нет данных."})
    
    # 2. Формируем текст: Заголовок, основной текст, и призыв к выбору
    main_text = (
        f"<b>{cpu_data['title']}</b>\n\n"
        f"{cpu_data['text']}\n\n"
        f"--- \n\n"
        f"📚 Выберите дополнительный раздел для изучения:"
    )

    builder = InlineKeyboardBuilder()
    
    # Кнопки для подтем
    builder.button(text="Что такое TDP", callback_data="tdp_info")
    builder.button(text="Как выбрать процессор", callback_data="cpu_choice")
    
    # Кнопка назад ведет в главное меню базы знаний
    builder.button(text="🔙 К темам", callback_data='knowledge_menu') 
    
    builder.adjust(1)
    # 3. Редактируем сообщение, показывая полный текст и кнопки
    await callback.message.edit_text(
        main_text, 
        reply_markup=builder.as_markup(),
        parse_mode="HTML"
    )


# --- Показ статьи из базы знаний (УНИВЕРСАЛЬНЫЙ) ---
@dp.callback_query(lambda c: c.data in knowledge)
async def knowledge_callback(callback: types.CallbackQuery):
    """Универсальный обработчик для показа любой статьи из knowledge."""
    topic_key = callback.data
    topic_data = knowledge[topic_key]
    
    builder = InlineKeyboardBuilder()
    
    # Логика кнопки "Назад" в зависимости от того, откуда пришел пользователь
    if topic_key in ["tdp_info", "cpu_choice"]:
         # Возвращаем на страницу CPU
         builder.button(text="🔙 К подтемам CPU", callback_data="cpu")
    else:
         # Возвращаем в главное меню Базы знаний
         builder.button(text="🔙 К темам", callback_data="knowledge_menu")
    
    text_response = f"<b>{topic_data['title']}</b>\n\n{topic_data['text']}"
    await callback.message.edit_text(text_response, parse_mode="HTML", reply_markup=builder.as_markup())

# --- Кнопка "Назад" (Возврат в Главное меню) ---
@dp.callback_query(F.data == "back_to_start")
async def back_to_start(callback: types.CallbackQuery, state: FSMContext):
    """Возвращает пользователя в самое главное меню."""
    await state.clear()
    builder = InlineKeyboardBuilder()
    builder.button(text="💻 Подобрать сборку", callback_data="start_build")
    builder.button(text="🧠 База знаний", callback_data="knowledge_menu")
    builder.adjust(1)
    await callback.message.edit_text("Главное меню:", reply_markup=builder.as_markup())


# --- Запуск ---
async def main():
    """Главная функция запуска бота."""
    print("Бот запущен...")
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)
if __name__ == "__main__":
    if TOKEN == "" or TOKEN == "_":
        print("ОШИБКА: Вы не вставили токен бота в переменную TOKEN!")
    else:
         try:
            asyncio.run(main())
         except KeyboardInterrupt:
            print("Бот остановлен.")