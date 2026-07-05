# SISTEMA DE PEAJE - GARITA
# Versión completa con menú blindado:
# - Solo acepta 1 dígito en el menú
# - Si la entrada es inválida, muestra solo "Error: no se permite eso"
# - Vuelve al menú sin imprimir basura
# - Entradas limitadas a 15 caracteres
# - Sin getpass
# - Sin bucles visuales agresivos
# - Sin eco de texto inválido

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
MAX_INTENTOS_LOGIN = 3
TIPOS_VALIDOS = {'vehiculo', 'moto', 'camion'}
OPCIONES_MENU = {'0', '1', '2', '3', '4', '5', '6', '7', '8', '9'}

# =========================
# UTILIDADES BÁSICAS
# =========================
def limpiar_pantalla():
    os.system('cls' if os.name == 'nt' else 'clear')

def titulo(texto):
    print("\n" + "=" * 60)
    print(texto.center(60))
    print("=" * 60)

def error_unico():
    print("Error: no se permite eso")

def registrar_evento(funcion, mensaje):
    registro_eventos.append({
        'fecha': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        'funcion': funcion,
        'mensaje': mensaje
    })

# =========================
# VALIDACIONES
# =========================
def validar_texto_seguro(texto, max_len=MAX_CARACTERES, permitir_espacios=False):
    try:
        if texto is None:
            return False
        texto = str(texto).strip()
        if not texto:
            return False
        if len(texto) > max_len:
            return False
        if permitir_espacios:
            patron = rf'^[A-Za-z0-9 ]{{1,{max_len}}}$'
        else:
            patron = rf'^[A-Za-z0-9]{{1,{max_len}}}$'
        return re.fullmatch(patron, texto) is not None
    except Exception:
        return False

def validar_tipo(tipo):
    try:
        return str(tipo).strip().lower() in TIPOS_VALIDOS
    except Exception:
        return False

def leer_texto(prompt, mayus=False, minus=False, espacios=False):
    try:
        valor = input(prompt)
        if valor is None:
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

        if not validar_texto_seguro(valor, max_len=MAX_CARACTERES, permitir_espacios=espacios):
            error_unico()
            return None

        return valor
    except:
        error_unico()
        return None

def leer_entero(prompt, minimo=None, maximo=None):
    try:
        valor = input(prompt).strip()
        numero = int(valor)

        if minimo is not None and numero < minimo:
            error_unico()
            return None
        if maximo is not None and numero > maximo:
            error_unico()
            return None

        return numero
    except:
        error_unico()
        return None

def leer_opcion_menu():
    try:
        texto = input("Seleccione opción: ").strip()

        # Solo 1 dígito exacto
        if len(texto) != 1:
            error_unico()
            return None

        if texto not in OPCIONES_MENU:
            error_unico()
            return None

        return texto
    except:
        error_unico()
        return None

def confirmar(prompt="¿Confirmar? (s/n): "):
    try:
        r = input(prompt).strip().lower()
        if r == 's':
            return True
        if r == 'n':
            return False
        error_unico()
        return False
    except:
        error_unico()
        return False

# =========================
# BÚSQUEDAS
# =========================
def buscar_usuario(nombre):
    for cred in garita_usuarios:
        if nombre in cred:
            return cred
    return None

def obtener_clave_operador(nombre):
    cred = buscar_usuario(nombre)
    if cred:
        return cred.get(nombre)
    return None

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
# AUTENTICACIÓN
# =========================
def autenticar_garita():
    global operador_actual
    titulo("INICIO DE SESIÓN")
    intentos = 0

    while intentos < MAX_INTENTOS_LOGIN:
        usuario = leer_texto("Nombre de operador: ", minus=True)
        if usuario is None:
            intentos += 1
            continue

        clave = leer_texto("Contraseña: ")
        if clave is None:
            intentos += 1
            continue

        if not validar_texto_seguro(usuario):
            error_unico()
            intentos += 1
            continue

        if not validar_texto_seguro(clave):
            error_unico()
            intentos += 1
            continue

        clave_real = obtener_clave_operador(usuario)
        if clave_real is not None and clave_real == clave:
            operador_actual = usuario
            registrar_evento("autenticar_garita", f"Usuario {usuario} autenticado")
            print(f"\nBienvenido, {usuario}")
            input("ENTER para continuar")
            return True
        else:
            intentos += 1
            print(f"Datos incorrectos. Intentos restantes: {MAX_INTENTOS_LOGIN - intentos}")

    registrar_evento("autenticar_garita", "Fallo de autenticación")
    return False

# =========================
# USUARIOS
# =========================
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
        input("ENTER para volver")
        return

    if buscar_usuario(usuario):
        error_unico()
        input("ENTER para volver")
        return

    clave = leer_texto("Nueva contraseña: ")
    if clave is None:
        input("ENTER para volver")
        return

    rol = leer_texto("Rol (supervisor/cajero): ", minus=True)
    if rol is None or rol not in {'supervisor', 'cajero'}:
        error_unico()
        input("ENTER para volver")
        return

    garita_usuarios.append({usuario: clave})
    registrar_evento("agregar_usuario", f"Usuario {usuario} creado")
    print("Usuario creado correctamente.")
    input("ENTER para volver")

def eliminar_usuario():
    titulo("ELIMINAR USUARIO")

    usuario = leer_texto("Usuario a eliminar: ", minus=True)
    if usuario is None:
        input("ENTER para volver")
        return

    if usuario in ('supervisor', 'cajero'):
        error_unico()
        input("ENTER para volver")
        return

    for i, cred in enumerate(garita_usuarios):
        if usuario in cred:
            if confirmar(f"¿Eliminar usuario {usuario}? (s/n): "):
                del garita_usuarios[i]
                registrar_evento("eliminar_usuario", f"Usuario {usuario} eliminado")
                print("Usuario eliminado.")
            else:
                print("Operación cancelada.")
            input("ENTER para volver")
            return

    error_unico()
    input("ENTER para volver")

def menu_usuarios():
    while True:
        titulo("GESTIÓN DE USUARIOS")
        print("1) Crear usuario")
        print("2) Listar usuarios")
        print("3) Eliminar usuario")
        print("0) Volver")

        op = leer_opcion_menu()
        if op is None:
            continue

        if op == '1':
            agregar_usuario()
        elif op == '2':
            listar_usuarios()
        elif op == '3':
            eliminar_usuario()
        elif op == '0':
            return

# =========================
# VEHÍCULOS
# =========================
def agregar_nuevo_vehiculo(placa_propuesta=None):
    titulo("REGISTRO DE VEHÍCULO")

    if placa_propuesta is not None:
        placa = str(placa_propuesta).strip().upper()
    else:
        placa = leer_texto("Ingrese placa: ", mayus=True)
        if placa is None:
            input("ENTER para volver")
            return None

    if buscar_vehiculo_por_placa(placa):
        error_unico()
        input("ENTER para volver")
        return None

    tipo = leer_texto("Ingrese tipo (vehiculo/moto/camion): ", minus=True)
    if tipo is None or not validar_tipo(tipo):
        error_unico()
        input("ENTER para volver")
        return None

    propietario = input("Propietario opcional (máx. 15): ").strip()
    if propietario and (len(propietario) > MAX_CARACTERES or not validar_texto_seguro(propietario, permitir_espacios=True)):
        error_unico()
        input("ENTER para volver")
        return None
    if not propietario:
        propietario = "-"

    vehiculos_registrados.append({
        'placa': placa[:MAX_CARACTERES],
        'tipo': tipo,
        'propietario': propietario[:MAX_CARACTERES]
    })

    registrar_evento("agregar_nuevo_vehiculo", f"Vehículo {placa} registrado")
    print("Vehículo registrado correctamente.")
    input("ENTER para volver")
    return tipo

def ver_vehiculos_registrados():
    titulo("VEHÍCULOS REGISTRADOS")
    if not vehiculos_registrados:
        print("No hay vehículos registrados.")
        input("ENTER para volver")
        return

    for v in vehiculos_registrados:
        print(f"Placa: {v['placa']:<15} Tipo: {v['tipo']:<10} Propietario: {v['propietario']}")
    input("ENTER para volver")

# =========================
# COBRO Y REPORTES
# =========================
def cobrar_peaje():
    titulo("COBRO DE PEAJE")

    placa = input("Ingrese placa o ENTER para no registrado: ").strip().upper()
    if len(placa) > MAX_CARACTERES:
        error_unico()
        input("ENTER para volver")
        return

    tipo = None

    if placa:
        v = buscar_vehiculo_por_placa(placa)
        if v:
            print(f"Vehículo encontrado: {v['placa']} | Tipo: {v['tipo']}")
            tipo = v['tipo']
        else:
            print("Vehículo no registrado.")
            if confirmar("¿Registrar ahora? (s/n): "):
                tipo = agregar_nuevo_vehiculo(placa_propuesta=placa)
                if not tipo:
                    return
            else:
                tipo = leer_texto("Ingrese tipo (vehiculo/moto/camion): ", minus=True)
    else:
        tipo = leer_texto("Ingrese tipo (vehiculo/moto/camion): ", minus=True)
        placa = leer_texto("Ingrese placa (o N/A): ", mayus=True)
        if placa is None:
            placa = "N/A"

    if not validar_tipo(tipo):
        error_unico()
        input("ENTER para volver")
        return

    tarifa = tarifas_peaje.get(tipo)
    print(f"Tarifa para {tipo}: {tarifa} pesos")

    pagado = leer_entero("Ingrese monto entregado: ", minimo=0)
    if pagado is None:
        input("ENTER para volver")
        return

    if pagado < tarifa:
        error_unico()
        registrar_evento("cobrar_peaje", "Monto insuficiente")
        input("ENTER para volver")
        return

    vuelto = calcular_vuelto(pagado, tarifa)
    movimientos_peaje.append({
        'fecha': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        'placa': placa[:MAX_CARACTERES],
        'tipo': tipo,
        'tarifa': tarifa,
        'pagado': pagado,
        'vuelto': vuelto
    })

    registrar_evento("cobrar_peaje", f"Cobro registrado para {placa}")
    print(f"Cobro registrado. Vuelto: {vuelto} pesos")
    input("ENTER para volver")

def mostrar_tarifas_peaje():
    titulo("TARIFAS VIGENTES")
    for k, v in tarifas_peaje.items():
        print(f"{k.capitalize():10} : {v} pesos")
    input("ENTER para volver")

def ajuste_tarifas_peaje():
    titulo("AJUSTE DE TARIFAS")

    if operador_actual != 'supervisor':
        error_unico()
        input("ENTER para volver")
        return

    clave = leer_texto("Ingrese contraseña del supervisor: ")
    if clave != obtener_clave_operador('supervisor'):
        error_unico()
        input("ENTER para volver")
        return

    tipo = leer_texto("Tipo a ajustar (vehiculo/moto/camion): ", minus=True)
    if tipo is None or not validar_tipo(tipo):
        error_unico()
        input("ENTER para volver")
        return

    nueva = leer_entero(f"Nueva tarifa para {tipo}: ", minimo=0)
    if nueva is None:
        input("ENTER para volver")
        return

    if confirmar("¿Confirmar cambio? (s/n): "):
        tarifas_peaje[tipo] = nueva
        registrar_evento("ajuste_tarifas_peaje", f"{tipo} -> {nueva}")
        print("Tarifa actualizada.")
    else:
        print("Operación cancelada.")
    input("ENTER para volver")

def ver_movimientos_peaje():
    titulo("HISTORIAL DE MOVIMIENTOS")
    if not movimientos_peaje:
        print("Sin movimientos")
        registrar_evento("ver_movimientos_peaje", "Sin movimientos")
        input("ENTER para volver")
        return

    for i, m in enumerate(movimientos_peaje, start=1):
        print(f"[{i}] {m['fecha']} | Placa: {m['placa']} | Tipo: {m['tipo']} | Tarifa: {m['tarifa']} | Pagado: {m['pagado']} | Vuelto: {m['vuelto']}")
    input("ENTER para volver")

def reporte_ingresos():
    titulo("REPORTE DE INGRESOS")
    if not movimientos_peaje:
        print("No hay movimientos.")
        registrar_evento("reporte_ingresos", "Sin movimientos")
        input("ENTER para volver")
        return

    totales = {k: 0 for k in tarifas_peaje}
    conteo = {k: 0 for k in tarifas_peaje}
    total_general = 0

    for m in movimientos_peaje:
        t = m.get('tipo')
        if t in totales:
            tarifa = int(m.get('tarifa', 0))
            totales[t] += tarifa
            conteo[t] += 1
            total_general += tarifa

    for k in totales:
        print(f"{k.capitalize():10} Recaudado: {totales[k]:8} | Pasos: {conteo[k]:3}")
    print(f"\nTotal general recaudado: {total_general} pesos")
    registrar_evento("reporte_ingresos", f"Total {total_general}")
    input("ENTER para volver")

def ver_registro_eventos():
    titulo("REGISTRO DE EVENTOS")
    if not registro_eventos:
        print("No hay eventos.")
        input("ENTER para volver")
        return

    for e in registro_eventos:
        print(f"{e['fecha']} | {e['funcion']} | {e['mensaje']}")
    input("ENTER para volver")

# =========================
# MENÚ PRINCIPAL
# =========================
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
                registrar_evento("menu_principal", "Cierre de sesión")
                break
        elif op == '1':
            ver_movimientos_peaje()
        elif op == '2':
            cobrar_peaje()
        elif op == '3':
            ajuste_tarifas_peaje()
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
                input("ENTER para volver")

# =========================
# INICIO
# =========================
if __name__ == "__main__":
    try:
        if autenticar_garita():
            menu_principal()
        else:
            print("Acceso denegado. Fin del programa.")
            registrar_evento("main", "Acceso denegado al iniciar")
    except Exception as e:
        print(f"Error fatal controlado: {e}")