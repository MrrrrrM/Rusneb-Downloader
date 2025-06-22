# Rusneb-Downloader

Позволяет парсить и скачивать книги, статьи, газеты по айди либо поисковым запросом в ресурсе [Национальной Электронной Библиотеки](https://rusneb.ru/).

Поддерживает асинхронность и использование прокси. Прогресс парсинга сохраняется в директории `results`. Логи хранятся в директории `logs`.

Настройка и запуск проекта:

```bash
python -m venv .venv
& .venv/Scripts/activate
pip install -r requirements.txt
python -u ./main.py --help
```

Аргументы командной строки:

```bash
usage: main.py [-h] --query QUERY [--search] [--proxy-file PROXY_FILE] [--chunk-size CHUNK_SIZE]
[--parser-workers PARSER_WORKERS] [--download-workers DOWNLOAD_WORKERS]
[--log-level {DEBUG,INFO,WARNING,ERROR,CRITICAL}]

Rusneb парсер и загрузчик документов

options:
  -h, --help            show this help message and exit
  --query QUERY         Поисковый запрос или идентификатор каталога для обработки
  --search              Используйте этот флаг, если запрос является поисковым термином, а не идентификатором каталога
  --proxy-file PROXY_FILE
                        Путь к файлу, содержащему адреса прокси (по одному на строку)
  --chunk-size CHUNK_SIZE
                        Размер чанка для обработки (по умолчанию: 10)
  --parser-workers PARSER_WORKERS
                        Количество воркеров для парсинга каталога (по умолчанию: 3)
  --download-workers DOWNLOAD_WORKERS
                        Количество воркеров для загрузки файлов (по умолчанию: 1)
  --log-level {DEBUG,INFO,WARNING,ERROR,CRITICAL}
                        Установить уровень логирования (по умолчанию: INFO)
```

Примеры использования:

```bash
python -u ./main.py --query 000200_000018_RU_NLR_DRGNLR_3107
```

```bash
python -u ./main.py --query "Петроградская газета 1911" --search
```

Для остановки скрипта используйте `CTRL+C`.

Файл с прокси должен находится в корневой директории (рядом с `main.py`).

Конфигурация находится в `src/config/config.py`.
