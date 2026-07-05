# SISTEMA DE PEAJE - GARITA
# Código completo con comentarios explicativos en cada sección, función y operación.
# Las siguientes líneas del archivo original definen usuarios y tarifas iniciales:
# garita_usuarios = [{'supervisor': '123'}, {'cajero': '321'}]
# tarifas_peaje = {'vehiculo': 500, 'moto': 250, 'camion': 1500}

import os
import time
import getpass
from datetime import datetime
import shutil

# -------------------------
# Configuración inicial
# -------------------------
# Lista de usuarios con sus claves (simulada en memoria).
# Cada diccionario contiene el nombre de usuario como clave y la contraseña como valor.
garita_usuarios = [{'supervisor': '123'}, {'cajero': '321'}]

# Tarifas por tipo de vehículo. Se usa para calcular cobros y reportes.
tarifas_peaje = {
    'vehiculo': 500,
    'moto': 250,
    'camion': 1500
}

# Lista de vehículos registrados inicialmente (simulación de base de datos en memoria).
# Cada entrada es un diccionario con 'placa', 'tipo' y 'propietario'.
vehiculos_registrados = [
    {'placa': 'ABC123', 'tipo': 'vehiculo', 'propietario': 'Empresa X'},
    {'placa': 'MOTO01', 'tipo': 'moto', 'propietario': 'Luis Perez'},
    {'placa': 'TRK999', 'tipo': 'camion', 'propietario': 'Transporte SA'}
]

# Lista que almacenará los movimientos de cobro realizados durante la ejecución.
# Cada movimiento será un diccionario con fecha, placa, tipo, tarifa, pagado y vuelto.
movimientos_peaje = []

# Lista para registrar eventos del sistema (por ejemplo: funciones que encontraron "sin datos").
# Se usa para auditoría interna y seguimiento de acciones/errores.
registro_eventos = []

# Variable global que guarda el operador actualmente autenticado.
operador_actual = None

# -------------------------
# Utilidades de interfaz
# -------------------------
def ancho_terminal(default=80):
    """
    Devuelve el ancho de la terminal para centrar y formatear salidas.
    Intenta obtener el tamaño real; si falla, devuelve un valor por defecto.
    """
    try:
        return shutil.get_terminal_size().columns
    except Exception:
        return default

def limpiar_pantalla():
    """
    Limpia la pantalla de la terminal según el sistema operativo.
    'cls' para Windows, 'clear' para Unix-like.
    """
    os.system('cls' if os.name == 'nt' else 'clear')

def centrar(texto, ancho=None):
    """
    Centra un texto en base al ancho de la terminal.
    Si no se pasa ancho, usa ancho_terminal() para calcularlo.
    """
    ancho = ancho or ancho_terminal()
    return texto.center(ancho)

def linea(char='─'):
    """
    Imprime una línea horizontal usando el ancho de la terminal.
    Útil para separar secciones visualmente.
    """
    print(char * ancho_terminal())

def espera_animacion(segundos=0.8, mensaje="Cargando"):
    """
    Muestra una animación simple de puntos durante un tiempo total.
    Parámetros:
      - segundos: duración total de la animación
      - mensaje: texto base que se muestra antes de los puntos
    Se usa para dar feedback visual al usuario.
    """
    pasos = 6
    for i in range(pasos):
        dots = '.' * ((i % 3) + 1)  # 1 a 3 puntos en ciclo
        print(f"\r{mensaje}{dots} ", end='', flush=True)
        time.sleep(segundos / pasos)
    # Limpia la línea al terminar la animación
    print("\r" + " " * (len(mensaje) + 4), end='\r')

def barra_progreso(total=20, duracion=0.6, mensaje="Procesando"):
    """
    Muestra una barra de progreso en consola.
    Parámetros:
      - total: longitud de la barra en "pasos"
      - duracion: tiempo total que tardará la barra en completarse
      - mensaje: texto que acompaña la barra
    Se usa para simular procesamiento en operaciones que tardan.
    """
    for i in range(total + 1):
        por = int((i / total) * 100)
        barra = '█' * i + '-' * (total - i)
        print(f"\r{mensaje} |{barra}| {por:3d}%", end='', flush=True)
        time.sleep(duracion / total)
    print()

def confirmar(texto="¿Confirmar? (s/n): "):
    """
    Solicita confirmación al usuario y valida la entrada.
    Retorna True para 's' y False para 'n'.
    Repite hasta recibir una respuesta válida.
    """
    while True:
        r = input(texto).strip().lower()
        if r in ('s', 'n'):
            return r == 's'
        print("Ingrese 's' para sí o 'n' para no.")

def beep():
    """
    Emite un beep de sistema (si la terminal lo soporta).
    Se usa para alertar al operador tras acciones importantes.
    """
    print('\a', end='')

# -------------------------
# Registro de eventos
# -------------------------
def registrar_evento(funcion, mensaje):
    """
    Registra un evento en la lista registro_eventos con timestamp, función y mensaje.
    Parámetros:
      - funcion: nombre de la función o sección que genera el evento
      - mensaje: descripción breve del evento
    Se usa para auditoría y seguimiento de acciones (p. ej. 'sin movimientos').
    """
    evento = {
        'fecha': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        'funcion': funcion,
        'mensaje': mensaje
    }
    registro_eventos.append(evento)

def ver_registro_eventos():
    """
    Muestra los eventos registrados por el sistema.
    Si no hay eventos, informa al usuario y vuelve al menú.
    """
    banner_inicio()           # Dibuja banner y limpia pantalla
    panel_usuario()           # Muestra información del operador y hora
    print(centrar("REGISTRO DE EVENTOS"))
    linea()
    if not registro_eventos:
        # Mensaje cuando no hay eventos registrados
        print(centrar("No hay eventos registrados"))
        espera_animacion(0.6, "Volviendo")
        return
    # Itera y muestra cada evento con fecha, función y mensaje
    for e in registro_eventos:
        print(f"{e['fecha']}  Función: {e['funcion']}  Mensaje: {e['mensaje']}")
        linea()
    input("ENTER para volver al menú")

# -------------------------
# Banner y panel
# -------------------------
def banner_inicio():
    """
    Dibuja el banner de inicio en la parte superior de la pantalla.
    Limpia la pantalla antes de dibujar para mantener la interfaz ordenada.
    """
    limpiar_pantalla()
    ancho = ancho_terminal()
    print('╔' + '═' * (ancho - 2) + '╗')
    print('║' + ' ' * (ancho - 2) + '║')
    print('║' + centrar('SISTEMA DE PEAJE - GARITA', ancho - 2) + '║')
    print('║' + centrar('Control de Acceso y Cobro', ancho - 2) + '║')
    print('║' + ' ' * (ancho - 2) + '║')
    print('╚' + '═' * (ancho - 2) + '╝')
    print()

def panel_usuario():
    """
    Muestra información del panel del usuario actual:
      - Título del panel según rol
      - Nombre del operador autenticado
      - Hora actual
    Se usa al inicio de cada pantalla para contexto.
    """
    ancho = ancho_terminal()
    panel = nombre_panel_por_rol(operador_actual)
    print(centrar(panel, ancho))
    linea()
    print(centrar(f"Operador: {operador_actual}", ancho))
    print(centrar(f"Hora: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", ancho))
    linea()

def nombre_panel_por_rol(rol):
    """
    Devuelve el título del panel según el rol del operador.
    Permite diferenciar visualmente permisos y funciones.
    """
    if rol == 'supervisor':
        return "PANEL SUPERVISOR - CONTROL TOTAL"
    if rol == 'cajero':
        return "PANEL CAJERO - OPERACIONES DE COBRO"
    return "PANEL OPERADOR"

# -------------------------
# Funciones de datos
# -------------------------
def buscar_vehiculo_por_placa(placa):
    """
    Busca un vehículo en la lista de registrados por su placa.
    - Normaliza la placa a mayúsculas para comparación case-insensitive.
    - Retorna el diccionario del vehículo o None si no existe.
    """
    placa = placa.upper()
    for v in vehiculos_registrados:
        if v['placa'].upper() == placa:
            return v
    return None

def calcular_vuelto(monto_pagado, tarifa):
    """
    Calcula el vuelto simple restando la tarifa al monto pagado.
    Retorna un entero (puede ser 0 si pagado == tarifa).
    """
    return monto_pagado - tarifa

def obtener_clave_operador(nombre_operador):
    """
    Recupera la clave almacenada para un operador dado.
    Busca en la lista garita_usuarios y retorna la contraseña si existe.
    """
    for cred in garita_usuarios:
        if nombre_operador in cred:
            return cred[nombre_operador]
    return None

# -------------------------
# Operaciones principales
# -------------------------
def ver_movimientos_peaje():
    """
    Muestra el historial de movimientos de cobro registrados.
    - Si no hay movimientos, muestra 'Sin movimientos', registra el evento y espera 3 segundos.
    - Si hay movimientos, los lista con fecha, placa, tipo, tarifa, pagado y vuelto.
    """
    banner_inicio()
    panel_usuario()
    print(centrar("HISTORIAL DE MOVIMIENTOS"))
    linea()
    # Mensaje cuando la lista de movimientos está vacía
    if not movimientos_peaje:
        # Mostrar exactamente la palabra solicitada por el usuario
        print(centrar("Sin movimientos"))
        # Registrar el evento indicando que la función no encontró movimientos
        registrar_evento('ver_movimientos_peaje', 'Sin movimientos')
        # Pausa solicitada antes de volver al menú para que el operador lea el mensaje
        time.sleep(3.0)
        return
    # Si hay movimientos, iterar y mostrarlos
    for i, m in enumerate(movimientos_peaje, start=1):
        # Cada movimiento contiene: fecha, placa, tipo, tarifa, pagado, vuelto
        print(f"[{i}] {m['fecha']}  Placa: {m['placa']}  Tipo: {m['tipo']}")
        print(f"     Tarifa: {m['tarifa']}  Pagado: {m['pagado']}  Vuelto: {m['vuelto']}")
        linea()
    input("Presione ENTER para volver al menú")

def cobrar_peaje():
    """
    Flujo principal para cobrar el peaje:
      - Solicita placa (o permite registrar vehículo no registrado)
      - Valida tipo y tarifa
      - Solicita monto pagado y verifica si es suficiente
      - Registra movimiento con fecha, placa, tipo, tarifa, pagado y vuelto
      - Registra eventos relevantes (cobro exitoso, cobro fallido, registro cancelado)
    """
    banner_inicio()
    panel_usuario()
    print(centrar("COBRO DE PEAJE"))
    linea()

    # Solicita la placa; si el usuario presiona ENTER, se considera no registrado
    placa = input("Ingrese placa del vehículo o ENTER para no registrado: ").strip().upper()

    if placa:
        # Si se ingresó placa, buscar en registros
        v = buscar_vehiculo_por_placa(placa)
        if v:
            # Vehículo conocido: se usa su tipo registrado
            print(f"Vehículo encontrado: {v['placa']}  Tipo: {v['tipo']}  Propietario: {v.get('propietario','-')}")
            tipo = v['tipo']
        else:
            # Vehículo no registrado: ofrecer registrar ahora o ingresar tipo manualmente
            print("Vehículo no registrado.")
            if confirmar("¿Registrar ahora? (s/n): "):
                # Llamada a agregar_nuevo_vehiculo con la placa propuesta
                tipo = agregar_nuevo_vehiculo(placa_propuesta=placa, preguntar_tipo=True)
                if not tipo:
                    # Si el registro fue cancelado, informar y registrar evento
                    print("Registro cancelado")
                    espera_animacion(0.6, "Volviendo")
                    registrar_evento('cobrar_peaje', f'Registro de placa {placa} cancelado por el operador')
                    return
            else:
                # Si no registra, solicita el tipo manualmente
                tipo = input("Ingrese tipo de vehículo (vehiculo/moto/camion): ").strip().lower()
    else:
        # Sin placa: solicita tipo y una placa opcional (o 'N/A')
        tipo = input("Ingrese tipo de vehículo (vehiculo/moto/camion): ").strip().lower()
        placa = input("Ingrese placa (o 'N/A'): ").strip().upper() or 'N/A'
        # Si la placa ingresada ya existe, usar el registro existente y su tipo
        if placa and buscar_vehiculo_por_placa(placa):
            print(f"La placa {placa} ya está registrada. Usando el registro existente.")
            v = buscar_vehiculo_por_placa(placa)
            tipo = v['tipo']

    # Validación del tipo contra las tarifas definidas
    if tipo not in tarifas_peaje:
        print("Tipo inválido")
        espera_animacion(0.6, "Cancelando")
        # Registrar evento de tipo inválido para auditoría
        registrar_evento('cobrar_peaje', 'Tipo inválido ingresado')
        return

    # Obtener tarifa según tipo y mostrarla
    tarifa = tarifas_peaje[tipo]
    print(f"Tarifa para {tipo}: {tarifa} pesos")

    # Solicita monto pagado y valida que sea entero
    while True:
        try:
            pagado = int(input("Ingrese monto entregado por el conductor: "))
            break
        except ValueError:
            print("Ingrese un número entero válido")

    # Verifica que el monto cubra la tarifa
    if pagado < tarifa:
        print("Monto insuficiente. Cobro no realizado")
        espera_animacion(0.6, "Volviendo")
        # Registrar evento de cobro fallido por monto insuficiente
        registrar_evento('cobrar_peaje', f'Cobro no realizado para placa {placa}: monto insuficiente')
        return

    # Simula procesamiento, calcula vuelto y registra el movimiento
    barra_progreso(20, 0.5, "Registrando cobro")
    vuelto = calcular_vuelto(pagado, tarifa)
    movimiento = {
        'fecha': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        'placa': placa,
        'tipo': tipo,
        'tarifa': tarifa,
        'pagado': pagado,
        'vuelto': vuelto
    }
    movimientos_peaje.append(movimiento)  # Añade el movimiento a la lista global
    beep()  # Señal sonora para indicar cobro registrado
    print(f"Cobro registrado. Vuelto a entregar: {vuelto} pesos")
    # Registrar evento de cobro exitoso para auditoría
    registrar_evento('cobrar_peaje', f'Cobro registrado para placa {placa}, tarifa {tarifa}')
    input("Presione ENTER para volver al menú")

def ajustar_tarifas_peaje():
    """
    Permite al supervisor ajustar las tarifas:
      - Verifica que el operador actual sea supervisor
      - Pide confirmación de contraseña
      - Permite cambiar la tarifa de un tipo específico
      - Registra eventos de acceso denegado, intentos fallidos y cambios aplicados
    """
    banner_inicio()
    panel_usuario()
    print(centrar("AJUSTE DE TARIFAS"))
    linea()

    # Control de acceso: solo supervisor puede modificar tarifas
    if operador_actual != 'supervisor':
        print(centrar("Acceso denegado. Solo supervisor puede editar tarifas"))
        espera_animacion(0.8, "Volviendo")
        registrar_evento('ajustar_tarifas_peaje', 'Acceso denegado a ajuste de tarifas')
        return

    # Solicita la clave del supervisor para confirmar la acción
    clave_confirm = getpass.getpass("Ingrese contraseña del supervisor para confirmar: ").strip()
    if clave_confirm != obtener_clave_operador('supervisor'):
        print("Contraseña incorrecta")
        espera_animacion(0.8, "Cancelando")
        registrar_evento('ajustar_tarifas_peaje', 'Contraseña incorrecta al intentar ajustar tarifas')
        return

    # Si no hay tarifas definidas (caso extremo), informar y registrar
    if not tarifas_peaje:
        print(centrar("No hay tarifas definidas"))
        registrar_evento('ajustar_tarifas_peaje', 'No hay tarifas definidas')
        espera_animacion(0.6, "Volviendo")
        return

    # Mostrar tarifas actuales y solicitar tipo a ajustar
    print("Tarifas actuales:")
    for k, v in tarifas_peaje.items():
        print(f" - {k}: {v} pesos")
    tipo = input("Tipo a ajustar (vehiculo/moto/camion): ").strip().lower()
    if tipo not in tarifas_peaje:
        print("Tipo inválido")
        espera_animacion(0.6, "Cancelando")
        registrar_evento('ajustar_tarifas_peaje', 'Tipo inválido al intentar ajustar tarifa')
        return

    # Solicita la nueva tarifa y valida que sea un entero
    while True:
        try:
            nueva = int(input(f"Ingrese nueva tarifa para {tipo}: "))
            break
        except ValueError:
            print("Ingrese un número entero válido")

    # Confirmación final antes de aplicar el cambio
    if confirmar(f"Confirmar cambio de {tipo} a {nueva} pesos? (s/n): "):
        tarifas_peaje[tipo] = nueva  # Aplica el cambio en el diccionario de tarifas
        barra_progreso(16, 0.6, "Aplicando cambio")
        print("Tarifa actualizada correctamente")
        registrar_evento('ajustar_tarifas_peaje', f'Tarifa de {tipo} cambiada a {nueva}')
    else:
        print("Operación cancelada")
        registrar_evento('ajustar_tarifas_peaje', 'Cambio de tarifa cancelado por el operador')
    input("ENTER para volver al menú")

def agregar_nuevo_vehiculo(placa_propuesta=None, preguntar_tipo=False):
    """
    Registra un nuevo vehículo en la lista de registrados.
    - Valida que la placa sea única (no permite duplicados, case-insensitive).
    - Si la placa ya existe, ofrece reintentar o cancelar.
    - Parámetros:
        placa_propuesta: si se pasa, se usa como placa inicial (evita pedirla)
        preguntar_tipo: si True, solicita explícitamente el tipo
    - Retorna el tipo registrado o None si se cancela.
    """
    banner_inicio()
    panel_usuario()
    print(centrar("REGISTRO DE VEHÍCULO"))
    linea()

    # Bucle para permitir reintentos si la placa ya existe o hay errores de entrada
    while True:
        if placa_propuesta:
            # Si se recibió una placa propuesta (por ejemplo desde cobrar_peaje), usarla
            placa = placa_propuesta.strip().upper()
            placa_propuesta = None  # solo usar la propuesta una vez
        else:
            placa = input("Ingrese placa: ").strip().upper()

        # Validar entrada mínima: la placa no puede estar vacía
        if not placa:
            print("Placa no puede estar vacía.")
            if not confirmar("¿Desea intentar nuevamente? (s/n): "):
                espera_animacion(0.6, "Volviendo")
                registrar_evento('agregar_nuevo_vehiculo', 'Registro cancelado: placa vacía')
                return None
            continue

        # Evita duplicados (comparación case-insensitive)
        if buscar_vehiculo_por_placa(placa):
            print(f"La placa {placa} ya está registrada.")
            if confirmar("¿Desea ingresar otra placa? (s/n): "):
                # si el usuario quiere reintentar, continuar el bucle
                continue
            else:
                espera_animacion(0.6, "Volviendo")
                registrar_evento('agregar_nuevo_vehiculo', f'Registro cancelado: placa {placa} ya existente')
                return None

        # Si la placa es 'N/A' o similar, preguntar confirmación para evitar duplicados no intencionales
        if placa == 'N/A':
            print("Ha ingresado 'N/A' como placa. Esto puede impedir búsquedas futuras.")
            if not confirmar("¿Confirma usar 'N/A' como placa única? (s/n): "):
                # Si no confirma, preguntar si desea intentar otra placa
                if confirmar("¿Desea intentar con otra placa? (s/n): "):
                    continue
                espera_animacion(0.6, "Volviendo")
                registrar_evento('agregar_nuevo_vehiculo', "Registro cancelado: 'N/A' no confirmado")
                return None

        # Solicita tipo (validación posterior)
        if preguntar_tipo:
            tipo = input("Ingrese tipo (vehiculo/moto/camion): ").strip().lower()
        else:
            tipo = input("Ingrese tipo (vehiculo/moto/camion): ").strip().lower()

        # Validación del tipo contra las tarifas definidas
        if tipo not in tarifas_peaje:
            print("Tipo inválido")
            if confirmar("¿Desea intentar nuevamente el registro? (s/n): "):
                continue
            espera_animacion(0.6, "Cancelando")
            registrar_evento('agregar_nuevo_vehiculo', f'Registro cancelado: tipo inválido ({tipo})')
            return None

        # Solicita propietario (opcional) y agrega el vehículo a la lista
        propietario = input("Ingrese propietario (opcional): ").strip() or '-'
        vehiculos_registrados.append({'placa': placa, 'tipo': tipo, 'propietario': propietario})
        barra_progreso(12, 0.5, "Registrando vehículo")
        print(f"Vehículo {placa} registrado como {tipo}")
        registrar_evento('agregar_nuevo_vehiculo', f'Vehículo {placa} registrado como {tipo}')
        return tipo

def ver_vehiculos_registrados():
    """
    Muestra la lista de vehículos registrados con placa, tipo y propietario.
    - Si no hay vehículos, muestra mensaje y registra el evento.
    """
    banner_inicio()
    panel_usuario()
    print(centrar("VEHÍCULOS REGISTRADOS"))
    linea()
    if not vehiculos_registrados:
        print(centrar("No hay vehículos registrados"))
        registrar_evento('ver_vehiculos_registrados', 'No hay vehículos registrados')
        espera_animacion(0.6, "Volviendo")
        return
    # Itera y muestra cada vehículo registrado
    for v in vehiculos_registrados:
        print(f"Placa: {v['placa']:8}  Tipo: {v['tipo']:8}  Propietario: {v.get('propietario','-')}")
    linea()
    input("ENTER para volver al menú")

def mostrar_tarifas_peaje():
    """
    Muestra las tarifas vigentes por tipo de vehículo.
    - Si no hay tarifas definidas, muestra mensaje y registra el evento.
    """
    banner_inicio()
    panel_usuario()
    print(centrar("TARIFAS VIGENTES"))
    linea()
    if not tarifas_peaje:
        print(centrar("No hay tarifas definidas"))
        registrar_evento('mostrar_tarifas_peaje', 'No hay tarifas definidas')
        espera_animacion(0.6, "Volviendo")
        return
    # Muestra cada tarifa con formato legible
    for k, v in tarifas_peaje.items():
        print(f" - {k.capitalize():10} : {v} pesos")
    linea()
    input("ENTER para volver al menú")

def reporte_ingresos():
    """
    Genera un reporte simple de ingresos:
      - Suma recaudado por tipo
      - Cuenta la cantidad de pasos por tipo
      - Muestra total general
    - Si no hay movimientos, muestra mensaje y registra el evento.
    """
    banner_inicio()
    panel_usuario()
    print(centrar("REPORTE DE INGRESOS"))
    linea()
    if not movimientos_peaje:
        print(centrar("No hay movimientos para generar reporte"))
        registrar_evento('reporte_ingresos', 'No hay movimientos para generar reporte')
        espera_animacion(0.6, "Volviendo")
        return

    # Inicializa acumuladores por tipo según las tarifas definidas
    totales = {k: 0 for k in tarifas_peaje}
    conteo = {k: 0 for k in tarifas_peaje}
    total_general = 0

    # Recorre movimientos y acumula por tipo
    for m in movimientos_peaje:
        t = m['tipo']
        totales[t] += m['tarifa']
        conteo[t] += 1
        total_general += m['tarifa']

    # Muestra resultados por tipo y total general
    for k in totales:
        print(f"{k.capitalize():10} Recaudado: {totales[k]:8}  Pasos: {conteo[k]:3}")
    linea()
    print(f"Total general recaudado: {total_general} pesos")
    # Registrar evento de generación de reporte con totales para auditoría
    registrar_evento('reporte_ingresos', f'Reporte generado. Total: {total_general} pesos')
    input("ENTER para volver al menú")

def opcion_invalida():
    """
    Mensaje genérico para opciones de menú inválidas.
    - Muestra un mensaje breve y registra el evento.
    """
    print("Opción inválida")
    time.sleep(0.8)
    registrar_evento('menu_principal', 'Opción inválida seleccionada')

# -------------------------
# Autenticación con interfaz
# -------------------------
def autenticar_garita():
    """
    Flujo de autenticación:
      - Pide nombre de operador y contraseña
      - Valida contra garita_usuarios
      - Permite hasta 3 intentos
      - Si es correcto, establece operador_actual y muestra panel de bienvenida
    Retorna True si la autenticación fue exitosa, False en caso contrario.
    """
    global operador_actual
    limpiar_pantalla()
    banner_inicio()
    print(centrar("INICIO DE SESIÓN"))
    linea()
    intentos = 0
    max_intentos = 3

    # Bucle de intentos de autenticación
    while intentos < max_intentos:
        usuario = input("Nombre de operador: ").strip()
        clave = getpass.getpass("Contraseña: ").strip()
        encontrado = False
        clave_almacenada = None

        # Busca credenciales en la lista en memoria
        for cred in garita_usuarios:
            if usuario in cred:
                encontrado = True
                clave_almacenada = cred[usuario]
                break

        # Valida credenciales
        if encontrado and clave_almacenada == clave:
            operador_actual = usuario  # Establece el operador global
            limpiar_pantalla()
            banner_inicio()
            panel = nombre_panel_por_rol(operador_actual)
            print(centrar(panel))
            linea()
            print(centrar(f"Bienvenido, {operador_actual}"))
            if operador_actual == 'supervisor':
                print(centrar("Acceso completo: puede ajustar tarifas"))
            else:
                print(centrar("Acceso limitado: funciones de cobro y registro"))
            linea()
            time.sleep(1.2)
            registrar_evento('autenticar_garita', f'Operador {operador_actual} autenticado correctamente')
            return True
        else:
            # Manejo de intentos fallidos: incrementar contador y mostrar restantes
            intentos += 1
            restante = max_intentos - intentos
            print("Operador o contraseña incorrectos.")
            if restante:
                print(f"Intentos restantes: {restante}")
            else:
                print("Se han agotado los intentos.")
            time.sleep(1.0)

    # Si se agotan los intentos, registrar evento y retornar False
    registrar_evento('autenticar_garita', 'Autenticación fallida: se agotaron intentos')
    return False

# -------------------------
# Menú principal interactivo
# -------------------------
def menu_principal():
    """
    Muestra el menú principal y despacha a las funciones correspondientes.
    - Define las opciones disponibles y sus funciones asociadas
    - Controla la salida del sistema con confirmación
    - Incluye opción para ver registro de eventos
    """
    limpiar_pantalla()
    opciones_menu = {
        '1': ("Ver Movimientos", ver_movimientos_peaje),
        '2': ("Cobrar peaje", cobrar_peaje),
        '3': ("Ajustar tarifas (solo supervisor)", ajustar_tarifas_peaje),
        '4': ("Agregar nuevo vehículo", agregar_nuevo_vehiculo),
        '5': ("Ver vehículos registrados", ver_vehiculos_registrados),
        '6': ("Mostrar tarifas", mostrar_tarifas_peaje),
        '7': ("Reporte de ingresos", reporte_ingresos),
        '8': ("Ver registro de eventos", ver_registro_eventos),
        '0': ("Salir", None)
    }

    # Bucle principal del menú: muestra opciones y ejecuta la función seleccionada
    while True:
        limpiar_pantalla()
        banner_inicio()
        panel_usuario()
        print(centrar("MENÚ PRINCIPAL"))
        linea()
        for k, v in opciones_menu.items():
            print(f" {k}) {v[0]}")
        linea()
        print("Atajo: presione la tecla del número y ENTER")
        elec = input("Seleccione opción: ").strip()

        # Manejo de salida con confirmación
        if elec == '0':
            if confirmar("¿Desea salir del sistema? (s/n): "):
                print("Cerrando sesión...")
                espera_animacion(0.8, "Saliendo")
                registrar_evento('menu_principal', 'Cierre de sesión por el operador')
                break
            else:
                continue

        accion = opciones_menu.get(elec)
        if accion:
            func = accion[1]
            if func:
                # Llama a la función asociada a la opción seleccionada
                func()
        else:
            # Opción inválida: mostrar mensaje y registrar evento
            opcion_invalida()

# -------------------------
# Entrada principal
# -------------------------
if __name__ == "__main__":
    # Punto de entrada: autentica y, si es exitoso, muestra el menú principal
    if autenticar_garita():
        menu_principal()
    else:
        print("Acceso denegado. Fin del programa.")
        registrar_evento('main', 'Acceso denegado al iniciar el programa')
