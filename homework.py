import logging
import os
import sys
import time
from http import HTTPStatus

import requests
import telegram
from dotenv import load_dotenv

load_dotenv()


PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

RETRY_TIME = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}
TOKENS = ('PRACTICUM_TOKEN', 'TELEGRAM_TOKEN', 'TELEGRAM_CHAT_ID')
GET_API_ANSWER_STATUS_ERROR_MASSAGE = (
    'При обращении к эндпоинту {endpoint}'
    ' с заголовком {header} и параметрами {params} '
    'возникла ошибка, код ответа {status_code}.'
)
CONNECTION_ERROR = (
    'Ошибка обращения к API: {error} c эндпоинтом '
    '{enpoint}, заголовком {header} и параметрами {params}'
)
KEY_ERROR = (
    'Получен json со значением {value} по ключу {key}, с эндпоинтом '
    '{enpoint}, заголовком {header} и параметрами {params}'
)
PARSE_STATUS_MASSAGE = (
    'Получен неожиданный статус {status} проверки домашней работы'
)
PARSE_STATUS_CHANGE_MESSAGE = (
    'Изменился статус проверки работы "{name}". '
    '{verdict}'
)
SEND_MESSAGE_ERROR = 'Ошибка отправки сообщения {message}: {error}'
CHECK_RESPONCE_NOT_DICT = 'В ответе API отсутствует словарь'
CHECK_RESPONCE_KEY_NO_IN_RESPONSE = 'Ключ "homeworks" не найден'
CHECK_RESPONCE_KEY_NOT_LIST = 'Значение для ключа "homeworks" не список'
CHECK_TOKENS_MESSAGE = 'Переменная окружения {name} не найдена либо пуста!'
MAIN_EXCEPTION_MASSAGE = 'Сбой в работе программы: {error}'
TOKENS_ERROR = 'Недостаточно переменных окружения для работы программы'


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
        return True
    except (telegram.error.TelegramError, Exception) as error:
        logging.error(SEND_MESSAGE_ERROR.format(message=message, error=error))
        return False


def get_api_answer(timestamp):
    """Отправка запроса к эндпоинту API-сервиса."""
    try:
        response = requests.get(
            ENDPOINT, headers=HEADERS, params={'from_date': timestamp}
        )
    except requests.exceptions.RequestException as error:
        raise ConnectionError(CONNECTION_ERROR.format(
            error=error,
            enpoint=ENDPOINT,
            header=HEADERS,
            params={'from_date': timestamp}
        ))
    if response.status_code != HTTPStatus.OK:
        raise ValueError(
            GET_API_ANSWER_STATUS_ERROR_MASSAGE.format(
                endpoint=ENDPOINT,
                header=HEADERS,
                params={'from_date': timestamp},
                status_code=response.status_code
            )
        )
    keys = ['code', 'error']
    for key in keys:
        if key in response.json():
            raise ValueError(KEY_ERROR.format(
                key=key,
                value=response.json().get(key),
                endpoint=ENDPOINT,
                header=HEADERS,
                params={'from_date': timestamp},
            ))
    return response.json()


def check_response(response):
    """Проверка корректности ответа API."""
    if not isinstance(response, dict):
        raise TypeError(CHECK_RESPONCE_NOT_DICT)
    if 'homeworks' not in response:
        raise KeyError(CHECK_RESPONCE_KEY_NO_IN_RESPONSE)
    if not isinstance(response.get('homeworks'), list):
        raise TypeError(CHECK_RESPONCE_KEY_NOT_LIST)
    return response.get('homeworks')


def parse_status(homework):
    """Получение статуса конкретной домашней работы."""
    name = homework['homework_name']
    status = homework['status']
    if status not in HOMEWORK_VERDICTS:
        raise ValueError(PARSE_STATUS_MASSAGE.format(status=status))
    return PARSE_STATUS_CHANGE_MESSAGE.format(
        name=name,
        verdict=HOMEWORK_VERDICTS[status]
    )


def check_tokens():
    """Проверка доступности переменных окружения."""
    for name in TOKENS:
        token = globals()[name]
        if token is None or token == '':
            logging.critical(CHECK_TOKENS_MESSAGE.format(name=name))
    tokens = [
        globals()[token] for token in TOKENS
        if globals()[token] is None or globals()[token] == ''
    ]
    if len(tokens) == 0:
        return True
    return False


def main():
    """Основная логика работы бота."""
    if check_tokens() is False:
        raise ValueError(TOKENS_ERROR)
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    timestamp = int(time.time())
    old_massage = ''
    while True:
        try:
            response = get_api_answer(timestamp)
            homeworks = check_response(response)
            if len(homeworks) != 0:
                send_message(bot, parse_status(homeworks[0]))
            timestamp = response.get('current_date', timestamp)
        except Exception as error:
            message = MAIN_EXCEPTION_MASSAGE.format(error=error)
            logging.exception(message)
            if message != old_massage:
                if send_message(bot, message):
                    old_massage = message
        time.sleep(RETRY_TIME)


if __name__ == '__main__':
    logging.basicConfig(
        format=(
            '%(asctime)s - %(levelname)s '
            '- %(funcName)s - %(lineno)d - %(message)s'
        ),
        handlers=[logging.FileHandler(filename=(__file__ + '.log')),
                  logging.StreamHandler(stream=sys.stdout)],
        level=logging.DEBUG)
    main()
