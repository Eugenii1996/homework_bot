import logging
import os
import sys
import requests
import telegram
import time

from http import HTTPStatus

from json.decoder import JSONDecodeError

from telegram.ext import Updater

from dotenv import load_dotenv

load_dotenv()


PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

RETRY_TIME = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}


HOMEWORK_STATUSES = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}

logging.basicConfig(
    format='%(asctime)s - %(levelname)s - %(message)s',
    filename='homework.log',
    level=logging.DEBUG)


def send_message(bot, message):
    """Отправка сообщения."""
    try:
        bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)
        logging.info(message)
    except Exception as error:
        message = f'Ошибка отправки сообщения: {error}'
        logging.error(message)
        raise Exception(message)


def get_api_answer(current_timestamp):
    """Отправка запроса к эндпоинту API-сервиса."""
    timestamp = current_timestamp or int(time.time())
    try:
        response = requests.get(
            ENDPOINT, headers=HEADERS, params={'from_date': timestamp}
        )
        if response.status_code != HTTPStatus.OK:
            message = 'API-сервис недоступен'
            logging.error(message)
            raise Exception(message)
        return response.json()
    except JSONDecodeError:
        message = 'Эндпоинт API-сервиса не доступен'
        logging.error(message)
        raise JSONDecodeError(message)
    except Exception as error:
        message = f'Ошибка обращения к API: {error}'
        logging.error(message)
        raise Exception(message)


def check_response(response):
    """Проверка корректности ответа API."""
    if not isinstance(response, dict):
        message = 'В ответе API отсутствует словарь'
        logging.error(message)
        raise TypeError(message)
    if 'homeworks' not in response:
        message = 'Ключ "homeworks" не найден'
        logging.error(message)
        raise KeyError(message)
    if not isinstance(response.get('homeworks'), list):
        message = 'Значение для ключа "homeworks" не список'
        logging.error(message)
        raise TypeError(message)
    return response.get('homeworks')


def parse_status(homework):
    """Получение статуса конкретной домашней работы."""
    homework_name = homework.get('homework_name')
    homework_status = homework.get('status')
    if homework_status in HOMEWORK_STATUSES:
        verdict = HOMEWORK_STATUSES[homework_status]
    else:
        message = 'Ключ не найден'
        logging.error(message)
        raise KeyError(message)
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def check_tokens():
    """Проверка доступности переменных окружения."""
    tokens = [PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID]
    for token in tokens:
        if token is None or token == "":
            logging.critical(
                'Переменная окружения {} не найдена либо пуста!'.format(token)
            )
            return False
    return True


def main():
    """Основная логика работы бота."""
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    current_timestamp = int(time.time())
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.DEBUG)
    handler = logging.StreamHandler(stream=sys.stdout)
    logger.addHandler(handler)
    updater = Updater(token=TELEGRAM_TOKEN)
    updater.start_polling(poll_interval=600.0)
    check_tokens()
    while True:
        try:
            response = get_api_answer(current_timestamp)
            homeworks = check_response(response)
            if len(homeworks) != 0:
                homework = homeworks[0]
                message = parse_status(homework)
                send_message(bot, message)
            current_timestamp = response.get('current_date')
            time.sleep(RETRY_TIME)

        except Exception as error:
            old_massage = ''
            message = f'Сбой в работе программы: {error}'
            logging.error(message)
            if message != old_massage:
                send_message(bot, message)
            old_massage = message
            time.sleep(RETRY_TIME)
        else:
            logging.debug('Статус работы не изменен')
            time.sleep(RETRY_TIME)


if __name__ == '__main__':
    main()
