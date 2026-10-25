"""Английский перевод интерфейса: ключ — исходная русская строка.

Нет перевода — показывается русский текст; tests/test_i18n.py следит, чтобы переводы были.
"""

EN = {
    # ошибки сервера и проверки
    "Дата рождения: не понял дату. Пример: 01.07.1975 или 01.07 без года.":
        "Birthday: couldn't read the date. Example: 1975-07-01, or 1 July without the year.",
    "Дата рождения: проверьте год.": "Birthday: check the year.",
    "Сервер контактов недоступен. Попробуйте ещё раз через минуту.":
        "The contacts server is unavailable. Please try again in a minute.",
    "Сервер контактов вернул ошибку. Попробуйте позже.": "The contacts server returned an error. Please try later.",
    "Не удалось создать адресную книгу (HTTP {status})": "Couldn't create the address book (HTTP {status})",
    "Сервер вернул некорректный ответ": "The server returned an invalid response",
    "Не удалось получить список контактов (HTTP {status})": "Couldn't load the contact list (HTTP {status})",
    "Не удалось получить контакты (HTTP {status})": "Couldn't load contacts (HTTP {status})",
    "Контакт не найден (HTTP {status})": "Contact not found (HTTP {status})",
    "Не удалось сохранить контакт (HTTP {status})": "Couldn't save the contact (HTTP {status})",
    "Не удалось удалить контакт (HTTP {status})": "Couldn't delete the contact (HTTP {status})",
    "пустой файл": "the file is empty",
    "файл больше 15 МБ": "the file is larger than 15 MB",
    "нужен JPEG, PNG, WebP или GIF": "JPEG, PNG, WebP or GIF is required",
    "не удалось прочитать изображение": "couldn't read the image",
    "Контакт не найден": "Contact not found",
    "Фото: {error}.": "Photo: {error}.",
    "Контакт изменился на другом устройстве. Перезагрузите карточку и повторите правку.":
        "The contact was changed on another device. Reload it and make your edit again.",
    "CSRF-токен неверен, обновите страницу": "Invalid CSRF token, please reload the page",
    "Только для администратора": "Administrators only",
    "Устройство": "Device",
    "Введите слово {word}, чтобы подтвердить.": "Type {word} to confirm.",
    "Файлы больше 20 МБ — разделите импорт на части.": "Files are larger than 20 MB — split the import into parts.",
    "За раз — не больше {n} контактов; импортированы первые {n}.":
        "At most {n} contacts at a time; the first {n} were imported.",
    "Не удалось разобрать карточку {uid}": "Couldn't parse card {uid}",
    "Импорт прерван из-за ошибки сервера, часть контактов могла не сохраниться.":
        "The import was interrupted by a server error; some contacts may not have been saved.",

    # пароль
    "Смена пароля": "Change password",
    "Задайте свой пароль": "Set your password",
    "Сейчас стоит пароль по умолчанию. Придумайте новый — без этого работа с контактами недоступна.":
        "You are using the default password. Choose a new one to start working with your contacts.",
    "Пароль для входа на сайт. Пароли устройств (DAVx5) не меняются.":
        "This is your web sign-in password. Device passwords (DAVx5) stay the same.",
    "Текущий пароль введён неверно.": "The current password is incorrect.",
    "Новый пароль короче 8 символов.": "The new password is shorter than 8 characters.",
    "Пароли не совпадают — введите ещё раз.": "Passwords don't match — please try again.",
    "Новый пароль совпадает с текущим.": "The new password is the same as the current one.",
    "Слишком много попыток. Подождите минуту.": "Too many attempts. Please wait a minute.",
    "Текущий пароль": "Current password",
    "Новый пароль, от 8 символов": "New password, at least 8 characters",
    "Новый пароль": "New password",
    "Повторите новый пароль": "Repeat the new password",
    "Сохранить пароль": "Save password",
    "Выйти": "Sign out",
    "Отмена": "Cancel",

    # админка
    "Админка": "Admin",
    "Пользователи": "Users",
    "Пользователь создан, адресная книга «{book}» заведена.":
        "User created, the “{book}” address book is ready.",
    "Пользователь удалён вместе со своей адресной книгой.": "The user and their address book were deleted.",
    "Пароль изменён.": "Password changed.",
    "Логин: только a-z, 0-9, дефис и подчёркивание, 3–32 символа.":
        "User name: a-z, 0-9, hyphen and underscore only, 3–32 characters.",
    "Пароль короче 8 символов.": "The password is shorter than 8 characters.",
    "Такой пользователь уже есть.": "This user already exists.",
    "Свой аккаунт удалить нельзя.": "You can't delete your own account.",
    "администратор": "administrator",
    "пользователь": "user",
    "с {date}": "since {date}",
    "Управление": "Manage",
    "Повторите пароль": "Repeat the password",
    "Сменить пароль": "Change password",
    "Удалить пользователя {name} и все его контакты?": "Delete user {name} and all their contacts?",
    "Удалить пользователя": "Delete user",
    "Новый пользователь": "New user",
    "Логин (a-z, 0-9, _ -)": "User name (a-z, 0-9, _ -)",
    "Логин": "User name",
    "Пароль, от 8 символов": "Password, at least 8 characters",
    "Пароль": "Password",
    "Администратор": "Administrator",
    "Создать": "Create",

    # шапка
    "Список": "Contacts",
    "Устройства": "Devices",
    "Тема и язык": "Theme and language",
    "Тема": "Theme",
    "Язык": "Language",
    "Как в системе": "System",
    "Светлая": "Light",
    "Тёмная": "Dark",

    # очистка
    "Очистить адресную книгу": "Clear address book",
    "Контакты": "Contacts",
    "Будут удалены все контакты: {n}.": "All contacts will be deleted: {n}.",
    "Удаление нельзя отменить.": "This can't be undone.",
    "При следующей синхронизации контакты пропадут и со всех подключённых телефонов.":
        "On the next sync the contacts will also disappear from all connected phones.",
    "Адресная книга и пароли устройств останутся — телефоны не нужно настраивать заново.":
        "The address book and device passwords stay — phones don't need to be set up again.",
    "Сначала сохраните копию": "Save a copy first",
    "Из файла всё можно будет вернуть через «Импорт».": "You can restore everything from the file via “Import”.",
    "Готовлю файл со всеми контактами…": "Preparing a file with all contacts…",
    "Скачать все контакты (.vcf)": "Download all contacts (.vcf)",
    "Удаляю контакты…": "Deleting contacts…",
    "Чтобы подтвердить, введите": "To confirm, type",
    "Удалить все контакты": "Delete all contacts",
    "Адресная книга уже пуста.": "The address book is already empty.",
    "К списку": "Back to contacts",

    # карточка
    "Контакт": "Contact",
    "Без имени": "No name",
    "Позвонить": "Call",
    "Написать": "E-mail",
    "Править": "Edit",
    "Сохранено.": "Saved.",
    "телефон": "phone",
    "день рождения": "birthday",
    "сайт": "website",
    "заметка": "note",
    "Готовлю карточку…": "Preparing the card…",
    "Экспорт в .vcf": "Export to .vcf",
    "Удалить контакт «{name}»?": "Delete contact “{name}”?",
    "Удалить контакт": "Delete contact",
    "мобильный": "mobile",
    "домашний": "home",
    "рабочий": "work",
    "основной": "main",
    "факс": "fax",
    "пейджер": "pager",
    "другой": "other",

    # форма контакта
    "Новый контакт": "New contact",
    "Правка контакта": "Edit contact",
    "Сохраняю…": "Saving…",
    "Готово": "Done",
    "Изменить фото": "Change photo",
    "Добавить фото": "Add photo",
    "убрать фото": "remove photo",
    "Имя": "First name",
    "Фамилия": "Last name",
    "Имя для показа (если не «Имя Фамилия»)": "Display name (if not “First Last”)",
    "Имя для показа": "Display name",
    "Организация": "Organization",
    "Должность": "Job title",
    "телефоны": "phones",
    "по одному в строке": "one per line",
    "01.07.1975 или 01.07": "1975-07-01 or 1 July",
    "Заметка": "Note",
    "Сохранить": "Save",

    # устройства
    "Пароль для «{name}» создан": "Password for “{name}” created",
    "Скопируйте его сейчас — второй раз он не покажется.": "Copy it now — it won't be shown again.",
    "Копировать": "Copy",
    "Новый пароль устройства": "New device password",
    "Название, например Pixel 9": "Name, e.g. Pixel 9",
    "Название устройства": "Device name",
    "Мои устройства": "My devices",
    "создан {date}": "created {date}",
    "синхронизация {date}": "last sync {date}",
    "ещё не подключался": "not connected yet",
    "Отозвать пароль «{name}»? Телефон перестанет синхронизироваться.":
        "Revoke the password “{name}”? The phone will stop syncing.",
    "Отозвать": "Revoke",
    "Паролей устройств пока нет.": "No device passwords yet.",
    "Как подключить телефон": "How to connect a phone",
    "Адрес сервера и имя пользователя одинаковы для всех приложений:":
        "The server address and user name are the same for every app:",
    "Адрес сервера": "Server address",
    "Скопировать адрес сервера": "Copy server address",
    "Имя пользователя": "User name",
    "Скопировать имя пользователя": "Copy user name",
    "Пароль — пароль устройства (не пароль входа на сайт).": "Password — a device password (not your web password).",
    "Откройте DAVx5 → «+» → «Вход по URL и имени пользователя».":
        "Open DAVx5 → “+” → “Login with URL and user name”.",
    "Введите адрес сервера, имя пользователя и пароль устройства.":
        "Enter the server address, your user name and a device password.",
    "В аккаунте выберите адресную книгу «{book}» и включите синхронизацию.":
        "In the account, select the “{book}” address book and turn on sync.",
    "Настройки → Контакты → Учётные записи → Новая учётная запись → Другое.":
        "Settings → Contacts → Accounts → Add Account → Other.",
    "«Учётная запись CardDAV»: сервер — адрес без https://, имя пользователя и пароль устройства.":
        "“Add CardDAV Account”: server is the address without https://, then your user name and a device password.",

    # ошибки и импорт
    "Ошибка": "Error",
    "Не получилось": "Something went wrong",
    "Вернуться к списку": "Back to contacts",
    "Импорт": "Import",
    "Готово, но не всё": "Done, with some errors",
    "карточек в файле: {n}": "cards in file: {n}",
    "добавлено": "added",
    "обновлено": "updated",
    "уже были": "already there",
    "ошибки": "errors",
    "В файле не нашлось карточек vCard (BEGIN:VCARD … END:VCARD).": "No vCard entries found in the file (BEGIN:VCARD … END:VCARD).",
    "Загрузить ещё": "Upload more",
    "Выберите файл .vcf": "Choose a .vcf file",
    "или перетащите сюда · можно несколько, до 20 МБ": "or drop it here · several files allowed, up to 20 MB",
    "Если контакт уже есть": "If a contact already exists",
    "Пропустить": "Skip",
    "сохранить то, что уже в адресной книге": "keep what is already in the address book",
    "Заменить": "Replace",
    "перезаписать карточкой из файла": "overwrite with the card from the file",
    "Совпадение определяется по UID карточки. Фото и все поля переносятся как есть.":
        "Matches are found by the card UID. Photos and all fields are imported as is.",
    "Импортировать": "Import",
    "Где взять файл": "Where to get the file",
    "приложение «Контакты» → Настройки → Экспорт → файл .vcf.": "Contacts app → Settings → Export → .vcf file.",
    "icloud.com → Контакты → выделить → «Экспортировать vCard».": "icloud.com → Contacts → select → “Export vCard”.",
    "contacts.google.com → Экспорт → «vCard (для iOS)».": "contacts.google.com → Export → “vCard (for iOS)”.",

    # список
    "Импорт и экспорт": "Import and export",
    "Импорт из .vcf": "Import from .vcf",
    "Экспорт всех в .vcf": "Export all to .vcf",
    "Пароль изменён. В других браузерах нужно будет войти заново.":
        "Password changed. You will need to sign in again in other browsers.",
    "Контакт удалён.": "Contact deleted.",
    "Адресная книга очищена: удалено {n}.": "Address book cleared: {n} deleted.",
    "Адресная книга очищена.": "Address book cleared.",
    "Поиск: имя, телефон, e-mail": "Search: name, phone, e-mail",
    "Поиск": "Search",
    "Фото": "Photo",
    "Все": "All",
    "С фото": "With photo",
    "Без фото": "No photo",
    "Все организации": "All organizations",
    "Без организации": "No organization",
    "Показать": "Show",
    "Найдено {n} из {total}": "Found {n} of {total}",
    "Буквы алфавита": "Alphabet index",
    "Ничего не нашлось.": "Nothing found.",
    "Пока пусто": "Nothing here yet",
    "Создайте первый контакт или подключите телефон в разделе «Устройства».":
        "Create your first contact or connect a phone in “Devices”.",

    # вход
    "Вход": "Sign in",
    "С возвращением": "Welcome back",
    "Войдите, чтобы открыть свои контакты": "Sign in to open your contacts",
    "Неверный логин или пароль.": "Wrong user name or password.",
    "Форма устарела, попробуйте ещё раз.": "The form has expired, please try again.",
    "Войти": "Sign in",
}

# формы слова при числе: русская форма для 1 → (one, many) по-английски
EN_PLURAL = {
    "контакт": ("contact", "contacts"),
}
