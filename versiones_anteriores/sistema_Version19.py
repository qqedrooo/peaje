# SISTEMA DE PEAJE - GARITA
# v17
# Corrección:
# - Al agotar 3 intentos, el programa sale limpiamente
# - Sin bucles infinitos
# - Sin spam rojo
# - Sin traceback
# - Login y menú mantienen bloqueo de spam

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
MAX_INTENTOS_SPAAM = 3
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
# VALIDACIÓN
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
    except:
        return False

def validar_tipo(tipo):
    try:
        return str(tipo).strip().lower() in TIPOS_VALIDOS
    except:
        return False

# =========================
# LECTURAS CON CONTROL DE SALIDA LIMPIA
# =========================
def leer_texto_controlado(prompt, mayus=False, minus=False, espacios=False, intentos=MAX_INTENTOS_SPAAM):
    fallos = 0
    while fallos < intentos:
        try:
            valor = input(prompt)
            if valor is None:
                error_unico()
                fallos += 1
                if fallos < intentos:
                    aviso_intento()
                continue

            valor = str(valor).strip()

            if len(valor) > MAX_CARACTERES:
                error_unico()
                fallos += 1
                if fallos < intentos:
                    aviso_intento()
                continue

            if mayus:
                valor = valor.upper()
            if minus:
                valor = valor.lower()

            if not validar_texto_seguro(valor, max_len=MAX_CARACTERES, permitir_espacios=espacios):
                error_unico()
                fallos += 1
                if fallos < intentos:
                    aviso_intento()
                continue

            return valor
        except:
            error_unico()
            fallos += 1
            if fallos < intentos:
                aviso_intento()

    cierre_seguridad()
    return None

def leer_entero_controlado(prompt, minimo=None, maximo=None, intentos=MAX_INTENTOS_SPAAM):
    fallos = 0
    while fallos < intentos:
        try:
            valor = input(prompt).strip()

            if len(valor) > MAX_CARACTERES:
                error_unico()
                fallos += 1
                if fallos < intentos:
                    aviso_intento()
                continue

            numero = int(valor)

            if minimo is not None and numero < minimo:
                error_unico()
                fallos += 1
                if fallos < intentos:
                    aviso_intento()
                continue

            if maximo is not None and numero > maximo:
                error_unico()
                fallos += 1
                if fallos < intentos:
                    aviso_intento()
                continue

            return numero
        except:
            error_unico()
            fallos += 1
            if fallos < intentos:
                aviso_intento()

    cierre_seguridad()
    return None

def leer_opcion_menu():
    fallos = 0
    while fallos < MAX_INTENTOS_SPAAM:
        try:
            op = input("Seleccione opción: ").strip()

            if len(op) != 1:
                error_unico()
                fallos += 1
                if fallos < MAX_INTENTOS_SPAAM:
                    aviso_intento()
                continue

            if op not in OPCIONES_MENU:
                error_unico()
                fallos += 1
                if fallos < MAX_INTENTOS_SPAAM:
                    aviso_intento()
                continue

            return op
        except:
            error_unico()
            fallos += 1
            if fallos < MAX_INTENTOS_SPAAM:
                aviso_intento()

    cierre_seguridad()
    return None

def confirmar(prompt="¿Confirmar? (s/n): "):
    fallos = 0
    while fallos < MAX_INTENTOS_SPAAM:
        try:
            r = input(prompt).strip().lower()
            if r == 's':
                return True
            if r == 'n':
                return False
            error_unico()
            fallos += 1
            if fallos < MAX_INTENTOS_SPAAM:
                aviso_intento()
        except:
            error_unico()
            fallos += 1
            if fallos < MAX_INTENTOS_SPAAM:
                aviso_intento()

    cierre_seguridad()
    return False

# =========================
# LOGIN
# =========================
def autenticar_garita():
    global operador_actual
    titulo("INICIO DE SESIÓN")

    fallos = 0
    while fallos < MAX_INTENTOS_SPAAM:
        usuario = leer_texto_controlado("Nombre de operador: ", minus=True)
        if usuario is None:
            fallos += 1
            if fallos < MAX_INTENTOS_SPAAM:
                aviso_intento()
            continue

        clave = leer_texto_controlado("Contraseña: ")
        if clave is None:
            fallos += 1
            if fallos < MAX_INTENTOS_SPAAM:
                aviso_intento()
            continue

        if not validar_texto_seguro(usuario) or not validar_texto_seguro(clave):
            error_unico()
            fallos += 1
            if fallos < MAX_INTENTOS_SPAAM:
                aviso_intento()
            continue

        clave_real = obtener_clave_operador(usuario)
        if clave_real is None or clave_real != clave:
            error_unico()
            fallos += 1
            if fallos < MAX_INTENTOS_SPAAM:
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
    usuario = leer_texto_controlado("Nuevo usuario: ", minus=True)
    if usuario is None:
        return
    if buscar_usuario(usuario):
        error_unico()
        input("ENTER para volver")
        return

    clave = leer_texto_controlado("Nueva contraseña: ")
    if clave is None:
        return

    rol = leer_texto_controlado("Rol (supervisor/cajero): ", minus=True)
    if rol not in {'supervisor', 'cajero'}:
        error_unico()
        input("ENTER para volver")
        return

    garita_usuarios.append({usuario: clave})
    registrar_evento("agregar_usuario", f"Usuario {usuario} creado")
    print("Usuario creado correctamente.")
    input("ENTER para volver")

def eliminar_usuario():
    titulo("ELIMINAR USUARIO")
    usuario = leer_texto_controlado("Usuario a eliminar: ", minus=True)
    if usuario is None:
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
            return

        if op == '1':
            agregar_usuario()
        elif op == '2':
            listar_usuarios()
        elif op == '3':
            eliminar_usuario()
        elif op == '0':
            return

# =========================
# VEHÍCULOS Y COBRO
# =========================
def agregar_nuevo_vehiculo(placa_propuesta=None):
    titulo("REGISTRO DE VEHÍCULO")
    if placa_propuesta is not None:
        placa = str(placa_propuesta).strip().upper()
    else:
        placa = leer_texto_controlado("Ingrese placa: ", mayus=True)
    if placa is None:
        return None

    if buscar_vehiculo_por_placa(placa):
        error_unico()
        input("ENTER para volver")
        return None

    tipo = leer_texto_controlado("Ingrese tipo (vehiculo/moto/camion): ", minus=True)
    if tipo not in TIPOS_VALIDOS:
        error_unico()
        input("ENTER para volver")
        return None

    propietario = leer_texto_controlado("Propietario opcional: ", espacios=True)
    if propietario is None:
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
                tipo = leer_texto_controlado("Ingrese tipo (vehiculo/moto/camion): ", minus=True)
    else:
        tipo = leer_texto_controlado("Ingrese tipo (vehiculo/moto/camion): ", minus=True)
        placa = leer_texto_controlado("Ingrese placa (o N/A): ", mayus=True)

    if not validar_tipo(tipo):
        error_unico()
        input("ENTER para volver")
        return

    tarifa = tarifas_peaje.get(tipo)
    print(f"Tarifa para {tipo}: {tarifa} pesos")
    pagado = leer_entero_controlado("Ingrese monto entregado: ", minimo=0)
    if pagado is None:
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

def ajuste_tarifas_peaje():
    titulo("AJUSTE DE TARIFAS")
    if operador_actual != 'supervisor':
        error_unico()
        input("ENTER para volver")
        return

    clave = leer_texto_controlado("Ingrese contraseña del supervisor: ")
    if clave != obtener_clave_operador('supervisor'):
        error_unico()
        input("ENTER para volver")
        return

    tipo = leer_texto_controlado("Tipo a ajustar (vehiculo/moto/camion): ", minus=True)
    if tipo not in TIPOS_VALIDOS:
        error_unico()
        input("ENTER para volver")
        return

    nueva = leer_entero_controlado(f"Nueva tarifa para {tipo}: ", minimo=0)
    if nueva is None:
        return

    if confirmar("¿Confirmar cambio? (s/n): "):
        tarifas_peaje[tipo] = nueva
        registrar_evento("ajuste_tarifas_peaje", f"{tipo} -> {nueva}")
        print("Tarifa actualizada.")
    else:
        print("Operación cancelada.")
    input("ENTER para volver")

def mostrar_tarifas_peaje():
    titulo("TARIFAS VIGENTES")
    for k, v in tarifas_peaje.items():
        print(f"{k.capitalize():10} : {v} pesos")
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
            return

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
            cierre_seguridad()
    except:
        cierre_seguridad()
        raise SystemExit(0)