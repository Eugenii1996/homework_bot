import logging
import os
import sys
import time

import requests
import telegram
from http import HTTPStatus
from dotenv import load_dotenv

load_dotenv()


PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

RETRY_TIME = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}
GET_IPI_ANSWER_MASSAGE = (
    'При обращении к эндпоинту {ENDPOINT}'
    ' с токеном {PRACTICUM_TOKEN} возникла ошибка, код ответа {status_code}.'
)
PARSE_STATUS_MASSAGE = 'Ключ {status} не найден в словаре HOMEWORK_VERDICTS'


HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}


def send_message(bot, message):
    """Отправка сообщения."""
    try:
        bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)
        logging.info(message)
    except Exception as error:
        raise ConnectionError(f'Ошибка отправки сообщения {message}: {error}')


def get_api_answer(current_timestamp):
    """Отправка запроса к эндпоинту API-сервиса."""
    try:
        response = requests.get(
            ENDPOINT, headers=HEADERS, params={'from_date': current_timestamp}
        )
    except ConnectionError as error:
        raise ConnectionError(f'Ошибка обращения к API: {error}')
    if response.status_code != HTTPStatus.OK:
        raise ConnectionError(
            GET_IPI_ANSWER_MASSAGE.format(
                ENDPOINT=ENDPOINT,
                PRACTICUM_TOKEN=PRACTICUM_TOKEN,
                status_code=response.status_code
            )
        )
    return response.json()


def check_response(response):
    """Проверка корректности ответа API."""
    if not isinstance(response, dict):
        message = 'В ответе API отсутствует словарь'
        raise TypeError(message)
    if 'homeworks' not in response:
        message = 'Ключ "homeworks" не найден'
        raise KeyError(message)
    if not isinstance(response.get('homeworks'), list):
        message = 'Значение для ключа "homeworks" не список'
        raise TypeError(message)
    return response.get('homeworks')


def parse_status(homework):
    """Получение статуса конкретной домашней работы."""
    homework_name = homework.get('homework_name')
    status = homework.get('status')
    if status not in HOMEWORK_VERDICTS:
        raise KeyError(PARSE_STATUS_MASSAGE.format(status=status))
    verdict = HOMEWORK_VERDICTS[status]
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def check_tokens():
    """Проверка доступности переменных окружения."""
    tokens = ['PRACTICUM_TOKEN', 'TELEGRAM_TOKEN', 'TELEGRAM_CHAT_ID']
    for name in tokens:
        token = globals()[name]
        if token is None or token == "":
            logging.critical(
                'Переменная окружения {} '
                'не найдена либо пуста!'.format(name)
            )
            return False
    return True


def main():
    """Основная логика работы бота."""
    logging.basicConfig(
        format=(
            '%(asctime)s - %(levelname)s '
            '- %(message)s - %(funcName)s - %(lineno)d'
        ),
        handlers=[logging.FileHandler(filename=(__file__ + '.log')),
                  logging.StreamHandler(stream=sys.stdout)],
        level=logging.DEBUG)
    check_tokens()
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    current_timestamp = int(time.time())
    while True:
        try:
            response = get_api_answer(current_timestamp)
            homeworks = check_response(response)
            if len(homeworks) != 0:
                homework = homeworks[0]
                message = parse_status(homework)
                send_message(bot, message)
            current_timestamp = response.get('current_date', current_timestamp)
        except Exception as error:
            old_massage = ''
            message = f'Сбой в работе программы: {error}'
            logging.exception(message)
            if message != old_massage:
                try:
                    send_message(bot, message)
                    old_massage = message
                except (telegram.error.TelegramError, Exception) as error:
                    message = f'Не удалось отправить сообщение: "{error}"'
                    logging.error(message)
        time.sleep(RETRY_TIME)


if __name__ == '__main__':
    main()
