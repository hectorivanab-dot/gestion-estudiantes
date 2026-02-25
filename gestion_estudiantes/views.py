import os
from django.shortcuts import render, redirect
from django.contrib import messages
# from django.http import  HttpRequestForbidden
from firebase_admin import firestore, auth
from config.firebaseConnection import initialize_firebase
from functools import wraps
import requests

db = initialize_firebase()

def bienvenido(request):
    return render(request, 'bienvenido.html')

def registro_usuario(request):
    mensaje = None
    if request.method == 'POST':
        email = request.POST.get('email')
        password = request.POST.get('password')
        try:
            # Vamos a crear en Firebase auth
            user = auth.create_user(
                email = email,
                password = password
            )

            # Crear en Firestore

            db.collection('educadores').document(user.uid).set({
                'email' : email,
                'uid' : user.uid,
                'rol' : 'Profesor-a/Instructor-a',
                'fecha_registro' : firestore.SERVER_TIMESTAMP,
            })

            mensaje = f"Usuario registrado correctamente con el UID: {user.uid}"
        except Exception as e:
            mensaje = f"Error: {e}"
    return render(request, 'registro.html', {'mensaje' : mensaje})

def login_required_firebase(view_func):
    # Este decorador personalizado va a proteger nuestras vistas
    # si el usuario no ha iniciado sesión.
    # Si el UID no existe, lo va a enviar a iniciar sesión.

    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if 'uid' not in request.session:
            messages.warning(request, "Warning, no has iniciado sesión")
            return redirect('login')
        return view_func(request, *args, **kwargs)
    return _wrapped_view

# logica para solicitarle a Google la validación

def login(request):
    if ('uid' in request.session):
        return redirect('dashboard')
    
    if request.method == 'POST':
        email = request.POST.get('email')
        password = request.POST.get('password')
        apiKey = os.getenv('FIREBASE_WEB_API_KEY')

        # Endpoind oficial de Google
        url = f"https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key={apiKey}"

        payload = {
            "email" : email,
            "password" : password,
            "returnSecureToken" : True
        }

        try:

            # petición http al servicio de autenticación de google
            response = requests.post(url, json=payload)
            data = response.json()

            if response.status_code == 200:
                # All good
                request.session['uid'] = data['localId']
                request.session['email'] = data['email']
                request.session['idToken'] = data['idToken']
                messages.success(request, f'✔ Acceso correcto al sistema')
                return redirect('listar_estudiantes')
            else:
                # Error: Analizarlo
                errorMessage = data.get('error', {}).get('message', 'UNKNOWN ERROR')

                errores_comunes = {
                    'INVALID_LOGIN_CREDENTIALS': 'La contraseña es incorrecta o el correo no es válido.',
                    'EMAIL_NOT_FOUND': 'Este correo no está registrado en el sistema.',
                    'USER_DISABLED': 'Esta cuenta ha sido inhabilitada por el administrador.',
                    'TOO_MANY_ATTEMPTS_TRY_LATER': 'Demasiados intentos fallidos. Espere unos minutos.'
                }

                mensaje_usuario = errores_comunes.get(errorMessage, "Error de autenticación, revisa tus credenciales")
                messages.error(request, mensaje_usuario)
        except requests.exceptions.RequestException as e:
            messages.error(request, "Error de conexión con el servidor")
        except Exception as e:
            messages.error(request, f"Error inesperado: {str(e)}")
    return render(request, 'login.html')

def cerrar_sesion(request):
    request.session.flush()
    messages.info(request, 'Has cerrado sesión correctamente')
    return redirect('login')

@login_required_firebase #Verifica que el user esté logueado
def dashboard(request):
    # Este es el panl principal, este solo lo permite si el decorador lo permite
    # Recuparar los datos de Firestore

    uid= request.session.get('uid')
    datosUser = {}

    try:
        # Consulta a Firestore usando SDK 
        doc_ref = db.collection('educadores').document(uid)
        doc = doc_ref.get()

        if doc.exists:
            datosUser = doc.to_dict()
        else:
            # Si entra en el out pero no tiene un perfil en Firestore vamos a manejar el caso
            datosUser = {
                'email' : request.session.get('email'),
                'rol' : request.session.get('rol'),
                'uid' : request.session.get('uid'),
                'fecha_registro' : firestore.SERVER_TIMESTAMP
            }
    except Exception as e:
        messages.error(request, f'Error al cargar los datos de la base de datos: {e}')
    return render(request, 'dashboard.html', {'datos': datosUser})

@login_required_firebase
def listar_estudiantes(request):
    """
    READ: Recuperar los estudiantes del usuario desde firestore
    """

    uid = request.session.get('uid')
    estudiantes = []

    try:
        #Filtramos los estudiantes que registro del usuario

        docs = db.collection('estudiantes').where('usuario_id', '==', uid).stream()
        for doc in docs:
            estudiante = doc.to_dict()
            estudiante['id'] = doc.id
            estudiantes.append(estudiante)
    except Exception as e:
        messages.error(request, f"Hubo un error al obtener los estudiantes {e}")
    
    return render(request, 'estudiantes/listar.html', {'estudiantes' : estudiantes})

@login_required_firebase # Verifica que el usuario esta loggeado
def anadir_estudiante(request):
    """
    CREATE: Reciben los datos desde el formulario y se suben a Firebase
    """
    if (request.method == 'POST'):
        nombre_estudiante = request.POST.get('nombre_estudiante')
        edad = request.POST.get('edad')
        correo = request.POST.get('correo')
        uid = request.session.get('uid')

        try:
            db.collection('estudiantes').add({
                'nombre_estudiante': nombre_estudiante,
                'edad': edad,
                'correo' : correo,
                'usuario_id': uid,
                'fecha_registro': firestore.SERVER_TIMESTAMP
            })
            messages.success(request, "estudiante registrado con exito")
            return redirect('listar_estudiantes')
        except Exception as e:
            messages.error(request, f"Error al registrar al estudiante {e}")
        
    return render(request, 'estudiantes/form.html')

@login_required_firebase # Verifica que el usuario esta loggeado
def eliminar_estudiante(request, estudiante_id):
    """
    DELETE: Eliminar un documento especifico por id
    """
    try:
        db.collection('estudiantes').document(estudiante_id).delete()
        messages.success(request, "🗑️ estudiante eliminado.")
    except Exception as e:
        messages.error(request, f"Error al eliminar: {e}")

    return redirect('listar_estudiantes')

@login_required_firebase # Verifica que el usuario esta loggeado
def editar_estudiante(request, estudiante_id):
    """
    UPDATE: Recupera los datos del estudiante especifico y actualiza los campos en firebase
    """
    uid = request.session.get('uid')
    estudiante_ref = db.collection('estudiantes').document(estudiante_id)

    try:
        doc = estudiante_ref.get()

        if not doc.exists:
            messages.error(request, "El estudiante no existe")
            return redirect('listar_estudiante')
        
        estudiante_data = doc.to_dict()

        if estudiante_data.get('usuario_id') != uid:
            messages.error(request, "No tienes permiso para editar este estudiante")
            return redirect('listar_estudiante')
        
        if request.method == 'POST':
            nuevo_titulo = request.POST.get('nombre_estudiante')
            nueva_edad = request.POST.get('edad')
            nuevo_correo = request.POST.get('correo')

            estudiante_ref.update({
                'nombre_estudiante': nuevo_titulo,
                'edad': nueva_edad,
                'correo': nuevo_correo,
                'fecha_actualizacion': firestore.SERVER_TIMESTAMP
            })

            messages.success(request, "✅ estudiante actualizado correctamente.")
            return redirect('listar_estudiantes')
    except Exception as e:
        messages.error(request, f"Error al editar el estudianteo: {e}")
        return redirect('listar_estudiantes')
    
    return render(request, 'estudiantes/editar.html', {'estudiante': estudiante_data, 'id': estudiante_id})