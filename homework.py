import http
import logging
import os
import sys
import time

from dotenv import load_dotenv
import requests
import vk_api

from exceptions import APIResponseError, MissingTokenError


load_dotenv()


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
    tokens = {
        'PRACTICUM_TOKEN': PRACTICUM_TOKEN,
        'VK_TOKEN': VK_TOKEN,
        'VK_USER_ID': VK_USER_ID,
    }
    missing_tokens = [name for name, value in tokens.items() if not value]

    if missing_tokens:
        error_msg = (
            f'Отсутствуют обязательные переменные окружения: '
            f'{missing_tokens}'
        )

        logging.critical(error_msg)
        raise MissingTokenError(error_msg)


def send_message(vk, message):
    """Отправляет текстовое сообщение в заданный чат VK."""
    try:
        logging.info('Начало отправки сообщения в VK')
        vk.messages.send(
            user_id=VK_USER_ID,
            message=message,
            random_id=0
        )
        logging.debug(f'Бот отправил сообщение: "{message}"')
        return True
    except (vk_api.exceptions.ApiError, requests.RequestException) as error:
        logging.error(f'Сбой при отправке сообщения в VK: {error}')
        return False
    except Exception as error:
        logging.error(f'Непредвиденная ошибка при отправке в VK: {error}')
        return False


def get_api_answer(timestamp):
    """Делает запрос к API Практикума и возвращает ответ."""
    request_params = {
        'url': ENDPOINT,
        'headers': HEADERS,
        'params': {'from_date': timestamp}
    }
    try:
        logging.info(
            'Начало запроса к API. URL: {url}, '
            'Headers: {headers}, Params: {params}'.format(**request_params)
        )
        response = requests.get(**request_params)
    except requests.RequestException as error:
        raise APIResponseError(f'Сбой при запросе к эндпоинту: {error}')

    if response.status_code != http.HTTPStatus.OK:
        raise APIResponseError(f'Код ответа API: {response.status_code}')

    return response.json()


def check_response(response):
    """Проверяет структуру ответа от API Практикума."""
    if not isinstance(response, dict):
        raise TypeError(
            f'Ответ API должен быть словарем, а пришел {type(response)}')

    if 'homeworks' not in response:
        raise KeyError('В ответе API нет ключа homeworks')

    if 'current_date' not in response:
        logging.error('В ответе API отсутствует ключ current_date')

    homeworks = response['homeworks']
    if not isinstance(homeworks, list):
        raise TypeError(
            f'Под ключом homeworks должен быть список, '
            f'а пришел {type(homeworks)}'
        )
    return homeworks


def parse_status(homework):
    """Возвращает строку со статусом проверки домашней работы."""
    if not isinstance(homework, dict):
        raise TypeError(
            'Данные домашней работы должны быть словарем, '
            f'а пришел {type(homework)}'
        )

    if 'status' not in homework:
        raise KeyError('В данных домашней работы нет ключа status')

    if 'homework_name' not in homework:
        raise KeyError('В данных домашней работы нет ключа homework_name')

    status = homework['status']
    if status not in HOMEWORK_VERDICTS:
        raise ValueError(f'Неизвестный статус домашней работы: {status}')

    homework_name = homework['homework_name']
    verdict = HOMEWORK_VERDICTS[status]
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def main():
    """Основная логика работы бота."""

    check_tokens()
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
                is_sent = send_message(vk, message)
            else:
                logging.debug('В ответе отсутствуют новые статусы.')
                is_sent = True

            if is_sent:
                timestamp = response.get('current_date', timestamp)

            last_error = ''

        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            logging.error(message)

            if message != last_error:
                send_message(vk, message)
                last_error = message

        finally:
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s [%(levelname)s] %(message)s',
        handlers=[logging.StreamHandler(sys.stdout)]
    )
    try:
        main()
    except Exception as error:
        logging.critical(f'Фатальный сбой в работе программы: {error}')
        sys.exit(f'Программа аварийно завершена: {error}')
