# Stateless API-обертка для Telegram

⚠️ **Важное уведомление**: Данное REST API доступно по адресу `telegramrest.ru`. Вы можете свободно им пользоваться, но настоятельно рекомендуется создать отдельный тестовый аккаунт Telegram с новым номером телефона для тестирования. Не используйте свой личный аккаунт Telegram во избежание потенциальных рисков безопасности.

Чтобы начать работу, вам необходимо зарегистрировать своё приложение:
1. Перейдите по ссылке https://my.telegram.org/apps
2. Создайте новое приложение для получения `api_id` и `api_hash`

Легковесная, работающая без сохранения состояния HTTP-обертка вокруг API Telegram, которая позволяет программно взаимодействовать с Telegram без необходимости поддержания постоянных сессий. Этот API-сервер предоставляет RESTful интерфейс для управления вашим аккаунтом Telegram, сообщениями и взаимодействия с группами.

## Возможности

- 🔐 **Аутентификация без состояния**: Не требуется хранить файлы сессий - состояние аутентификации поддерживается через строки сессий в заголовках
- 📱 **Управление аккаунтом**: Вход по номеру телефона и управление двухфакторной аутентификацией
- 💬 **Операции с сообщениями**:
  - Отправка текстовых сообщений и файлов
  - Удаление сообщений
  - Пересылка сообщений между чатами
  - Редактирование сообщений
  - Получение истории сообщений с фильтрацией
  - Загрузка медиаконтента
- 👥 **Управление группами**:
  - Присоединение к публичным и приватным группам
  - Вход по пригласительным ссылкам
  - Список всех чатов и групп
- 🔄 **Управление сессиями**: Безопасная обработка сессий с шифрованием учетных данных

## Требования

- Python 3.7+
- FastAPI
- Telethon
- Ваши учетные данные API Telegram (api_id и api_hash)

## Установка

```bash
# Клонировать репозиторий
git clone https://github.com/yourusername/telegram-api-wrapper

# Установить зависимости
pip install fastapi telethon uvicorn python-multipart aiofiles
```

## Конфигурация

Перед запуском сервера необходимо получить учетные данные API Telegram:

1. Перейдите на https://my.telegram.org/auth
2. Войдите с помощью своего номера телефона
3. Перейдите в 'API development tools'
4. Создайте новое приложение для получения `api_id` и `api_hash`

## Использование

### Запуск сервера

```bash
uvicorn telegram_api_server_stateless:app --host 0.0.0.0 --port 8000
```

### Процесс аутентификации

1. **Начальная аутентификация**:
```http
POST http://localhost:8000/auth/send_code
Content-Type: application/json

{
  "phone": "+1234567890",
  "api_id": ваш_api_id,
  "api_hash": "ваш_api_hash"
}
```

2. **Проверка кода**:
```http
POST http://localhost:8000/auth/verify_code
X-Session-String: {строка_сессии_из_предыдущего_ответа}
Content-Type: application/json

{
  "code": "12345"
}
```

3. **Двухфакторная аутентификация (если включена)**:
```http
POST http://localhost:8000/auth/verify_password
X-Session-String: {строка_сессии}
Content-Type: application/json

{
  "password": "ваш_пароль_2fa"
}
```

### Основные операции

#### Отправка сообщения
```http
POST http://localhost:8000/messages/send
X-Session-String: {строка_сессии}
Content-Type: application/json

{
  "chat_id": "@имя_пользователя_или_id_чата",
  "text": "Привет, мир!"
}
```

#### Получение сообщений
```http
GET http://localhost:8000/messages/?chat_id=123456&limit=100
X-Session-String: {строка_сессии}
```

#### Присоединение к группе
```http
POST http://localhost:8000/groups/join
X-Session-String: {строка_сессии}
Content-Type: application/json

{
  "group_identifier": "@username_группы"
}
```

## Безопасность

- Сервер шифрует учетные данные API в строках сессий
- Отсутствует постоянное хранение учетных данных или данных сессий
- Каждый запрос требует аутентификации через строку сессии
- Строки сессий следует рассматривать как конфиденциальные данные

## Обработка ошибок

API возвращает соответствующие HTTP-коды состояния и сообщения об ошибках:

- `400`: Неверный запрос (неверные параметры)
- `401`: Не авторизован (недействительная сессия)
- `403`: Запрещено (недостаточно прав)
- `404`: Не найдено (чат/сообщение не найдены)
- `429`: Слишком много запросов (превышен лимит Telegram)

## Варианты использования

Эта обертка особенно полезна для:

- Создания чат-ботов без управления сессиями
- Автоматизации операций в Telegram
- Интеграции с другими сервисами
- Управления несколькими аккаунтами Telegram
- Создания пользовательских клиентов Telegram

## Ограничения

- Применяются ограничения скорости согласно ограничениям API Telegram
- Некоторые функции Telegram могут быть недоступны
- Операции с медиафайлами являются временными (файлы удаляются после отправки)

## Участие в разработке

Мы приветствуем вклад в развитие проекта! Не стесняйтесь отправлять pull request'ы или создавать issue для сообщения об ошибках и предложения новых функций.

## Лицензия

Этот проект лицензирован под MIT License - подробности см. в файле LICENSE.

## Отказ от ответственности

Этот проект не является официально связанным с Telegram. Используйте ответственно и в соответствии с условиями использования Telegram.