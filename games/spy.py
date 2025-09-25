from aiogram import F, Router
from aiogram.types import Message, InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery
import random
import config
import time

router = Router()

# перехватывание стартового сообщения игрой шпион
async def start_message(message: Message, chat_id):
    btn = [[InlineKeyboardButton(text='💔 Завершить игру 💔', callback_data='end_game')]] # кнопки, пока тут только "завершить игру"
    # добавление кнопки голосования, если локация выбрана
    btn.insert(0, [InlineKeyboardButton(text='Голосовать', callback_data='vote')] if config.location[chat_id] else [])

    keyboard = InlineKeyboardMarkup(inline_keyboard=btn)
    await message.answer('Вы играете "Шпион"', reply_markup=keyboard)


@router.callback_query(F.data == "spy")
async def spy_handler(callback: CallbackQuery):
    chat_id = callback.message.chat.id

    config.current_game[chat_id] = "spy"
    participate_button = InlineKeyboardButton(text="Участвую", callback_data="participate")
    start_game_spy_button = InlineKeyboardButton(text="Начать игру", callback_data="start_spy")
    keyboard = InlineKeyboardMarkup(inline_keyboard=[[participate_button], [start_game_spy_button]])

    await callback.message.edit_text('Выбрана игра "Шпион"', reply_markup=keyboard)
    print(f'чат {callback.message.chat.title} начал игру "Шпион"')

# старт игры
@router.callback_query(F.data == "start_spy")
async def start_spy_handler(callback: CallbackQuery):
    chat_id = callback.message.chat.id
    random.seed(time.time())  # обновлять сид каждый раз для лучшей рандомности

    if len(config.participants[chat_id]) >= 2: # достаточно ли игроков
        # совпадает ли список participants с who_list, чтобы узнать, все ли отправили слова
        # далее обернуть missing в список, чтобы уведомить игроков кто именно не отправил
        missing = list(set(config.participants[chat_id].keys()) - set(config.who_list[chat_id].values()))
        if missing:
            for player in missing:
                await callback.bot.send_message(
                    chat_id,
                    text='там баг, который мне лень фиксить, '
                         f'{config.href(player, config.participants[chat_id][player]["full_name"])}, отправь хотя бы одну локацию 🔫',
                    parse_mode="HTML",
                    disable_web_page_preview=True
                )
            return

        # выбор шпиона
        spy = random.choice(list(config.participants[chat_id].keys()))
        config.participants[chat_id][spy]["is_spy"] = True
        for location, username in list(config.who_list[chat_id].items()):
            if username == spy:
                # удалить все локации, отправленные шпионом, чтобы она не выпала и не сделала игру шпиона легче
                config.who_list[chat_id].pop(location, None)
        await callback.bot.send_message(config.participants[chat_id][spy]["id"], text='ты шпион')
        print(f'{config.participants[chat_id][spy]["full_name"]} шпион')

        config.location[chat_id] = random.choice(list(config.who_list[chat_id].keys())) # выбор случайной локации
        print(f'выбрана локация {config.location[chat_id]}')

        for player, values in config.participants[chat_id].items(): # отправить игрокам локацию
            if player != spy: # отправить локацию всем кроме шпиона
                await callback.bot.send_message(values["id"], text=f'🌟 Локация {config.location[chat_id]}')

        await callback.message.answer('локация выбрана и отправлена участникам')
        await callback.bot.delete_message(chat_id, callback.message.message_id)
    else:
        await callback.bot.send_message(chat_id, text="невозможно начать, недостаточно игроков")

# отправка правил игры
async def send_rules(message):
    await message.answer(config.games['Шпион'])

# голосование
async def vote_func(callback, chat_id):
    # добавление всех игроков в список с их полными именами
    keyboard = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=f'{user_data["full_name"]}',
                                    callback_data=f'{user_data["name"]}_vote')]
                                    for user_data in config.participants[chat_id].values()])

    for user, user_id in config.participants[chat_id].items(): # отправить голосование каждому игроку в лс
        await callback.bot.send_message(user_id["id"], 'Голосовать за:', reply_markup=keyboard)

async def vote_for_handler(callback, group_chat_id, user): # user это пользователь, который голосует
    voted_username = callback.data.replace('_vote', '')  # извлечение ника из коллбэка, это игрок за которого голосуют
    voted_full_name = config.participants[group_chat_id][voted_username]["full_name"]

    # настоящий шпион
    for player, data in config.participants[group_chat_id].items():
        if data['is_spy']:
            spy = player  # ник шпиона
            spy_full_name = data["full_name"] # полное имя шпиона

            config.participants[group_chat_id][voted_username]["voted_people"].append(user.username)  # +1 голос игроку
            await callback.bot.send_message(group_chat_id,
                f'🔫 {config.href(user.username, user.full_name)} голосует за {config.href(voted_username, voted_full_name)}',
                parse_mode="HTML", disable_web_page_preview=True)

            # достаточно ли голосов за игрока, чтобы закончить игру
            if len(config.participants[group_chat_id][voted_username]["voted_people"]) >= len(config.participants[group_chat_id]) / 2:
                if voted_username == spy:  # шпион ли выбывший игрок
                    await callback.bot.send_message(group_chat_id, f'вы победили, {config.href(voted_username, voted_full_name)} шпион',
                        parse_mode="HTML", disable_web_page_preview=True)
                    print(f'шпион {voted_full_name} проигрывает')
                else:
                    await callback.bot.send_message(group_chat_id, f'{config.href(voted_username, voted_full_name)} не шпион\n'
                        f'{config.href(spy, spy_full_name)} побеждает',
                        parse_mode="HTML", disable_web_page_preview=True)
                    print(f'шпион {spy_full_name} побеждает')

                # удаление сообщения с голосованием
                await callback.bot.delete_message(callback.message.chat.id, callback.message.message_id)
                await config.end_game_func(callback.message, group_chat_id)
                break

# отправить локации
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