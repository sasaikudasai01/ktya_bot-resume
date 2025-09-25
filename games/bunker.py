from aiogram import F, Router
from aiogram.types import Message, InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery
import random
import config
import time
import asyncio

random.seed(time.time())

router = Router()

# перехватывание стартового сообщения бункером
async def start_message(message: Message, chat_id):
    btn = [[InlineKeyboardButton(text='💔 Завершить игру 💔', callback_data='end_game')]] # кнопки, пока тут только "завершить игру"
    # добавление кнопки голосования, если локация выбрана
    btn.insert(0, [InlineKeyboardButton(text='Голосовать', callback_data='vote')] if config.location[chat_id] else [])

    keyboard = InlineKeyboardMarkup(inline_keyboard=btn)
    await message.answer('Вы играете "Бункер"', reply_markup=keyboard)

# прошлый метод был на 82 строки кода в отличие от 16 текущих...
async def send_word_func(message: Message, chat_id, username, full_name):
    send_word_list = [word.strip().lower() for word in message.text.split(maxsplit=1)[1].split(",")]
    for card in send_word_list:
        # поделить строку карты на название и описание
        card_name = card.split(maxsplit=1)[0] # название карты
        card_data = card.split(maxsplit=1)[1] # описание карты
        config.who_list[chat_id].setdefault(card_name, {})  # создать ключ названия карты если его не существует
        if card_data in config.who_list[chat_id][card_name].keys():  # существует ли уже такая карта или нет
            await message.answer(f'{card_name} - {card_data}\n\nуже существует в списке карт, отправь что нибудь другое')
            return
        else:
            config.who_list[chat_id][card_name][card_data] = username
            await message.answer(f'внесено\n{card_name}: {card_data}')
            print(f'{full_name}\n{card_name} - {card_data}\n')

    await message.bot.send_message(chat_id, f'🌟 {config.href(username, full_name)} добавил карты 🌟', parse_mode="HTML",
                                                                                                disable_web_page_preview=True)

# стартовое сообщение
@router.callback_query(F.data == "bunker")
async def bunker_handler(callback: CallbackQuery):
    chat_id = callback.message.chat.id

    config.current_game[chat_id] = "bunker"
    participate_button = InlineKeyboardButton(text="Участвую", callback_data="participate")
    start_game_bunker_button = InlineKeyboardButton(text="Начать игру", callback_data="start_bunker")
    keyboard = InlineKeyboardMarkup(inline_keyboard=[[participate_button], [start_game_bunker_button]])

    await callback.message.edit_text('Выбрана игра "Бункер"\n\nстарайтесь отправлять адекватные карточки,'
                                     ' чтобы не усложнять жизнь другим игрокам', reply_markup=keyboard)
    print(f'чат {callback.message.chat.title} начал игру "Бункер"')

# старт игры
@router.callback_query(F.data == "start_bunker")
async def start_bunker_handler(callback: CallbackQuery):
    chat_id = callback.message.chat.id

    if len(config.participants[chat_id]) >= 2: # достаточно ли игроков
        for player in config.participants[chat_id]:
            for card, value in config.who_list[chat_id].items(): # название карты и список значений от игроков
                if player not in value.values():  # все ли отправили слова
                    await callback.bot.send_message(
                        chat_id,
                        text=f'каждый должен отправить карты, '
                             f'<a href="https://t.me/{player}">{config.participants[chat_id][player]["full_name"]}</a>, отправляй 🔫',
                        parse_mode="HTML",
                        disable_web_page_preview=True
                    )
                    return

        for player in config.participants[chat_id]:
            for card, value in config.who_list[chat_id].items():  # название карты и список значений от игроков
                # присвоение случайной карты игроку
                random_card = random.choice(list(value.keys()))
                config.participants[chat_id][player]['bunker_cards'][f'{card}'] = random_card
                config.who_list[chat_id][card].pop(random_card, None) # удалить значение из списка карт

        # отправить игрокам их карты
        for username, user_id in config.user_ids[chat_id].items():
            message_for_send = '🌟 вот твои карты\n\n'
            for card, value in config.participants[chat_id][username]["cards"].items():
                message_for_send += f'{card}: {value}\n//////////////////\n'
                print(f'{config.participants[chat_id][username]["full_name"]}\n{card}: {value}\n')
            await callback.bot.send_message(user_id, message_for_send)

        await callback.message.answer('игра "Бункер" началась')
        config.location[chat_id] = 'bunker' # костыль, чтобы кнопка "голосование" появилась
    else:
        await callback.bot.send_message(chat_id, text="невозможно начать, недостаточно игроков")


# отправка правил игры
async def send_rules(message):
    await message.answer(config.games['Бункер'])

# голосование
async def vote_func(callback, chat_id):
    config.players[chat_id] = {}  # список кнопок с именами участников
    for user_name, user_id in config.user_ids[chat_id].items():
        config.players[chat_id][user_name] = []  # список кнопок с именами участников для этого игрока
        # для каждого игрока создается своя копия списка игроков для голосования
        config.players[chat_id][user_name] = [
            # добавить в список только полные имена игроков
            InlineKeyboardButton(text=f'{user_data["full_name"]}', callback_data=f'{user_data["name"]}_vote')
            for user_data in config.participants[chat_id].values()
            if user_data["name"] != user_name]  # не добавлять в список самого игрока
        keyboard = InlineKeyboardMarkup(inline_keyboard=[[button] for button in config.players[chat_id][user_name]])
        await callback.bot.send_message(user_id, 'кого выгоняем?', reply_markup=keyboard)
    await callback.message.answer('голосование отправлено вам в лс')
    await callback.bot.delete_message(chat_id, callback.message.message_id)
    await asyncio.sleep(30)  # таймер, чтобы завершить голосование
    await bunker_vote(chat_id, callback.message)  # вызов функции, определяющей выбывшего игрока
    await callback.message.answer('голосование завершено')

async def vote_for_handler(callback, group_chat_id, user): # user это пользователь, который голосует
    voted_username = callback.data.replace('_vote', '')  # извлечение ника из коллбэка, это игрок за которого голосуют
    voted_full_name = config.participants[group_chat_id][voted_username]["full_name"]

    config.participants[group_chat_id][voted_username]["voted_people"].append(user.username)

    await callback.message.answer(f'ты голосуешь за {config.href(voted_username, voted_full_name)}',
                                  parse_mode="HTML", disable_web_page_preview=True)

    await callback.bot.send_message(group_chat_id,
        f'🔫 {config.href(user.username, user.full_name)} голосует за {config.href(voted_username, voted_full_name)}',
        parse_mode="HTML", disable_web_page_preview=True)
    await callback.bot.delete_message(callback.message.chat.id, callback.message.message_id)

# определение выбывшего игрока в бункере
async def bunker_vote(chat_id, message):
    highest_vote = random.choice(list(config.participants[chat_id].keys())) # игрок с большим количеством голосов
    vote_counter = []  # суммы голосов каждого игрока
    for player, values in config.participants[chat_id].items():
        vote_counter.append(len(values["voted_people"]))
        if len(values["voted_people"]) > len(config.participants[chat_id][highest_vote]["voted_people"]):
            highest_vote = player

    # проверка повторений в vote_counter, чтобы проверить, разошлись ли мнения игроков
    if vote_counter.count(len(config.participants[chat_id][highest_vote]["voted_people"])) > 1:
        await message.bot.send_message(chat_id, f'мнения разошлись')
    else:
        highest_vote_full_name = config.participants[chat_id][highest_vote]["full_name"] # полное имя выбывшего игрока
        await message.bot.send_message(chat_id, f'{config.href(highest_vote, highest_vote_full_name)} выбывает',
            parse_mode="HTML", disable_web_page_preview=True)

        config.participants[chat_id].pop(highest_vote, None) # удалить выбывшего игрока из списка игроков
        config.user_ids[chat_id].pop(highest_vote, None)

        if len(config.participants[chat_id]) <= 2: # сколько игроков осталось, чтобы завершить игру
            await message.bot.send_message(chat_id, 'в бункер проходят:')
            print('в бункер проходят:')
            for player, data in config.participants[chat_id].items():
                player_full_name = data["full_name"]
                await message.bot.send_message(chat_id, config.href(player, player_full_name), parse_mode="HTML", disable_web_page_preview=True)
                print(player_full_name)
            await config.end_game_func(message, chat_id)