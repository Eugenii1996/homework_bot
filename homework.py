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
    ' с заголовком {header} от даты {timestamp} '
    'возникла ошибка, код ответа {status_code}.'
)
GET_API_ANSWER_CONNECTION_ERROR_MASSAGE = (
    'Ошибка обращения к API: {error} c эндпоинтом '
    '{enpoint} и заголовком {header} от даты {timestamp}'
)
PARSE_STATUS_MASSAGE = (
    'Получен неожиданный статус {status} проверки домашней работы'
)
PARSE_STATUS_CHANGE_MESSAGE = (
    'Изменился статус проверки работы "{homework_name}". '
    '{verdict}'
)
SEND_MESSAGE = 'Ошибка отправки сообщения {message}: {error}'
CHECK_RESPONCE_NOT_DICT = 'В ответе API отсутствует словарь'
CHECK_RESPONCE_KEY_NO_IN_RESPONSE = 'Ключ "homeworks" не найден'
CHECK_RESPONCE_KEY_NOT_LIST = 'Значение для ключа "homeworks" не список'
CHECK_TOKENS_MESSAGE = 'Переменная окружения {name} не найдена либо пуста!'
MAIN_EXCEPTION_MASSAGE = 'Сбой в работе программы: {error}'


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
    except Exception as error:
        raise ConnectionError(
            SEND_MESSAGE.format(message=message, error=error)
        )


def get_api_answer(timestamp):
    """Отправка запроса к эндпоинту API-сервиса."""
    try:
        response = requests.get(
            ENDPOINT, headers=HEADERS, params={'from_date': timestamp}
        )
    except requests.exceptions.RequestException as error:
        raise ConnectionError(GET_API_ANSWER_CONNECTION_ERROR_MASSAGE.format(
            error=error, enpoint=ENDPOINT, header=HEADERS, timestamp=timestamp
        ))
    if response.status_code != HTTPStatus.OK:
        raise ValueError(
            GET_API_ANSWER_STATUS_ERROR_MASSAGE.format(
                endpoint=ENDPOINT,
                header=HEADERS,
                timestamp=timestamp,
                status_code=response.status_code
            )
        )
    if 'code' in response.json():
        raise ValueError('Сервер вернул некорректный json.')
    if 'error' in response.json():
        raise ValueError('Сервер вернул некорректный json.')
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
    homework_name = homework.get('homework_name')
    status = homework['status']
    if status not in HOMEWORK_VERDICTS:
        raise KeyError(PARSE_STATUS_MASSAGE.format(status=status))
    return PARSE_STATUS_CHANGE_MESSAGE.format(
        homework_name=homework_name,
        verdict=HOMEWORK_VERDICTS[status]
    )


def check_tokens():
    """Проверка доступности переменных окружения."""
    tokens = []
    for name in TOKENS:
        token = globals()[name]
        if token is None or token == '':
            logging.critical(CHECK_TOKENS_MESSAGE.format(name=name))
            tokens.append(token)
    if len(tokens) == 0:
        return True
    return False


def main():
    """Основная логика работы бота."""
    if check_tokens() is False:
        sys.exit(1)
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    timestamp = int(time.time())
    old_massage = ''
    while True:
        try:
            response = get_api_answer(timestamp)
            homeworks = check_response(response)
            if len(homeworks) != 0:
                homework = homeworks[0]
                message = parse_status(homework)
                send_message(bot, message)
            timestamp = response.get('current_date', timestamp)
        except Exception as error:
            message = MAIN_EXCEPTION_MASSAGE.format(error=error)
            logging.exception(message)
            if message != old_massage:
                if send_message(bot, message) is True:
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
