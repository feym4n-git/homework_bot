import logging
import os
import sys
import time
from http import HTTPStatus
from typing import Final

import requests
import telegram
from dotenv import load_dotenv

from exception import Send_MessageError

load_dotenv()

PRACTICUM_TOKEN: Final = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN: Final = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID: Final = os.getenv('TELEGRAM_CHAT_ID')

RETRY_PERIOD = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}

HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.',
}

logger = logging.getLogger(__name__)

formatter = logging.Formatter(
    '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger.setLevel(logging.DEBUG)
handler = logging.StreamHandler(sys.stdout)
logger.addHandler(handler)
handler.setFormatter(formatter)


def check_tokens():
    """Проверка наличия в переменных окружения необходимых токенов."""
    variables = {
        "PRACTICUM_TOKEN": PRACTICUM_TOKEN,
        "TELEGRAM_TOKEN": TELEGRAM_TOKEN,
        "TELEGRAM_CHAT_ID": TELEGRAM_CHAT_ID,
    }
    for name, value in variables.items():
        if value is None:
            logger.critical(
                f'Отсутствует обязательная переменная окружения:{name}.')
            raise ValueError('Invalid tokens')
    logger.debug('Проверка токенов прошла успешно')


def send_message(bot, message: str) -> None:
    """Отправка сообщения в чат."""
    try:
        bot.send_message("TELEGRAM_CHAT_ID", message)
        logger.debug(f'Бот отправил сообщение: {message}')
    except telegram.error.BadRequest:
        raise Send_MessageError('Ошибка BadRequest отправки в Telegram')
    except Exception:
        logger.error('Не удалось отправить сообщение в Telegram')
        raise Exception('Ошибка в отправке сообщения')


def get_api_answer(timestamp):
    """Получение ответа от эндпоинта."""
    payload = {'from_date': timestamp}
    try:
        homework_statuses = requests.get(
            ENDPOINT,
            headers=HEADERS,
            params=payload
        )
    except requests.RequestException:
        raise Exception('Ошибка при запросе')
    code = homework_statuses.status_code
    if code != HTTPStatus.OK:
        logger.error(f'Эндпоинт недоступен. Код ответа API: {code}')
        raise Exception(f'Эндпоинт недоступен. Код ответа API: {code}')
    return homework_statuses.json()


def check_response(response):
    """Проверка необходимых ключей в ответе."""
    if not isinstance(response, dict):
        raise TypeError('Получен не словарь')
    if 'homeworks' not in response:
        logger.error('Ключа "homeworks" нет в ответе от эндпоинта')
        raise KeyError('Ключа "homeworks" нет в ответе от эндпоинта')
    if 'current_date' not in response:
        logger.error('Ключа "current_date" нет в ответе от эндпоинта')
        raise KeyError('Ключа "current_date" нет в ответе от эндпоинта')
    if not isinstance(response['homeworks'],list):
        raise TypeError('homeworks type is not a list')


def parse_status(homework):
    """Формирование сообщения для отправки в чат."""
    if 'homework_name' not in homework:
        raise KeyError('homework_name ключ не найден')
    homework_name = homework['homework_name']
    home_work_status = homework.get('status', 'Нет статуса')
    if home_work_status not in HOMEWORK_VERDICTS:
        raise Exception('Неопознаный статус домашней работы')
    verdict = HOMEWORK_VERDICTS[home_work_status]
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def main():
    """Основная логика работы бота."""
    logger.debug('Начата работа программы')
    check_tokens()
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    timestamp = 1678667054
    # timestamp = int(time.time())
    while True:
        try:
            answer = get_api_answer(timestamp)
            check_response(answer)
            if answer['homeworks']:
                for homework in answer['homeworks']:
                    changes = parse_status(homework)
                    send_message(bot, changes)
            else:
                logger.debug('Нет измений в статусах работ')
            timestamp = answer['current_date']
        except Send_MessageError:
            logger.error('Не удалось отправить сообщение в Telegram')
        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            try:
                send_message(bot, message)
            except Exception as error:
                message = f'Сбой в отправке сообщения в чат: {error}'
                logger.error(message)
        time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()
