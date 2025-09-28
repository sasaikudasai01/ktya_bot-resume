import json
from games import kto_ya, spy, bunker, liars_bar
from openai import OpenAI
import random
import time
from aiogram import Bot
import asyncio

BOT_TOKEN_SHINOBU ='' # main shinobu
BOT_TOKEN_RUMI ='' # main rumi

OPENAI_GPT_API = ''

# test tokens
TEST_TOKEN_SHINOBU ='' # test shinobu
TEST_TOKEN_RUMI ='' # test rumi

# нужно менять эти переменные для теста ботов, чтобы не отключать основные
CURRENT_BOT_TOKEN_SHINOBU = BOT_TOKEN_SHINOBU # current shinobu (main or test)
CURRENT_BOT_TOKEN_RUMI = BOT_TOKEN_RUMI # current rumi (main or test)

bot_shinobu = Bot(token=CURRENT_BOT_TOKEN_SHINOBU) # шинобу
bot_rumi = Bot(token=CURRENT_BOT_TOKEN_RUMI) # руми

# ссылки на <игры>.py
game_modules = {
    "kto_ya": kto_ya,
    "bunker": bunker,
    "spy": spy,
    "liars_bar": liars_bar
}

ai_memory = {} # память для ии
last_reply = {}

current_game = {} # текущая игра
participants = {} # словарь участников
user_ids = {} # id пользователей, чтобы отправлять им личные сообщения
players = {} # список кнопок с именами участников для голосования

who_list = {} # словарь слов кто я, шпион и бункер
location = {} # локация для игры "Шпион"

cards = {} # карты для Liar's Bar
trump_card = {}

download_urls = {} # ссылки по которым должна качать руми

ban_ids = ['7638221884', '882735772', '1332064220'] # ban

with open("rules.json", "r", encoding="utf-8") as f: # прочитать файл с правилами игр
    data = json.load(f)
# записать правила в переменную
games = {
    "Кто Я": data['kto_ya'].replace("'", '"'),  # заменить одинарные кавычки на двойные
    "Шпион": data['spy'].replace("'", '"'),
    "Бункер": data['bunker'].replace("'", '"'),
    "Бар Лжецов": data['liars_bar'].replace("'", '"')
}

# прочитать файл с личностью шинобу
with open("personality.txt", "r", encoding="utf-8") as f:
    shinobu_content = f.read()

# прочитать файл с личностью руми
with open("personality_rumi.txt", "r", encoding="utf-8") as f:
    rumi_content = f.read()

# "режиссер" для ии, в ключ нужно прописывать ник бота
gpt_content = {'playful_shinobu_bot': f'Ты Telegram-бот, с помощью тебя люди играют в игры из {games}. твоя личность {shinobu_content}. если тебя попросят рассказать'
                                      f' правила, то расскажи правила используя информацию из {games}. ведущего у игр нет, им разве'
                                      ' что можно назвать только тебя, потому что ты рассылаешь игрокам слова. можешь перефразировать, менять'
                                      ' структуру, но главное передать всю суть. в шпионе если что ты выбираешь только одну локацию,'
                                      'ее ты отправляешь всем участникам кроме шпиона. отвечай коротко.'
                                      f'твоя сестра Руми, вот какая она: {rumi_content}, НИКОГДА НЕ ПУТАЙ ЕЕ С СОБОЙ, ТЫ ШИНОБУ.'
                                      f'ты японка, поэтому иногда используй "~" в конце, как это делают японцы в переписках.'
                                      'если решишь использовать форматирование, то используй ТОЛЬКО допустимые HTML-теги Telegram:\n'
                                      '- <b>, <i>, <u>, <s>, <code>, <pre>, <a href="...">, <span class="tg-spoiler">\n'
                                      '- Никаких вложенных тегов.\n'
                                      '- Не используй другие теги, CSS или стили.\n'
                                      '- Каждый тег должен быть корректно закрыт.\n'
                                      '- Генерируй чистый HTML без Markdown, без *, без \\.\n'
                                      '- Структура ответа должна быть читаемой в Telegram.\n'
                                      'все остальные способы форматирования СТОРОГО запрещены. ** заменяй на <b>. используй форматирование HTML чаще.'
                                      'говори очень КОРОТКО и только по делу.',
               'rumi_wave_bot': 'Ты Telegram-бот, с помощью тебя люди могут скачивать видео с ютуба в mp3 формате без каких либо ограничений.'
                                f'твоя личность {rumi_content}'
                                f'твоя сестра Шинобу Ошино, вот какая она: {shinobu_content}, это личность твоей сестры, но НЕ ПУТАЙ ее со своей личностью.'
                                'если решишь использовать форматирование, то используй ТОЛЬКО допустимые HTML-теги Telegram:\n'
                                '- <b>, <i>, <u>, <s>, <code>, <pre>, <a href="...">, <span class="tg-spoiler">\n'
                                '- Никаких вложенных тегов.\n'
                                '- Не используй другие теги, CSS или стили.\n'
                                '- Каждый тег должен быть корректно закрыт.\n'
                                '- Генерируй чистый HTML без Markdown, без *, без \\.\n'
                                '- Структура ответа должна быть читаемой в Telegram.\n'
                                'все остальные способы форматирования СТОРОГО запрещены. ** заменяй на <b>. используй форматирование HTML чаще.'
                                'говори очень КОРОТКО и только по делу.'}

# авто href для ников с гиперссылкой. тут обязательно нужно использовать parse_mode="HTML"
def href(name, fullname):
    return f'<a href="https://t.me/{name}">{fullname}</a>'

# завершение всех игр
async def end_game_func(message, chat_id):
    # очистить все списки для запуска следующей игры
    participants.pop(chat_id, None)
    who_list.pop(chat_id, None)
    user_ids.pop(chat_id, None)
    current_game.pop(chat_id, None)
    location.pop(chat_id, None)

    await message.bot.send_message(chat_id, text="игра завершена")
    print(f'чат {chat_id} завершил все игры')

# генерация ответа
async def gpt_response(message, chat_id, username, user_text, user_id, answer, bot):
    try:
        global OPENAI_GPT_API
        random.seed(time.time())  # обновлять сид каждый раз для лучшей рандомности
        me = await bot.get_me() # bot

        message_id = message.message_id # id сообщения
        thread_id = message.message_thread_id # id треда

        client = OpenAI(
            base_url="https://models.github.ai/inference",
            api_key=OPENAI_GPT_API
        )

        # это нужно, чтобы легче было менять личность и не менять ник в gpt_content при переключении с основного бота на тестового
        # в никах основного и тестового ботов должно быть одинаковое имя, которое прописывается в проверке ниже
        # например @test_SHINOBU_bot для тестового и @playful_SHINOBU_bot для основного бота
        ###
        #response_system_content = (f'{gpt_content[me.username]}.'
        #                           'к тебе сейчас обращается пользователь с ником @{username}')
        ###
        if 'shinobu' in me.username:
            gpt_system_content = gpt_content['playful_shinobu_bot']
        else:
            gpt_system_content = gpt_content['rumi_wave_bot']

        if answer:
            response_system_content = (f'{gpt_system_content}.'
                                       f'ответь на последнее сообщение, сообщение написала твоя сестра.')
        else:
            response_system_content = (f'{gpt_system_content}.'
                                       'к тебе сейчас обращается пользователь с ником @{username}')

        response = client.chat.completions.create(
            model='openai/gpt-4o',
            messages=[
                {"role": "system", "content": response_system_content},  # режиссер для ии
                *ai_memory.get(chat_id, [])  # история диалога
            ],
            temperature=1,
            top_p=1.0,
            max_tokens=2048
        )

        gpt_reply = response.choices[0].message.content  # генерация ответа
        print(f'{message.chat.title}: {username} - {chat_id}: {user_text}\n{me.username}: {gpt_reply}\n')

        # базовые аргументы для отправки сообщения ии
        send_args = {
            "chat_id": chat_id,
            "text": gpt_reply,
            "parse_mode": 'HTML'
        }

        if answer: # если это не ответ другому боту
            send_args['message_thread_id'] = thread_id
        else:
            send_args["reply_to_message_id"] = message_id

        await bot.send_message(**send_args) # отправка ответа нейросети

        if random.choice([0, 1]) == 1 and message.chat.type in ("group", "supergroup"): # bot1 решает ответит ли ему bot2
            # какой бот должен ответить
            if me.username == 'playful_shinobu_bot':
                send_bot = bot_rumi
            else:
                send_bot = bot_shinobu

            try:
                # сохранение ответа bot1 как запрос пользователя, чтобы bot2 смог правильно ответить
                ai_memory[chat_id].append({"role": "user", "content": gpt_reply})
                await gpt_response(message, chat_id, f"@{me.username}", gpt_reply, user_id, True, send_bot)
            except Exception as e:
                if "413" in str(e):  # если уперлась в лимит по запросам
                    ai_memory.pop(chat_id, None)  # сброс памяти
                    ai_memory.setdefault(chat_id, []).append({"role": "user", "content": gpt_reply})  # обновление памяти нейросети
                    await gpt_response(message, chat_id, f"@{me.username}", gpt_reply, user_id, True, send_bot)
        else:
            ai_memory[chat_id].append({"role": "assistant", "content": gpt_reply})
    except Exception as e:
        if "413" in str(e):  # если уперлась в лимит по токенам
            ai_memory.pop(chat_id, None)  # сброс памяти
            await gpt_response(message, chat_id, username, user_text, user_id, False, bot)  # повторный вызов генерации ответа нейросети
        else:
            await message.answer(f'я не могу тебе ответить, но вы можете продолжать играть', reply_to_message_id=message_id)
            print(f'Err: {e}')