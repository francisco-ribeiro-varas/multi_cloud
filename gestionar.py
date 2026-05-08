from flask import Flask, render_template, request, redirect, url_for, send_from_directory
from flaskext.mysql import MySQL
from pymongo import MongoClient
import os
from werkzeug.utils import secure_filename

app = Flask(__name__)

# Configuración de carpetas
UPLOAD_FOLDER = os.path.join(app.root_path, 'uploads')
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
mongo_client = MongoClient("mongodb://127.0.0.1:27017/")
mongo_db = mongo_client["multi_cloud_backup"]
mongo_coleccion = mongo_db["tareas"]

@app.route('/')
def index():
    cur = mysql.get_db().cursor()
    cur.execute("SELECT * FROM tareas WHERE imagen_url IS NULL OR imagen_url = ''")
    datos = cur.fetchall()
    return render_template('index.ejs', tareas=datos)

@app.route('/formulario')
def formulario():
    return render_template('agregar.ejs')

@app.route('/guardar', methods=['POST'])
def guardar():
    nombre = request.form['nombre']
    prioridad = request.form['prioridad']
    fecha = request.form['fecha']
    cur = mysql.get_db().cursor()
    cur.execute("INSERT INTO tareas (nombre, prioridad, fecha_entrega) VALUES (%s, %s, %s)", (nombre, prioridad, fecha))
    mysql.get_db().commit()
    mongo_coleccion.insert_one({"nombre": nombre, "prioridad": prioridad, "fecha_entrega": fecha, "imagen_url": None})
    return redirect(url_for('index'))

@app.route('/completar_menu/<int:id>')
def completar_menu(id):
    cur = mysql.get_db().cursor()
    cur.execute("SELECT * FROM tareas WHERE ID = %s", (id,))
    tarea = cur.fetchone()
    return render_template('completar_form.ejs', tarea=tarea)

@app.route('/subir_completada/<int:id>', methods=['POST'])
def subir_completada(id):
    file = request.files['imagen']
    if file:
        filename = secure_filename(file.filename)
        file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
        
        # IMPORTANTE: Guardamos solo el nombre del archivo o la ruta relativa correcta
        url_foto = filename 
        
        cur = mysql.get_db().cursor()
        cur.execute("SELECT nombre FROM tareas WHERE ID = %s", (id,))
        nombre_tarea = cur.fetchone()[0]
        
        cur.execute("UPDATE tareas SET imagen_url = %s WHERE ID = %s", (url_foto, id))
        mysql.get_db().commit()
        
        mongo_coleccion.update_one({"nombre": nombre_tarea}, {"$set": {"imagen_url": url_foto}})
    return redirect(url_for('historial'))

@app.route('/historial')
def historial():
    cur = mysql.get_db().cursor()
    cur.execute("SELECT * FROM tareas WHERE imagen_url IS NOT NULL AND imagen_url != ''")
    datos = cur.fetchall()
    return render_template('historial.ejs', tareas=datos)

# ESTA FUNCIÓN ES LA QUE "MUESTRA" LA IMAGEN AL NAVEGADOR
@app.route('/ver_foto/<filename>')
def ver_foto(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

if __name__ == '__main__':
    app.run(debug=True, port=3000)