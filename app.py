from flask import Flask, jsonify, request, render_template
import csv
import re
import unicodedata
from pathlib import Path
from urllib.parse import quote, urlparse

app = Flask(__name__)
DATA_FILE = Path('base_datos_v1.csv')

ETAPAS = ['Infantil', 'Primaria', 'Secundaria', 'Especial']
NIVELES = [
    '2º ciclo de infantil', 'Primer ciclo', 'Segundo ciclo', 'Tercer ciclo',
    '1º ESO', '2º ESO', '3º ESO', '4º ESO', 'Bachillerato', 'Adultos', 'EBO', 'TVA'
]
EDADES = [str(i) for i in range(2, 17)] + ['a partir de 16']


def get_preview_image(url):
    if not url:
        return ''
    if not url.startswith(('http://', 'https://')):
        url = 'https://' + url
    parsed = urlparse(url)
    if not parsed.netloc:
        return ''
    encoded = quote(url, safe=':/?&=#')
    return f'https://s.wordpress.com/mshots/v1/{encoded}?w=640'


def load_data():
    rows = []
    with DATA_FILE.open('r', encoding='latin1', errors='replace') as f:
        reader = csv.DictReader(f, delimiter=';')
        for row in reader:
            row['preview_image'] = get_preview_image(row.get('Enlace web', '').strip())
            rows.append(row)
    return rows


def normalize(text):
    if not isinstance(text, str):
        return ''
    text = text.strip().lower()
    text = unicodedata.normalize('NFKD', text)
    return ''.join(ch for ch in text if not unicodedata.combining(ch))


def parse_age_range(text):
    if not isinstance(text, str):
        return None
    normalized = normalize(text)
    if '+' in normalized or 'más' in normalized or 'mas' in normalized:
        numbers = [int(n) for n in re.findall(r'\b(\d{1,2})\b', normalized)]
        if numbers:
            return (numbers[0], None)
    if 'a partir de' in normalized or 'desde' in normalized or 'mayor' in normalized:
        numbers = [int(n) for n in re.findall(r'\b(\d{1,2})\b', normalized)]
        if numbers:
            return (numbers[0], None)
        return None

    numbers = [int(n) for n in re.findall(r'\b(\d{1,2})\b', normalized)]
    if len(numbers) >= 2:
        return (min(numbers), max(numbers))
    if len(numbers) == 1:
        return (numbers[0], numbers[0])
    return None


def age_matches(row_age, filter_age):
    row_range = parse_age_range(row_age)
    filter_range = parse_age_range(filter_age)
    if filter_range is None:
        return False
    if row_range is None:
        return normalize(filter_age) in normalize(row_age)

    filter_min, filter_max = filter_range
    row_min, row_max = row_range
    row_max = float('inf') if row_max is None else row_max
    filter_max = float('inf') if filter_max is None else filter_max

    return row_min <= filter_max and filter_min <= row_max


def build_filter_options(data):
    fuente_values = sorted(
        {row.get('Fuente', '').strip() for row in data if row.get('Fuente', '').strip()},
        key=lambda x: x.lower()
    )
    return {
        'Fuente': fuente_values,
        'Etapa educativa': ETAPAS,
        'Nivel': NIVELES,
        'Edad': EDADES,
    }


def matches_filters(row, params):
    for field, value in params.items():
        if not value:
            continue
        if field == 'Edad':
            if not age_matches(row.get(field, ''), value):
                return False
            continue
        if normalize(value) not in normalize(row.get(field, '')):
            return False
    return True


@app.route('/api/data')
def api_data():
    data = load_data()
    query = request.args.get('q', '').strip().lower()
    filters = {
        'Fuente': request.args.get('fuente', '').strip(),
        'Etapa educativa': request.args.get('etapa', '').strip(),
        'Nivel': request.args.get('nivel', '').strip(),
        'Edad': request.args.get('edad', '').strip(),
    }
    if query:
        data = [row for row in data if query in ' '.join(row.values()).lower()]
    data = [row for row in data if matches_filters(row, filters)]
    return jsonify(data)


@app.route('/api/filters')
def api_filters():
    data = load_data()
    return jsonify(build_filter_options(data))


@app.route('/')
def index():
    return render_template('index.html')


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
