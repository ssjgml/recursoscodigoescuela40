from flask import Flask, jsonify, request, render_template
import csv
import re
import unicodedata
from pathlib import Path
from urllib.parse import quote, urlparse

app = Flask(__name__)
DATA_FILE = Path('base_datos_v1.csv')

FIELD_ALIASES = {
    'fuente': 'Fuente',
    'evento/programa': 'Evento/Programa',
    'etapaeducativa': 'Etapa educativa',
    'nivel': 'Nivel',
    'edad': 'Edad',
    'modalidadtecnologia': 'Modalidad/Tecnologia',
    'modalidad/tecnologia': 'Modalidad/Tecnologia',
    'modalidad/tecnología': 'Modalidad/Tecnologia',
    'modalidad/tecnolog�a': 'Modalidad/Tecnologia',
    'titulo': 'Título',
    'título': 'Título',
    't�tulo': 'Título',
    'descripcion': 'Descripción',
    'descripción': 'Descripción',
    'descripci�n': 'Descripción',
    'enlaceweb': 'Enlace web',
    'enlace': 'Enlace web',
    'etiquetas': 'Etiquetas',
}

ETAPAS = ['Infantil', 'Primaria', 'Secundaria', 'Especial']
NIVELES = [
    '2º ciclo de infantil', 'Primer ciclo', 'Segundo ciclo', 'Tercer ciclo',
    '1º ESO', '2º ESO', '3º ESO', '4º ESO', 'Bachillerato', 'Adultos', 'EBO', 'TVA'
]
EDADES = [str(i) for i in range(2, 17)] + ['a partir de 16']


def clean_text(text):
    if not isinstance(text, str):
        return ''
    text = text.strip()
    try:
        fixed = text.encode('latin1').decode('utf-8')
        if fixed and '�' not in fixed:
            text = fixed
    except Exception:
        pass
    replacements = {
        'ï¿½': 'º',
        '�': 'º',
        'aï¿½os': 'años',
        'Aï¿½os': 'Años',
        'Educaciï¿½n': 'Educación',
        'Transcripciï¿½n': 'Transcripción',
        'Descripciï¿½n': 'Descripción',
        'Tecnologï¿½a': 'Tecnología',
        'cï¿½digo': 'código',
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    return text


def canonical_header(name):
    if not isinstance(name, str):
        return ''
    normalized = normalize(name)
    normalized = re.sub(r'[^a-z0-9]', '', normalized)
    return normalized


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


def get_row_value(row, *names):
    for name in names:
        if name in row and row[name] is not None:
            value = clean_text(row[name]).strip()
            if value:
                return value
    return ''


def standardize_row(row):
    cleaned = {clean_text(k): clean_text(v) if isinstance(v, str) else v for k, v in row.items()}
    standardized = {}
    for key, value in cleaned.items():
        canonical = canonical_header(key)
        mapped = FIELD_ALIASES.get(canonical)
        if mapped:
            standardized[mapped] = value
        else:
            standardized[key] = value
    if standardized.get('Enlace web', '').startswith('Dhttps://'):
        standardized['Enlace web'] = standardized['Enlace web'][1:]
    if standardized.get('Enlace web', '').startswith('Dhttp://'):
        standardized['Enlace web'] = standardized['Enlace web'][1:]
    return standardized


def load_data():
    rows = []
    with DATA_FILE.open('r', encoding='latin1', errors='replace') as f:
        reader = csv.DictReader(f, delimiter=';')
        for row in reader:
            row = standardize_row(row)
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


STAGE_LEVELS = {
    'Infantil': ['2º ciclo de infantil'],
    'Primaria': ['Primer ciclo', 'Segundo ciclo', 'Tercer ciclo'],
    'Secundaria': ['1º ESO', '2º ESO', '3º ESO', '4º ESO', 'Bachillerato', 'Adultos', 'EBO', 'TVA'],
    'Especial': [],
}

STAGE_AGE_RANGES = {
    'Infantil': (3, 5),
    'Primaria': (6, 12),
    'Secundaria': (13, None),
}


def level_allowed_for_stage(stage, level):
    if stage == 'Especial' or not stage:
        return True
    allowed = STAGE_LEVELS.get(stage, [])
    return normalize(level) in {normalize(v) for v in allowed}


def age_allowed_for_stage(stage, age_value):
    if stage == 'Especial' or not stage:
        return True
    stage_range = STAGE_AGE_RANGES.get(stage)
    if not stage_range:
        return True
    age_range = parse_age_range(age_value)
    if age_range is None:
        return normalize(age_value) in normalize(stage)
    row_min, row_max = age_range
    row_max = float('inf') if row_max is None else row_max
    stage_min, stage_max = stage_range
    stage_max = float('inf') if stage_max is None else stage_max
    return row_min <= stage_max and stage_min <= row_max


def build_filter_options(data, selected_stage=None):
    fuente_values = sorted(
        {row.get('Fuente', '').strip() for row in data if row.get('Fuente', '').strip()},
        key=lambda x: x.lower()
    )
    modalidad_values = sorted(
        {row.get('Modalidad/Tecnologia', '').strip() for row in data if row.get('Modalidad/Tecnologia', '').strip()},
        key=lambda x: x.lower()
    )
    nivel_values = sorted(
        {row.get('Nivel', '').strip() for row in data if row.get('Nivel', '').strip() and level_allowed_for_stage(selected_stage, row.get('Nivel', '').strip())},
        key=lambda x: x.lower()
    )
    edad_values = sorted(
        {row.get('Edad', '').strip() for row in data if row.get('Edad', '').strip() and age_allowed_for_stage(selected_stage, row.get('Edad', '').strip())},
        key=lambda x: (float('inf') if x == 'a partir de 16' else int(re.findall(r'\d+', x)[0]) if re.findall(r'\d+', x) else 999, x)
    )
    return {
        'Fuente': fuente_values,
        'Etapa educativa': ETAPAS,
        'Nivel': nivel_values,
        'Edad': edad_values,
        'Modalidad/Tecnologia': modalidad_values,
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
        'Modalidad/Tecnologia': request.args.get('modalidad', '').strip(),
    }
    if query:
        data = [row for row in data if query in ' '.join(str(v) for v in row.values()).lower()]
    data = [row for row in data if matches_filters(row, filters)]
    return jsonify(data)


@app.route('/api/filters')
def api_filters():
    data = load_data()
    filters = {
        'Fuente': request.args.get('fuente', '').strip(),
        'Etapa educativa': request.args.get('etapa', '').strip(),
        'Nivel': request.args.get('nivel', '').strip(),
        'Edad': request.args.get('edad', '').strip(),
        'Modalidad/Tecnologia': request.args.get('modalidad', '').strip(),
    }
    filtered_data = [row for row in data if matches_filters(row, filters)]
    return jsonify(build_filter_options(filtered_data, selected_stage=filters['Etapa educativa']))


@app.route('/')
def index():
    return render_template('index.html')


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
