from aiogram import F, Router
from aiogram.types import Message, InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery
import random
import config
import time
from collections import Counter

router = Router()

# перехватывание стартового сообщения игрой бар лжецов
async def start_message(message: Message, chat_id):
    config.current_game[chat_id] = "liars_bar" # установить текущую игру
    end_game_button = InlineKeyboardButton(text='💔 Завершить игру 💔', callback_data='end_game')
    keyboard = InlineKeyboardMarkup(inline_keyboard=[[end_game_button]])
    await message.answer("Вы играете Liar's Bar", reply_markup=keyboard)

@router.callback_query(F.data == "liars_bar")
async def liars_bar_handler(callback: CallbackQuery):
    chat_id = callback.message.chat.id

    config.current_game[chat_id] = "liars_bar"
    participate_button = InlineKeyboardButton(text="Участвую", callback_data="participate")
    start_game_kto_ya_button = InlineKeyboardButton(text="Начать игру", callback_data="start_liars_bar")
    keyboard = InlineKeyboardMarkup(inline_keyboard=[[participate_button], [start_game_kto_ya_button]])

    await callback.message.edit_text("выбрана игра Liar's Bar", reply_markup=keyboard)
    print(f"чат {callback.message.chat.title} начал игру Liar's Bar")

# старт игры // разрача карт игрокам
@router.callback_query(F.data == "start_liars_bar")
async def start_liars_bar_handler(callback: CallbackQuery):
    await start_liars_bar_game(callback.message) # раздача карт
    await callback.message.bot.delete_message(callback.message.chat.id, callback.message.message_id)

# раздача карт
async def start_liars_bar_game(message):
    chat_id = message.chat.id
    random.seed(time.time())  # обновлять сид каждый раз для лучшей рандомности

    config.cards[chat_id] = {"ace": 6, "king": 6, "queen": 6, "joker": 2, "devil": 2} # общая колода карт

    if len(config.participants[chat_id]) <= 4: # в бар лжецов могут играть максимум 4 игрока
        for player, data in config.participants[chat_id].items():
            while sum(data["cards"].values()) != 5: # продолжать давать игроку карты пока не наберется 5
                random_card = random.choice(list(config.cards[chat_id].keys())) # выбор случайной карты
                if config.cards[chat_id][random_card] != 0: # остались ли такие карты
                    config.cards[chat_id][random_card] -= 1 # забрать карту из общей колоды
                    data["cards"].setdefault(random_card, 0) # создать дефолтное значение карты
                    data["cards"][random_card] += 1 # дать карту игроку
                else:
                    config.cards[chat_id].pop(random_card, None) # удалить ключ карты из общей колоды если этих карт не осталось

            await message.bot.send_message(data["id"], 'твои карты\n"название карты" - "количество"')

            for card, number in data["cards"].items():
                await message.bot.send_message(data["id"], f'{card} - {number}')

            await message.bot.send_message(chat_id, f'🌟 {config.href(player, data["full_name"])} получил свои карты 🌟',
                                            parse_mode="HTML", disable_web_page_preview=True)

        config.trump_card[chat_id] = [random.choice(["ace", "king", "queen"])] # выбор козыря
        config.cards[chat_id] = {}  # освободить колоду карт, создав пустой словарь
        await message.answer(f'козырь <b>{config.trump_card[chat_id][0]}</b>', parse_mode="HTML")

# игрок выбирает какие карты кинуть
async def send_word_func(message, group_chat_id, user, full_name):
    # список карт, что отправил игрок в виде текста "карта количество"
    send_cards = [w.lower().strip() for w in message.text.split(maxsplit=1)[1].split(',')]
    temp_cards = {} # временная переменная для проверки правильности карт, в случае чего они добавляются к общему количеству карт на столе
    user_cards = config.participants[group_chat_id][user.username]["cards"] # карты, которые есть у игрока

    if any(card.startswith("devil") for card in send_cards): # выбрал ли игрок карту дьявола
        if len(send_cards) > 1 or "devil" not in user_cards.keys(): # сколько карт отправил игрок и есть ли карта дьявола у игрока
            await message.answer('ты не можешь выбрать эти карты')
            return

    for card in send_cards:
        try:
            card_name = card.split(maxsplit=1)[0] # название карты
            cards_number = int(card.split(maxsplit=1)[1]) # количество карт
            # есть ли такая карта у игрока и правильное ли количество карт ввел игрок
            if card_name in user_cards.keys() and cards_number <= user_cards[card_name]:
                if "devil" in card_name and cards_number > 1: # правильное ли кол-во карт дьявола выбрал игрок
                    await message.answer('ты не можешь выбрать эти карты')
                    return
                else:
                    temp_cards[card_name] = cards_number
            else:
                return # прервать выполнение кода, чтобы не злить игрока из-за опечатки
        except:
            await message.answer('что то пошло не так')

    if temp_cards and sum(temp_cards.values()) <= 3:
        await message.answer(f'ты выбираешь карты:\n{", ".join(f"{card} - {cards_number}" for card, cards_number in temp_cards.items())}')
        await message.bot.send_message(group_chat_id,
            f'{config.href(user.username, full_name)} выложил {sum(temp_cards.values())} {config.trump_card[group_chat_id][0]}',
            parse_mode="HTML", disable_web_page_preview=True)

        # вычитать использованные карты у игрока
        config.participants[group_chat_id][user.username]["cards"] = dict(Counter(user_cards) - Counter(temp_cards))
        user_cards = config.participants[group_chat_id][user.username]["cards"]
        await message.answer(
            f'оставшиеся карты:\n{", ".join(f"{card} - {cards_number}" for card, cards_number in user_cards.items())}')

        temp_cards["full_name"] = user.full_name # полное имя, чтобы было легче к нему обратиться
        config.cards[group_chat_id] = {user.username: temp_cards}  # общая колода карт для проверки

        # отправить кнопку с решением верить игроку или нет
        trust_button = InlineKeyboardButton(text="не верю", callback_data="not_trust_button_pressed")
        keyboard = InlineKeyboardMarkup(inline_keyboard=[[trust_button]])
        await message.bot.send_message(group_chat_id, 'верить или нет?', reply_markup=keyboard)



# JoJo reference
async def jojo_reference(message):
    user_text = message.text.lower()

    if user_text.lower() == "стоять, я все еще могу поднимать ставку!":
        await message.answer_animation('https://i.gifer.com/Oq7.gif', caption='R-R-R-R-R-R-R-R-RAISE? ТЕБЕ БОЛЬШЕ НЕЧЕГО СТАВИТЬ!')



@router.callback_query(F.data == "not_trust_button_pressed")
# 💥 я тебе не верю! ты несешь х#йню!
async def liar(callback: CallbackQuery):
    message = callback.message
    group_chat_id = callback.message.chat.id
    user = callback.from_user

    # имя и полное имя игрока, которого хотят проверить
    name_for_check, data_check = next(iter(config.cards[group_chat_id].items()))

    await message.answer(f'{config.href(user.username, user.full_name)} хочет проверить игрока '
                         f'{config.href(name_for_check, data_check["full_name"])}',
                            parse_mode="HTML", disable_web_page_preview=True)

    if "devil" in data_check.keys(): # если игрок выбрал карту дьявола
        await message.answer(f'{config.href(name_for_check, data_check["full_name"])} кинул карту дьявола\n'
                             'все игроки должны сыграть в русскую рулетку', parse_mode="HTML", disable_web_page_preview=True)

        # нужно обернуть participants в list(), потому что participants будет меняться во время итерации
        for player, data in list(config.participants[group_chat_id].items()): # русская рулетка
            if player != name_for_check:
                await revolver_func(message, player, group_chat_id) # русская рулетка
        await start_liars_bar_game(message)  # раздать карты игрокам
        config.cards[group_chat_id] = {}  # освободить колоду карт, создав пустой словарь
        return

    # в эту переменную записываются карты не являющиеся козырем
    extra_cards = list(set(config.cards[group_chat_id][name_for_check].keys()) - set(config.trump_card[group_chat_id]))
    extra_cards.remove("full_name") # этот ключ нужен был для легкого доступа к полному имени подсудимого игрока
    if len(extra_cards) == 1 and "joker" in extra_cards: # отправил ли подсудимый джокера
        await message.answer(f'{config.href(name_for_check, data_check["full_name"])} выложил карту джокера\n'
                             f'{config.href(user.username, user.full_name)} должен сыграть в русскую рулетку',
                             parse_mode="HTML", disable_web_page_preview=True)

        await revolver_func(message, user.username, group_chat_id) # русская рулетка
        await start_liars_bar_game(message)  # раздать карты игрокам
        config.cards[group_chat_id] = {}  # освободить колоду карт, создав пустой словарь
        return

    if extra_cards: # подсудимый курт кобейнится
        for extra_card in extra_cards:
            await message.answer(f'{config.href(name_for_check, data_check["full_name"])} выложил карту:\n'
                                 f'{extra_card}\n\n{config.href(name_for_check, data_check["full_name"])} должен сделать выстрел',
                                 parse_mode="HTML", disable_web_page_preview=True)

        await revolver_func(message, name_for_check, group_chat_id) # русская рулетка
        await start_liars_bar_game(message)  # раздать карты игрокам
        config.cards[group_chat_id] = {}  # освободить колоду карт, создав пустой словарь
    else: # неверующий курт кобейнится
        await message.answer(f'{config.href(name_for_check, data_check["full_name"])} выбрал карту: '
                             f'{config.trump_card[group_chat_id][0]}\n{config.href(user.username, user.full_name)}'
                             f' должен засунуть револьвер в рот', parse_mode="HTML", disable_web_page_preview=True)

        await revolver_func(message, user.username, group_chat_id)  # русская рулетка
        await start_liars_bar_game(message)  # раздать карты игрокам
        config.cards[group_chat_id] = {}  # освободить колоду карт, создав пустой словарь

    await message.bot.delete_message(group_chat_id, message.message_id)



# русская рулетка
async def revolver_func(message, player_name, chat_id):
    player_shots = config.participants[chat_id][player_name]["shots"]
    shot = random.choice(player_shots) # выстрел
    player_full_name = config.participants[chat_id][player_name]["full_name"]
    random.seed(time.time())  # обновлять сид каждый раз для лучшей рандомности

    if shot == 1:
        await message.answer(f'игрок {config.href(player_name, player_full_name)} помер 🔫\n'
                             'он выбывает из игры', parse_mode="HTML",
                             disable_web_page_preview=True)

        # удалить выбывшего игрока из списка игроков
        config.participants[chat_id].pop(player_name, None)
        config.user_ids[chat_id].pop(player_name, None)

        if len(config.participants[chat_id]) == 1: # определение победителя
            for player, data in config.participants[chat_id].items():
                await message.answer(f'{config.href(player, data["full_name"])} побеждает',
                                     parse_mode="HTML", disable_web_page_preview=True)
            await config.end_game_func(message, chat_id)
            return
    else:
        player_shots.remove(shot)
        await message.answer(f'{config.href(player_name, player_full_name)} выжил 😩\n'
                             f'патронов в револьвере осталось: {len(player_shots)}',
                             parse_mode="HTML", disable_web_page_preview=True)

    for player, data in config.participants[chat_id].items():  # очистить карты игроков, чтобы раздать новые
        data["cards"] = {}

# отправка правил игры
async def send_rules(message):
    await message.answer(config.games['Бар Лжецов'], parse_mode="HTML")