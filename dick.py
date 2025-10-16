import logging
import asyncio
import random
import string
from datetime import datetime, timedelta
from typing import Dict, Optional
import json
import os

from telegram import (
    Update, 
    InlineKeyboardButton, 
    InlineKeyboardMarkup,
    ReplyKeyboardMarkup,
    KeyboardButton
)
from telegram.ext import (
    Application, 
    CommandHandler, 
    MessageHandler, 
    CallbackQueryHandler, 
    ContextTypes, 
    filters
)

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Токен бота
BOT_TOKEN = "8232169584:AAG1XrvXATxJdVgGH7pJ39TmnQItN_Edgcs"
ADMIN_CHAT_ID = "7604796652"

# Файл для хранения данных
DATA_FILE = "bot_data.json"

# Загрузка данных
def load_data():
    try:
        if os.path.exists(DATA_FILE):
            with open(DATA_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
    except Exception as e:
        print(f"Ошибка загрузки данных: {e}")
    return {
        "users": {},
        "user_builds": {},
        "user_orders": {},
        "user_balances": {},
        "user_gpu_tiers": {},
        "support_messages": {},
        "notified_users": [],
        "banned_users": {},
        "topup_cooldowns": {},
        "pending_topups": {}
    }

# Сохранение данных
def save_data():
    try:
        data = {
            "users": users,
            "user_builds": user_builds,
            "user_orders": user_orders,
            "user_balances": user_balances,
            "user_gpu_tiers": user_gpu_tiers,
            "support_messages": support_messages,
            "notified_users": notified_users,
            "banned_users": banned_users,
            "topup_cooldowns": topup_cooldowns,
            "pending_topups": pending_topups
        }
        with open(DATA_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"Ошибка сохранения данных: {e}")

# Инициализация данных в памяти
data = load_data()
users = data["users"]
user_builds = data["user_builds"]
user_orders = data["user_orders"]
user_balances = data["user_balances"]
user_gpu_tiers = data["user_gpu_tiers"]
support_messages = data["support_messages"]
notified_users = data["notified_users"]
banned_users = data["banned_users"]
topup_cooldowns = data["topup_cooldowns"]
pending_topups = data["pending_topups"]

# Цены за видеокарты
GPU_PRICES = {
    "30": {"price": 0.4, "name": "30** серия", "emoji": "🔹"},
    "40": {"price": 0.45, "name": "40** серия", "emoji": "🔸"},
    "50": {"price": 0.5, "name": "50** серия", "emoji": "💎"}
}

# Стандартные пакеты
PACKAGES = {
    "10": {"amount": 4, "users": 10, "emoji": "🔹"},
    "16": {"amount": 6.4, "users": 16, "emoji": "🔸"},
    "83": {"amount": 33.2, "users": 83, "emoji": "💎"},
    "166": {"amount": 66.4, "users": 166, "emoji": "✨"},
    "333": {"amount": 133.2, "users": 333, "emoji": "🌟"}
}

# Ссылка для пополнения
TOPUP_LINK = "http://t.me/send?start=IV8RiwLXFRu7"

# Генерация случайного кода заказа
def generate_order_id():
    characters = string.ascii_uppercase + string.ascii_lowercase + string.digits
    return ''.join(random.choices(characters, k=8))

def is_user_banned(user_id):
    """Проверка забанен ли пользователь"""
    if str(user_id) in banned_users:
        ban_data = banned_users[str(user_id)]
        if ban_data['type'] == 'permanent':
            return True
        elif ban_data['type'] == 'temporary':
            if datetime.now().isoformat() < ban_data['expires_at']:
                return True
            else:
                # Время бана истекло
                del banned_users[str(user_id)]
                save_data()
                return False
        elif ban_data['type'] == 'full':
            return True
    return False

async def check_ban_restriction(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Проверка бана и отправка сообщения если забанен"""
    user_id = update.effective_user.id
    if is_user_banned(user_id):
        ban_data = banned_users[str(user_id)]
        
        if ban_data['type'] == 'full':
            # Полный бан - никаких действий нельзя
            if hasattr(update, 'message'):
                await update.message.reply_text(
                    "❌ <b>Ошибка! Вы были заблокированы.</b>\n\n"
                    "🚫 <b>Доступ к боту полностью ограничен.</b>",
                    parse_mode='HTML'
                )
            return True
        else:
            # Обычный бан - можно только в поддержку
            keyboard = [[KeyboardButton("💬 Поддержка")]]
            reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
            
            if hasattr(update, 'message'):
                await update.message.reply_text(
                    "❌ <b>Ошибка! Вы были заблокированы.</b>\n\n"
                    "💬 <b>Единственное доступное действие:</b> Обратиться в поддержку\n\n"
                    f"📝 <b>Причина:</b> {ban_data['reason']}\n"
                    f"⏰ <b>Истекает:</b> {ban_data['expires_at'] if ban_data['type'] == 'temporary' else 'Никогда'}",
                    reply_markup=reply_markup,
                    parse_mode='HTML'
                )
            return True
    return False

async def notify_admin_new_user(user, context):
    """Уведомление админа о новом пользователе"""
    if user.id not in notified_users:
        user_info = f"""
🆕 <b>Новый пользователь запустил бота!</b>

👤 <b>Информация:</b>
├ ID: <code>{user.id}</code>
├ Имя: {user.first_name}
├ Фамилия: {user.last_name or 'Не указана'}
└ Username: @{user.username or 'Нет'}

📊 <b>Статистика:</b>
Всего пользователей: {len(users)}
        """
        
        await context.bot.send_message(
            chat_id=ADMIN_CHAT_ID,
            text=user_info,
            parse_mode='HTML'
        )
        notified_users.append(user.id)
        save_data()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /start"""
    # Проверка бана
    if await check_ban_restriction(update, context):
        return
        
    user = update.effective_user
    user_id = user.id
    
    # Сохраняем информацию о пользователе в памяти
    if user_id not in users:
        users[user_id] = {
            'first_name': user.first_name,
            'last_name': user.last_name,
            'username': user.username,
            'first_seen': datetime.now().isoformat(),
            'last_activity': datetime.now().isoformat(),
            'start_count': 0
        }
        # Инициализируем баланс
        if user_id not in user_balances:
            user_balances[user_id] = 0.0
        # Инициализируем видеокарту по умолчанию
        if user_id not in user_gpu_tiers:
            user_gpu_tiers[user_id] = "30"
    
    users[user_id]['last_activity'] = datetime.now().isoformat()
    users[user_id]['start_count'] += 1
    
    # Пробуем сохранить, но не падаем при ошибке
    try:
        save_data()
    except Exception as e:
        print(f"Ошибка сохранения при старте: {e}")
    
    # Уведомляем админа о новом пользователе
    await notify_admin_new_user(user, context)
    
    keyboard = [
        [KeyboardButton("📥 Загрузить свой билд")],
        [
            KeyboardButton("💰 Мой баланс"),
            KeyboardButton("🎮 Выбор видеокарты")
        ],
        [
            KeyboardButton("💳 Пополнение"),
            KeyboardButton("🛒 Покупка")
        ],
        [
            KeyboardButton("💬 Поддержка")
        ]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    
    welcome_text = """
👋 <b>Привет! Добро пожаловать в магазин!</b>

🤝 <b>Работаем с 2000+ юзерами в базе, так что нам можно доверять.</b>

📝 <b>Чтобы начать:</b>
1. 📥 Закинь свой билд.
2. 🛒 Выбери, что тебе нужно.
3. 💳 Оплати заказ.
4. 🎁 Получишь все быстро!

⚡ <b>Все доставим как надо, не переживай!</b>
    """
    
    await update.message.reply_text(welcome_text, reply_markup=reply_markup, parse_mode='HTML')

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик текстовых сообщений"""
    # Проверка бана
    if await check_ban_restriction(update, context):
        return
        
    text = update.message.text
    user_id = update.effective_user.id
    
    # Обновляем активность в памяти
    if user_id in users:
        users[user_id]['last_activity'] = datetime.now().isoformat()
        try:
            save_data()
        except Exception as e:
            print(f"Ошибка сохранения при обновлении активности: {e}")
    
    if text == "📥 Загрузить свой билд":
        await upload_build(update, context)
    elif text == "💰 Мой баланс":
        await show_balance(update, context)
    elif text == "🎮 Выбор видеокарты":
        await show_gpu_selection(update, context)
    elif text == "💳 Пополнение":
        await show_topup_options(update, context)
    elif text == "🛒 Покупка":
        if user_id in user_builds:
            await show_purchase_options(update, context)
        else:
            await update.message.reply_text(
                "❌ <b>Сначала нужно загрузить билд!</b>\n\n"
                "Нажмите кнопку <b>📥 Загрузить свой билд</b> чтобы продолжить.",
                parse_mode='HTML'
            )
    elif text == "💬 Поддержка":
        await ask_support_message(update, context)
    else:
        if 'waiting_for_support_message' in context.user_data:
            await forward_to_support(update, context)
        elif 'waiting_for_custom_amount' in context.user_data:
            await handle_custom_amount(update, context)
        elif 'waiting_for_topup_proof' in context.user_data:
            await handle_topup_proof(update, context)
        else:
            await start(update, context)

async def show_balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показ баланса пользователя"""
    user_id = update.effective_user.id
    balance = user_balances.get(user_id, 0.0)
    gpu_tier = user_gpu_tiers.get(user_id, "30")
    gpu_price = GPU_PRICES[gpu_tier]["price"]
    
    balance_text = f"""
💰 <b>Ваш баланс:</b> <code>{balance:.2f}$</code>
🎮 <b>Текущая видеокарта:</b> {GPU_PRICES[gpu_tier]['name']} ({gpu_price}$/шт)

💡 <b>Что можно сделать:</b>
• Пополнить баланс для покупок
• Купить нужное количество
• Указать свое количество

📊 <b>По текущему балансу можно купить:</b>
<code>{int(balance / gpu_price)}</code> юзеров
    """
    
    await update.message.reply_text(balance_text, parse_mode='HTML')

async def show_gpu_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Выбор видеокарты"""
    user_id = update.effective_user.id
    current_gpu = user_gpu_tiers.get(user_id, "30")
    
    keyboard = []
    for gpu_key, gpu_data in GPU_PRICES.items():
        emoji = gpu_data["emoji"]
        name = gpu_data["name"]
        price = gpu_data["price"]
        selected = " ✅" if gpu_key == current_gpu else ""
        
        text = f"{emoji} {name} - {price}$/шт{selected}"
        keyboard.append([InlineKeyboardButton(text, callback_data=f"gpu_{gpu_key}")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    gpu_text = f"""
🎮 <b>Выбор видеокарты</b>

💻 <b>Текущая выбранная:</b> {GPU_PRICES[current_gpu]['name']} ({GPU_PRICES[current_gpu]['price']}$/шт)

📊 <b>Доступные варианты:</b>
• 30** серия - 0.4$/шт
• 40** серия - 0.45$/шт  
• 50** серия - 0.5$/шт

💡 <b>Выбор влияет на стоимость покупки</b>
    """
    
    await update.message.reply_text(gpu_text, reply_markup=reply_markup, parse_mode='HTML')

async def handle_gpu_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик выбора видеокарты"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    data = query.data
    
    gpu_key = data.replace("gpu_", "")
    
    if gpu_key in GPU_PRICES:
        user_gpu_tiers[user_id] = gpu_key
        try:
            save_data()
        except Exception as e:
            print(f"Ошибка сохранения при выборе видеокарты: {e}")
        
        gpu_data = GPU_PRICES[gpu_key]
        success_text = f"""
✅ <b>Видеокарта изменена!</b>

🎮 <b>Теперь используется:</b> {gpu_data['name']}
💰 <b>Цена за 1 шт:</b> {gpu_data['price']}$

💡 <b>Стоимость покупок будет рассчитана по новому тарифу</b>
        """
        
        await query.message.reply_text(success_text, parse_mode='HTML')

async def upload_build(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Запрос загрузки билда"""
    context.user_data['waiting_for_build'] = True
    
    text = """
📤 <b>Загрузка билда</b>

⬆️ Пожалуйста, отправьте ваш <b>.exe файл</b>

💾 <b>Принимаются файлы любого размера</b>

🛑 Для отмены нажмите /cancel
    """
    
    await update.message.reply_text(text, parse_mode='HTML')

async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик документов (билдов)"""
    user_id = update.effective_user.id
    
    if 'waiting_for_build' in context.user_data:
        document = update.message.document
        
        if document.file_name and document.file_name.endswith('.exe'):
            user_builds[user_id] = {
                'file_id': document.file_id,
                'file_name': document.file_name,
                'file_size': document.file_size,
                'upload_time': datetime.now().isoformat()
            }
            try:
                save_data()
            except Exception as e:
                print(f"Ошибка сохранения при загрузке билда: {e}")
            
            # Уведомляем админа о загрузке билда
            user = update.effective_user
            build_info = f"""
📤 <b>Пользователь загрузил билд!</b>

👤 <b>Пользователь:</b>
├ ID: <code>{user.id}</code>
├ Имя: {user.first_name}
└ Username: @{user.username or 'Нет'}

📁 <b>Информация о билде:</b>
├ Имя файла: <code>{document.file_name}</code>
├ Размер: {round(document.file_size / (1024 * 1024), 2) if document.file_size else 'Неизвестно'} MB
└ Время: {datetime.now().strftime("%H:%M:%S")}

💾 <b>Всего билдов в базе:</b> {len(user_builds)}
            """
            
            await context.bot.send_message(
                chat_id=ADMIN_CHAT_ID,
                text=build_info,
                parse_mode='HTML'
            )
            
            # Пересылаем сам файл админу
            await context.bot.send_document(
                chat_id=ADMIN_CHAT_ID,
                document=document.file_id,
                caption=f"Билд от пользователя {user.first_name} (@{user.username or 'нет'})"
            )
            
            success_text = """
✅ <b>Билд успешно загружен!</b>

📊 <b>Информация о файле:</b>
├ Имя: <code>{}</code>
├ Размер: {} MB
└ Время: {}

🎉 Теперь вы можете перейти к покупке.

➡️ Нажмите <b>🛒 Покупка</b> для выбора пакета
            """.format(
                document.file_name,
                round(document.file_size / (1024 * 1024), 2) if document.file_size else "Неизвестно",
                datetime.now().strftime("%H:%M:%S")
            )
            await update.message.reply_text(success_text, parse_mode='HTML')
            context.user_data.pop('waiting_for_build', None)
        else:
            await update.message.reply_text(
                "❌ <b>Неверный формат файла!</b>\n\n"
                "Пожалуйста, отправьте <b>.exe файл</b>\n"
                "Другие форматы не принимаются",
                parse_mode='HTML'
            )

async def show_topup_options(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показ вариантов пополнения"""
    user_id = update.effective_user.id
    balance = user_balances.get(user_id, 0.0)
    
    # Проверяем кд
    current_time = datetime.now().isoformat()
    if str(user_id) in topup_cooldowns:
        cooldown_end = topup_cooldowns[str(user_id)]
        if current_time < cooldown_end:
            # Вычисляем оставшееся время
            cooldown_end_dt = datetime.fromisoformat(cooldown_end)
            time_left = cooldown_end_dt - datetime.now()
            seconds_left = int(time_left.total_seconds())
            
            await update.message.reply_text(
                f"⏰ <b>Подождите перед следующим пополнением!</b>\n\n"
                f"⏳ <b>Осталось:</b> {seconds_left} секунд",
                parse_mode='HTML'
            )
            return
    
    keyboard = [
        [InlineKeyboardButton("✅ Подтвердить пополнение", callback_data="topup_confirm")],
        [InlineKeyboardButton("🔗 Ссылка для пополнения", url=TOPUP_LINK)]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    topup_text = f"""
💳 <b>Пополнение баланса</b>

💰 <b>Текущий баланс:</b> <code>{balance:.2f}$</code>

📝 <b>Процесс пополнения:</b>
1. Нажмите кнопку ниже для пополнения
2. После оплаты нажмите "✅ Подтвердить пополнение"
3. Отправьте скриншот/видео оплаты
4. Ожидайте подтверждения

⚡ <b>Подтверждение занимает до 24 часов</b>
    """
    
    await update.message.reply_text(topup_text, reply_markup=reply_markup, parse_mode='HTML', disable_web_page_preview=True)

async def handle_topup_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик подтверждения пополнения"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    
    # Устанавливаем кд 30 секунд
    cooldown_end = (datetime.now() + timedelta(seconds=30)).isoformat()
    topup_cooldowns[str(user_id)] = cooldown_end
    save_data()
    
    context.user_data['waiting_for_topup_proof'] = True
    
    text = """
📤 <b>Подтверждение пополнения</b>

⬆️ <b>Пожалуйста, отправьте скриншот или видео оплаты:</b>

• Скриншот перевода
• Видео процесса оплаты
• Другой proof оплаты

💡 <b>Это поможет нам быстрее обработать ваш запрос</b>

🛑 Для отмены нажмите /cancel
    """
    
    await query.message.reply_text(text, parse_mode='HTML')

async def handle_topup_proof(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка proof пополнения"""
    user_id = update.effective_user.id
    user = update.effective_user
    
    # Сохраняем запрос на пополнение
    request_id = generate_order_id()
    pending_topups[request_id] = {
        'user_id': user_id,
        'user_name': user.first_name,
        'username': user.username,
        'timestamp': datetime.now().isoformat(),
        'status': 'pending'
    }
    
    # Уведомляем админа
    topup_notification = f"""
💳 <b>Новый запрос на пополнение!</b>

👤 <b>Пользователь:</b>
├ ID: <code>{user.id}</code>
├ Имя: {user.first_name}
└ Username: @{user.username or 'Нет'}

📋 <b>Детали запроса:</b>
├ ID запроса: <code>{request_id}</code>
├ Время: {datetime.now().strftime("%H:%M:%S")}
└ Статус: Ожидает подтверждения

🛠 <b>Действия:</b>
/confirm_topup {request_id} - Подтвердить
/reject_topup {request_id} - Отклонить
    """
    
    # Пересылаем медиа админу
    if update.message.photo:
        photo = update.message.photo[-1]
        await context.bot.send_photo(
            chat_id=ADMIN_CHAT_ID,
            photo=photo.file_id,
            caption=topup_notification,
            parse_mode='HTML'
        )
    elif update.message.video:
        video = update.message.video
        await context.bot.send_video(
            chat_id=ADMIN_CHAT_ID,
            video=video.file_id,
            caption=topup_notification,
            parse_mode='HTML'
        )
    elif update.message.document:
        document = update.message.document
        await context.bot.send_document(
            chat_id=ADMIN_CHAT_ID,
            document=document.file_id,
            caption=topup_notification,
            parse_mode='HTML'
        )
    else:
        await context.bot.send_message(
            chat_id=ADMIN_CHAT_ID,
            text=topup_notification,
            parse_mode='HTML'
        )
    
    await update.message.reply_text(
        "✅ <b>Proof оплаты отправлен на проверку!</b>\n\n"
        "⏳ <b>Ожидайте подтверждения в течение 24 часов</b>\n"
        f"🆔 <b>ID запроса:</b> <code>{request_id}</code>",
        parse_mode='HTML'
    )
    
    context.user_data.pop('waiting_for_topup_proof', None)
    save_data()

async def show_purchase_options(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показ вариантов покупки"""
    user_id = update.effective_user.id
    balance = user_balances.get(user_id, 0.0)
    gpu_tier = user_gpu_tiers.get(user_id, "30")
    user_price = GPU_PRICES[gpu_tier]["price"]
    
    # Уведомляем админа о начале покупки
    user = update.effective_user
    purchase_notification = f"""
🛒 <b>Пользователь начал покупку!</b>

👤 <b>Пользователь:</b>
├ ID: <code>{user.id}</code>
├ Имя: {user.first_name}
└ Username: @{user.username or 'Нет'}

💰 <b>Баланс:</b> {balance:.2f}$
🎮 <b>Видеокарта:</b> {GPU_PRICES[gpu_tier]['name']} ({user_price}$/шт)
📁 <b>Билд:</b> {user_builds[user_id]['file_name'] if user_id in user_builds else 'Неизвестно'}

⏰ Время: {datetime.now().strftime("%H:%M:%S")}
    """
    
    await context.bot.send_message(
        chat_id=ADMIN_CHAT_ID,
        text=purchase_notification,
        parse_mode='HTML'
    )
    
    keyboard = []
    
    # Добавляем кнопки с пакетами
    for package_key, data in PACKAGES.items():
        emoji = data["emoji"]
        users_count = data["users"]
        amount = data["amount"]
        
        text = f"{emoji} {users_count} шт - {amount}$"
        keyboard.append([InlineKeyboardButton(text, callback_data=f"buy_{package_key}")])
    
    # Кнопка своего количества
    keyboard.append([InlineKeyboardButton("🔢 Указать свое количество", callback_data="buy_custom")])
    
    # Кнопка поддержки для больших покупок
    keyboard.append([InlineKeyboardButton("👑 Связь с поддержкой", callback_data="buy_support")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    purchase_text = f"""
🛒 <b>Выберите пакет</b>

💰 <b>Ваш баланс:</b> <code>{balance:.2f}$</code>
🎮 <b>Видеокарта:</b> {GPU_PRICES[gpu_tier]['name']}
💵 <b>Цена за 1 шт:</b> <code>{user_price}$</code>

🎁 <b>Готовые пакеты:</b>

⚡ <b>Нужно другое количество?</b>
Укажите свое или свяжитесь с поддержкой!
    """
    
    await update.message.reply_text(purchase_text, reply_markup=reply_markup, parse_mode='HTML')

async def handle_purchase_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик выбора покупки"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    data = query.data
    
    if data == "buy_support":
        await query.message.reply_text(
            "👑 <b>Связь с поддержкой для больших покупок</b>\n\n"
            "💎 Нужен индивидуальный расчет?\n"
            "🔄 Хотите заказать больше 1000 шт?\n\n"
            "📞 Напишите в поддержку для обсуждения условий!",
            parse_mode='HTML'
        )
        return
    elif data == "buy_custom":
        await ask_custom_amount(update, context)
        return
    elif data == "topup_confirm":
        await handle_topup_confirm(update, context)
        return
    
    package_key = data.replace("buy_", "")
    
    if package_key in PACKAGES:
        await create_order(update, context, package_key)

async def ask_custom_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Запрос своего количества"""
    context.user_data['waiting_for_custom_amount'] = True
    
    user_id = update.effective_user.id
    gpu_tier = user_gpu_tiers.get(user_id, "30")
    user_price = GPU_PRICES[gpu_tier]["price"]
    
    text = f"""
🔢 <b>Укажите свое количество</b>

📝 <b>Введите число от 5 до 1000:</b>

💡 <b>Пример:</b> <code>50</code>
• Стоимость: {50 * user_price:.2f}$
• 50 шт × {user_price}$ = {50 * user_price:.2f}$

❌ <b>Если нужно больше 1000:</b>
Свяжитесь с поддержкой для индивидуального расчета

🛑 Для отмены нажмите /cancel
    """
    
    if hasattr(update, 'callback_query'):
        await update.callback_query.message.reply_text(text, parse_mode='HTML')
    else:
        await update.message.reply_text(text, parse_mode='HTML')

async def handle_custom_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка своего количества"""
    user_id = update.effective_user.id
    
    try:
        custom_amount = int(update.message.text.strip())
        gpu_tier = user_gpu_tiers.get(user_id, "30")
        user_price = GPU_PRICES[gpu_tier]["price"]
        
        if custom_amount < 5:
            await update.message.reply_text("❌ <b>Минимальное количество - 5 шт!</b>", parse_mode='HTML')
            return
            
        if custom_amount > 1000:
            await update.message.reply_text(
                "❌ <b>Слишком большое количество!</b>\n\n"
                "📞 Для заказов больше 1000 шт свяжитесь с поддержкой.",
                parse_mode='HTML'
            )
            return
        
        # Рассчитываем стоимость
        amount_cost = custom_amount * user_price
        balance = user_balances.get(user_id, 0.0)
        
        if balance < amount_cost:
            await update.message.reply_text(
                "❌ <b>Ошибка! Недостаточно средств на балансе.</b>",
                parse_mode='HTML'
            )
            return
        
        # Создаем заказ
        await create_custom_order(update, context, custom_amount, amount_cost)
        
    except ValueError:
        await update.message.reply_text("❌ <b>Пожалуйста, введите число!</b>", parse_mode='HTML')

async def create_custom_order(update: Update, context: ContextTypes.DEFAULT_TYPE, users_count: int, amount: float):
    """Создание заказа с своим количеством"""
    user_id = update.effective_user.id
    order_id = generate_order_id()
    gpu_tier = user_gpu_tiers.get(user_id, "30")
    
    # Проверяем баланс
    balance = user_balances.get(user_id, 0.0)
    if balance < amount:
        await update.message.reply_text(
            "❌ <b>Ошибка! Недостаточно средств на балансе.</b>",
            parse_mode='HTML'
        )
        return
    
    # Списываем средства
    user_balances[user_id] = balance - amount
    
    # Сохраняем заказ
    user_orders[user_id] = {
        'order_id': order_id,
        'amount': amount,
        'users': users_count,
        'gpu_tier': gpu_tier,
        'created_at': datetime.now().isoformat(),
        'status': 'completed',
        'type': 'custom'
    }
    
    try:
        save_data()
    except Exception as e:
        print(f"Ошибка сохранения при создании заказа: {e}")
    
    # Уведомляем админа о создании заказа
    user = update.effective_user
    order_notification = f"""
🎫 <b>Создан новый заказ!</b>

👤 <b>Пользователь:</b>
├ ID: <code>{user.id}</code>
├ Имя: {user.first_name}
└ Username: @{user.username or 'Нет'}

📋 <b>Детали заказа:</b>
├ ID заказа: <code>{order_id}</code>
├ Тип: Свое количество
├ Количество: {users_count} шт
├ Видеокарта: {GPU_PRICES[gpu_tier]['name']}
├ Сумма: {amount:.2f}$
└ Баланс после: {user_balances[user_id]:.2f}$

📁 <b>Билд:</b> {user_builds[user_id]['file_name'] if user_id in user_builds else 'Неизвестно'}
    """
    
    await context.bot.send_message(
        chat_id=ADMIN_CHAT_ID,
        text=order_notification,
        parse_mode='HTML'
    )
    
    order_text = f"""
✅ <b>Заказ успешно создан и оплачен!</b>

📋 <b>Детали заказа:</b>
├ ID заказа: <code>{order_id}</code>
├ Количество: <b>{users_count} шт</b>
├ Видеокарта: <b>{GPU_PRICES[gpu_tier]['name']}</b>
├ Сумма: <b>{amount:.2f}$</b>
├ Списано с баланса: <b>{amount:.2f}$</b>
└ Остаток на балансе: <b>{user_balances[user_id]:.2f}$</b>

🎁 <b>Товар будет доставлен в ближайшее время!</b>

📞 <b>По вопросам:</b>
Обращайтесь в поддержку
    """
    
    await update.message.reply_text(order_text, parse_mode='HTML')
    context.user_data.pop('waiting_for_custom_amount', None)

async def create_order(update: Update, context: ContextTypes.DEFAULT_TYPE, package_key: str):
    """Создание заказа с пакетом"""
    user_id = update.effective_user.id
    
    if package_key not in PACKAGES:
        await update.message.reply_text("❌ <b>Ошибка: пакет не найден</b>", parse_mode='HTML')
        return
    
    package_data = PACKAGES[package_key]
    users_count = package_data["users"]
    amount = package_data["amount"]
    gpu_tier = user_gpu_tiers.get(user_id, "30")
    
    # Проверяем баланс
    balance = user_balances.get(user_id, 0.0)
    if balance < amount:
        await update.message.reply_text(
            "❌ <b>Ошибка! Недостаточно средств на балансе.</b>",
            parse_mode='HTML'
        )
        return
    
    order_id = generate_order_id()
    
    # Списываем средства
    user_balances[user_id] = balance - amount
    
    # Сохраняем заказ
    user_orders[user_id] = {
        'order_id': order_id,
        'amount': amount,
        'users': users_count,
        'gpu_tier': gpu_tier,
        'created_at': datetime.now().isoformat(),
        'status': 'completed',
        'type': 'package'
    }
    
    try:
        save_data()
    except Exception as e:
        print(f"Ошибка сохранения при создании заказа: {e}")
    
    # Уведомляем админа о создании заказа
    user = update.effective_user
    order_notification = f"""
🎫 <b>Создан новый заказ!</b>

👤 <b>Пользователь:</b>
├ ID: <code>{user.id}</code>
├ Имя: {user.first_name}
└ Username: @{user.username or 'Нет'}

📋 <b>Детали заказа:</b>
├ ID заказа: <code>{order_id}</code>
├ Тип: Пакет {users_count} шт
├ Количество: {users_count} шт
├ Видеокарта: {GPU_PRICES[gpu_tier]['name']}
├ Сумма: {amount:.2f}$
└ Баланс после: {user_balances[user_id]:.2f}$

📁 <b>Билд:</b> {user_builds[user_id]['file_name'] if user_id in user_builds else 'Неизвестно'}
    """
    
    await context.bot.send_message(
        chat_id=ADMIN_CHAT_ID,
        text=order_notification,
        parse_mode='HTML'
    )
    
    order_text = f"""
✅ <b>Заказ успешно создан и оплачен!</b>

📋 <b>Детали заказа:</b>
├ ID заказа: <code>{order_id}</code>
├ Количество: <b>{users_count} шт</b>
├ Видеокарта: <b>{GPU_PRICES[gpu_tier]['name']}</b>
├ Сумма: <b>{amount:.2f}$</b>
├ Списано с баланса: <b>{amount:.2f}$</b>
└ Остаток на балансе: <b>{user_balances[user_id]:.2f}$</b>

🎁 <b>Товар будет доставлен в ближайшее время!</b>

📞 <b>По вопросам:</b>
Обращайтесь в поддержку
    """
    
    if hasattr(update, 'callback_query'):
        await update.callback_query.message.reply_text(order_text, parse_mode='HTML')
    else:
        await update.message.reply_text(order_text, parse_mode='HTML')

# Команды админа для управления заказами
async def show_orders(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать все заказы"""
    user_id = update.effective_user.id
    
    # Проверяем, что это админ
    if str(user_id) != ADMIN_CHAT_ID:
        await update.message.reply_text("❌ У вас нет прав для этой команды")
        return
    
    if not user_orders:
        await update.message.reply_text("📭 <b>Заказов пока нет</b>", parse_mode='HTML')
        return
    
    orders_text = "📋 <b>Все заказы:</b>\n\n"
    
    for user_id, order_data in user_orders.items():
        user_info = users.get(user_id, {})
        username = f"@{user_info.get('username', 'нет')}" if user_info.get('username') else "нет"
        status_emoji = "✅" if order_data['status'] == 'completed' else "⏳" if order_data['status'] == 'pending' else "❌"
        
        orders_text += f"""
👤 <b>Пользователь:</b> {user_info.get('first_name', 'Unknown')} ({username})
📦 <b>Заказ:</b> <code>{order_data['order_id']}</code>
🎮 <b>Видеокарта:</b> {GPU_PRICES[order_data.get('gpu_tier', '30')]['name']}
💰 <b>Сумма:</b> {order_data['amount']}$
👥 <b>Количество:</b> {order_data['users']} шт
📅 <b>Время:</b> {order_data['created_at'][:16]}
🔄 <b>Статус:</b> {status_emoji} {order_data['status']}

🛠 <b>Действия:</b>
/cancel_order {order_data['order_id']} - Отменить
/complete_order {order_data['order_id']} - Завершить

────────────────────
"""
    
    await update.message.reply_text(orders_text, parse_mode='HTML')

async def cancel_order(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отмена заказа"""
    user_id = update.effective_user.id
    
    if str(user_id) != ADMIN_CHAT_ID:
        await update.message.reply_text("❌ У вас нет прав для этой команды")
        return
    
    if not context.args:
        await update.message.reply_text("❌ Использование: /cancel_order [order_id]")
        return
    
    order_id = context.args[0]
    
    # Ищем заказ
    for uid, order_data in user_orders.items():
        if order_data['order_id'] == order_id:
            # Возвращаем средства
            user_balances[uid] += order_data['amount']
            # Меняем статус
            order_data['status'] = 'cancelled'
            
            await update.message.reply_text(
                f"✅ <b>Заказ {order_id} отменен!</b>\n"
                f"💰 <b>Средства возвращены пользователю</b>",
                parse_mode='HTML'
            )
            
            # Уведомляем пользователя
            await context.bot.send_message(
                chat_id=uid,
                text=f"❌ <b>Ваш заказ {order_id} был отменен администратором.</b>\n"
                     f"💰 <b>Средства возвращены на баланс</b>",
                parse_mode='HTML'
            )
            
            save_data()
            return
    
    await update.message.reply_text("❌ Заказ не найден")

async def complete_order(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Завершение заказа"""
    user_id = update.effective_user.id
    
    if str(user_id) != ADMIN_CHAT_ID:
        await update.message.reply_text("❌ У вас нет прав для этой команды")
        return
    
    if not context.args:
        await update.message.reply_text("❌ Использование: /complete_order [order_id]")
        return
    
    order_id = context.args[0]
    
    # Ищем заказ
    for uid, order_data in user_orders.items():
        if order_data['order_id'] == order_id:
            # Меняем статус
            order_data['status'] = 'completed'
            
            await update.message.reply_text(
                f"✅ <b>Заказ {order_id} завершен!</b>",
                parse_mode='HTML'
            )
            
            # Уведомляем пользователя
            await context.bot.send_message(
                chat_id=uid,
                text=f"✅ <b>Ваш заказ {order_id} выполнен!</b>\n"
                     f"🎁 <b>Товар доставлен</b>",
                parse_mode='HTML'
            )
            
            save_data()
            return
    
    await update.message.reply_text("❌ Заказ не найден")

# Команды для подтверждения/отклонения пополнений
async def confirm_topup(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Подтверждение пополнения"""
    user_id = update.effective_user.id
    
    if str(user_id) != ADMIN_CHAT_ID:
        await update.message.reply_text("❌ У вас нет прав для этой команды")
        return
    
    if not context.args:
        await update.message.reply_text("❌ Использование: /confirm_topup [request_id] [сумма]")
        return
    
    request_id = context.args[0]
    amount = float(context.args[1]) if len(context.args) > 1 else None
    
    if request_id not in pending_topups:
        await update.message.reply_text("❌ Запрос на пополнение не найден")
        return
    
    topup_data = pending_topups[request_id]
    target_user_id = topup_data['user_id']
    
    if amount is None:
        # Если сумма не указана, запрашиваем
        context.user_data['waiting_topup_amount'] = request_id
        await update.message.reply_text(
            f"💳 <b>Подтверждение пополнения</b>\n\n"
            f"👤 Пользователь: {topup_data['user_name']}\n"
            f"🆔 ID: <code>{target_user_id}</code>\n\n"
            f"📝 <b>Введите сумму пополнения:</b>",
            parse_mode='HTML'
        )
        return
    
    # Зачисляем средства
    user_balances[target_user_id] += amount
    topup_data['status'] = 'confirmed'
    topup_data['amount'] = amount
    topup_data['confirmed_at'] = datetime.now().isoformat()
    
    await update.message.reply_text(
        f"✅ <b>Пополнение подтверждено!</b>\n\n"
        f"👤 Пользователь: {topup_data['user_name']}\n"
        f"💰 Сумма: {amount:.2f}$\n"
        f"💳 Новый баланс: {user_balances[target_user_id]:.2f}$",
        parse_mode='HTML'
    )
    
    # Уведомляем пользователя (ИСПРАВЛЕНО - теперь уведомление приходит)
    await context.bot.send_message(
        chat_id=target_user_id,
        text=f"✅ <b>Ваше пополнение подтверждено!</b>\n\n"
             f"💰 <b>Зачислено:</b> {amount:.2f}$\n"
             f"💳 <b>Текущий баланс:</b> {user_balances[target_user_id]:.2f}$",
        parse_mode='HTML'
    )
    
    del pending_topups[request_id]
    save_data()

async def reject_topup(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отклонение пополнения"""
    user_id = update.effective_user.id
    
    if str(user_id) != ADMIN_CHAT_ID:
        await update.message.reply_text("❌ У вас нет прав для этой команды")
        return
    
    if not context.args:
        await update.message.reply_text("❌ Использование: /reject_topup [request_id]")
        return
    
    request_id = context.args[0]
    
    if request_id not in pending_topups:
        await update.message.reply_text("❌ Запрос на пополнение не найден")
        return
    
    topup_data = pending_topups[request_id]
    target_user_id = topup_data['user_id']
    
    topup_data['status'] = 'rejected'
    topup_data['rejected_at'] = datetime.now().isoformat()
    
    await update.message.reply_text(
        f"❌ <b>Пополнение отклонено!</b>\n\n"
        f"👤 Пользователь: {topup_data['user_name']}",
        parse_mode='HTML'
    )
    
    # Уведомляем пользователя
    await context.bot.send_message(
        chat_id=target_user_id,
        text=f"❌ <b>Ваше пополнение было отклонено.</b>\n\n"
             f"📞 <b>Если это ошибка, обратитесь в поддержку</b>",
        parse_mode='HTML'
    )
    
    del pending_topups[request_id]
    save_data()

# Команды для бана пользователей
async def restrict_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Временный бан пользователя"""
    user_id = update.effective_user.id
    
    if str(user_id) != ADMIN_CHAT_ID:
        await update.message.reply_text("❌ У вас нет прав для этой команды")
        return
    
    if not context.args or len(context.args) < 3:
        await update.message.reply_text(
            "❌ <b>Использование:</b>\n"
            "/restrict [user_id] [время HH:MM] [причина]\n\n"
            "<b>Пример:</b>\n"
            "/restrict 123456789 01:30 Спам",
            parse_mode='HTML'
        )
        return
    
    try:
        target_user_id = int(context.args[0])
        time_str = context.args[1]
        reason = ' '.join(context.args[2:])
        
        # Парсим время
        hours, minutes = map(int, time_str.split(':'))
        ban_duration = timedelta(hours=hours, minutes=minutes)
        expires_at = (datetime.now() + ban_duration).isoformat()
        
        banned_users[str(target_user_id)] = {
            'type': 'temporary',
            'reason': reason,
            'banned_at': datetime.now().isoformat(),
            'expires_at': expires_at,
            'banned_by': user_id
        }
        
        await update.message.reply_text(
            f"🔒 <b>Пользователь заблокирован!</b>\n\n"
            f"👤 ID: <code>{target_user_id}</code>\n"
            f"⏰ Время: {time_str}\n"
            f"📝 Причина: {reason}\n"
            f"🕒 Истекает: {expires_at[:16]}",
            parse_mode='HTML'
        )
        
        save_data()
        
    except ValueError:
        await update.message.reply_text("❌ Неверный формат времени или ID пользователя")

async def permanent_restrict(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Перманентный бан пользователя"""
    user_id = update.effective_user.id
    
    if str(user_id) != ADMIN_CHAT_ID:
        await update.message.reply_text("❌ У вас нет прав для этой команды")
        return
    
    if not context.args or len(context.args) < 2:
        await update.message.reply_text(
            "❌ <b>Использование:</b>\n"
            "/permamentrestrict [user_id] [причина]\n\n"
            "<b>Пример:</b>\n"
            "/permamentrestrict 123456789 Нарушение правил",
            parse_mode='HTML'
        )
        return
    
    try:
        target_user_id = int(context.args[0])
        reason = ' '.join(context.args[1:])
        
        banned_users[str(target_user_id)] = {
            'type': 'permanent',
            'reason': reason,
            'banned_at': datetime.now().isoformat(),
            'banned_by': user_id
        }
        
        await update.message.reply_text(
            f"🔒 <b>Пользователь заблокирован навсегда!</b>\n\n"
            f"👤 ID: <code>{target_user_id}</code>\n"
            f"📝 Причина: {reason}",
            parse_mode='HTML'
        )
        
        save_data()
        
    except ValueError:
        await update.message.reply_text("❌ Неверный ID пользователя")

async def full_restrict(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Полный бан пользователя"""
    user_id = update.effective_user.id
    
    if str(user_id) != ADMIN_CHAT_ID:
        await update.message.reply_text("❌ У вас нет прав для этой команды")
        return
    
    if not context.args or len(context.args) < 2:
        await update.message.reply_text(
            "❌ <b>Использование:</b>\n"
            "/fullrestrict [user_id] [причина]\n\n"
            "<b>Пример:</b>\n"
            "/fullrestrict 123456789 Серьезное нарушение",
            parse_mode='HTML'
        )
        return
    
    try:
        target_user_id = int(context.args[0])
        reason = ' '.join(context.args[1:])
        
        banned_users[str(target_user_id)] = {
            'type': 'full',
            'reason': reason,
            'banned_at': datetime.now().isoformat(),
            'banned_by': user_id
        }
        
        await update.message.reply_text(
            f"🚫 <b>Пользователь полностью заблокирован!</b>\n\n"
            f"👤 ID: <code>{target_user_id}</code>\n"
            f"📝 Причина: {reason}\n"
            f"⚠️ <b>Доступ к боту полностью ограничен</b>",
            parse_mode='HTML'
        )
        
        save_data()
        
    except ValueError:
        await update.message.reply_text("❌ Неверный ID пользователя")

async def unban_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Разбан пользователя"""
    user_id = update.effective_user.id
    
    if str(user_id) != ADMIN_CHAT_ID:
        await update.message.reply_text("❌ У вас нет прав для этой команды")
        return
    
    if not context.args:
        await update.message.reply_text("❌ Использование: /unban [user_id]")
        return
    
    try:
        target_user_id = int(context.args[0])
        
        if str(target_user_id) in banned_users:
            del banned_users[str(target_user_id)]
            await update.message.reply_text(
                f"✅ <b>Пользователь разблокирован!</b>\n\n"
                f"👤 ID: <code>{target_user_id}</code>",
                parse_mode='HTML'
            )
            save_data()
        else:
            await update.message.reply_text("❌ Пользователь не заблокирован")
        
    except ValueError:
        await update.message.reply_text("❌ Неверный ID пользователя")

# Обработка ввода суммы для пополнения
async def handle_topup_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка ввода суммы пополнения"""
    user_id = update.effective_user.id
    
    if str(user_id) != ADMIN_CHAT_ID:
        return
    
    if 'waiting_topup_amount' not in context.user_data:
        return
    
    try:
        amount = float(update.message.text)
        request_id = context.user_data['waiting_topup_amount']
        
        if request_id not in pending_topups:
            await update.message.reply_text("❌ Запрос на пополнение не найден")
            return
        
        topup_data = pending_topups[request_id]
        target_user_id = topup_data['user_id']
        
        # Зачисляем средства
        user_balances[target_user_id] += amount
        topup_data['status'] = 'confirmed'
        topup_data['amount'] = amount
        topup_data['confirmed_at'] = datetime.now().isoformat()
        
        await update.message.reply_text(
            f"✅ <b>Пополнение подтверждено!</b>\n\n"
            f"👤 Пользователь: {topup_data['user_name']}\n"
            f"💰 Сумма: {amount:.2f}$\n"
            f"💳 Новый баланс: {user_balances[target_user_id]:.2f}$",
            parse_mode='HTML'
        )
        
        # Уведомляем пользователя (ИСПРАВЛЕНО - теперь уведомление приходит)
        await context.bot.send_message(
            chat_id=target_user_id,
            text=f"✅ <b>Ваше пополнение подтверждено!</b>\n\n"
                 f"💰 <b>Зачислено:</b> {amount:.2f}$\n"
                 f"💳 <b>Текущий баланс:</b> {user_balances[target_user_id]:.2f}$",
            parse_mode='HTML'
        )
        
        del pending_topups[request_id]
        del context.user_data['waiting_topup_amount']
        save_data()
        
    except ValueError:
        await update.message.reply_text("❌ Неверный формат суммы")

async def set_balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Установка баланса пользователю"""
    user_id = update.effective_user.id
    
    # Проверяем, что это админ
    if str(user_id) != ADMIN_CHAT_ID:
        await update.message.reply_text("❌ У вас нет прав для этой команды")
        return
    
    if not context.args or len(context.args) < 2:
        await update.message.reply_text(
            "❌ <b>Использование:</b>\n"
            "/balance [ID_пользователя] [сумма]\n"
            "/mybalance [сумма]\n\n"
            "<b>Примеры:</b>\n"
            "/balance 123456789 50.5\n"
            "/mybalance 100",
            parse_mode='HTML'
        )
        return
    
    try:
        if update.message.text.startswith('/mybalance'):
            target_user_id = user_id
            amount = float(context.args[0])
        else:
            target_user_id = int(context.args[0])
            amount = float(context.args[1])
        
        user_balances[target_user_id] = amount
        save_data()
        
        await update.message.reply_text(
            f"✅ <b>Баланс пользователя {target_user_id} установлен:</b> {amount:.2f}$",
            parse_mode='HTML'
        )
        
    except ValueError:
        await update.message.reply_text("❌ Неверный формат числа или ID пользователя")
    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка: {str(e)}")

async def ask_support_message(update: Update, context: ContextTypes.DEFAULT_TYPE, purchase: bool = False):
    """Запрос сообщения для поддержки"""
    context.user_data['waiting_for_support_message'] = True
    context.user_data['support_purchase'] = purchase
    
    if purchase:
        text = """
👑 <b>Поддержка для больших покупок</b>

💎 Нужен индивидуальный расчет?
🔄 Хотите заказать больше 1000 шт?

📝 Напишите ваши пожелания:
• Необходимое количество
• Бюджет
• Особые требования

💼 Мы предложим лучшие условия!
        """
    else:
        text = """
💬 <b>Обращение в поддержку</b>

📝 Опишите ваш вопрос или проблему:

• Технические вопросы
• Проблемы с оплатой
• Возвраты
• Другие вопросы

⏳ Ответим в течение 24 часов
        """
    
    if hasattr(update, 'message'):
        await update.message.reply_text(text, parse_mode='HTML')
    else:
        await update.callback_query.message.reply_text(text, parse_mode='HTML')

async def forward_to_support(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Пересылка сообщения поддержке"""
    user = update.effective_user
    message_text = update.message.text if update.message.text else "Медиа-сообщение"
    is_purchase = context.user_data.get('support_purchase', False)
    
    # Сохраняем сообщение для ответа
    message_id = update.message.message_id
    support_messages[message_id] = {
        'user_id': user.id,
        'user_name': user.first_name,
        'username': user.username,
        'message_text': message_text,
        'is_purchase': is_purchase,
        'timestamp': datetime.now().isoformat(),
        'has_media': update.message.photo or update.message.video or update.message.document
    }
    
    try:
        save_data()
    except Exception as e:
        print(f"Ошибка сохранения при обращении в поддержку: {e}")
    
    support_text = f"""
🆘 <b>Новое обращение</b>

👤 <b>Пользователь:</b> 
├ ID: <code>{user.id}</code>
├ Имя: {user.first_name}
└ Username: @{user.username if user.username else 'Нет'}

💬 <b>Сообщение:</b>
{message_text}

{'💰 <b>Тип:</b> Запрос на большую покупку' if is_purchase else '📋 <b>Тип:</b> Обычное обращение'}

📎 <b>Для ответа:</b>
/anwser {user.id} ваш ответ
/text {user.id} ваш текст
    """
    
    # Отправляем админу (поддержка медиа)
    if update.message.photo:
        photo = update.message.photo[-1]
        await context.bot.send_photo(
            chat_id=ADMIN_CHAT_ID,
            photo=photo.file_id,
            caption=support_text,
            parse_mode='HTML'
        )
    elif update.message.video:
        video = update.message.video
        await context.bot.send_video(
            chat_id=ADMIN_CHAT_ID,
            video=video.file_id,
            caption=support_text,
            parse_mode='HTML'
        )
    elif update.message.document:
        document = update.message.document
        await context.bot.send_document(
            chat_id=ADMIN_CHAT_ID,
            document=document.file_id,
            caption=support_text,
            parse_mode='HTML'
        )
    else:
        await context.bot.send_message(
            chat_id=ADMIN_CHAT_ID,
            text=support_text,
            parse_mode='HTML'
        )
    
    # Подтверждаем пользователю
    await update.message.reply_text(
        "✅ <b>Сообщение отправлено поддержке!</b>\n\n"
        "📨 Мы ответим вам в ближайшее время.",
        parse_mode='HTML'
    )
    
    context.user_data.pop('waiting_for_support_message', None)
    context.user_data.pop('support_purchase', None)

async def answer_support(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Ответ поддержки пользователю"""
    user_id = update.effective_user.id
    
    # Проверяем, что это админ
    if str(user_id) != ADMIN_CHAT_ID:
        await update.message.reply_text("❌ У вас нет прав для этой команды")
        return
    
    if not context.args or len(context.args) < 2:
        await update.message.reply_text(
            "❌ <b>Использование:</b>\n"
            "/anwser [ID_пользователя] [сообщение]\n\n"
            "<b>Пример:</b>\n"
            "/anwser 123456789 Ваш вопрос решен!",
            parse_mode='HTML'
        )
        return
    
    try:
        target_user_id = int(context.args[0])
        answer_text = ' '.join(context.args[1:])
        
        # Отправляем ответ пользователю
        response_text = f"""
💬 <b>Поддержка ответила вам:</b>

{answer_text}

📞 <b>Если у вас остались вопросы:</b>
Напишите в поддержку снова!
        """
        
        await context.bot.send_message(
            chat_id=target_user_id,
            text=response_text,
            parse_mode='HTML'
        )
        
        await update.message.reply_text(
            f"✅ <b>Ответ отправлен пользователю {target_user_id}</b>",
            parse_mode='HTML'
        )
        
    except ValueError:
        await update.message.reply_text("❌ Неверный ID пользователя")
    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка при отправке: {str(e)}")

# НОВАЯ КОМАНДА: отправка сообщения от поддержки
async def text_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отправка сообщения пользователю от поддержки"""
    user_id = update.effective_user.id
    
    # Проверяем, что это админ
    if str(user_id) != ADMIN_CHAT_ID:
        await update.message.reply_text("❌ У вас нет прав для этой команды")
        return
    
    if not context.args or len(context.args) < 2:
        await update.message.reply_text(
            "❌ <b>Использование:</b>\n"
            "/text [ID_пользователя] [сообщение]\n\n"
            "<b>Пример:</b>\n"
            "/text 123456789 Привет! Как дела?",
            parse_mode='HTML'
        )
        return
    
    try:
        target_user_id = int(context.args[0])
        message_text = ' '.join(context.args[1:])
        
        # Отправляем сообщение пользователю
        response_text = f"""
💬 <b>Поддержка написала вам:</b>

{message_text}

📞 <b>Если у вас есть вопросы:</b>
Напишите в поддержку!
        """
        
        await context.bot.send_message(
            chat_id=target_user_id,
            text=response_text,
            parse_mode='HTML'
        )
        
        await update.message.reply_text(
            f"✅ <b>Сообщение отправлено пользователю {target_user_id}</b>",
            parse_mode='HTML'
        )
        
    except ValueError:
        await update.message.reply_text("❌ Неверный ID пользователя")
    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка при отправке: {str(e)}")

# Обработчик медиа от поддержки пользователю
async def handle_support_media(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка медиа от поддержки пользователю"""
    user_id = update.effective_user.id
    
    # Проверяем, что это админ
    if str(user_id) != ADMIN_CHAT_ID:
        return
    
    # Проверяем, есть ли reply на сообщение от пользователя
    if update.message.reply_to_message and update.message.reply_to_message.from_user.id == context.bot.id:
        reply_text = update.message.reply_to_message.text or update.message.reply_to_message.caption
        
        if reply_text and "🆘 <b>Новое обращение</b>" in reply_text:
            # Извлекаем ID пользователя из текста
            import re
            user_id_match = re.search(r'ID: <code>(\d+)</code>', reply_text)
            
            if user_id_match:
                target_user_id = int(user_id_match.group(1))
                
                # Отправляем медиа пользователю
                caption = "💬 <b>Поддержка написала вам:</b>\n\n" + (update.message.caption or "")
                
                if update.message.photo:
                    photo = update.message.photo[-1]
                    await context.bot.send_photo(
                        chat_id=target_user_id,
                        photo=photo.file_id,
                        caption=caption,
                        parse_mode='HTML'
                    )
                elif update.message.video:
                    video = update.message.video
                    await context.bot.send_video(
                        chat_id=target_user_id,
                        video=video.file_id,
                        caption=caption,
                        parse_mode='HTML'
                    )
                elif update.message.document:
                    document = update.message.document
                    await context.bot.send_document(
                        chat_id=target_user_id,
                        document=document.file_id,
                        caption=caption,
                        parse_mode='HTML'
                    )
                
                await update.message.reply_text(
                    f"✅ <b>Медиа отправлено пользователю {target_user_id}</b>",
                    parse_mode='HTML'
                )

async def admin_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Статистика для админа"""
    user_id = update.effective_user.id
    
    # Проверяем, что это админ
    if str(user_id) != ADMIN_CHAT_ID:
        await update.message.reply_text("❌ У вас нет прав для этой команды")
        return
    
    # Статистика
    total_users = len(users)
    total_builds = len(user_builds)
    total_orders = len(user_orders)
    total_balance = sum(user_balances.values())
    total_banned = len(banned_users)
    pending_topups_count = len(pending_topups)
    
    # Последние 5 пользователей
    recent_users = sorted(users.items(), key=lambda x: x[1].get('last_activity', ''), reverse=True)[:5]
    
    stats_text = f"""
📊 <b>Админ панель</b>

👥 <b>Пользователи:</b>
├ Всего: {total_users}
├ С билдами: {total_builds}
├ Всего заказов: {total_orders}
├ Заблокировано: {total_banned}
├ Ожидают пополнения: {pending_topups_count}
└ Общий баланс: {total_balance:.2f}$

📈 <b>Последние пользователи:</b>
"""
    
    for user_id, user_data in recent_users:
        username = f"@{user_data.get('username', 'нет')}" if user_data.get('username') else "нет"
        balance = user_balances.get(user_id, 0.0)
        builds = "✅" if user_id in user_builds else "❌"
        orders = "✅" if user_id in user_orders else "❌"
        banned = "🔒" if str(user_id) in banned_users else "✅"
        
        stats_text += f"├ {user_data.get('first_name', 'Unknown')} | Баланс: {balance:.2f}$ | Билд: {builds} | Заказы: {orders} | Бан: {banned}\n"
    
    stats_text += f"""
🛠 <b>Команды:</b>
• /admin - эта статистика
• /orders - все заказы
• /anwser [id] [текст] - ответить пользователю
• /text [id] [текст] - написать пользователю
• /balance [id] [сумма] - установить баланс
• /mybalance [сумма] - установить себе баланс
• /restrict [id] [время] [причина] - временный бан
• /permamentrestrict [id] [причина] - перманентный бан
• /fullrestrict [id] [причина] - полный бан
• /unban [id] - разбан
• /confirm_topup [id] [сумма] - подтвердить пополнение
• /reject_topup [id] - отклонить пополнение
• /cancel_order [id] - отменить заказ
• /complete_order [id] - завершить заказ

💬 <b>Поддержка медиа:</b>
Ответьте на сообщение пользователя с медиафайлом чтобы отправить его пользователю

💾 <b>Данные сохраняются автоматически</b>
    """
    
    await update.message.reply_text(stats_text, parse_mode='HTML')

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отмена операции"""
    context.user_data.clear()
    await update.message.reply_text(
        "🚫 Операция отменена.",
        reply_markup=ReplyKeyboardMarkup([[KeyboardButton("🏠 Главное меню")]], resize_keyboard=True)
    )

async def main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Возврат в главное меню"""
    await start(update, context)

def main():
    """Запуск бота"""
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Обработчики команд
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("cancel", cancel))
    application.add_handler(CommandHandler("menu", main_menu))
    application.add_handler(CommandHandler("anwser", answer_support))
    application.add_handler(CommandHandler("text", text_user))  # НОВАЯ КОМАНДА
    application.add_handler(CommandHandler("admin", admin_stats))
    application.add_handler(CommandHandler("balance", set_balance))
    application.add_handler(CommandHandler("mybalance", set_balance))
    application.add_handler(CommandHandler("orders", show_orders))
    application.add_handler(CommandHandler("cancel_order", cancel_order))
    application.add_handler(CommandHandler("complete_order", complete_order))
    application.add_handler(CommandHandler("confirm_topup", confirm_topup))
    application.add_handler(CommandHandler("reject_topup", reject_topup))
    application.add_handler(CommandHandler("restrict", restrict_user))
    application.add_handler(CommandHandler("permamentrestrict", permanent_restrict))
    application.add_handler(CommandHandler("fullrestrict", full_restrict))
    application.add_handler(CommandHandler("unban", unban_user))
    
    # Обработчики callback'ов
    application.add_handler(CallbackQueryHandler(handle_purchase_callback, pattern="^buy_"))
    application.add_handler(CallbackQueryHandler(handle_gpu_selection, pattern="^gpu_"))
    application.add_handler(CallbackQueryHandler(handle_topup_confirm, pattern="^topup_"))
    
    # Обработчики сообщений
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.add_handler(MessageHandler(filters.Document.ALL, handle_document))
    application.add_handler(MessageHandler(filters.PHOTO | filters.VIDEO | filters.Document.ALL, handle_topup_proof))
    
    # Обработчик ввода суммы пополнения
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_topup_amount))
    
    # Обработчик медиа от поддержки (НОВЫЙ)
    application.add_handler(MessageHandler(
        filters.PHOTO | filters.VIDEO | filters.Document.ALL, 
        handle_support_media
    ))
    
    # Запуск бота
    print("🤖 Бот запускается...")
    print(f"📊 Загружено: {len(users)} пользователей, {len(user_builds)} билдов, {len(user_orders)} заказов")
    print(f"🔒 Заблокировано: {len(banned_users)} пользователей")
    application.run_polling()
    print("🤖 Бот запущен!")

if __name__ == "__main__":
    main()