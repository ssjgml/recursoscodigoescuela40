# Base de datos recursos Código Escuela 4.0

Esta web muestra recursos educativos creados por los Dinamizadores de Transformación Digital y Robótica (DTDR) de la Consejería de Educación, Cultura y Deportes de Castilla-La Mancha, como apoyo a la dotación de dispositivos del programa Código Escuela 4.0.

La aplicación es una web estática Servida por Flask con:
- `app.py` como backend
- `templates/index.html` como frontend
- `base_datos_v1.csv` como fuente de datos

## Cómo ejecutar

1. Instala Flask si no lo tienes:
   ```bash
   python -m pip install flask
   ```
2. Ejecuta la app:
   ```bash
   python app.py
   ```
3. Abre `http://127.0.0.1:5000` en el navegador.

## Publicar en GitHub

Para publicar el proyecto en GitHub necesitas tener instalado Git y/o GitHub CLI.

### Recomendado

1. Instala Git para Windows desde: https://git-scm.com/download/win
2. Configura tu nombre y correo:
   ```bash
   git config --global user.name "jjgm140"
   git config --global user.email "tu-email@example.com"
   ```
3. Inicializa el repositorio:
   ```bash
   git init
   git add .
   git commit -m "Initial commit"
   ```
4. Crea un repositorio público en GitHub y sube tu proyecto.

Si quieres, puedo seguirte paso a paso cuando Git y/o la GitHub CLI estén disponibles en este equipo.
