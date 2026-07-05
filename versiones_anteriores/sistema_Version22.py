# SISTEMA DE PEAJE - GARITA
# Versión estable para Visual Studio Code
# Objetivos:
# - No crashear al pegar texto masivo
# - Tratar bloques pegados como 1 intento
# - Máximo 3 intentos por bloque
# - Salida limpia sin traceback
# - Sin spam rojo en consola
# - Compatible con VS Code

import os
import re
from datetime import datetime

# =========================
# DATOS BASE
# =========================
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

# =========================
# UTILIDADES
# =========================
def titulo(texto):
    print("\n" + "=" * 60)
    print(texto.center(60))
    print("=" * 60)

def error_unico():
    print("Error: no se permite eso")

def aviso_intento():
    print("Tienes otro intento más")

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

def calcular_vuelto(pagado, tarifa):
    try:
        return int(pagado) - int(tarifa)
    except:
        return 0

# =========================
# VALIDACIÓN PARA VS CODE
# =========================
def es_bloque_pegar(valor):
    """
    Detecta pegado masivo en VS Code:
    - varias líneas
    - texto muy largo
    """
    try:
        if valor is None:
            return True
        valor = str(valor)
        return ('\n' in valor) or ('\r' in valor) or (len(valor) > MAX_CARACTERES)
    except:
        return True

def texto_valido_basico(valor, espacios=False):
    try:
        if valor is None:
            return False
        valor = str(valor).strip()
        if not valor:
            return False
        if espacios:
            patron = r'^[A-Za-z0-9 ]+$'
        else:
            patron = r'^[A-Za-z0-9]+$'
        return re.fullmatch(patron, valor) is not None
    except:
        return False

# =========================
# LECTURA SEGURA EN VS CODE
# =========================
def leer_texto_vs(prompt, mayus=False, minus=False, espacios=False, bloquear_pegado=True):
    """
    Lee una sola línea en VS Code.
    Si detecta pegado masivo, retorna None sin crashear.
    """
    try:
        valor = input(prompt)

        if bloquear_pegado and es_bloque_pegar(valor):
            error_unico()
            return None

        valor = str(valor).strip()

        if len(valor) > MAX_CARACTERES:
            error_unico()
            return None

        if mayus:
            valor = valor.upper()
        if minus:
            valor = valor.lower()

        if not texto_valido_basico(valor, espacios=espacios):
            error_unico()
            return None

        return valor
    except:
        error_unico()
        return None

def leer_entero_vs(prompt):
    try:
        valor = input(prompt)

        if es_bloque_pegar(valor):
            error_unico()
            return None

        valor = valor.strip()
        numero = int(valor)
        return numero
    except:
        error_unico()
        return None

def confirmar_vs(prompt="¿Confirmar? (s/n): "):
    try:
        valor = input(prompt)

        if es_bloque_pegar(valor):
            error_unico()
            return False

        valor = valor.strip().lower()
        if valor == 's':
            return True
        if valor == 'n':
            return False

        error_unico()
        return False
    except:
        error_unico()
        return False

def leer_opcion_vs():
    """
    Menú blindado para VS Code:
    - una sola línea
    - si es pegado masivo, cuenta como error
    - máximo 3 intentos
    """
    intentos = 0
    while intentos < MAX_INTENTOS:
        try:
            op = input("Seleccione opción: ")

            if es_bloque_pegar(op):
                error_unico()
                intentos += 1
                if intentos < MAX_INTENTOS:
                    aviso_intento()
                continue

            op = op.strip()

            if len(op) != 1 or op not in OPCIONES_MENU:
                error_unico()
                intentos += 1
                if intentos < MAX_INTENTOS:
                    aviso_intento()
                continue

            return op
        except:
            error_unico()
            intentos += 1
            if intentos < MAX_INTENTOS:
                aviso_intento()

    cierre_seguridad()
    return None

# =========================
# LOGIN VS CODE
# =========================
def autenticar_garita():
    global operador_actual
    titulo("INICIO DE SESIÓN")

    intentos = 0
    while intentos < MAX_INTENTOS:
        usuario = leer_texto_vs("Nombre de operador: ", minus=True)
        if usuario is None:
            intentos += 1
            if intentos < MAX_INTENTOS:
                aviso_intento()
            continue

        clave = leer_texto_vs("Contraseña: ")
        if clave is None:
            intentos += 1
            if intentos < MAX_INTENTOS:
                aviso_intento()
            continue

        if not texto_valido_basico(usuario) or not texto_valido_basico(clave):
            error_unico()
            intentos += 1
            if intentos < MAX_INTENTOS:
                aviso_intento()
            continue

        clave_real = obtener_clave_operador(usuario)
        if clave_real is None or clave_real != clave:
            error_unico()
            intentos += 1
            if intentos < MAX_INTENTOS:
                aviso_intento()
            continue

        operador_actual = usuario
        registrar_evento("autenticar_garita", f"Usuario {usuario} autenticado")
        print(f"\nBienvenido, {usuario}")
        input("ENTER para continuar")
        return True

    cierre_seguridad()
    return False

# =========================
# FUNCIONES DEL SISTEMA
# =========================
def listar_usuarios():
    titulo("USUARIOS REGISTRADOS")
    for cred in garita_usuarios:
        for usuario in cred:
            print(f"Usuario: {usuario}")
    input("ENTER para volver")

def agregar_usuario():
    titulo("CREAR USUARIO")

    usuario = leer_texto_vs("Nuevo usuario: ", minus=True)
    if usuario is None:
        return

    if buscar_usuario(usuario):
        error_unico()
        return

    clave = leer_texto_vs("Nueva contraseña: ")
    if clave is None:
        return

    rol = leer_texto_vs("Rol (supervisor/cajero): ", minus=True)
    if rol not in {'supervisor', 'cajero'}:
        error_unico()
        return

    garita_usuarios.append({usuario: clave})
    print("Usuario creado correctamente.")

def eliminar_usuario():
    titulo("ELIMINAR USUARIO")

    usuario = leer_texto_vs("Usuario a eliminar: ", minus=True)
    if usuario is None:
        return

    if usuario in ('supervisor', 'cajero'):
        error_unico()
        return

    for i, cred in enumerate(garita_usuarios):
        if usuario in cred:
            if confirmar_vs(f"¿Eliminar usuario {usuario}? (s/n): "):
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

        op = leer_opcion_vs()
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

    placa = leer_texto_vs("Ingrese placa: ", mayus=True)
    if placa is None:
        return

    if buscar_vehiculo_por_placa(placa):
        error_unico()
        return

    tipo = leer_texto_vs("Ingrese tipo (vehiculo/moto/camion): ", minus=True)
    if tipo not in TIPOS_VALIDOS:
        error_unico()
        return

    propietario = leer_texto_vs("Propietario opcional: ", espacios=True)
    if propietario is None:
        propietario = "-"

    vehiculos_registrados.append({
        'placa': placa,
        'tipo': tipo,
        'propietario': propietario
    })
    print("Vehículo registrado correctamente.")

def ver_vehiculos_registrados():
    titulo("VEHÍCULOS REGISTRADOS")
    for v in vehiculos_registrados:
        print(f"Placa: {v['placa']} | Tipo: {v['tipo']} | Propietario: {v['propietario']}")
    input("ENTER para volver")

def cobrar_peaje():
    titulo("COBRO DE PEAJE")
    placa = input("Ingrese placa o ENTER para no registrado: ").strip().upper()

    if len(placa) > MAX_CARACTERES:
        error_unico()
        return

    tipo = None
    if placa:
        v = buscar_vehiculo_por_placa(placa)
        if v:
            print(f"Vehículo encontrado: {v['placa']} | Tipo: {v['tipo']}")
            tipo = v['tipo']
        else:
            print("Vehículo no registrado.")
            if confirmar_vs("¿Registrar ahora? (s/n): "):
                tipo = agregar_nuevo_vehiculo_con_placa(placa)
            else:
                tipo = leer_texto_vs("Ingrese tipo (vehiculo/moto/camion): ", minus=True)
    else:
        tipo = leer_texto_vs("Ingrese tipo (vehiculo/moto/camion): ", minus=True)
        placa = leer_texto_vs("Ingrese placa (o N/A): ", mayus=True)

    if tipo not in TIPOS_VALIDOS:
        error_unico()
        return

    tarifa = tarifas_peaje.get(tipo)
    print(f"Tarifa para {tipo}: {tarifa} pesos")

    pagado = leer_entero_vs("Ingrese monto entregado: ")
    if pagado is None:
        return

    if pagado < tarifa:
        error_unico()
        return

    vuelto = calcular_vuelto(pagado, tarifa)
    movimientos_peaje.append({
        'fecha': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        'placa': placa,
        'tipo': tipo,
        'tarifa': tarifa,
        'pagado': pagado,
        'vuelto': vuelto
    })
    print(f"Cobro registrado. Vuelto: {vuelto} pesos")

def agregar_nuevo_vehiculo_con_placa(placa):
    titulo("REGISTRO DE VEHÍCULO")
    tipo = leer_texto_vs("Ingrese tipo (vehiculo/moto/camion): ", minus=True)
    if tipo not in TIPOS_VALIDOS:
        error_unico()
        return None

    propietario = leer_texto_vs("Propietario opcional: ", espacios=True)
    if propietario is None:
        propietario = "-"

    vehiculos_registrados.append({
        'placa': placa,
        'tipo': tipo,
        'propietario': propietario
    })
    print("Vehículo registrado correctamente.")
    return tipo

def ajustar_tarifas_peaje():
    titulo("AJUSTE DE TARIFAS")
    if operador_actual != 'supervisor':
        error_unico()
        return

    clave = leer_texto_vs("Ingrese contraseña del supervisor: ")
    if clave != obtener_clave_operador('supervisor'):
        error_unico()
        return

    tipo = leer_texto_vs("Tipo a ajustar (vehiculo/moto/camion): ", minus=True)
    if tipo not in TIPOS_VALIDOS:
        error_unico()
        return

    nueva = leer_entero_vs(f"Nueva tarifa para {tipo}: ")
    if nueva is None:
        return

    if confirmar_vs("¿Confirmar cambio? (s/n): "):
        tarifas_peaje[tipo] = nueva
        print("Tarifa actualizada.")
    else:
        print("Operación cancelada.")

def mostrar_tarifas_peaje():
    titulo("TARIFAS VIGENTES")
    for k, v in tarifas_peaje.items():
        print(f"{k.capitalize():10} : {v} pesos")
    input("ENTER para volver")

def ver_movimientos_peaje():
    titulo("HISTORIAL DE MOVIMIENTOS")
    for i, m in enumerate(movimientos_peaje, start=1):
        print(f"[{i}] {m['fecha']} | Placa: {m['placa']} | Tipo: {m['tipo']} | Tarifa: {m['tarifa']} | Pagado: {m['pagado']} | Vuelto: {m['vuelto']}")
    input("ENTER para volver")

def reporte_ingresos():
    titulo("REPORTE DE INGRESOS")
    totales = {k: 0 for k in tarifas_peaje}
    for m in movimientos_peaje:
        t = m.get('tipo')
        if t in totales:
            totales[t] += int(m.get('tarifa', 0))
    for k, v in totales.items():
        print(f"{k.capitalize():10} : {v}")
    input("ENTER para volver")

def ver_registro_eventos():
    titulo("REGISTRO DE EVENTOS")
    for e in registro_eventos:
        print(f"{e['fecha']} | {e['funcion']} | {e['mensaje']}")
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

        op = leer_opcion_vs()
        if op is None:
            return

        if op == '0':
            if confirmar_vs("¿Desea salir del sistema? (s/n): "):
                print("Cerrando sesión...")
                break
        elif op == '1':
            ver_movimientos_peaje()
        elif op == '2':
            cobrar_peaje()
        elif op == '3':
            ajustar_tarifas_peaje()
        elif op == '4':
            agregar_nuevo_vehiculo()
        elif op == '5':
            ver_vehiculos_registrados()
        elif op == '6':
            mostrar_tarifas_peaje()
        elif op == '7':
            reporte_ingresos()
        elif op == '8':
            ver_registro_eventos()
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