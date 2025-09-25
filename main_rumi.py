from logging import exception

from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery, FSInputFile
from aiogram.filters import CommandStart
import asyncio
import random
import config
from aiogram.exceptions import TelegramNetworkError
import time
from yt_dlp import YoutubeDL
import os

random.seed(time.time())

bot = Bot(token=config.BOT_TOKEN_RUMI) # руми
dp_rumi = Dispatcher()

# /start
@dp_rumi.message(CommandStart())
async def start_handler_rumi(message: Message):
    # забанен ли пользователь
    if f'{message.from_user.id}' in config.ban_ids:
        await message.answer('ты забанен')
        return

    await message.answer('отправь мне ссылку на видео')

# функция скачивания аудио с ютуба
async def download_yt(message):
    mp3_button = InlineKeyboardButton(text="mp3", callback_data='mp3_download')
    mp4_button = InlineKeyboardButton(text="mp4", callback_data='mp4_download')
    keyboard = InlineKeyboardMarkup(inline_keyboard=[[mp3_button], [mp4_button]])
    await message.answer('в каком формате скачать?', reply_markup=keyboard, reply_to_message_id=message.message_id)



# вырезать офишал музик видео из названия
async def skobki_remove(title):
    skobki = title
    # получение текста в скобках если есть скобки
    if '(' in title:
        skobki = title.split('(')[1].split(')')[0]
    if '[' in title:
        skobki = title.split('[')[1].split(']')[0]

    replacements = ['official', 'video', 'lyrics',
                    'lyric', 'color', 'hd', 'live',
                    'remaster', 'audio', 'original',
                    'ost', 'soundtrack', 'remastered', 'hq']

    for replacement in replacements:
        # эта проверка нужна, чтобы функция была универсальной, иначе пришлось бы сравнивать каждый вариант вручную, учитывая все варианты заглавных букв
        if replacement in skobki.lower():
            return title.replace(f'({skobki})', '').replace(f'[{skobki}]', '').strip()
    return title

@dp_rumi.callback_query(F.data.endswith('_download'))
async def download_yt_mp3(callback: CallbackQuery):
    message = callback.message
    yt_format = callback.data.replace('_download', '') # какой формат скачать

    is_no_playlist = True # плейлист ли это
    url = config.download_urls[callback.from_user.id]  # ссылка на ютуб видео

    if message.text.startswith('https://youtu.be/'): # работа с укороченными ссылками
        text = message.text.replace('https://youtu.be/', '')
        url = text.split('?')[0].strip() # ссылка на ютуб видео
    elif 'playlist?' in url: # плейлист ли это
        is_no_playlist = False
        if not url.startswith('https://www.youtube.com/'): # поменять ссылку
            text = url.replace('https://', 'https://www.')
            url = text.split('&si')[0].strip() # нормальная ссылка на плейлист

    await message.answer('сейчас скачаю, подожди минутку', reply_to_message_id=config.download_urls['message_id'])

    # если пользователь хочет скачать аудио
    if yt_format == 'mp3':
        ydl_opts_format = 'bestaudio/best'
        ydl_opts_postprocessors = [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',  # формат аудио
            'preferredquality': '192',  # качество после кодирования
        }]
        ydl_opts_outtmpl = 'music'
    else:
        ydl_opts_format = 'bestvideo[ext=mp4][vcodec^=avc1]+bestaudio[ext=m4a]/best[ext=mp4][vcodec^=avc1]'  # попытка получить лучшее видео и аудио в mp4
        ydl_opts_postprocessors = [{
            'key': 'FFmpegVideoConvertor',
            'preferedformat': 'mp4'  # Перекодирует финальный файл
        }]
        ydl_opts_outtmpl = 'video'
        ydl_opts_merge_output_format  = 'mp4'

    # параметры для скачиваемого аудио
    ydl_opts = {
        'format': ydl_opts_format, # качество аудио
        'outtmpl': f'downloads/{ydl_opts_outtmpl}/{message.chat.id}_%(title)s.%(ext)s', # название
        'restrictfilenames': True, # избавление от лишних символов в названии
        'postprocessors': ydl_opts_postprocessors,
        'noplaylist': is_no_playlist,
        'cookiefile': 'cookies.txt',
        'quiet': True
    }
    if yt_format == 'mp4':
        ydl_opts['merge_output_format'] = ydl_opts_merge_output_format

    try:
        with YoutubeDL(ydl_opts) as ydl:
            yt_video_info = ydl.extract_info(url, download=True)
            if 'entries' in yt_video_info: # проверка плейлист ли это
                for entry in yt_video_info['entries']:
                    if entry is None:
                        continue  # иногда бывают пустые entry
                    file_path = os.path.splitext(ydl.prepare_filename(entry))[0] + f'.{yt_format}' # путь к файлу

                    if '(' or '[' in entry['title']:
                        mp34_filename = await skobki_remove(entry['title'])
                    else:
                        mp34_filename = entry['title']

                    yt_file = FSInputFile(file_path, filename=mp34_filename.replace('/', '_'))  # параметры файла для отправки в телегу
                    if yt_format == 'mp3':
                        await asyncio.sleep(5)
                        await message.answer_audio(audio=yt_file, reply_to_message_id=config.download_urls['message_id'])  # отправка аудио файла
                    elif yt_format == 'mp4':
                        await asyncio.sleep(5)
                        await message.answer_video(video=yt_file, reply_to_message_id=config.download_urls['message_id'])  # отправка видео файла
                    os.remove(file_path)  # удаление временного файла после отправки пользователю

            else:
                file_path = os.path.splitext(ydl.prepare_filename(yt_video_info))[0] + f'.{yt_format}' # путь к файлу

                if '(' or '[' in yt_video_info['title']:
                    mp34_filename = await skobki_remove(yt_video_info['title'])
                else:
                    mp34_filename = yt_video_info['title']

                yt_file = FSInputFile(file_path, filename=mp34_filename.replace('/', '_').strip())  # параметры файла для отправки в телегу
                if yt_format == 'mp3':
                    await message.answer_audio(audio=yt_file, reply_to_message_id=config.download_urls['message_id'])

                elif yt_format == 'mp4':
                    await message.answer_video(video=yt_file, reply_to_message_id=config.download_urls['message_id'])
                os.remove(file_path) # удаление временного файла после отправки пользователю

        await bot.delete_message(message.chat.id, callback.message.message_id)

    except Exception as e:
        await message.reply(f'что то пошло не так')
        if '403' in str(e):
            await bot.send_message(988789518, 'нужно обновить кукисы') # уведомить разработчика о том, что нужно обновить кукисы
            await message.reply(f'нужно обновить кукисы. я только что уведомила разработчика об этом, он скоро пофиксит ошибку')
        if 'ERROR: [youtube] JuSsvM8B4Jc: Requested format is not available. Use --list-formats for a list of available formats' in str(e):
            await bot.send_message(988789518, 'нужно обновить yt-dlp')  # уведомить разработчика о том, что нужно обновить yt-dlp
        print(f'Error: {e}')



# функция скачивания тик токов
async def download_tiktok(message):
    url = message.text

    # параметры для скачивания тик токов
    ydl_opts = {
        'format': 'mp4',
        'outtmpl': 'downloads/tiktok/%(id)s.%(ext)s',
        'noplaylist': True,
        'no_warnings': True,
        'restrictfilenames': True,  # избавление от лишних символов в названии
    }

    with YoutubeDL(ydl_opts) as ydl:
        try:
            await message.answer('сейчас скачаю, подожди минутку', reply_to_message_id=message.message_id)
            yt_video_info = ydl.extract_info(url, download=True)
            file_path = ydl.prepare_filename(yt_video_info)
            video = FSInputFile(file_path)  # параметры аудиофайла для отправки в телегу
            await message.answer_video(video=video, reply_to_message_id=message.message_id)  # отправка аудио файла
            os.remove(file_path)  # удаление временного файла после отправки пользователю
        except Exception as e:
            await message.answer('фото скачать не получится', reply_to_message_id=message.message_id)
            print(f'{message.chat.id} пытается скачать тик ток\nError: {e}')



async def download_soundcloud(message):
    url = message.text # ссылка

    ydl_opts = {
        "format": "bestaudio/best",
        "outtmpl": f'downloads/music/{message.chat.id}_%(title)s.%(ext)s',  # сохранить с названием
        "noplaylist": True,
        "hls_prefer_native": True,  # форсируем HLS
        "postprocessors": [
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "192",
            }
        ],
        'restrictfilenames': True,  # избавление от лишних символов в названии
        "allow_unplayable_formats": True # попробует скачать даже "неиграбельные"
    }

    with YoutubeDL(ydl_opts) as ydl:
        try:
            await message.answer('сейчас скачаю, подожди минутку', reply_to_message_id=message.message_id)
            sc_audio_info = ydl.extract_info(url, download=True)
            file_path = os.path.splitext(ydl.prepare_filename(sc_audio_info))[0] + f'.mp3' # путь к файлу
            sc_file = FSInputFile(file_path, filename=sc_audio_info['title'].replace('/', '_'))  # параметры файла для отправки в телегу
            await message.answer_audio(audio=sc_file, reply_to_message_id=message.message_id)
            os.remove(file_path)  # удаление временного файла после отправки пользователю
        except Exception as e:
            await message.answer('не получилось скачать, попробуй отправить другую ссылку', reply_to_message_id=message.message_id)
            print(f'{message.chat.id} кто то пытается скачать аудио из soundcloud\nError: {e}')

# нейросеть ответить
@dp_rumi.message(lambda message: message.text)
async def response_to_message_rumi(message: Message):
    chat_id = message.chat.id
    user = message.from_user
    user_text = message.text.lower()
    message_id = message.message_id
    username = message.from_user.username
    user_id = user.id
    user_full_name = user.full_name

    # скачивание аудио
    if message.text.startswith(('https://www.youtube.com', 'https://youtube.com/', 'https://youtu.be/')):
        print(f'{username} пытается скачать ютуб')

        config.download_urls[user_id] = message.text # сохранить ссылку которую нужно скачать
        config.download_urls['message_id'] = message.message_id # айди сообщения на которое ответит руми
        await download_yt(message)
        return

    elif message.text.startswith(('https://www.tiktok.com/', 'https://vm.tiktok.com/')):
        print(f'{username} пытается скачать тик ток')

        await download_tiktok(message)
        return

    elif message.text.startswith('https://soundcloud.com/'):
        print(f'{username} пытается скачать саундклауд')

        await download_soundcloud(message)
        return

    config.ai_memory.setdefault(chat_id, []).append({"role": "user",
                                                     "content": f'ты руми, говори от лица руми. запрос пользователя - @{username}: {user_text}'}) # обновление памяти нейросети

    is_answer_to_bot = False
    if message.reply_to_message: # отвечает ли пользователь на сообщение нейросети
        if message.reply_to_message.from_user.id == (await bot.me()).id:
            is_answer_to_bot = True

    if user_text.startswith(('руми', '@rumi_wave_bot', 'девочки')) or is_answer_to_bot: # обратился ли пользователь к руми
        await config.gpt_response(message, chat_id, username, user_text, user_id, False, bot)



# запуск руми
async def start_rumi():
    while True:
        try:
            await dp_rumi.start_polling(bot)
        except TelegramNetworkError as e:
            print(f"[Rumi] Потеря связи: {e}. Повтор через 5 секунд...")
            await asyncio.sleep(5)
        except Exception as e:
            print(f"[Rumi] Непредвиденная ошибка: {e}")
            await asyncio.sleep(5)