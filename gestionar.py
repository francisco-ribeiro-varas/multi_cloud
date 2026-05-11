from flask import Flask, render_template, request, redirect, url_for
from flaskext.mysql import MySQL
from pymongo import MongoClient
import os
from werkzeug.utils import secure_filename

app = Flask(__name__)

# Configuración de carpetas
UPLOAD_FOLDER = os.path.join('static', 'uploads')
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# --- CONFIGURACIÓN MYSQL ---
mysql = MySQL()
app.config['MYSQL_DATABASE_HOST'] = 'localhost'
app.config['MYSQL_DATABASE_USER'] = 'root'
app.config['MYSQL_DATABASE_PASSWORD'] = ''
app.config['MYSQL_DATABASE_DB'] = 'multi_cloud_db'
mysql.init_app(app)

# --- CONFIGURACIÓN MONGODB ---
try:
    mongo_client = MongoClient("mongodb://127.0.0.1:27017/", serverSelectionTimeoutMS=2000)
    mongo_db = mongo_client["multi_cloud_backup"]
    mongo_coleccion = mongo_db["tareas"]
except:
    print("⚠️ No se pudo conectar a MongoDB")

# 1. INICIO CON RESCATE
@app.route('/')
def index():
    datos = []
    try:
        cur = mysql.get_db().cursor()
        cur.execute("SELECT ID, nombre, prioridad, CAST(fecha_entrega AS CHAR), imagen_url FROM tareas WHERE imagen_url IS NULL OR imagen_url = ''")
        datos = cur.fetchall()
        if not datos: raise Exception("Vacío")
    except:
        # Si MySQL falla, saca las pendientes de Mongo
        print("Rescatando pendientes de MongoDB...")
        tareas_mongo = list(mongo_coleccion.find({"imagen_url": None}))
        datos = [(0, t['nombre'], t['prioridad'], t['fecha_entrega'], None) for t in tareas_mongo]
    
    return render_template('index.ejs', tareas=datos)

@app.route('/formulario')
def formulario():
    return render_template('agregar.ejs')

@app.route('/guardar', methods=['POST'])
def guardar():
    nombre = request.form['nombre']
    prioridad = request.form['prioridad']
    fecha = request.form['fecha']
    
    # Guardar en MySQL
    try:
        db = mysql.get_db()
        cur = db.cursor()
        cur.execute("INSERT INTO tareas (nombre, prioridad, fecha_entrega) VALUES (%s, %s, %s)", (nombre, prioridad, fecha))
        db.commit()
    except:
        print("No se pudo guardar en MySQL, pero se guardará en Mongo")

    # Guardar en MongoDB (Respaldo)
    mongo_coleccion.insert_one({
        "nombre": nombre, 
        "prioridad": prioridad, 
        "fecha_entrega": str(fecha), 
        "imagen_url": None
    })
    return redirect(url_for('index'))

@app.route('/completar_menu/<int:id>')
def completar_menu(id):
    try:
        cur = mysql.get_db().cursor()
        cur.execute("SELECT ID, nombre, prioridad, CAST(fecha_entrega AS CHAR), imagen_url FROM tareas WHERE ID = %s", (id,))
        tarea = cur.fetchone()
    except:
        tarea = (id, "Tarea de Respaldo", "Alta", "2026-05-01", None)
    return render_template('completar_form.ejs', tarea=tarea)

@app.route('/subir_completada/<int:id>', methods=['POST'])
def subir_completada(id):
    file = request.files['imagen']
    nombre_tarea = request.form.get('nombre_tarea') # Asegúrate de enviar esto desde el form
    
    if file:
        filename = secure_filename(file.filename)
        file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
        
        # Actualizar MySQL
        try:
            db = mysql.get_db()
            cur = db.cursor()
            cur.execute("UPDATE tareas SET imagen_url = %s WHERE ID = %s", (filename, id))
            db.commit()
        except: pass
        
        # Actualizar Mongo (Sincronización)
        mongo_coleccion.update_one({"nombre": nombre_tarea}, {"$set": {"imagen_url": filename}})
        
    return redirect(url_for('historial'))

# 2. HISTORIAL CON RESCATE (LO QUE QUERÍAS)
@app.route('/historial')
def historial():
    datos_finales = []
    try:
        cur = mysql.get_db().cursor()
        cur.execute("SELECT ID, nombre, prioridad, CAST(fecha_entrega AS CHAR), imagen_url FROM tareas WHERE imagen_url IS NOT NULL AND imagen_url != ''")
        datos_mysql = cur.fetchall()
        if datos_mysql:
            datos_finales = datos_mysql
        else: raise Exception("MySQL vacío")
    except:
        print("⚠️ MySQL falló. Cargando historial desde MongoDB...")
        tareas_mongo = list(mongo_coleccion.find({"imagen_url": {"$ne": None}}))
        datos_finales = [(0, t['nombre'], t['prioridad'], t['fecha_entrega'], t['imagen_url']) for t in tareas_mongo]

    return render_template('historial.ejs', tareas=datos_finales)

if __name__ == '__main__':
    app.run(debug=True, port=3000)