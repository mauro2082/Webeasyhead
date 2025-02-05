from flask import Flask, render_template, request, redirect, url_for, abort, session
import sqlite3
import paypalrestsdk
from functools import wraps
import os
import json
from dotenv import load_dotenv
import mysql.connector
from werkzeug.security import generate_password_hash, check_password_hash  # Para hash de contraseñas


# Cargar las variables de entorno
load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "mysecretkey")

# Configuración de PayPal con variables de entorno (debe tener un archivo .env)
paypalrestsdk.configure({
    'mode': 'live',  # 'live' para producción
    'client_id': os.getenv('PAYPAL_CLIENT_ID'),
    'client_secret': os.getenv('PAYPAL_CLIENT_SECRET')
})

def get_db_connection():
    """
    Establece una conexión a la base de datos MySQL.
    Usa variables de entorno para la configuración y valores predeterminados si faltan.
    """
    try:
        # Conectar a la base de datos usando los valores de las variables de entorno
        conn = mysql.connector.connect(
            host=os.getenv("DB_HOST", "localhost"),
            user=os.getenv("DB_USER", "root"),
            password=os.getenv("DB_PASSWORD", ""),
            database=os.getenv("DB_NAME", "database")
        )

        return conn
    except mysql.connector.Error as err:
        # Manejo de errores específicos de MySQL
        if err.errno == mysql.connector.errorcode.ER_ACCESS_DENIED_ERROR:
            print("Error: Usuario o contraseña incorrectos.")
        elif err.errno == mysql.connector.errorcode.ER_BAD_DB_ERROR:
            print("Error: La base de datos no existe.")
        else:
            print(f"Error inesperado al conectar a la base de datos: {err}")
        return None  # Devuelve None si no se pudo conectar


def create_table():
    """
    Crea la tabla `feedback` en la base de datos si no existe.
    """
    conn = get_db_connection()
    if conn is None:
        print("Error: No se pudo conectar a la base de datos para crear la tabla.")
        return
    
    try:
        cursor = conn.cursor()
        # Comando SQL para crear la tabla
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS feedback (
                id INT AUTO_INCREMENT PRIMARY KEY,
                email VARCHAR(255) NOT NULL,
                text TEXT NOT NULL,
                name VARCHAR(255) NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        conn.commit()  # Confirmar la creación de la tabla
        print("Tabla `feedback` creada o ya existía.")
    except mysql.connector.Error as err:
        print(f"Error al crear la tabla: {err}")
    finally:
        conn.close()
        
        
def create_users_table():
    
    conn = get_db_connection()
    if conn is None:
        print("Error: No se pudo conectar a la base de datos para crear la tabla.")
        return

    try:
        cursor = conn.cursor()
        cursor.execute('''
          CREATE TABLE IF NOT EXISTS users (
             id INT AUTO_INCREMENT PRIMARY KEY,
             username VARCHAR(150) NOT NULL UNIQUE,
             email VARCHAR(255) NOT NULL UNIQUE,
             password_hash VARCHAR(255) NOT NULL,
             created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        ''')
        conn.commit()
        print("Tabla `users` creada o ya existía.")
    except mysql.connector.errors.ProgrammingError as err: # Captura errores de sintaxis SQL
        print(f"Error de sintaxis SQL al crear la tabla `users`: {err}")
    except mysql.connector.errors.IntegrityError as err: # Captura errores de integridad (ej. clave duplicada)
        print(f"Error de integridad al crear la tabla `users`: {err}")
    except mysql.connector.Error as err: # Captura otros errores de MySQL
        print(f"Otro error de MySQL al crear la tabla `users`: {err}")
    finally:
        if conn.is_connected(): # Verifica si la conexión está abierta antes de cerrarla
            cursor.close()
            conn.close()

def requires_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))  # Redirige a la página de inicio de sesión si no está autenticado
        return f(*args, **kwargs)
    return decorated


@app.route('/feedback', methods=['GET', 'POST'])
@requires_auth
def feedback():
    if request.method == 'POST':
        # Procesar datos del formulario
        name = request.form['name']
        email = request.form['email']
        text = request.form['text']

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('INSERT INTO feedback (name, email, text) VALUES (%s, %s, %s)', (name, email, text))
        conn.commit()
        cursor.close()
        conn.close()

        return redirect('/inicio')  # Redirige para mostrar los comentarios

    # Si es GET, simplemente muestra la página con los comentarios
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute('SELECT id, name, email, text FROM feedback')
    feedbacks = cursor.fetchall()
    cursor.close()
    conn.close()
    return render_template('/feedback.html', feedbacks=feedbacks)


# ruta eliminar comentario 

@app.route('/feedback/delete/<int:feedback_id>', methods=['POST'])
def delete_feedback(feedback_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('DELETE FROM feedback WHERE id = %s', (feedback_id,))
    conn.commit()
    cursor.close()
    conn.close()

    return redirect(url_for('feedback'))

# Redirigir a la página de inicio si acceden a la raíz '/'
@app.route('/')
def redirect_to_inicio():
    response = redirect(url_for('index'))
    response.headers["Content-Type"] = "text/html; charset=UTF-8"
    return response

# Autenticación
def check_auth(username, password):
    return username == '1' and password == '1'

def authenticate():
    return abort(401, 'Unauthorized Access')

def requires_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        from flask import request, Response
        auth = request.authorization
        if not auth or not check_auth(auth.username, auth.password):
            return Response(
                'Login Required!', 401,
                {'WWW-Authenticate': 'Basic realm="Login Required"'}
            )
        return f(*args, **kwargs)
    return decorated


@app.route('/logout')
def logout():
    session.pop('user_id', None)
    session.pop('username', None)
    return redirect(url_for('index'))


# Página principal
@app.route('/inicio')
def index():
    return render_template('inicio.html')

# Crear sesión de pago con PayPal
@app.route('/create-checkout-session', methods=['POST'])
def create_checkout_session():
    product = request.form.get('product')
    
    # Precios
    prices = {
        'comercial1': 15000,  # en centavos
        'comercial2': 25000,
        'comercial3': 35000,
        'empresarial1': 50000,
        'particular1': 75000
    }
    
    if product not in prices:
        return 'Producto no encontrado', 404
    
    amount = prices[product] / 100  # Dividir entre 100 para convertir a pesos

    # Crear una nueva sesión de pago en PayPal
    payment = paypalrestsdk.Payment({
        "intent": "sale",
        "payer": {
            "payment_method": "paypal"
        },
        "redirect_urls": {
            "return_url": url_for('success', _external=True),
            "cancel_url": url_for('cancel', _external=True)
        },
        "transactions": [{
            "item_list": {
                "items": [{
                    "name": product,
                    "sku": product,
                    "price": amount,
                    "currency": "MXN",  # Cambiado a pesos mexicanos
                    "quantity": 1
                }]
            },
            "amount": {
                "total": amount,
                "currency": "MXN"  # Cambiado a pesos mexicanos
            },
            "description": "Compra de " + product
        }]
    })
    
    if payment.create():
        for link in payment.links:
            if link.rel == "approval_url":
                approval_url = link.href
                return redirect(approval_url)
    else:
        return f'Error al crear la sesión de pago: {payment.error["message"]}', 500

# Página de éxito
@app.route('/success')
def success():
    return render_template('success.html')

# Página Portafolio
@app.route('/portafolio')
def portfolio():
    try:
        # Obtener la ruta absoluta del archivo
        base_dir = os.path.abspath(os.path.dirname(__file__))
        json_path = os.path.join(base_dir, 'data.json')

        # Leer el archivo JSON
        with open(json_path, 'r', encoding='utf-8') as f:
            doctors = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        doctors = []  # En caso de error, usa una lista vacía

    return render_template('portafolio.html', doctors=doctors)



# Ruta para la página "iniciar sesión"


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        conn = get_db_connection()
        if conn is None:
            return "Error: No se pudo conectar a la base de datos.", 500

        try:
            cursor = conn.cursor(dictionary=True)
            cursor.execute('SELECT * FROM users WHERE username = %s', (username,))
            user = cursor.fetchone()
            cursor.close()
        finally:
            conn.close()

        if user and check_password_hash(user['password_hash'], password):
            session['user_id'] = user['id']
            session['username'] = user['username']
            return redirect(url_for('feedback'))
        else:
            return "Usuario o contraseña incorrectos", 401
        
    return render_template('feedback.html')


@app.route('/iniciarSesion', methods=['GET', 'POST'])
def iniciarSesion():
    return render_template('iniciarSesion.html')


# Ruta para la página "registro"


@app.route('/registro', methods=['GET', 'POST'])
def registro():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        confirm_password = request.form['confirm-password']

        if password != confirm_password:
            return "Las contraseñas no coinciden", 400

        password_hash = generate_password_hash(password)

        conn = get_db_connection()
        if conn is None:
            return "Error: No se pudo conectar a la base de datos.", 500

        try:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO users (username, email, password_hash)
                VALUES (%s, %s, %s)
            ''', (username, email, password_hash))
            conn.commit()
            cursor.close()
        except mysql.connector.Error as err:
            return f"Error al registrar el usuario: {err}", 500
        finally:
            conn.close()

        return redirect(url_for('index'))

    return render_template('registro.html')




# Ruta para la página "Afíliate"
@app.route('/afiliate')
def afiliate():
    return render_template('afiliate.html')


# Enviar comentario
""" @app.route('/feedback')
def feedback():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT name, email, text FROM feedback")
    feedbacks = cursor.fetchall()
    cursor.close()
    conn.close()
    return render_template('feedback.html', feedbacks=feedbacks)
 """

if __name__ == "__main__":
    create_table()  # Crear tabla feedback
    create_users_table()  # Crear tabla users
    app.run(debug=True)
