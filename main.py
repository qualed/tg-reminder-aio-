import os
from datetime import datetime, timedelta, timezone
from dateutil import parser
from aiogram import Bot, Dispatcher, types
from aiogram.types import Message
from aiogram.filters import Command
from aiogram.utils.keyboard import ReplyKeyboardBuilder
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from dotenv import load_dotenv
from pytz import timezone

load_dotenv()
TOKEN = os.getenv("BOT_TOKEN")

bot = Bot(token=TOKEN)
dp = Dispatcher()
scheduler = AsyncIOScheduler()

# Хранилище задач и часовых поясов
tasks = {}
task_id = 0
users_tz = {}
#moscow_tz = timezone('Europe/Moscow')

@dp.message(Command("start"))
async def start(message: Message):
    await message.answer("Привет. Тут ты можешь поставить себе напоминание. "
                         "Используй /addtask [описание] [дата ДД.ММ.ГГ ЧЧ:ММ] чтобы добавить задачу.")

@dp.message(Command("addtz"))
async def add_tz(message: Message):
    try:
        tz_str = message.text.split()[-1].upper()
        offset = int(tz_str.replace("МСК", "").replace("+", ""))
        users_tz[message.from_user.id] = offset
        await message.answer("Часовой пояс успешно установлен")  
    except:
        await message.answer("Введити часовой пояс в формате: МСК+3, МСК0, МСК-1")  

@dp.message(Command("addtask"))
async def add_task(message: Message):
    global task_id
    user_id = message.from_user.id
    user_tz = users_tz.get(user_id)
    if user_tz:
        try:
            task_str = message.text.split()
            date_str = task_str[-2].replace("/", ".").replace("-", ".")
            time_str = task_str[-1].replace(".", ":")
            desc = " ".join(task_str[1:-2])
            if len(date_str.split(".")) == 2:
                date_str += f".{datetime.now().year}"
            usertime_p = parser.parse(f"{date_str} {time_str}", dayfirst=True)
            offset = users_tz[user_id]
            #datetime_p = usertime_p.astimezone(moscow_tz) - timedelta(hours=offset)
            datetime_p = usertime_p - timedelta(hours=offset) + timedelta(hours=1)
            
            tasks.setdefault(user_id, {})[task_id] = {
                'desc': desc,
                'datetime': usertime_p
            }
            
            scheduler.add_job(remind, "date", run_date=datetime_p, args=[task_id, user_id])
            task_id += 1
            await message.answer("Задача успешно добавлена.")
        except:
            await message.answer("Неверный формат. Пример: /addtask Сходить в магазин 20.07.25 19:00")
    else:
        await message.answer("Давайте определим ваш часовой пояс. Введите /addtz Мск +-?")

async def remind(task_id: int, user_id: int):
    task = tasks.get(user_id, {}).get(task_id)
    if task:
        await bot.send_message(user_id, f"Напоминание: {task['desc']}")
        del tasks[user_id][task_id]

@dp.message(Command("mytasks"))
async def my_tasks(message: Message):
    user_id = message.from_user.id
    if user_id in tasks and tasks[user_id]:
        all_tasks_str = "\n".join(
            [f"{task_data['desc']} {task_data['datetime'].strftime('%d.%m.%Y %H:%M')} ID[{task_id}]"
             for task_id, task_data in tasks[user_id].items()]
        )
        await message.answer(f"Ваши задачи:\n{all_tasks_str}")
    else:
        await message.answer("У вас нет запланированных задач.")

@dp.message(Command("deltask"))
async def del_task(message: Message):
    try:
        task_id = int(message.text.split()[1])
        user_tasks = tasks.get(message.from_user.id, {})
        if task_id in user_tasks:
            del user_tasks[task_id]
            await message.answer(f"Задача {task_id} удалена")
        else:
            await message.answer("Такой задачи нет")
    except:
        await message.answer("Введите ID задачи")

async def main():
    scheduler.start()
    await dp.start_polling(bot)

if __name__ == "__main__":
    import asyncio #тут, чтобы не грузить память при импорте как модуль в другой скрипт. но не критично
    asyncio.run(main())