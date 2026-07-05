# SISTEMA DE PEAJE - GARITA
# v18
# Corrección fuerte:
# - No repite infinitamente las entradas
# - Máximo 3 intentos por bloque
# - Si falla, sale limpiamente
# - Sin spam de errores
# - Sin traceback

import os
import re
from datetime import datetime

garita_usuarios = [
    {'supervisor': '123'},
    {'cajero': '321'}
]

tarifas_peaje = {
    'vehiculo': 500,
    'moto': 250,
    'camion': 1500
}

vehiculos_registrados = [
    {'placa': 'ABC123', 'tipo': 'vehiculo', 'propietario': 'EmpresaX'},
    {'placa': 'MOTO01', 'tipo': 'moto', 'propietario': 'LuisPerez'},
    {'placa': 'TRK999', 'tipo': 'camion', 'propietario': 'TransporteSA'}
]

movimientos_peaje = []
registro_eventos = []
operador_actual = None

MAX_CARACTERES = 15
MAX_INTENTOS = 3
TIPOS_VALIDOS = {'vehiculo', 'moto', 'camion'}
OPCIONES_MENU = {'0', '1', '2', '3', '4', '5', '6', '7', '8', '9'}

def titulo(texto):
    print("\n" + "=" * 60)
    print(texto.center(60))
    print("=" * 60)

def error_unico():
    print("Error: no se permite eso")

def cierre_seguridad():
    print("Programa cerrado por seguridad")

def registrar_evento(funcion, mensaje):
    registro_eventos.append({
        'fecha': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        'funcion': funcion,
        'mensaje': mensaje
    })

def buscar_usuario(nombre):
    for cred in garita_usuarios:
        if nombre in cred:
            return cred
    return None

def obtener_clave_operador(nombre):
    cred = buscar_usuario(nombre)
    return cred.get(nombre) if cred else None

def buscar_vehiculo_por_placa(placa):
    placa = str(placa).strip().upper()
    for v in vehiculos_registrados:
        if str(v.get('placa', '')).upper() == placa:
            return v
    return None

def validar_texto(texto, espacios=False):
    if texto is None:
        return False
    texto = str(texto).strip()
    if not texto or len(texto) > MAX_CARACTERES:
        return False
    patron = r'^[A-Za-z0-9 ]+$' if espacios else r'^[A-Za-z0-9]+$'
    return re.fullmatch(patron, texto) is not None

def leer_texto(prompt, mayus=False, minus=False, espacios=False):
    try:
        valor = input(prompt)
        if mayus:
            valor = valor.upper()
        if minus:
            valor = valor.lower()
        if not validar_texto(valor, espacios=espacios):
            error_unico()
            return None
        return valor.strip()
    except:
        error_unico()
        return None

def leer_entero(prompt):
    try:
        valor = input(prompt).strip()
        if len(valor) > MAX_CARACTERES:
            error_unico()
            return None
        return int(valor)
    except:
        error_unico()
        return None

def confirmar(prompt="¿Confirmar? (s/n): "):
    try:
        r = input(prompt).strip().lower()
        return r == 's'
    except:
        error_unico()
        return False

def leer_opcion_menu():
    try:
        op = input("Seleccione opción: ").strip()
        if len(op) != 1 or op not in OPCIONES_MENU:
            error_unico()
            return None
        return op
    except:
        error_unico()
        return None

def autenticar_garita():
    global operador_actual
    titulo("INICIO DE SESIÓN")

    intentos = 0
    while intentos < MAX_INTENTOS:
        usuario = leer_texto("Nombre de operador: ", minus=True)
        clave = leer_texto("Contraseña: ")

        if usuario is None or clave is None:
            intentos += 1
            if intentos < MAX_INTENTOS:
                print("Tienes otro intento más")
            continue

        clave_real = obtener_clave_operador(usuario)
        if clave_real == clave:
            operador_actual = usuario
            registrar_evento("autenticar_garita", f"Usuario {usuario} autenticado")
            print(f"\nBienvenido, {usuario}")
            input("ENTER para continuar")
            return True

        error_unico()
        intentos += 1
        if intentos < MAX_INTENTOS:
            print("Tienes otro intento más")

    cierre_seguridad()
    return False

def listar_usuarios():
    titulo("USUARIOS REGISTRADOS")
    for cred in garita_usuarios:
        for usuario in cred:
            print(f"Usuario: {usuario}")
    input("ENTER para volver")

def agregar_usuario():
    titulo("CREAR USUARIO")
    usuario = leer_texto("Nuevo usuario: ", minus=True)
    if usuario is None:
        return
    if buscar_usuario(usuario):
        error_unico()
        return
    clave = leer_texto("Nueva contraseña: ")
    if clave is None:
        return
    rol = leer_texto("Rol (supervisor/cajero): ", minus=True)
    if rol not in {'supervisor', 'cajero'}:
        error_unico()
        return
    garita_usuarios.append({usuario: clave})
    print("Usuario creado correctamente.")

def eliminar_usuario():
    titulo("ELIMINAR USUARIO")
    usuario = leer_texto("Usuario a eliminar: ", minus=True)
    if usuario in ('supervisor', 'cajero'):
        error_unico()
        return
    for i, cred in enumerate(garita_usuarios):
        if usuario in cred:
            if confirmar(f"¿Eliminar usuario {usuario}? (s/n): "):
                del garita_usuarios[i]
                print("Usuario eliminado.")
            return
    error_unico()

def menu_usuarios():
    while True:
        titulo("GESTIÓN DE USUARIOS")
        print("1) Crear usuario")
        print("2) Listar usuarios")
        print("3) Eliminar usuario")
        print("0) Volver")
        op = leer_opcion_menu()
        if op is None:
            return
        if op == '1':
            agregar_usuario()
        elif op == '2':
            listar_usuarios()
        elif op == '3':
            eliminar_usuario()
        elif op == '0':
            return

def agregar_nuevo_vehiculo():
    titulo("REGISTRO DE VEHÍCULO")
    placa = leer_texto("Ingrese placa: ", mayus=True)
    if placa is None or buscar_vehiculo_por_placa(placa):
        error_unico()
        return
    tipo = leer_texto("Ingrese tipo (vehiculo/moto/camion): ", minus=True)
    if tipo not in TIPOS_VALIDOS:
        error_unico()
        return
    propietario = leer_texto("Propietario opcional: ", espacios=True)
    if propietario is None:
        propietario = "-"
    vehiculos_registrados.append({'placa': placa, 'tipo': tipo, 'propietario': propietario})
    print("Vehículo registrado correctamente.")

def ver_vehiculos_registrados():
    titulo("VEHÍCULOS REGISTRADOS")
    for v in vehiculos_registrados:
        print(f"Placa: {v['placa']} | Tipo: {v['tipo']} | Propietario: {v['propietario']}")
    input("ENTER para volver")

def mostrar_tarifas_peaje():
    titulo("TARIFAS VIGENTES")
    for k, v in tarifas_peaje.items():
        print(f"{k.capitalize()}: {v}")
    input("ENTER para volver")

def menu_principal():
    while True:
        titulo("MENÚ PRINCIPAL")
        print("1) Ver Movimientos")
        print("2) Cobrar peaje")
        print("3) Ajustar tarifas")
        print("4) Agregar nuevo vehículo")
        print("5) Ver vehículos registrados")
        print("6) Mostrar tarifas")
        print("7) Reporte de ingresos")
        print("8) Ver registro de eventos")
        print("9) Gestionar usuarios")
        print("0) Salir")

        op = leer_opcion_menu()
        if op is None:
            continue

        if op == '0':
            if confirmar("¿Desea salir del sistema? (s/n): "):
                print("Cerrando sesión...")
                break
        elif op == '4':
            agregar_nuevo_vehiculo()
        elif op == '5':
            ver_vehiculos_registrados()
        elif op == '6':
            mostrar_tarifas_peaje()
        elif op == '9':
            if operador_actual == 'supervisor':
                menu_usuarios()
            else:
                error_unico()

if __name__ == "__main__":
    try:
        if autenticar_garita():
            menu_principal()
        else:
            cierre_seguridad()
    except:
        cierre_seguridad()