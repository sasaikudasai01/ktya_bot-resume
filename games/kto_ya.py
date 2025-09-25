from aiogram import F, Router
from aiogram.types import Message, InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery
import random
import config
import time

router = Router()

# перехватывание стартового сообщения игрой кто я
async def start_message(message: Message, chat_id):
    config.current_game[chat_id] = "kto_ya" # установить текущую игру
    end_game_button = InlineKeyboardButton(text='💔 Завершить игру 💔', callback_data='end_game')
    keyboard = InlineKeyboardMarkup(inline_keyboard=[[end_game_button]])
    await message.answer('Вы играете "Кто Я"', reply_markup=keyboard)

@router.callback_query(F.data == "kto_ya")
async def kto_ya_handler(callback: CallbackQuery):
    chat_id = callback.message.chat.id

    config.current_game[chat_id] = "kto_ya"
    participate_button = InlineKeyboardButton(text="Участвую", callback_data="participate")
    start_game_kto_ya_button = InlineKeyboardButton(text="Начать игру", callback_data="start_game_kto_ya")
    keyboard = InlineKeyboardMarkup(inline_keyboard=[[participate_button], [start_game_kto_ya_button]])

    await callback.message.edit_text('Выбрана игра "Кто Я"', reply_markup=keyboard)
    print(f'чат {callback.message.chat.title} начал игру "Кто Я"')

# стартовое сообщение
@router.callback_query(F.data == "start_game_kto_ya")
async def start_game_kto_ya_handler(callback: CallbackQuery):
    chat_id = callback.message.chat.id
    message_id = callback.message.message_id
    random.seed(time.time()) # обновлять сид каждый раз для лучшей рандомности

    if len(config.participants[chat_id]) >= 2: # достаточно ли игроков
        # совпадает ли список participants с who_list, чтобы узнать, все ли отправили слова
        # далее обернуть missing в список, чтобы уведомить игроков кто именно не отправил
        missing = list(set(config.participants[chat_id].keys()) - set(config.who_list[chat_id].values()))
        if missing:
            for player in missing:
                await callback.bot.send_message(chat_id, text='там баг, который мне лень фиксить, '
                    f'{config.href(player, config.participants[chat_id][player]["full_name"])}, отправь хотя бы одно слово 🔫',
                    parse_mode="HTML", disable_web_page_preview=True)
            return

        # присвоение слов участникам
        for player, data in config.participants[chat_id].items():
            while data['word'] == "": # продолжать выбирать слова
                random_word = random.choice(list(config.who_list[chat_id].keys())) # выбор случайного слова
                if config.who_list[chat_id][random_word] != player: # присвоение слова, если оно отправлено не игроком
                    data["word"] = random_word
                    await callback.bot.send_message(chat_id, text=f'{config.href(player, data["full_name"])} получил свое слово',
                        parse_mode="HTML", disable_web_page_preview=True)
                    print(f'{player} - {random_word}')

        # отправить участникам список игроков
        for user_id in config.user_ids[chat_id].values():
            message = '🌟 Вот слова участников:\n'
            for player, data in config.participants[chat_id].items():
                if user_id != data["id"]:
                    message += f'{config.href(player, data["full_name"])} - {data["word"]}\n'
            await callback.bot.send_message(user_id, text=f"{message}", parse_mode="HTML", disable_web_page_preview=True)
        await callback.bot.delete_message(chat_id, message_id)
    else:
        await callback.bot.send_message(chat_id, text="невозможно начать, недостаточно игроков")

# отправка правил игры
async def send_rules(message):
    await message.answer(config.games['Кто Я'])

# отправить слова
async def send_word_func(message: Message, chat_id, username, full_name):
    # один раз отделить /sendword от слов и составить список слов из сообщения пользователя
    send_word_list = [word.strip() for word in message.text.split(maxsplit=1)[1].split(",")]
    common_words = list(set(send_word_list) & set(config.who_list[chat_id].keys()))  # есть ли повторяющиеся слова
    if not common_words:
        for word in send_word_list:
            # ключ это слово, а не пользователь, потому что пользователи могут позже добавить еще слов
            config.who_list[chat_id][word] = username  # добавление слов в список слов
    else:
        await message.answer(f'{common_words}\nуже есть в списке слов, отправь что то еще')
        return
    await message.answer("список слов обновлен")
    await message.bot.send_message(chat_id, text=f'🌟 {config.href(username, full_name)} добавил слова 🌟',
                           parse_mode="HTML", disable_web_page_preview=True)
    print(f"{full_name} отправил слова: {send_word_list}")