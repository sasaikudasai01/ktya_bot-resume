from openai import OpenAI
from aiogram import Bot, Dispatcher, types, F
from aiogram.types import Message, InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery
from aiogram.filters import CommandStart
import asyncio
from aiogram.filters import Command
import random
import config
from aiogram.exceptions import TelegramNetworkError
import time
import games # импорт модулей игр
import main_rumi

random.seed(time.time())

bot = Bot(token=config.BOT_TOKEN_SHINOBU)
dp = Dispatcher()

# роутер для модулей игр для корректной работы callback_query
routers = [
    games.kto_ya.router,
    games.spy.router,
    games.bunker.router,
    games.liars_bar.router
]

for router in routers:
    if router.parent_router is None:
        dp.include_router(router)

# /start
@dp.message(CommandStart())
async def start_handler(message: Message):
    chat_id = message.chat.id

    # id чата
    config.participants.setdefault(chat_id, {}) # ключ chat_id в списке игроков
    config.who_list.setdefault(chat_id, {}) # ключ chat_id в списке слов, локаций и карточек бункера
    config.location.setdefault(chat_id, "") # ключ chat_id для локации в игре шпион
    config.user_ids.setdefault(chat_id, {}) # ключ chat_id в списке user_id для отправки сообщений
    config.ai_memory.setdefault(chat_id, {}) # ключ chat_id для памяти нейросети
    config.cards.setdefault(chat_id, {})  # ключ chat_id в списке cards для сохранения карт в игре Liar's Bar

    # перехватывание стартового сообщения другими модулями
    if config.current_game.get(chat_id): # проверка запущена ли какая-то игра
        # динамическая ссылка на модуль игры из config.py через значение current_game
        # во всех модулях игр должна быть функция start_message
        await config.game_modules[config.current_game[chat_id]].start_message(message, chat_id)
        return

    # отправка стартового сообщения
    if message.chat.type in ("group", "supergroup"):
        kto_ya_button = InlineKeyboardButton(text="Кто Я", callback_data="kto_ya")
        spy_button = InlineKeyboardButton(text='Шпион', callback_data='spy')
        bunker_button = InlineKeyboardButton(text='Бункер', callback_data='bunker')
        liars_bar_button = InlineKeyboardButton(text="Liar's Bar", callback_data='liars_bar')
        keyboard = InlineKeyboardMarkup(inline_keyboard=[[kto_ya_button, spy_button], [bunker_button, liars_bar_button]])
        await message.answer('Grand Theft Auto VI start game\n\nВо что будете играть?', reply_markup=keyboard)
    else:
        await message.answer("/start нужно писать в группе, а тут давай я объясню тебе правила")
        await rules_func(message)



# Обработка кнопки "Участвую"
@dp.callback_query(F.data == "participate")
async def participate_handler(callback: CallbackQuery):
    chat_id = callback.message.chat.id
    user = callback.from_user
    username = user.username
    user_full_name = user.full_name

    # добавление нового пользователя
    if username not in config.participants[chat_id]:
        config.participants[chat_id][username] = {}
        config.participants[chat_id][username]["name"] = username
        config.participants[chat_id][username]["full_name"] = user.full_name
        config.participants[chat_id][username]["id"] = user.id
        config.participants[chat_id][username]["word"] = ""
        config.participants[chat_id][username]["is_spy"] = False
        config.participants[chat_id][username]["hint"] = False
        config.participants[chat_id][username]["cards"] = {}
        config.participants[chat_id][username]["voted_people"] = []
        config.participants[chat_id][username]["shots"] = [0, 0, 0, 0, 0, 1]

        config.user_ids[chat_id][username] = user.id

        await callback.answer("ты участвуешь!")
        await callback.message.answer(f'{config.href(username, user_full_name)} участвует',
            parse_mode="HTML", disable_web_page_preview=True)
    else:
        await callback.answer("ты уже участвуешь")



# голосование
@dp.callback_query(F.data == "vote")
async def vote_handler(callback: CallbackQuery):
    chat_id = callback.message.chat.id

    if callback.message.chat.type in ("group", "supergroup"): # проверка, чтобы голосование начинали только в группе
        # во всех модулях игр должна быть функция vote_func
        await callback.message.answer('голосование отправлено вам в лс')
        await config.game_modules[config.current_game[chat_id]].vote_func(callback, chat_id)
        await bot.delete_message(chat_id, callback.message.message_id)

@dp.callback_query(F.data.endswith('_vote'))
async def vote_for_handler(callback: CallbackQuery):
    current_chat_id = callback.message.chat.id # id чата откуда пользователь голосует
    user = callback.from_user

    for chat, users in config.participants.items():
        if user.username in users:
            group_chat_id = chat # id группы

    if config.current_game.get(current_chat_id) == 'spy' or 'bunker':
        # во всех модулях игр должна быть функция vote_for_handler
        await config.game_modules[config.current_game[group_chat_id]].vote_for_handler(callback, group_chat_id, user)



# подсказка
@dp.message(Command("hint"))
async def hint_handler(message: Message):
    user = message.from_user.username
    full_name = message.from_user.full_name

    message_id = message.message_id

    client = OpenAI(base_url="https://api.langdock.com/openai/eu/v1", api_key=config.OPENAI_GPT_API)

    try:
        for chat, players in config.participants.items(): # получить chat_id чтобы подсказку можно было использовать в лс бота
            if user in players:
                chat_id = chat

                # участвует ли пользователь в игре и использовал ли он подсказку
                if config.current_game.get(chat_id, '') == "kto_ya" and not config.participants[chat_id][user]["hint"] and config.participants[chat_id][user]["word"] != "":
                    print(f'{user} использовал подсказку')
                    config.participants[chat_id][user]["hint"] = True

                    response_system_content = (f'{config.gpt_content}.'
                                               'твоя цель - помочь пользователю угадать слово пользователя в игре "кто я"')
                    response_user_content = (f'ты должна дать сложную подсказку к слову {config.participants[chat_id][user]["word"]}.'
                    f'ни в коем случае и ни при каких обстоятельствах не говори само слово {config.participants[chat_id][user]["word"]}')

                elif config.current_game.get(chat_id, '') == "spy" and not config.participants[chat_id][user]["hint"] and config.location[chat_id] != "":
                    print(f'{user} использовал подсказку')
                    config.participants[chat_id][user]["hint"] = True

                    response_system_content = (f'{config.gpt_content}.'
                                               'твоя цель - помочь пользователю угадать слово пользователя в игре "шпион"')
                    response_user_content = (f'ты должна дать сложную подсказку к локации {config.location[chat_id]}.'
                        f'ни в коем случае и ни при каких обстоятельствах не говори саму локацию {config.location[chat_id]}')

                else:
                    await message.answer(f'{config.href(user, full_name)} сейчас пока не получится получить подсказку',
                                        parse_mode="HTML", disable_web_page_preview=True)
                    print(f'{full_name} пытается использовать подсказку')
                    return

                # ответ нейросети
                response = client.chat.completions.create(model="gpt-4o",
                                                        messages=[{"role": "system", "content": response_system_content},
                                                                  {"role": "user", "content": response_user_content}])
                gpt_reply = response.choices[0].message.content
                await bot.send_message(message.chat.id, gpt_reply, reply_to_message_id=message_id)
            break # остановить цикл, чтобы случайно не отправить подсказку другим игрокам
    except:
        await message.answer(f'{config.href(user, full_name)} сейчас пока не получится получить подсказку',
            parse_mode="HTML", disable_web_page_preview=True)
        print(f'{message.from_user.full_name} пытается использовать подсказку')



# я угадал слово?
@dp.message(Command("myword"))
async def myword_handler(message: Message):
    chat_id = message.chat.id
    user = message.from_user
    user_name = user.username
    full_name = user.full_name

    parts = message.text.split(maxsplit=1)  # отделить команду от слова

    if len(parts) > 1:
        word = parts[1]  # слово после команды

        if config.current_game.get(chat_id) == "kto_ya": # если группа играет кто я
            if word.lower() == config.participants[chat_id][message.from_user.username]["word"]: # угадал ли игрок свое слово
                await config.end_game_func(message, chat_id)
                await message.answer(f"{config.href(user_name, full_name)} угадал слово 🦵")
                print(f"{message.from_user.full_name} wins")
            else:
                await message.answer(f"Нет, {config.href(user_name, full_name)}, это неверно")
        elif config.current_game.get(chat_id) == "spy": # если группа играет шпион
            # правильное ли слово ввел игрок и был ли это пион
            if word.lower() == config.location[chat_id] and config.participants[chat_id][user_name]["is_spy"]:
                await message.answer(f'шпион {config.href(user_name, full_name)} угадал локацию 🦵',
                    parse_mode="HTML", disable_web_page_preview=True)
                await config.end_game_func(message, chat_id)
                print(f"{message.from_user.full_name} угадал локацию")
            else: # если слово неправильное или это был не шпион
                await message.answer(f'{config.href(user_name, full_name)} попытался угадать локацию\nвы можете'
                    f' проголосовать за него, но он может быть и не шпионом',
                    parse_mode="HTML", disable_web_page_preview=True)
        elif config.current_game.get(chat_id) == 'bunker':
            try:
                # этот метод я сократил до 6 строк вместо 55, что были раньше...
                await message.answer(f'{config.href(user_name, full_name)} вскрывает карту\n\n'
                                     f'{word} - {config.participants[chat_id][user.username]["cards"][word]}',
                                     parse_mode="HTML", disable_web_page_preview=True)
                print(f'{user.full_name} вскрывает: {word}')
            except KeyError:
                await message.answer(f'{config.href(user_name, full_name)} такой карты не существует',
                                     parse_mode="HTML", disable_web_page_preview=True)



# правила
@dp.message(Command("rules"))
async def rules_handler(message: types.Message):
    await rules_func(message)

async def rules_func(message):
    kto_ya_rules_button = InlineKeyboardButton(text='Кто Я', callback_data='kto_ya_rules')
    spy_rules_button = InlineKeyboardButton(text='Шпион', callback_data='spy_rules')
    bunker_rules_button = InlineKeyboardButton(text='Бункер', callback_data='bunker_rules')
    liars_bar_rules_button = InlineKeyboardButton(text='Бар Лжецов', callback_data='liars_bar_rules')
    keyboard = InlineKeyboardMarkup(inline_keyboard=[[kto_ya_rules_button], [spy_rules_button], [bunker_rules_button], [liars_bar_rules_button]])
    await message.answer('выбери игру', reply_markup=keyboard)

@dp.callback_query(F.data.endswith('_rules'))
async def endswith_rules_handler(callback: CallbackQuery):
    game_name = callback.data.replace('_rules', '') # извлечение название игры из коллбэка

    game = config.game_modules[game_name] # динамическая ссылка на модуль игры из config.py через значение game_name
    await game.send_rules(callback.message) # во всех модулях игр должна быть функция send_rules



# /sendword
@dp.message(Command("sendword"))
async def sendword_handler(message: Message):
    user = message.from_user
    username = user.username
    full_name = user.full_name

    for chat_id, users in config.participants.items():
        if username in users: # участвует ли пользователь в игре или нет
            # sendword для liars_bar нужен для того, чтобы игрок выбрал какую карту кинуть
            # в остальных играх это для отправки слов, локаций и карточек бункера
            game = config.game_modules[config.current_game[chat_id]]
            await game.send_word_func(message, chat_id, username, full_name) # динамический вызов функции отправки слов каждого модуля



# завершить все игры
@dp.callback_query(F.data == "end_game")
async def end_game_handler(callback: CallbackQuery):
    await config.end_game_func(callback.message, callback.message.chat.id)



# нейросеть ответить
@dp.message(lambda message: message.text)
async def response_to_message(message: Message):
    chat_id = message.chat.id
    user = message.from_user
    user_text = message.text.lower()
    message_id = message.message_id
    username = message.from_user.username
    user_id = user.id

    # узнать id чата в котором играет игрок если он играет
    group_chat_id = next((chat for chat, player in config.participants.items() if username in player), None)
    if message.chat.type in ("group", "supergroup"): # обвинить во лжи можно только в группе
        # началась ли игра бар лжецов и раздали ли карты
        if group_chat_id and config.participants[group_chat_id][username]["cards"] and config.current_game[group_chat_id] == "liars_bar":
            await config.game_modules["liars_bar"].jojo_reference(message)
            return

    config.ai_memory.setdefault(chat_id, []).append({"role": "user",
                                                     "content": f'ты шинобу, говори от лица шинобу. запрос пользователя - @{username}: {user_text}'}) # обновление памяти нейросети

    is_answer_to_bot = False
    if message.reply_to_message: # отвечает ли пользователь на сообщение нейросети
        if message.reply_to_message.from_user.id == (await bot.me()).id:
            is_answer_to_bot = True

    if user_text.startswith(('шинобу', '@playful_shinobu_bot', 'девочки')) or is_answer_to_bot: # обратился ли пользователь к шинобу
        await config.gpt_response(message, chat_id, username, user_text, user_id, False, bot)



# запуск шинобу
async def start_shinobu():
    while True:
        try:
            await dp.start_polling(bot)
        except TelegramNetworkError as e:
            print(f"[Shinobu] Потеря связи: {e}. Повтор через 5 секунд...")
            await asyncio.sleep(5)
        except Exception as e:
            print(f"[Shinobu] Непредвиденная ошибка: {e}")
            await asyncio.sleep(5)

# запуск шинобу и руми
async def main():
    await asyncio.gather(
        start_shinobu(),
        main_rumi.start_rumi()
    )

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except:
        print('exit')