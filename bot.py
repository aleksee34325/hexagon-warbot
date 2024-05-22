import math
import logging
from telegram import Update
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackContext
from PIL import Image, ImageDraw, ImageFont
import random
import time

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

QUESTIONS = [
    ('Что является столицей России?', 'Москва'),
    ('Какова площадь прямоугольника с длиной 5 см и шириной 3 см?', '15 см²'),
    ('Кто написал роман "Война и мир"?', 'Лев Толстой'),
    ('В каком году началась Великая Отечественная война?', '1941'),
    ('Как называется процесс перехода воды из жидкого состояния в газообразное?', 'Испарение'),
    ('Как называется самая длинная река в мире?', 'Амазонка'),
    ('Кто является автором теории относительности?', 'Альберт Эйнштейн'),
    ('Какое химическое вещество является основным компонентом поваренной соли?', 'Хлорид натрия'),
    ('Как называется геометрическая фигура с четырьмя равными сторонами и четырьмя равными углами?', 'Квадрат'),
    ('Какое животное является символом Австралии?', 'Кенгуру'),
    ('Как называется основной закон электричества, описывающий зависимость силы тока, напряжения и сопротивления?', 'Закон Ома'),
    ('Какое слово в русском языке обозначает и музыкальное произведение, и крепость?', 'Соната'),
    ('Какой элемент является основным в органических соединениях?', 'Углерод'),
    ('В каком году был подписан Пакт Молотова-Риббентропа?', '1939'),
    ('Кто является автором романа "Преступление и наказание"?', 'Фёдор Достоевский'),
    ('Какое небесное тело является центром нашей Солнечной системы?', 'Солнце'),
    ('Какое озеро является самым глубоким в мире?', 'Байкал'),
    ('Какой математический знак используется для обозначения разности?', 'Минус'),
    ('Кто написал "Евгения Онегина"?', 'Александр Пушкин'),
    ('В какой стране находится Великая китайская стена?', 'Китай'),
]


def generate_field(rows, cols):
    field = {}
    for row in range(rows):
        for col in range(cols):
            cell = f"{chr(65 + row)}{col + 1}"
            field[cell] = {'answered': False, 'owner': None, 'color': None}
    return field

def draw_field(field, rows, cols):
    image_size = 400
    hex_size = image_size / (2 * cols)
    image = Image.new('RGB', (image_size, image_size), 'white')
    draw = ImageDraw.Draw(image)
    font = ImageFont.load_default()

    for row in range(rows):
        for col in range(cols):
            cell = f"{chr(65 + row)}{col + 1}"
            center = (
                image_size * (col + 1) / (cols + 1),
                image_size * (row + 1) / (rows + 1)
            )
            color = field[cell]['color'] if field[cell]['answered'] else 'grey'
            draw_hexagon(draw, center, hex_size, color)
            draw.text((center[0] - 10, center[1] - 10), cell, font=font, fill='black')

    field_image_path = 'field.png'
    image.save(field_image_path)
    return field_image_path

def draw_hexagon(draw, center, size, fill):
    angle_deg = 60
    angle_rad = math.pi / 180 * angle_deg
    points = [
        (center[0] + size * math.cos(angle_rad * i), center[1] + size * math.sin(angle_rad * i))
        for i in range(6)
    ]
    draw.polygon(points, outline='black', fill=fill)

def start(update: Update, context: CallbackContext) -> None:
    user = update.effective_user
    if 'players' not in context.bot_data:
        context.bot_data['players'] = []
        context.bot_data['field'] = generate_field(6, 6)
        context.bot_data['player_colors'] = {}
        context.bot_data['player_scores'] = {}
    if user.id not in context.bot_data['players']:
        context.bot_data['players'].append(user.id)
    update.message.reply_text(f'Добро пожаловать, {user.first_name}! Начнем викторину!')
    send_field(update, context)

def send_field(update: Update, context: CallbackContext) -> None:
    field_image_path = draw_field(context.bot_data['field'], 6, 6)

    with open(field_image_path, 'rb') as field_image:
        for player_id in context.bot_data['players']:
            field_image.seek(0)
            context.bot.send_photo(chat_id=player_id, photo=field_image)
    send_scores(update, context)

def handle_cell_selection(update: Update, context: CallbackContext) -> None:
    user_id = update.effective_user.id
    cell = update.message.text.upper()
    if cell in context.bot_data['field']:
        cell_owner = context.bot_data['field'][cell]['owner']
        if cell_owner is None or cell_owner != user_id:
            if 'block_time' in context.user_data and time.time() < context.user_data['block_time']:
                update.message.reply_text("Вы заблокированы на 15 секунд из-за неправильного ответа.")
            else:
                context.user_data['selected_cell'] = cell
                question, answer = random.choice(QUESTIONS)
                context.user_data['current_question'] = (question, answer)
                update.message.reply_text(f"Вопрос: {question}")
        elif cell_owner == user_id:
            update.message.reply_text("Эта клетка уже захвачена вами.")
    else:
        update.message.reply_text("Неправильный выбор клетки.")

def handle_answer(update: Update, context: CallbackContext) -> None:
    if 'block_time' in context.user_data and time.time() < context.user_data['block_time']:
        return

    user_answer = update.message.text
    question, correct_answer = context.user_data['current_question']

    if user_answer.lower() == correct_answer.lower():
        user_id = update.effective_user.id
        cell = context.user_data['selected_cell']
        cell_owner = context.bot_data['field'][cell]['owner']
        if cell_owner is None:
            context.bot_data['field'][cell]['owner'] = user_id
            context.bot_data['field'][cell]['color'] = context.bot_data['player_colors'].setdefault(user_id, generate_unique_color())
            context.bot_data['field'][cell]['answered'] = True
            
            context.bot_data['player_scores'][user_id] = context.bot_data['player_scores'].get(user_id, 0) + 100
            
            update.message.reply_text(f"Вы захватили клетку {cell}!")
            send_field(update, context)
        elif cell_owner != user_id:
            if 'consecutive_correct_answers' not in context.user_data:
                context.user_data['consecutive_correct_answers'] = 1
                question, answer = random.choice(QUESTIONS)
                context.user_data['current_question'] = (question, answer)
                update.message.reply_text(f"Вопрос: {question}")
            else:
                context.user_data['consecutive_correct_answers'] += 1

            if context.user_data['consecutive_correct_answers'] >= 2:
                context.bot_data['field'][cell]['owner'] = user_id
                context.bot_data['field'][cell]['color'] = context.bot_data['player_colors'].setdefault(user_id, generate_unique_color())
                context.bot_data['field'][cell]['answered'] = True
                
                context.bot_data['player_scores'][user_id] = context.bot_data['player_scores'].get(user_id, 0) + 300
                
                update.message.reply_text(f"Вы захватили клетку {cell}!")
                send_field(update, context)
                context.user_data['consecutive_correct_answers'] = 0
            else:
                update.message.reply_text(f"Правильно! Ответьте правильно еще раз, чтобы захватить клетку.")
    else:
        context.user_data['consecutive_correct_answers'] = 0
        update.message.reply_text(f"Неправильно! Попробуйте снова.")
        context.user_data['block_time'] = time.time() + 15

def generate_unique_color():
    return '#' + ''.join([random.choice('0123456789ABCDEF') for _ in range(6)])

def send_scores(update: Update, context: CallbackContext) -> None:
    scores_message = "Текущие очки:\n"
    for player_id, score in context.bot_data['player_scores'].items():
        user_info = context.bot.get_chat(player_id)
        user_name = user_info.username if user_info.username else user_info.first_name
        scores_message += f"Игрок {user_name}: {score}\n"
    update.message.reply_text(scores_message)

def error(update: Update, context: CallbackContext) -> None:
    logger.warning(f'Update {update} caused error {context.error}')

def main() -> None:
    updater = Updater("6916710859:AAH3Pu4LMNpni46X_V-EoYg_o_P_YN-k41w")

    dispatcher = updater.dispatcher
    dispatcher.add_handler(CommandHandler("start", start))
    dispatcher.add_handler(MessageHandler(Filters.text & ~Filters.command & Filters.regex(r'^[A-F][1-6]$'), handle_cell_selection))
    dispatcher.add_handler(MessageHandler(Filters.text & ~Filters.command, handle_answer))
    dispatcher.add_error_handler(error)

    updater.start_polling()
    updater.idle()

if __name__ == '__main__':
    main()
