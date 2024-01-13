import datetime
from dotenv import load_dotenv
import sqlite3
from aiogram import Bot, Dispatcher, types
from aiogram.utils import executor
from telethon.sync import TelegramClient
from telethon.tl.functions.channels import GetParticipantsRequest
from telethon.tl.types import ChannelParticipantsSearch
import configparser
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
import json
import yaml
import xml.etree.ElementTree as ET

load_dotenv()

config = configparser.ConfigParser()
config.read("config.ini")

api_id = config['Telegram']['api_id']
api_hash = config['Telegram']['api_hash']
username = config['Telegram']['username']
bot_token = config['Telegram']['bot_token']

bot = Bot(token=bot_token, parse_mode=types.ParseMode.HTML)
dp = Dispatcher(bot, storage=MemoryStorage())

client = TelegramClient(username, api_id, api_hash)
client.start()


class Form(StatesGroup):
    url = State()


async def dump_all_participants(channel):
    global all_users_details
    offset_user = 0
    limit_user = 100

    all_participants = []
    filter_user = ChannelParticipantsSearch('')

    while True:
        participants = await client(GetParticipantsRequest(channel,
                                                           filter_user, offset_user, limit_user, hash=0))
        if not participants.users:
            break
        all_participants.extend(participants.users)
        offset_user += len(participants.users)

    all_users_details = []

    for participant in all_participants:
        all_users_details.append({"id": participant.id,
                                  "first_name": participant.first_name,
                                  "username": participant.username,
                                  "phone": participant.phone})

    conn = sqlite3.connect('users/users.sql')
    cur = conn.cursor()

    cur.execute('SELECT id FROM "%s"' % channel_title)
    cor_users_id = cur.fetchall()
    users_id = []
    for i in cor_users_id:
        for j in i:
            users_id.append(j)

    for i in all_users_details:
        try:
            if i.get('id') in users_id:
                continue
            else:
                cur.execute('INSERT INTO "%s"(id, first_name, username, phone) VALUES ("%s","%s", "%s","%s")' %
                            (channel_title, i.get('id'), i.get('first_name'), i.get('username'), i.get('phone')))
        except:
            continue
    conn.commit()

    cur.close()
    conn.close()


async def main(url):
    global channel, channel_title
    channel = await client.get_entity(url)

    channel_title = channel.title.strip().replace('\\', '_').strip()

    comn = sqlite3.connect('users/users.sql')
    cur = comn.cursor()

    cur.execute(
        'CREATE TABLE IF NOT EXISTS "%s" (id int, first_name varchar(50), username varchar(50), phone int)' % channel_title)

    comn.commit()
    cur.close()
    comn.close()

    await dump_all_participants(channel)


@dp.message_handler(commands=['start'])
async def handle_text(message: types.Message):
    await message.answer(f'Здраствуй, <b>{message.from_user.first_name}.</b>\n<b>Я grabeer</b>, бот который поможет тебе собрать данные об участниках чата, '
                         f'нажми на <i>/search</i> и следуй инструкциям')


@dp.message_handler(commands=['search'])
async def handle_text(message: types.Message):
    await message.answer('Введите ссылку на чат:')
    await Form.url.set()


@dp.message_handler(state=Form.url)
async def non_stop(message: types.Message, state: FSMContext):
    try:
        url = message.text.strip()
        await message.answer('В процессе...')
        await main(url)
        button = types.InlineKeyboardButton('.txt', callback_data='txt')
        button1 = types.InlineKeyboardButton('.json', callback_data='json')
        button2 = types.InlineKeyboardButton('.yaml', callback_data='yaml')
        button3 = types.InlineKeyboardButton('.db', callback_data='db')
        button4 = types.InlineKeyboardButton('.xml', callback_data='xml')
        markup = types.InlineKeyboardMarkup().row(button, button1, button2, button3, button4)
        await message.answer("Участники сохранены в базе данных.\n\nВ каком формате хотите получить файл?", reply_markup=markup)
        await state.finish()

    except Exception as e:
        await message.answer(f'Введённый текст не является ссылкой на чат')
        with open(f'errors.txt', 'a', encoding='utf8') as outfile:
            outfile.write(f'Дата: {datetime.datetime.now()}\nОшибка: {e}\n\n')
        await state.finish()

@dp.message_handler()
async def none_command(message: types.Message):
    await message.answer('Команда нераспознана, введите\n<i>/search</i> для поиска информации.')


@dp.callback_query_handler()
async def markup_callback(callback: types.CallbackQuery):
    global channel, all_users_details, channel_title
    if callback.data == 'txt':
        await callback.message.answer('В процессе...')

        f = open(f'users/{channel_title}.txt', 'w', encoding='utf-8')
        conn = sqlite3.connect('users/users.sql')
        cur = conn.cursor()

        cur.execute('SELECT first_name, username, phone FROM "%s"' % channel_title)
        result = cur.fetchall()
        for i in result:
            f.write(f'name: {i[0]} ; username: @{i[1]} ; phone: {i[2]}\n\n')
        cur.close()
        conn.close()
        f.close()

        await callback.message.reply_document(open(f'users/{channel_title}.txt', 'rb'))

    elif callback.data == 'json':
        await callback.message.answer('В процессе...')

        with open(f'users/{channel_title}.json', 'w', encoding='utf8') as outfile:
            json.dump(all_users_details, outfile, ensure_ascii=False)

        await callback.message.reply_document(open(f'users/{channel_title}.json', 'rb'))

    elif callback.data == 'db':
        await callback.message.answer('В процессе...')

        conn = sqlite3.connect('users/users.sql')
        cur = conn.cursor()

        cur.execute('SELECT * FROM "%s"' % channel_title)
        result = cur.fetchall()

        cur.close()
        conn.close()

        new_conn = sqlite3.connect(f'users/{channel_title}.db')
        new_cur = new_conn.cursor()

        new_cur.execute('CREATE TABLE IF NOT EXISTS "%s"(id int, first_name varchar(50), username varchar(50), phone int)' % channel_title)
        new_conn.commit()
        new_cur.execute('SELECT id FROM "%s"' % channel_title)
        users_id = new_cur.fetchall()

        new_cur.close()
        new_conn.close()

        new_users_id = []
        for i in users_id:
            for j in i:
                new_users_id.append(j)

        new_new_conn = sqlite3.connect(f'users/{channel_title}.db')
        new_new_cur = new_new_conn.cursor()

        for i in result:
            try:
                if i[0] in new_users_id:
                    continue
                else:
                    new_new_cur.execute('INSERT INTO "%s"(id, first_name, username, phone) VALUES ("%s","%s", "%s","%s")' % (
                        channel_title, i[0], i[1], i[2], i[3]))
            except:
                continue

        new_new_conn.commit()

        new_new_cur.close()
        new_new_conn.close()

        await callback.message.reply_document(open(f'users/{channel_title}.db', 'rb'))

    elif callback.data == 'yaml':
        await callback.message.answer('В процессе...')

        with open(f'users/{channel_title}.yaml', 'w', encoding='utf8') as f:
            yaml.dump(all_users_details, f, allow_unicode=True)
        await callback.message.reply_document(open(f'users/{channel_title}.yaml', 'rb'))

    elif callback.data == 'xml':
        await callback.message.answer('В процессе...')

        root = ET.Element("users")

        for participant in all_users_details:
            participant_element = ET.SubElement(root, str(participant.get('username')))

            ET.SubElement(participant_element, "id").text = str(participant.get('id'))

            ET.SubElement(participant_element, "first_name").text = str(participant.get('first_name'))

            ET.SubElement(participant_element, "username").text = str(participant.get('username'))

            ET.SubElement(participant_element, "phone").text = str(participant.get('phone'))

        tree = ET.ElementTree(root)

        tree.write(f'users/{channel_title}.xml')

        await callback.message.reply_document(open(f'users/{channel_title}.xml', 'rb'))


if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)
