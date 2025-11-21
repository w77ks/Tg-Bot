import logging
import random
import time
import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Токен бота
TOKEN = "8546826064:AAFN519DhqO3Gm1oQOwrevshAH8JrGCWV94"

# Хранилище времени последнего сигнала для пользователей
user_cooldowns = {}

# Хранилище доступа пользователей {user_id: access_until_timestamp}
user_access = {}

# Флаг технических работ
technical_works = False

# Админ пользователи
ADMIN_USERNAMES = ["Xanezy", "xanezy"]  # Юзернеймы админа
ADMIN_USER_IDS = [8223197188]  # Юзер айди админа

def is_admin(user):
    """Проверка является ли пользователь админом"""
    return user.id in ADMIN_USER_IDS or (user.username and user.username.lower() in [name.lower() for name in ADMIN_USERNAMES])

def has_access(user_id):
    """Проверка есть ли у пользователя доступ"""
    if user_id not in user_access:
        return False
    
    access_until = user_access[user_id]
    if time.time() > access_until:
        # Время доступа истекло
        del user_access[user_id]
        return False
    
    return True

def grant_access(user_id, duration_minutes):
    """Выдать доступ пользователю"""
    access_until = time.time() + (duration_minutes * 60)
    user_access[user_id] = access_until
    return access_until

def generate_signal():
    """Генерация сигнала с нужными параметрами"""
    # Основной коэффициент 1.0-1.5
    main_coef = round(random.uniform(1.0, 1.5), 2)
    
    # Точность 85-95% (если тех работы - меньше точность)
    if technical_works:
        accuracy = random.randint(70, 85)  # Пониженная точность при тех работах
    else:
        accuracy = random.randint(85, 95)
    
    # Коэффициент для закрытия (немного ниже основного, но не меньше 1.0)
    min_close_coef = max(1.0, main_coef - 0.3)  # Минимум 1.0, максимум на 0.3 ниже основного
    max_close_coef = max(1.05, main_coef - 0.1)  # Минимум 1.05, максимум на 0.1 ниже основного
    close_coef = round(random.uniform(min_close_coef, max_close_coef), 2)
    
    return main_coef, accuracy, close_coef

def is_user_in_cooldown(user_id):
    """Проверка кулдауна пользователя"""
    if user_id not in user_cooldowns:
        return False
    
    cooldown_end = user_cooldowns[user_id]
    return time.time() < cooldown_end

def set_user_cooldown(user_id):
    """Установка кулдауна 10-15 секунд"""
    cooldown = random.randint(10, 15)
    user_cooldowns[user_id] = time.time() + cooldown
    return cooldown

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /start"""
    user_id = update.effective_user.id
    
    # Проверяем доступ
    if not has_access(user_id):
        # Создаем клавиатуру без доступа
        keyboard = [
            [InlineKeyboardButton("♻️ ПОДДЕРЖКА", url="https://t.me/xanezy")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        message = "❌ Доступ к боту ограничен!"
        await update.message.reply_text(message, reply_markup=reply_markup)
        return
    
    # Если есть доступ - показываем основной интерфейс
    # Создаем клавиатуру
    keyboard = [
        [InlineKeyboardButton("🔄️ ВЫДАТЬ СИГНАЛ", callback_data="get_signal")],
        [InlineKeyboardButton("♻️ ПОДДЕРЖКА", url="https://t.me/xanezy")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    message = (
        f"✅ Поздравляю, теперь у тебя есть доступ к сигнальному боту\n"
        f"👤 Твой юзер ID: {user_id}\n"
        f"🔗 Нажимай Выдать сигнал и начинай зарабатывать, пока не прикрыли данную возможность!"
    )
    
    await update.message.reply_text(message, reply_markup=reply_markup)

async def technical_works_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда для включения/выключения технических работ"""
    user = update.effective_user
    
    if not is_admin(user):
        await update.message.reply_text("❌ У вас нет прав для выполнения этой команды!")
        return
    
    global technical_works
    technical_works = not technical_works
    
    status = "включены" if technical_works else "выключены"
    await update.message.reply_text(f"⚙️ Технические работы {status}!")

async def give_access_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда для выдачи доступа"""
    user = update.effective_user
    
    if not is_admin(user):
        await update.message.reply_text("❌ У вас нет прав для выполнения этой команды!")
        return
    
    if len(context.args) < 2:
        await update.message.reply_text("❌ Использование: /give <user_id> <минуты>")
        return
    
    try:
        target_user_id = int(context.args[0])
        duration_minutes = int(context.args[1])
        
        if duration_minutes <= 0:
            await update.message.reply_text("❌ Время доступа должно быть больше 0 минут!")
            return
        
        access_until = grant_access(target_user_id, duration_minutes)
        
        from datetime import datetime
        access_until_str = datetime.fromtimestamp(access_until).strftime("%d.%m.%Y %H:%M")
        
        await update.message.reply_text(
            f"✅ Доступ выдан пользователю {target_user_id}\n"
            f"⏰ До: {access_until_str}\n"
            f"⏱️ На {duration_minutes} минут"
        )
        
    except ValueError:
        await update.message.reply_text("❌ Неверный формат. Использование: /give <user_id> <минуты>")

async def send_signal_with_animation(chat_id, context):
    """Функция отправки сигнала с анимацией загрузки"""
    # Первое сообщение загрузки
    message1 = await context.bot.send_message(chat_id, "🤖 Просчитываю сервер...")
    await asyncio.sleep(random.uniform(0.5, 1.5))
    await context.bot.delete_message(chat_id, message1.message_id)
    
    # Второе сообщение загрузки
    message2 = await context.bot.send_message(chat_id, "🎯 Высчитываю сигнал...")
    await asyncio.sleep(random.uniform(0.5, 1.2))
    await context.bot.delete_message(chat_id, message2.message_id)
    
    # Генерируем сигнал
    main_coef, accuracy, close_coef = generate_signal()
    
    # Создаем сообщение с сигналом
    signal_message = (
        "🤖 Сигнал на следующий раунд\n\n"
        f"🎯 {main_coef}X\n"
        f"💪 Точность сигнала: {accuracy}%\n"
        f"ℹ️ Идеально закрыть сигнал на {close_coef}X"
    )
    
    # Добавляем предупреждение о тех работах если они включены
    if technical_works:
        signal_message = "⚠️ Ведутся технические работы над ботом! Точность сигналов может быть ослаблена из-за большого наплыва пользователей на GiftUp.\n\n" + signal_message
    
    # Клавиатура для сигнала
    keyboard = [
        [InlineKeyboardButton("🔄️ Получить сигнал", callback_data="get_signal")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await context.bot.send_message(chat_id, signal_message, reply_markup=reply_markup)

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик нажатий на кнопки"""
    query = update.callback_query
    user_id = query.from_user.id
    
    await query.answer()
    
    # Проверяем доступ
    if not has_access(user_id):
        await query.message.reply_text("❌ Доступ к боту ограничен!")
        return
    
    if query.data == "get_signal":
        # Проверяем кулдаун
        if is_user_in_cooldown(user_id):
            await query.message.reply_text("🚀 Сначала дождитесь нового раунда!")
            return
        
        # Устанавливаем кулдаун
        cooldown = set_user_cooldown(user_id)
        
        # Отправляем сигнал с анимацией
        await send_signal_with_animation(query.message.chat_id, context)

async def signal_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /signal"""
    user_id = update.effective_user.id
    
    # Проверяем доступ
    if not has_access(user_id):
        await update.message.reply_text("❌ Доступ к боту ограничен!")
        return
    
    # Проверяем кулдаун
    if is_user_in_cooldown(user_id):
        await update.message.reply_text("🚀 Сначала дождитесь нового раунда!")
        return
    
    # Устанавливаем кулдаун
    cooldown = set_user_cooldown(user_id)
    
    # Отправляем сигнал с анимацией
    await send_signal_with_animation(update.message.chat_id, context)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка текстовых сообщений"""
    user_id = update.effective_user.id
    
    # Проверяем доступ
    if not has_access(user_id):
        await update.message.reply_text("❌ Доступ к боту ограничен!")
        return
    
    text = update.message.text.lower()
    
    if any(word in text for word in ['сигнал', 'ставка', 'коэф', 'прогноз', 'ракетка']):
        await signal_command(update, context)
    else:
        # Показываем стартовое сообщение на любое другое сообщение
        await start_command(update, context)

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик ошибок"""
    logger.error(f"Ошибка: {context.error}")

def main():
    """Основная функция"""
    try:
        # Создаем приложение
        app = Application.builder().token(TOKEN).build()
        
        # Добавляем обработчики
        app.add_handler(CommandHandler("start", start_command))
        app.add_handler(CommandHandler("signal", signal_command))
        app.add_handler(CommandHandler("technicalworks", technical_works_command))
        app.add_handler(CommandHandler("give", give_access_command))
        app.add_handler(CallbackQueryHandler(handle_callback))
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
        app.add_error_handler(error_handler)
        
        # Запускаем бота
        logging.info("Бот запущен...")
        print("Бот успешно запущен! Нажмите Ctrl+C для остановки.")
        app.run_polling()
        
    except Exception as e:
        logging.error(f"Ошибка запуска бота: {e}")
        print(f"Ошибка: {e}")

if __name__ == "__main__":
    main()
