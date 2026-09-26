import os
import sys
import time
import logging

from dotenv import load_dotenv
import requests
import vk_api

from exceptions import APIResponseError

load_dotenv()


logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)


PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
VK_TOKEN = os.getenv('VK_TOKEN')
VK_USER_ID = os.getenv('VK_USER_ID')

RETRY_PERIOD = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}


HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}


def check_tokens():
    """Проверяет доступность переменных окружения."""
    return all([PRACTICUM_TOKEN, VK_TOKEN, VK_USER_ID])


def send_message(vk, message):
    """Отправляет текстовое сообщение в заданный чат VK."""
    try:
        vk.messages.send(
            user_id=VK_USER_ID,
            message=message,
            random_id=0
        )
        logging.debug(f'Бот отправил сообщение: "{message}"')
    except Exception as error:
        logging.error(f'Сбой при отправке сообщения в VK: {error}')


def get_api_answer(timestamp):
    """Делает запрос к API Практикума и возвращает ответ."""
    params = {'from_date': timestamp}
    try:
        response = requests.get(ENDPOINT, headers=HEADERS, params=params)
    except requests.RequestException as error:
        raise APIResponseError(f'Сбой при запросе к эндпоинту: {error}')

    if response.status_code != 200:
        raise APIResponseError(f'Код ответа API: {response.status_code}')

    return response.json()


def check_response(response):
    """Проверяет структуру ответа от API Практикума."""
    if not isinstance(response, dict):
        raise TypeError('Ответ API должен быть словарем')

    if 'homeworks' not in response:
        error_msg = 'В ответе API нет ключа homeworks'
        logging.error(error_msg)
        raise KeyError(error_msg)

    if 'current_date' not in response:
        error_msg = 'В ответе API нет ключа current_date'
        logging.error(error_msg)
        raise KeyError(error_msg)

    homeworks = response['homeworks']
    if not isinstance(homeworks, list):
        raise TypeError('Под ключом homeworks должен быть список')

    return homeworks


def parse_status(homework):
    """Возвращает строку со статусом проверки домашней работы."""
    if 'homework_name' not in homework:
        raise KeyError('В данных домашней работы нет ключа homework_name')

    status = homework.get('status')
    if status not in HOMEWORK_VERDICTS:
        error_msg = f'Неизвестный статус домашней работы: {status}'
        logging.error(error_msg)
        raise ValueError(error_msg)

    homework_name = homework['homework_name']
    verdict = HOMEWORK_VERDICTS[status]
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def main():
    """Основная логика работы бота."""
    if not check_tokens():
        error_msg = 'Отсутствуют обязательные переменные окружения!'
        logging.critical(error_msg)
        sys.exit(error_msg)

    vk_session = vk_api.VkApi(token=VK_TOKEN)
    vk = vk_session.get_api()
    timestamp = int(time.time())

    last_error = ''

    while True:
        try:
            response = get_api_answer(timestamp)
            homeworks = check_response(response)

            if homeworks:
                homework = homeworks[0]
                message = parse_status(homework)
                send_message(vk, message)
            else:
                logging.debug('В ответе отсутствуют новые статусы.')

            timestamp = response.get('current_date', timestamp)
            last_error = ''
            time.sleep(RETRY_PERIOD)

        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            logging.error(message)

            if message != last_error:
                send_message(vk, message)
                last_error = message

            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()
