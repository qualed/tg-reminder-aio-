import os
from datetime import datetime, timedelta, timezone
from dateutil import parser
from aiogram import Bot, Dispatcher, types, F
from aiogram.types import Message
from aiogram.filters import Command
from aiogram.utils.keyboard import ReplyKeyboardBuilder
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from dotenv import load_dotenv
from pytz import timezone
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext

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

class TaskStates(StatesGroup):
    waiting_for_task = State()
    waiting_for_tz = State()

@dp.message(Command("start"))
async def start(message: Message):
    # Создаем клавиатуру
    builder = ReplyKeyboardBuilder()
    builder.button(text="📝 Добавить задачу")
    builder.button(text="📋 Мои задачи")
    builder.button(text="🗑 Удалить задачу")
    builder.button(text="⚙ Настройки")

    # Генерируем ReplyKeyboardMarkup
    keyboard = builder.as_markup(resize_keyboard=True)
    await message.answer('Привет. Тут ты можешь поставить себе напоминание. '
                         'Нажми \n"📝 Добавить задачу"',
                         reply_markup=keyboard)
    
@dp.message(F.text == "📝 Добавить задачу")
async def ask_for_task(message: Message, state: FSMContext):
    await message.answer("Введити задачу, например: Запись к врачу 17.05.25 14:00")
    await state.set_state(TaskStates.waiting_for_task)

@dp.message(Command("addtask"))
async def comand_addtask(message: Message, state: FSMContext):
    await add_task(message, state)
    
@dp.message(TaskStates.waiting_for_task)
async def btn_addtask(message: Message, state: FSMContext):
    await add_task(message, state)

# Прикольная фишка, но вряд ли используем на практике. если await state.set_state(...) выполнится с задержкой,
#   и обработчик не сработает:
# @dp.message()
# async def catch_any_message(message: Message, state: FSMContext):
#     current_state = await state.get_state()
#     if current_state == TaskStates.waiting_for_task:
#         await btn_addtask(message, state)  
#     else:
#         await message.answer("Я не понял. Используйте кнопки или команды!")
    
@dp.message(TaskStates.waiting_for_tz)
async def add_tz(message: Message, state: FSMContext):
    try:
        tz_str = message.text.split()[-1].upper()
        offset = int(tz_str.replace("МСК", "").replace("+", ""))
        users_tz[message.from_user.id] = offset
        await message.answer("Часовой пояс успешно установлен")  
        await message.answer("Введити задачу, например: Запись к врачу 17.05.25 14:00")
        await state.set_state(TaskStates.waiting_for_task)
    except:
        await message.answer("Введити часовой пояс в формате: МСК+3, МСК0, МСК-1")  

async def add_task(message: Message, state: FSMContext):
    global task_id
    user_id = message.from_user.id
    user_tz = users_tz.get(user_id)
    if user_tz:
        try:
            task_str = message.text.split()
            if task_str[0] == "/addtask":
                task_str = task_str[1:]
            date_str = task_str[-2].replace("/", ".").replace("-", ".")
            time_str = task_str[-1].replace(".", ":")
            desc = " ".join(task_str[:-2])
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
            await state.clear()
        except:
            await message.answer('Неверный формат. Пример: "Сходить в магазин 20.07.25 19:00"')
    else:
        await message.answer('Давайте определим ваш часовой пояс. Введите разницу с МСК: "МСК+3"')
        await state.set_state(TaskStates.waiting_for_tz)

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