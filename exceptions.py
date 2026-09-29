class APIResponseError(Exception):
    """Кастомное исключение для сбоев при запросе к API."""


class MissingTokenError(Exception):
    """Кастомное исключение при отсутствии токенов."""
