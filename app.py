import os
import hashlib
import pandas as pd
from flask import Flask, render_template, request, jsonify
from concurrent.futures import ThreadPoolExecutor, as_completed
from PIL import Image
import requests
from io import BytesIO
from flask_socketio import SocketIO

app = Flask(__name__)
socketio = SocketIO(app)

# Путь к кешу изображений
IMAGE_CACHE_DIR = "static/image_cache"
CSV_FILE = "update_assortment.csv"
IMAGES_PER_PAGE = 50  # Количество строк из csv на одной странице


# Функция для создания уникального имени файла на основе URL
def get_image_filename(url):
    hash_object = hashlib.md5(url.encode())
    return hash_object.hexdigest() + ".png"


# Функция для загрузки изображения из кеша или с URL
def load_image_from_cache_or_url(url):
    if not os.path.exists(IMAGE_CACHE_DIR):
        os.makedirs(IMAGE_CACHE_DIR)

    image_filename = os.path.join(IMAGE_CACHE_DIR, get_image_filename(url))

    if os.path.exists(image_filename):
        return image_filename  # Вернем путь к кешированному изображению

    try:
        response = requests.get(url)
        img = Image.open(BytesIO(response.content))

        # Проверяем, если изображение в CMYK, конвертируем в RGB
        if img.mode == 'CMYK':
            img = img.convert('RGB')

        img.save(image_filename, 'PNG')  # Сохраняем изображение в кеш
        return image_filename
    except Exception as e:
        print(f"Ошибка загрузки изображения с URL {url}: {e}")
        return None  # Если не удалось загрузить изображение


# Функция для загрузки изображения с многопоточностью
def download_image(img_url):
    if pd.notna(img_url):
        return load_image_from_cache_or_url(img_url)


# Функция для загрузки всех изображений из CSV в кеш с многопоточностью
def cache_all_images():
    try:
        df = pd.read_csv(CSV_FILE, sep=';', dtype=str)
    except Exception as e:
        print(f"Ошибка загрузки CSV файла: {e}")
        return

    image_columns = [col for col in df.columns if col.startswith('Изображения товаров')]

    # Используем ThreadPoolExecutor для многопоточности
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = []

        # Собираем все задачи для загрузки изображений
        for index, row in df.iterrows():
            for col in image_columns:
                img_url = row.get(col)
                if pd.notna(img_url):
                    futures.append(executor.submit(download_image, img_url))

        # Ожидаем завершения всех задач
        for future in as_completed(futures):
            result = future.result()
            if result:
                print(f"Изображение успешно загружено и закешировано: {result}")

    print("Все изображения загружены и закешированы.")

@app.route('/delete_image/<artikul>', methods=['POST'])
def delete_image(artikul):
    img_url = request.json.get('imgUrl')

    if not img_url:
        return jsonify({'status': 'error', 'message': 'URL изображения не предоставлен'}), 400

    # Загружаем данные из CSV
    df = load_data()

    # Определяем, какие столбцы относятся к изображениям
    image_columns = [col for col in df.columns if col.startswith('Изображения товаров')]

    # Найдем строку с этим артикулом
    row = df[df['Код артикула'] == artikul]

    if not row.empty:
        # Удаляем URL изображения из соответствующего столбца
        for col in image_columns:
            if df.at[row.index[0], col] == img_url:
                df.at[row.index[0], col] = None
                break  # Останавливаемся после нахождения совпадения

        # Сохраняем изменения обратно в CSV
        save_data(df)

        # Также можно удалить файл изображения из кеша, если это нужно
        image_filename = os.path.join(IMAGE_CACHE_DIR, get_image_filename(img_url))
        if os.path.exists(image_filename):
            os.remove(image_filename)

        return jsonify({'status': 'success', 'message': 'Изображение удалено'})
    else:
        return jsonify({'status': 'error', 'message': 'Артикул не найден'}), 400


# Главная страница с постраничным отображением
@app.route('/')
def index():
    # Загружаем CSV файл
    try:
        df = pd.read_csv(CSV_FILE, sep=';', dtype=str)
    except Exception as e:
        return f"Ошибка загрузки CSV файла: {e}"

    image_columns = [col for col in df.columns if col.startswith('Изображения товаров')]

    # Получаем номер страницы из параметров запроса (по умолчанию 1)
    page = int(request.args.get('page', 1))
    start_idx = (page - 1) * IMAGES_PER_PAGE
    end_idx = start_idx + IMAGES_PER_PAGE

    # Генерируем отображение данных
    data = []
    total_rows = len(df)
    total_pages = (total_rows // IMAGES_PER_PAGE) + 1

    for index, row in df.iloc[start_idx:end_idx].iterrows():
        row_data = {
            'artikul': row.get('Код артикула', 'Нет значения'),
            'row_id': start_idx + index,  # Уникальный идентификатор на основе номера страницы
            'images': []
        }

        # Загрузка изображений
        for col in image_columns:
            img_url = row.get(col)
            if pd.notna(img_url):
                img_path = load_image_from_cache_or_url(img_url)
                row_data['images'].append({'url': img_url, 'path': img_path})
            else:
                row_data['images'].append(None)

        data.append(row_data)

    # Передаем max и min в шаблон
    return render_template('index.html', data=data, page=page, total_pages=total_pages, max=max, min=min)

def load_data():
    df = pd.read_csv(CSV_FILE, sep=';', dtype=str)  # Загружаем файл
    return df  # Возвращаем DataFrame

def save_data(df):
    df.to_csv(CSV_FILE, index=False, sep=';')  # Сохраняем DataFrame в CSV


@app.route('/reorder_images/<row_id>', methods=['POST'])
def reorder_images(row_id):  # row_id теперь будет артикулом
    img_urls = request.json.get('imgUrls', [])

    print(f"Новый порядок изображений для артикула {row_id}: {img_urls}")
    # Загружаем данные из CSV
    df = load_data()

    # Определяем, какие столбцы относятся к изображениям
    image_columns = [col for col in df.columns if col.startswith('Изображения товаров')]

    # Найдем строку с этим артикулом
    row = df[df['Код артикула'] == row_id]

    if not row.empty:
        # Обновляем порядок изображений для данной строки
        for i, col in enumerate(image_columns):
            if i < len(img_urls):
                df.at[row.index[0], col] = img_urls[i]  # Заполняем новые URL изображений
            else:
                df.at[row.index[0], col] = None  # Очищаем лишние столбцы, если изображений меньше

        # Сохраняем изменения обратно в CSV
        save_data(df)

        return jsonify({'status': 'success', 'message': 'Порядок изображений сохранен'})
    else:
        return jsonify({'status': 'error', 'message': 'Артикул не найден'}), 400


if __name__ == '__main__':
    # Кешируем все изображения перед запуском сервера
    # cache_all_images()
    socketio.run(app, debug=True, allow_unsafe_werkzeug=True)
