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
    'transcripcion': 'Transcripcion',
    'transcripción': 'Transcripcion',
    'transcripci�n': 'Transcripcion',
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
        'aï¿½os': 'años',
        'Aï¿½os': 'Años',
        'Educaciï¿½n': 'Educación',
        'Transcripciï¿½n': 'Transcripción',
        'Descripciï¿½n': 'Descripción',
        'Tecnologï¿½a': 'Tecnología',
        'cï¿½digo': 'código',
        'T�tulo': 'Título',
        'Descripci�n': 'Descripción',
        'Transcripci�n': 'Transcripción',
        'Modalidad/Tecnolog�a': 'Modalidad/Tecnología',
        'Ã¡': 'á',
        'Ã©': 'é',
        'Ã­': 'í',
        'Ã³': 'ó',
        'Ãº': 'ú',
        'Ã±': 'ñ',
        'Ã‘': 'Ñ',
        'Ã‰': 'É',
        'Ãš': 'Ú',
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    text = re.sub(r'(\d)�', r'\1º', text)
    text = text.replace('n�', 'ñ').replace('N�', 'Ñ')
    text = text.replace('a�', 'á').replace('A�', 'Á')
    text = text.replace('e�', 'é').replace('E�', 'É')
    text = text.replace('i�', 'í').replace('I�', 'Í')
    text = text.replace('o�', 'ó').replace('O�', 'Ó')
    text = text.replace('u�', 'ú').replace('U�', 'Ú')
    return text


def canonical_header(name):
    if not isinstance(name, str):
        return ''
    name = clean_text(name)
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


def get_row_field(row, *names):
    for name in names:
        value = row.get(name)
        if isinstance(value, str):
            cleaned_value = clean_text(value).strip()
            if cleaned_value:
                return cleaned_value
    return ''


def standardize_row(row):
    cleaned = {clean_text(k): clean_text(v) if isinstance(v, str) else v for k, v in row.items()}
    standardized = {}
    for key, value in cleaned.items():
        canonical = canonical_header(key)
        mapped = FIELD_ALIASES.get(canonical)
        if not mapped:
            if canonical in {canonical_header('título'), canonical_header('titulo'), canonical_header('t�tulo')}:
                mapped = 'Título'
            elif canonical in {canonical_header('descripción'), canonical_header('descripcion'), canonical_header('descripci�n')}:
                mapped = 'Descripción'
            elif canonical in {canonical_header('modalidad/tecnologia'), canonical_header('modalidadtecnologia'), canonical_header('modalidad/tecnolog�a')}:
                mapped = 'Modalidad/Tecnologia'
            elif canonical in {canonical_header('etapa educativa'), canonical_header('etapaeducativa')}:
                mapped = 'Etapa educativa'
            elif canonical in {canonical_header('evento/programa'), canonical_header('eventoprograma')}:
                mapped = 'Evento/Programa'
            elif canonical in {canonical_header('enlace web'), canonical_header('enlaceweb'), canonical_header('enlace')}:
                mapped = 'Enlace web'
            elif canonical in {canonical_header('etiquetas')}:
                mapped = 'Etiquetas'

        if mapped:
            if mapped in standardized:
                standardized[mapped] += ' ' + value
            else:
                standardized[mapped] = value
        else:
            standardized[key] = value
    if standardized.get('Enlace web', '').startswith('Dhttps://'):
        standardized['Enlace web'] = standardized['Enlace web'][1:]
    if standardized.get('Enlace web', '').startswith('Dhttp://'):
        standardized['Enlace web'] = standardized['Enlace web'][1:]

    # Ensure common fields are present under the normalized names.
    fallback_fields = {
        'Título': ['Título', 'T�tulo', 'Titulo'],
        'Descripción': ['Descripción', 'Descripci�n', 'Transcripcion', 'Transcripción', 'Descripcion'],
        'Modalidad/Tecnologia': ['Modalidad/Tecnologia', 'Modalidad/Tecnología', 'Modalidad/Tecnolog�a'],
        'Enlace web': ['Enlace web', 'Enlace'],
        'Etapa educativa': ['Etapa educativa'],
        'Fuente': ['Fuente'],
        'Nivel': ['Nivel'],
        'Edad': ['Edad'],
        'Etiquetas': ['Etiquetas'],
    }
    for target, aliases in fallback_fields.items():
        if not standardized.get(target):
            for alias in aliases:
                if standardized.get(alias):
                    standardized[target] = standardized[alias]
                    break

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
    if 'años' in normalized:
        normalized = normalized.replace('años', 'a')
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


# Canonicalize alias keys so mojibake or accented header names still match.
FIELD_ALIASES = {canonical_header(k): v for k, v in FIELD_ALIASES.items()}


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


def split_modality_terms(value):
    if not isinstance(value, str):
        return []
    cleaned = value.strip()
    if not cleaned:
        return []
    separators = r'[;,\|/]+\s*'
    parts = [part.strip() for part in re.split(separators, cleaned) if part.strip()]
    return parts


def build_filter_options(data, selected_stage=None):
    fuente_values = sorted(
        {get_row_field(row, 'Fuente').strip() for row in data if get_row_field(row, 'Fuente').strip()},
        key=lambda x: x.lower()
    )
    modalidad_values = sorted(
        {term for row in data for term in split_modality_terms(get_row_field(row, 'Modalidad/Tecnologia', 'Modalidad/Tecnología', 'Modalidad/Tecnolog�a'))},
        key=lambda x: x.lower()
    )
    nivel_values = sorted(
        {get_row_field(row, 'Nivel').strip() for row in data if get_row_field(row, 'Nivel').strip() and level_allowed_for_stage(selected_stage, get_row_field(row, 'Nivel').strip())},
        key=lambda x: x.lower()
    )
    edad_values = sorted(
        {get_row_field(row, 'Edad').strip() for row in data if get_row_field(row, 'Edad').strip() and age_allowed_for_stage(selected_stage, get_row_field(row, 'Edad').strip())},
        key=lambda x: (float('inf') if x == 'a partir de 16' else int(re.findall(r'\d+', x)[0]) if re.findall(r'\d+', x) else 999, x)
    )
    return {
        'Fuente': fuente_values,
        'Etapa educativa': ETAPAS,
        'Nivel': nivel_values,
        'Edad': edad_values,
        'Modalidad/Tecnologia': modalidad_values,
    }


def modality_matches(row_value, selected_value):
    if not selected_value:
        return True
    if not isinstance(row_value, str):
        return False
    row_value_normalized = normalize(row_value)
    selected_normalized = normalize(selected_value)
    if selected_normalized in row_value_normalized:
        return True
    for term in split_modality_terms(row_value):
        if normalize(term) == selected_normalized:
            return True
    return False


def matches_filters(row, params):
    for field, value in params.items():
        if not value:
            continue
        if field == 'Edad':
            if not age_matches(get_row_field(row, 'Edad'), value):
                return False
            continue
        if field == 'Modalidad/Tecnologia':
            if not modality_matches(get_row_field(row, 'Modalidad/Tecnologia', 'Modalidad/Tecnología', 'Modalidad/Tecnolog�a'), value):
                return False
            continue
        if field == 'Etapa educativa':
            if normalize(value) not in normalize(get_row_field(row, 'Etapa educativa')):
                return False
            continue
        if normalize(value) not in normalize(get_row_field(row, field, field.replace(' ', ''))):
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
