"""
FLASK CRONOGRAMA APP - GESTIÓN DE EXÁMENES

Esta aplicación permite:
- Registrar exámenes con fecha, espacio curricular, año, horario y docente
- Visualizar todos los exámenes en una tabla ordenada por fecha
- Exportar el cronograma a PDF (si ReportLab está disponible) o CSV
- Editar y eliminar exámenes existentes

Características especiales:
- Compatible con entornos restringidos (desactiva debug y reloader)
- Base de datos configurable para testing
- ReportLab es opcional (fallback a CSV si no está disponible)
- Formato de fecha personalizado: "VIERNES 12/09/2025"
- Lista desplegable de espacios curriculares predefinidos
- Validación completa de datos
- Manejo de errores

Cómo usar:
- Iniciar servidor: python app.py
- Ejecutar tests: python app.py test
"""

from flask import Flask, render_template, request, redirect, url_for, send_file
import sqlite3
import os
import tempfile
import csv
import sys
import datetime  # Para el formateo de fechas

# =============================================================================
# CONFIGURACIÓN DE DEPENDENCIAS OPCIONALES
# =============================================================================

# Intentar importar ReportLab (opcional - para exportación PDF)
try:
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    from reportlab.lib.pagesizes import A4
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.lib.fonts import addMapping
    REPORTLAB_AVAILABLE = True
except ImportError:
    # Si ReportLab no está instalado, usaremos CSV para exportar
    REPORTLAB_AVAILABLE = False

# =============================================================================
# CONFIGURACIÓN DE LA APLICACIÓN FLASK
# =============================================================================

# Crear la aplicación Flask
app = Flask(__name__)
# Configurar la ruta de la base de datos (puede cambiarse para tests)
app.config['DATABASE'] = 'cronograma.db'

# =============================================================================
# LISTA DE ESPACIOS CURRICULARES PREDEFINIDOS
# =============================================================================

# Lista de espacios curriculares/materias disponibles para seleccionar
ESPACIOS_CURRICULARES = [
    "Lengua",
    "Matemática",
    "Lengua Extranjera",
    "Educación Física",
    "Ciencias Sociales: Geografía",
    "Ciencias Sociales: Historia-Formación Ética y Ciudadana",
    "Ciencias Naturales",
    "Educación Artística (C) Artes Visuales",
    "Educación Artística (A) Teatro",
    "Educación Artística (B) Música",
    "Comunicación Social",
    "Educación Tecnológica",
    "Lengua y Literatura",
    "Geografía",
    "Historia",
    "Física",
    "Biología",
    "Prácticas Artísticas",
    "Comunicación",
    "Sistemas de Información Contable I (PP 1)",
    "Tecnologías de la Información y la Comunicación",
    "Procesamiento Digital",
    "Proyecto Integrado: Ciencias Sociales",
    "Química",
    "Sistemas de Información Contable II",
    "Administración de las Organizaciones",
    "Economía I",
    "Derecho",
    "Tecnología, Sociedad y Conocimiento",
    "Producción Multimedial",
    "Funcionamiento de Sistemas Digitales",
    "Resoluciones Lógicas",
    "Economía Social",
    "Formación Ética y Ciudadana",
    "Formación para la Vida y el Trabajo",
    "Proyecto y Gestión de Microemprendimientos",
    "Sistemas de Información Contable III",
    "Teoría y Práctica Impositiva",
    "Economía II",
    "Arquitectura de Hardware",
    "Sistemas digitales y redes",
    "Programación",
    "Desarrollo de Sistemas Digitales",
]

# =============================================================================
# FUNCIONES AUXILIARES
# =============================================================================

def init_db(db_path=None):
    """
    Inicializa la base de datos creando la tabla 'examenes' si no existe.
    
    Args:
        db_path (str, opcional): Ruta personalizada para la base de datos.
                                 Si es None, usa la configurada en la app.
    """
    db = db_path or app.config.get('DATABASE', 'cronograma.db')
    # Asegurar que el directorio existe si la ruta contiene subdirectorios
    dirpath = os.path.dirname(os.path.abspath(db))
    if dirpath and not os.path.exists(dirpath):
        os.makedirs(dirpath, exist_ok=True)
    
    # Conectar a la base de datos y crear la tabla si no existe
    with sqlite3.connect(db) as conn:
        c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS examenes (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        fecha TEXT NOT NULL,
                        espacio_curricular TEXT NOT NULL,
                        anio TEXT NOT NULL,
                        horario TEXT NOT NULL,
                        docente TEXT NOT NULL
                    )''')
        conn.commit()

def get_db_path():
    """
    Obtiene la ruta de la base de datos desde la configuración de la app.
    
    Returns:
        str: Ruta al archivo de base de datos
    """
    return app.config.get('DATABASE', 'cronograma.db')

def formatear_fecha(fecha_str):
    """
    Convierte una fecha en formato YYYY-MM-DD a formato 'VIERNES 12/09/2025'.
    
    Args:
        fecha_str (str): Fecha en formato string YYYY-MM-DD
        
    Returns:
        str: Fecha formateada como 'VIERNES 12/09/2025' o la fecha original
             si hay error en el formato.
    """
    try:
        # Diccionario para los nombres de los días en español
        dias_semana = [
            "LUNES", "MARTES", "MIÉRCOLES", "JUEVES", 
            "VIERNES", "SÁBADO", "DOMINGO"
        ]
        
        # Parsear la fecha desde string a objeto datetime
        fecha = datetime.datetime.strptime(fecha_str, '%Y-%m-%d')
        
        # Obtener día de la semana (0=Lunes, 6=Domingo)
        dia_semana = dias_semana[fecha.weekday()]
        
        # Formatear fecha como DD/MM/YYYY
        fecha_formateada = fecha.strftime('%d/%m/%Y')
        
        # Combinar día de la semana y fecha
        return f"{dia_semana} {fecha_formateada}"
    except (ValueError, TypeError):
        # Si hay error en el formato, devolver la fecha original
        return fecha_str

def formatear_fecha_compacta(fecha_str):
    """
    Convierte una fecha en formato YYYY-MM-DD a formato compacto para PDF.
    
    Args:
        fecha_str (str): Fecha en formato string YYYY-MM-DD
        
    Returns:
        str: Fecha formateada como 'VIE 12/09/2025' para mejor ajuste en PDF
    """
    try:
        # Diccionario para los nombres abreviados de los días en español
        dias_semana_abrev = [
            "LUN", "MAR", "MIE", "JUE", 
            "VIE", "SAB", "DOM"
        ]
        
        # Parsear la fecha desde string a objeto datetime
        fecha = datetime.datetime.strptime(fecha_str, '%Y-%m-%d')
        
        # Obtener día de la semana abreviado (0=Lunes, 6=Domingo)
        dia_semana = dias_semana_abrev[fecha.weekday()]
        
        # Formatear fecha como DD/MM/YYYY
        fecha_formateada = fecha.strftime('%d/%m/%Y')
        
        # Combinar día de la semana abreviado y fecha
        return f"{dia_semana} {fecha_formateada}"
    except (ValueError, TypeError):
        # Si hay error en el formato, devolver la fecha original
        return fecha_str

def validar_datos_examen(fecha, espacio_curricular, anio, horario, docente):
    """
    Valida los datos del examen antes de insertar en la base de datos.
    
    Returns:
        tuple: (es_valido, mensaje_error)
    """
    # Validar fecha
    try:
        datetime.datetime.strptime(fecha, '%Y-%m-%d')
    except ValueError:
        return False, "Fecha inválida"
    
    # Validar que el espacio curricular esté en la lista permitida
    if espacio_curricular not in ESPACIOS_CURRICULARES:
        return False, "Espacio curricular no válido"
    
    # Validar año
    anios_permitidos = ['1° año', '2° año', '3° año', '4° año', '5° año']
    if anio not in anios_permitidos:
        return False, "Año no válido"
    
    # Validar que horario y docente no estén vacíos
    if not horario.strip():
        return False, "Horario no puede estar vacío"
    
    if not docente.strip():
        return False, "Docente no puede estar vacío"
    
    return True, ""

# =============================================================================
# MANEJO DE ERRORES
# =============================================================================

@app.errorhandler(404)
def pagina_no_encontrada(error):
    return render_template('error.html', mensaje="Página no encontrada"), 404

@app.errorhandler(500)
def error_servidor(error):
    return render_template('error.html', mensaje="Error interno del servidor"), 500

# =============================================================================
# RUTAS DE LA APLICACIÓN
# =============================================================================

@app.route('/')
def index():
    """
    Ruta principal: Muestra todos los exámenes en una tabla ordenados por fecha.
    
    Returns:
        HTML renderizado con la tabla de exámenes
    """
    db = get_db_path()
    with sqlite3.connect(db) as conn:
        c = conn.cursor()
        c.execute("SELECT * FROM examenes ORDER BY fecha")
        examenes = c.fetchall()
    
    # Convertir las fechas al formato deseado "VIERNES 12/09/2025"
    examenes_formateados = []
    for examen in examenes:
        # Convertir la fecha al nuevo formato
        fecha_original = examen[1]  # La fecha está en la posición 1
        fecha_formateada = formatear_fecha(fecha_original)
        
        # Crear una nueva tupla con la fecha formateada
        examen_lista = list(examen)
        examen_lista[1] = fecha_formateada
        examenes_formateados.append(tuple(examen_lista))
    
    return render_template('index.html', examenes=examenes_formateados)

@app.route('/agregar', methods=['GET', 'POST'])
def agregar():
    """
    Ruta para agregar nuevos exámenes.
    
    GET: Muestra el formulario para agregar examen
    POST: Procesa el formulario y guarda en la base de datos
    
    Returns:
        Redirección a la página principal o formulario HTML
    """
    if request.method == 'POST':
        # Obtener datos del formulario
        fecha = request.form.get('fecha')
        espacio_curricular = request.form.get('espacio_curricular')
        anio = request.form.get('anio')
        horario = request.form.get('horario')
        docente = request.form.get('docente')

        # Validación básica de campos obligatorios
        if not (fecha and espacio_curricular and anio and horario and docente):
            return render_template('error.html', mensaje="Faltan datos. Por favor complete todos los campos."), 400
        
        # Validación avanzada
        es_valido, mensaje_error = validar_datos_examen(fecha, espacio_curricular, anio, horario, docente)
        if not es_valido:
            return render_template('error.html', mensaje=f"Datos inválidos: {mensaje_error}"), 400

        # Guardar en la base de datos
        db = get_db_path()
        with sqlite3.connect(db) as conn:
            c = conn.cursor()
            c.execute(
                "INSERT INTO examenes (fecha, espacio_curricular, anio, horario, docente) VALUES (?, ?, ?, ?, ?)",
                (fecha, espacio_curricular, anio, horario, docente)
            )
            conn.commit()
        
        # Redirigir a la página principal después de guardar
        return redirect(url_for('index'))

    # Mostrar formulario para método GET con la lista de espacios curriculares
    return render_template('agregar.html', espacios_curriculares=ESPACIOS_CURRICULARES)

@app.route('/editar/<int:id>', methods=['GET', 'POST'])
def editar(id):
    """Editar un examen existente"""
    db = get_db_path()
    
    if request.method == 'POST':
        fecha = request.form.get('fecha')
        espacio_curricular = request.form.get('espacio_curricular')
        anio = request.form.get('anio')
        horario = request.form.get('horario')
        docente = request.form.get('docente')
        
        # Validación básica
        if not (fecha and espacio_curricular and anio and horario and docente):
            return render_template('error.html', mensaje="Faltan datos. Por favor complete todos los campos."), 400
        
        # Validación avanzada
        es_valido, mensaje_error = validar_datos_examen(fecha, espacio_curricular, anio, horario, docente)
        if not es_valido:
            return render_template('error.html', mensaje=f"Datos inválidos: {mensaje_error}"), 400
        
        with sqlite3.connect(db) as conn:
            c = conn.cursor()
            c.execute('''UPDATE examenes 
                        SET fecha=?, espacio_curricular=?, anio=?, horario=?, docente=?
                        WHERE id=?''',
                     (fecha, espacio_curricular, anio, horario, docente, id))
            conn.commit()
        
        return redirect(url_for('index'))
    
    # GET: Mostrar formulario con datos actuales
    with sqlite3.connect(db) as conn:
        c = conn.cursor()
        c.execute("SELECT * FROM examenes WHERE id=?", (id,))
        examen = c.fetchone()
    
    if not examen:
        return render_template('error.html', mensaje="Examen no encontrado"), 404
    
    return render_template('editar.html', examen=examen, espacios_curriculares=ESPACIOS_CURRICULARES)

@app.route('/eliminar/<int:id>')
def eliminar(id):
    """Eliminar un examen"""
    db = get_db_path()
    with sqlite3.connect(db) as conn:
        c = conn.cursor()
        c.execute("DELETE FROM examenes WHERE id=?", (id,))
        conn.commit()
    
    return redirect(url_for('index'))

@app.route('/exportar_pdf')
def exportar_pdf():
    """
    Exporta el cronograma de exámenes.
    
    Si ReportLab está disponible: genera un PDF con formato profesional
    Si ReportLab no está disponible: genera un archivo CSV
    
    Returns:
        Archivo PDF o CSV para descargar
    """
    db = get_db_path()
    with sqlite3.connect(db) as conn:
        c = conn.cursor()
        c.execute("SELECT fecha, espacio_curricular, anio, horario, docente FROM examenes ORDER BY fecha")
        examenes = c.fetchall()

    # Formatear las fechas para la exportación - usar formato compacto para PDF
    examenes_formateados = []
    for ex in examenes:
        ex_lista = list(ex)
        ex_lista[0] = formatear_fecha_compacta(ex_lista[0])  # Formatear la fecha en formato compacto
        examenes_formateados.append(ex_lista)
    
    if REPORTLAB_AVAILABLE:
        # Generar PDF con ReportLab
        try:
            # Crear archivo temporal para el PDF
            tmp = tempfile.NamedTemporaryFile(delete=False, suffix='.pdf')
            tmp.close()
            archivo_pdf = tmp.name

            # Configurar documento PDF
            doc = SimpleDocTemplate(archivo_pdf, pagesize=A4)
            elementos = []

            # Estilos para el PDF
            estilos = getSampleStyleSheet()
            titulo = Paragraph("Cronograma de Exámenes", estilos['Title'])
            elementos.append(titulo)
            elementos.append(Spacer(1, 12))

            # Preparar datos para la tabla con anchos de columna optimizados
            data = [["Fecha", "Espacio Curricular", "Año", "Horario", "Docente"]]
            for ex in examenes_formateados:
                data.append(list(ex))

            # Calcular anchos de columna optimizados para A4
            # A4 width: 595 points, márgenes: ~72 puntos cada lado -> ancho útil: ~450 puntos
            tabla = Table(data, repeatRows=1, colWidths=[90, 150, 50, 70, 90])  # Total: 450 puntos
            
            # Estilo mejorado para la tabla
            tabla.setStyle(TableStyle([
                # Encabezado
                ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#3498db")),
                ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke),
                ('ALIGN', (0,0), (-1,0), 'CENTER'),
                ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
                ('FONTSIZE', (0,0), (-1,0), 10),
                
                # Cuerpo de la tabla
                ('ALIGN', (0,1), (-1,-1), 'LEFT'),
                ('FONTNAME', (0,1), (-1,-1), 'Helvetica'),
                ('FONTSIZE', (0,1), (-1,-1), 8),
                ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
                
                # Bordes
                ('GRID', (0,0), (-1,-1), 0.5, colors.grey),
                ('LINEBELOW', (0,0), (-1,0), 1.5, colors.black),
                
                # Alternar colores de fila para mejor legibilidad
                ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.HexColor("#f8f9fa")]),
                
                # Padding para mejor apariencia
                ('LEFTPADDING', (0,0), (-1,-1), 6),
                ('RIGHTPADDING', (0,0), (-1,-1), 6),
                ('TOPPADDING', (0,0), (-1,-1), 4),
                ('BOTTOMPADDING', (0,0), (-1,-1), 4),
            ]))
            
            elementos.append(tabla)
            
            # Agregar pie de página con información
            elementos.append(Spacer(1, 12))
            fecha_exportacion = datetime.datetime.now().strftime("%d/%m/%Y %H:%M")
            pie_pagina = Paragraph(f"<i>Exportado el {fecha_exportacion} - Total de exámenes: {len(examenes_formateados)}</i>", estilos['Normal'])
            elementos.append(pie_pagina)

            # Generar PDF
            doc.build(elementos)

            # Enviar archivo como descarga
            return send_file(archivo_pdf, as_attachment=True, download_name="cronograma_examenes.pdf")
            
        except Exception as e:
            # Manejar errores en la generación del PDF
            return render_template('error.html', mensaje=f"Error al generar PDF: {e}"), 500
            
    else:
        # Fallback: generar CSV si ReportLab no está disponible
        try:
            tmp = tempfile.NamedTemporaryFile(delete=False, suffix='.csv', mode='w', newline='', encoding='utf-8')
            csv_path = tmp.name
            tmp.close()
            
            with open(csv_path, 'w', newline='', encoding='utf-8') as csvfile:
                writer = csv.writer(csvfile)
                writer.writerow(["Fecha", "Espacio Curricular", "Año", "Horario", "Docente"])
                for ex in examenes_formateados:
                    writer.writerow(ex)
                    
            return send_file(csv_path, as_attachment=True, download_name="cronograma_examenes.csv", mimetype='text/csv')
            
        except Exception as e:
            return render_template('error.html', mensaje=f"Error al generar CSV: {e}"), 500

# =============================================================================
# PLANTILLAS HTML (se crean automáticamente si no existen)
# =============================================================================

# Plantilla para la página principal
templates_index = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>Cronograma de Exámenes</title>
    <style>
        body { 
            font-family: Arial, sans-serif; 
            margin: 20px; 
            background-color: #f5f5f5;
        }
        .container {
            background: white;
            padding: 20px;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        h1 {
            color: #2c3e50;
            border-bottom: 2px solid #3498db;
            padding-bottom: 10px;
        }
        table { 
            border-collapse: collapse; 
            width: 100%; 
            margin-top: 20px;
        }
        th, td { 
            border: 1px solid #ddd; 
            padding: 12px; 
            text-align: left; 
        }
        th { 
            background: #3498db; 
            color: white;
            font-weight: bold;
        }
        tr:nth-child(even) {
            background-color: #f2f2f2;
        }
        tr:hover {
            background-color: #e9f7fe;
        }
        a.button { 
            display: inline-block;
            padding: 10px 15px; 
            border: none; 
            background: #3498db; 
            color: white; 
            text-decoration: none; 
            margin-right: 10px;
            border-radius: 4px;
            font-weight: bold;
            transition: background 0.3s;
        }
        a.button:hover {
            background: #2980b9;
        }
        .acciones {
            margin-bottom: 20px;
        }
        .acciones-examen {
            margin-top: 5px;
        }
        .acciones-examen a {
            color: #3498db;
            text-decoration: none;
            margin-right: 10px;
            font-size: 0.9em;
        }
        .acciones-examen a:hover {
            text-decoration: underline;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>Cronograma de Exámenes</h1>
        
        <div class="acciones">
            <a class="button" href="{{ url_for('agregar') }}">➕ Agregar nuevo examen</a>
            <a class="button" href="{{ url_for('exportar_pdf') }}">📊 Exportar (PDF o CSV)</a>
        </div>
        
        <table>
            <tr>
                <th>ID</th>
                <th>Fecha</th>
                <th>Espacio Curricular</th>
                <th>Año</th>
                <th>Horario</th>
                <th>Docente</th>
                <th>Acciones</th>
            </tr>
            {% for examen in examenes %}
            <tr>
                <td>{{ examen[0] }}</td>
                <td><strong>{{ examen[1] }}</strong></td>  <!-- Fecha formateada -->
                <td>{{ examen[2] }}</td>
                <td>{{ examen[3] }}</td>
                <td>{{ examen[4] }}</td>
                <td>{{ examen[5] }}</td>
                <td class="acciones-examen">
                    <a href="{{ url_for('editar', id=examen[0]) }}">✏️ Editar</a>
                    <a href="{{ url_for('eliminar', id=examen[0]) }}" onclick="return confirm('¿Está seguro de que desea eliminar este examen?')">🗑️ Eliminar</a>
                </td>
            </tr>
            {% else %}
            <tr><td colspan="7" style="text-align: center; padding: 20px;">No hay exámenes registrados.</td></tr>
            {% endfor %}
        </table>
    </div>
</body>
</html>
"""

# Plantilla para el formulario de agregar examen
templates_agregar = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>Agregar Examen</title>
    <style> 
        body { 
            font-family: Arial, sans-serif; 
            margin: 20px;
            background-color: #f5f5f5;
        }
        .container {
            background: white;
            padding: 20px;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            max-width: 500px;
        }
        h1 {
            color: #2c3e50;
            border-bottom: 2px solid #3498db;
            padding-bottom: 10px;
        }
        label { 
            display: block; 
            margin-top: 15px; 
            font-weight: bold;
            color: #2c3e50;
        }
        input, select {
            width: 100%;
            padding: 10px;
            margin-top: 5px;
            border: 1px solid #ddd;
            border-radius: 4px;
            box-sizing: border-box;
        }
        button { 
            margin-top: 20px;
            padding: 10px 20px;
            background: #3498db;
            color: white;
            border: none;
            border-radius: 4px;
            cursor: pointer;
            font-weight: bold;
        }
        button:hover {
            background: #2980b9;
        }
        .volver {
            display: inline-block;
            margin-top: 15px;
            color: #3498db;
            text-decoration: none;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>Agregar Examen</h1>
        
        <form method="POST">
            <label>Fecha: 
                <input type="date" name="fecha" required>
            </label>
            
            <label>Espacio Curricular: 
                <select name="espacio_curricular" required>
                    <option value="">Seleccione un espacio curricular</option>
                    {% for espacio in espacios_curriculares %}
                    <option value="{{ espacio }}">{{ espacio }}</option>
                    {% endfor %}
                </select>
            </label>
            
            <label>Año:
                <select name="anio" required>
                    <option value="">Seleccione el año</option>
                    <option value="1° año">1° año</option>
                    <option value="2° año">2° año</option>
                    <option value="3° año">3° año</option>
                    <option value="4° año">4° año</option>
                    <option value="5° año">5° año</option>
                </select>
            </label>
            
            <label>Horario: 
                <input type="text" name="horario" required placeholder="Ej: 09:00 - 11:00">
            </label>
            
            <label>Docente: 
                <input type="text" name="docente" required placeholder="Ej: GONZALEZ, MARIA">
            </label>
            
            <br>
            <button type="submit">💾 Guardar Examen</button>
        </form>
        
        <br>
        <a class="volver" href="{{ url_for('index') }}">← Volver al listado</a>
    </div>
</body>
</html>
"""

# Plantilla para editar examen
templates_editar = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>Editar Examen</title>
    <style> 
        body { 
            font-family: Arial, sans-serif; 
            margin: 20px;
            background-color: #f5f5f5;
        }
        .container {
            background: white;
            padding: 20px;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            max-width: 500px;
        }
        h1 {
            color: #2c3e50;
            border-bottom: 2px solid #3498db;
            padding-bottom: 10px;
        }
        label { 
            display: block; 
            margin-top: 15px; 
            font-weight: bold;
            color: #2c3e50;
        }
        input, select {
            width: 100%;
            padding: 10px;
            margin-top: 5px;
            border: 1px solid #ddd;
            border-radius: 4px;
            box-sizing: border-box;
        }
        button { 
            margin-top: 20px;
            padding: 10px 20px;
            background: #3498db;
            color: white;
            border: none;
            border-radius: 4px;
            cursor: pointer;
            font-weight: bold;
        }
        button:hover {
            background: #2980b9;
        }
        .volver {
            display: inline-block;
            margin-top: 15px;
            color: #3498db;
            text-decoration: none;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>Editar Examen</h1>
        
        <form method="POST">
            <label>Fecha: 
                <input type="date" name="fecha" value="{{ examen[1] }}" required>
            </label>
            
            <label>Espacio Curricular: 
                <select name="espacio_curricular" required>
                    <option value="">Seleccione un espacio curricular</option>
                    {% for espacio in espacios_curriculares %}
                    <option value="{{ espacio }}" {% if espacio == examen[2] %}selected{% endif %}>{{ espacio }}</option>
                    {% endfor %}
                </select>
            </label>
            
            <label>Año:
                <select name="anio" required>
                    <option value="">Seleccione el año</option>
                    <option value="1° año" {% if examen[3] == '1° año' %}selected{% endif %}>1° año</option>
                    <option value="2° año" {% if examen[3] == '2° año' %}selected{% endif %}>2° año</option>
                    <option value="3° año" {% if examen[3] == '3° año' %}selected{% endif %}>3° año</option>
                    <option value="4° año" {% if examen[3] == '4° año' %}selected{% endif %}>4° año</option>
                    <option value="5° año" {% if examen[3] == '5° año' %}selected{% endif %}>5° año</option>
                </select>
            </label>
            
            <label>Horario: 
                <input type="text" name="horario" value="{{ examen[4] }}" required placeholder="Ej: 09:00 - 11:00">
            </label>
            
            <label>Docente: 
                <input type="text" name="docente" value="{{ examen[5] }}" required placeholder="Ej: GONZALEZ, MARIA">
            </label>
            
            <br>
            <button type="submit">💾 Actualizar Examen</button>
        </form>
        
        <br>
        <a class="volver" href="{{ url_for('index') }}">← Volver al listado</a>
    </div>
</body>
</html>
"""

# Plantilla para página de error
templates_error = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>Error</title>
    <style>
        body { 
            font-family: Arial, sans-serif; 
            margin: 40px; 
            background-color: #f8d7da;
        }
        .container { 
            background: white; 
            padding: 30px; 
            border-radius: 8px; 
            border-left: 4px solid #dc3545;
            text-align: center;
        }
        h1 { 
            color: #721c24; 
            margin-bottom: 20px;
        }
        p {
            color: #856404;
            font-size: 1.1em;
            margin-bottom: 20px;
        }
        .volver { 
            display: inline-block;
            padding: 10px 20px;
            background: #007bff; 
            color: white; 
            text-decoration: none; 
            border-radius: 4px;
            font-weight: bold;
        }
        .volver:hover {
            background: #0056b3;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>❌ Error</h1>
        <p>{{ mensaje }}</p>
        <a class="volver" href="{{ url_for('index') }}">← Volver al inicio</a>
    </div>
</body>
</html>
"""

# Crear directorio de plantillas y archivos si no existen
if not os.path.exists('templates'):
    os.makedirs('templates')
    
with open('templates/index.html', 'w', encoding='utf-8') as f:
    f.write(templates_index)
    
with open('templates/agregar.html', 'w', encoding='utf-8') as f:
    f.write(templates_agregar)
    
with open('templates/editar.html', 'w', encoding='utf-8') as f:
    f.write(templates_editar)
    
with open('templates/error.html', 'w', encoding='utf-8') as f:
    f.write(templates_error)

# =============================================================================
# TESTS UNITARIOS
# =============================================================================

import unittest

class CronogramaAppTests(unittest.TestCase):
    """Suite de tests para la aplicación Cronograma"""
    
    def setUp(self):
        """
        Configuración inicial antes de cada test.
        Usa una base de datos temporal para pruebas.
        """
        self.test_db = 'test_cronograma.db'
        if os.path.exists(self.test_db):
            os.remove(self.test_db)
        app.config['DATABASE'] = self.test_db
        init_db(self.test_db)
        app.config['TESTING'] = True
        self.client = app.test_client()

    def tearDown(self):
        """Limpieza después de cada test: elimina la base de datos temporal"""
        if os.path.exists(self.test_db):
            try:
                os.remove(self.test_db)
            except Exception:
                pass

    def test_index_empty(self):
        """Test: La página principal carga correctamente cuando no hay exámenes"""
        rv = self.client.get('/')
        self.assertEqual(rv.status_code, 200)
        self.assertIn(b'Cronograma de Examenes', rv.data)

    def test_agregar_get(self):
        """Test: El formulario de agregar examen se carga correctamente"""
        rv = self.client.get('/agregar')
        self.assertEqual(rv.status_code, 200)
        self.assertIn(b'Agregar Examen', rv.data)
        # Verificar que se incluyen los espacios curriculares en el formulario
        self.assertIn(b'Matem\xc3\xa1tica', rv.data)  # "Matemática" en UTF-8
        self.assertIn(b'Lengua y Literatura', rv.data)

    def test_agregar_post_and_list(self):
        """Test: Se puede agregar un examen y aparece en el listado"""
        data = {
            'fecha': '2025-08-22',
            'espacio_curricular': 'Matemática',
            'anio': '1° año',
            'horario': '09:30',
            'docente': 'DIAZ, PAMELA'
        }
        rv = self.client.post('/agregar', data=data, follow_redirects=True)
        self.assertEqual(rv.status_code, 200)
        # Verificar que el docente aparece en el listado
        self.assertIn(b'DIAZ, PAMELA', rv.data)
        # Verificar que la materia aparece en el listado
        self.assertIn(b'Matem\xc3\xa1tica', rv.data)  # "Matemática" en UTF-8

    def test_export_route(self):
        """Test: La ruta de exportación responde correctamente"""
        rv = self.client.get('/exportar_pdf')
        self.assertEqual(rv.status_code, 200)
        # Verificar que se devuelve un archivo para descargar
        cd = rv.headers.get('Content-Disposition', '')
        self.assertTrue('attachment' in cd or 'inline' in cd or rv.data)

    def test_formatear_fecha(self):
        """Test: La función de formateo de fechas funciona correctamente"""
        # Test con fecha válida
        fecha_formateada = formatear_fecha('2025-09-12')
        self.assertIn('VIERNES', fecha_formateada)
        self.assertIn('12/09/2025', fecha_formateada)
        
        # Test con fecha inválida
        fecha_invalida = formatear_fecha('fecha-invalida')
        self.assertEqual('fecha-invalida', fecha_invalida)

    def test_formatear_fecha_compacta(self):
        """Test: La función de formateo de fechas compacta funciona correctamente"""
        # Test con fecha válida
        fecha_formateada = formatear_fecha_compacta('2025-09-12')
        self.assertIn('VIE', fecha_formateada)
        self.assertIn('12/09/2025', fecha_formateada)
        
        # Test con fecha inválida
        fecha_invalida = formatear_fecha_compacta('fecha-invalida')
        self.assertEqual('fecha-invalida', fecha_invalida)

    def test_editar_examen(self):
        """Test: Se puede editar un examen existente"""
        # Primero crear un examen
        data = {
            'fecha': '2025-08-22',
            'espacio_curricular': 'Matemática',
            'anio': '1° año',
            'horario': '09:30',
            'docente': 'DIAZ, PAMELA'
        }
        self.client.post('/agregar', data=data)
        
        # Editar el examen
        data_editado = {
            'fecha': '2025-08-23',
            'espacio_curricular': 'Lengua',
            'anio': '2° año',
            'horario': '14:00',
            'docente': 'GOMEZ, CARLOS'
        }
        rv = self.client.post('/editar/1', data=data_editado, follow_redirects=True)
        self.assertEqual(rv.status_code, 200)
        self.assertIn(b'GOMEZ, CARLOS', rv.data)

    def test_eliminar_examen(self):
        """Test: Se puede eliminar un examen"""
        # Primero crear un examen
        data = {
            'fecha': '2025-08-22',
            'espacio_curricular': 'Matemática',
            'anio': '1° año',
            'horario': '09:30',
            'docente': 'DIAZ, PAMELA'
        }
        self.client.post('/agregar', data=data)
        
        # Eliminar el examen
        rv = self.client.get('/eliminar/1', follow_redirects=True)
        self.assertEqual(rv.status_code, 200)
        # Verificar que ya no aparece en el listado
        self.assertNotIn(b'DIAZ, PAMELA', rv.data)

# =============================================================================
# EJECUCIÓN DE LA APLICACIÓN
# =============================================================================

if __name__ == '__main__':
    # Inicializar la base de datos principal
    init_db()
    
    # Manejar argumentos de línea de comandos
    if len(sys.argv) > 1 and sys.argv[1] == 'test':
        # Ejecutar tests unitarios
        print("Ejecutando tests unitarios...")
        unittest.main(argv=[sys.argv[0]])
    else:
        # Ejecutar la aplicación en modo producción
        print("Iniciando servidor Flask Cronograma App...")
        print("Accede en: http://localhost:5000")
        print("Presiona CTRL+C para detener el servidor")
        # Importante: desactivar debug y recargador para entornos restringidos
        app.run(host='0.0.0.0', port=5000, debug=False, use_reloader=False)