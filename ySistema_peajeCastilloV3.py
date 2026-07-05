# ============================================================
#  SISTEMA DE PEAJE - GARITA  (Versión Segura v2.0)
# ============================================================
#
# MEJORAS DE SEGURIDAD IMPLEMENTADAS
# ────────────────────────────────────────────────────────────
#
# 1. HASHING DE CONTRASEÑAS (PBKDF2-SHA256)
#    • Contraseñas almacenadas SOLO como hash + salt único
#    • 200.000 iteraciones PBKDF2-HMAC-SHA256 (resistente a GPU cracking)
#    • Comparación en tiempo constante → anti "timing attack"
#    • Jamás aparece ninguna contraseña en texto plano en este archivo
#
# 2. ENTRADA SEGURA CON LÍMITE DURO DE CARACTERES
#    • getpass_limitado(): lectura carácter a carácter, muestra '*',
#      bloquea silenciosamente al llegar al límite (anti-DoS por teclado)
#    • input_seguro(): igual pero muestra el texto; corta al límite
#    • Fallback automático a getpass/input si termios/msvcrt no están
#    • Compatible con Unix (termios) y Windows (msvcrt)
#
# 3. PROTECCIÓN ANTI FUERZA BRUTA
#    • Máximo 3 intentos de login antes de bloquear
#    • Retardo exponencial por cada fallo: 2^intento segundos (2s, 4s, 8s)
#    • Bloqueo de 30 segundos al agotar intentos con cuenta regresiva
#    • El mensaje de error nunca revela qué campo (usuario o clave) es incorrecto
#
# 4. VALIDACIÓN Y SANITIZACIÓN DE ENTRADAS
#    • Placas: solo [A-Z0-9], máximo MAX_LEN_PLACA caracteres
#    • Montos: enteros, rango 1 – MAX_MONTO (anti overflow / valores absurdos)
#    • Texto libre: eliminación de caracteres de control (\x00–\x1f)
#    • Tipos de vehículo: validados contra lista blanca (whitelist)
#
# 5. INTEGRIDAD DEL REGISTRO DE EVENTOS
#    • Los eventos NO registran contraseñas, hashes ni datos sensibles
#    • Los mensajes de error no filtran información de la BD interna
#
# ────────────────────────────────────────────────────────────
#  PARA CAMBIAR UNA CONTRASEÑA ejecute en Python:
#      from peaje_seguro import hash_clave
#      salt, h = hash_clave("nueva_clave")
#      print(f"'salt': '{salt}', 'hash': '{h}'")
#  Luego actualice el bloque garita_usuarios con los nuevos valores.
# ============================================================

import os
import sys
import time
import hashlib
import secrets
import shutil
from datetime import datetime

# ============================================================
# SECCIÓN 1 · CONSTANTES DE SEGURIDAD
# ============================================================
MAX_LEN_PASSWORD    = 32          # Máx. caracteres aceptados en campo contraseña
MAX_LEN_PLACA       = 10          # Máx. caracteres para número de placa
MAX_LEN_TEXTO       = 50          # Máx. caracteres para texto general
MAX_LEN_PROPIETARIO = 60          # Máx. caracteres para nombre del propietario
MAX_MONTO           = 10_000_000  # Monto máximo razonable (anti-overflow)
MIN_MONTO           = 1           # Monto mínimo positivo
MAX_INTENTOS_LOGIN  = 3           # Intentos de login antes del bloqueo
LOCKOUT_SEGUNDOS    = 30          # Segundos de bloqueo tras agotar intentos

# ============================================================
# SECCIÓN 2 · CONTRASEÑAS HASHEADAS  (PBKDF2-SHA256 + salt)
# ============================================================
# ⚠  NINGUNA CONTRASEÑA APARECE EN TEXTO PLANO EN ESTE ARCHIVO ⚠
#
# Campos:
#   nombre → identificador del operador
#   salt   → cadena aleatoria única por usuario (hex 32 chars)
#   hash   → PBKDF2-HMAC-SHA256(contraseña, salt, 200000) en hex
#
# Credenciales actuales del sistema (los valores hash son la forma
# segura de almacenar las contraseñas; no permiten recuperar el
# texto original sin conocerlo de antemano):
#
#   supervisor  →  contraseña hasheada (hash almacenado abajo)
#   cajero      →  contraseña hasheada (hash almacenado abajo)
#
garita_usuarios = [
    {
        'nombre': 'supervisor',
        'salt':   'f5a287e73e584b4ab0f7afa6f752b8ae',
        'hash':   '8e7b659d48c0c29dbb1b79a5c3f913a6bb3801556d011f538f4aedb01ba8ea46'
    },
    {
        'nombre': 'cajero',
        'salt':   '092a05e028b0d23f5e910cfbcf94e7d6',
        'hash':   'b564ad619d70b93b341a04670740e08998cb18f184fa54e0fd9259013433b7af'
    }
]

# ============================================================
# SECCIÓN 3 · DATOS DEL SISTEMA (sin cambios funcionales)
# ============================================================
tarifas_peaje = {
    'vehiculo': 500,
    'moto':     250,
    'camion':   1500
}

vehiculos_registrados = [
    {'placa': 'ABC123', 'tipo': 'vehiculo', 'propietario': 'Empresa X'},
    {'placa': 'MOTO01', 'tipo': 'moto',     'propietario': 'Luis Perez'},
    {'placa': 'TRK999', 'tipo': 'camion',   'propietario': 'Transporte SA'}
]

movimientos_peaje  = []
registro_eventos   = []
operador_actual    = None

# ============================================================
# SECCIÓN 4 · FUNCIONES DE HASHING Y VERIFICACIÓN
# ============================================================

def hash_clave(clave: str, salt: str = None) -> tuple:
    """
    Genera un hash seguro con PBKDF2-HMAC-SHA256.

    Parámetros:
        clave : contraseña en texto plano
        salt  : cadena de sal; si None genera una aleatoria de 32 chars hex

    Retorna:
        (salt: str, hash_hex: str)

    Uso para registrar nueva contraseña:
        salt, h = hash_clave("mi_nueva_clave")
        → guardar salt y h en garita_usuarios
    """
    if salt is None:
        salt = secrets.token_hex(16)     # 128 bits de entropía
    dk = hashlib.pbkdf2_hmac(
        'sha256',
        clave.encode('utf-8'),
        salt.encode('utf-8'),
        iterations=200_000               # lento para quien ataque, rápido para uso normal
    )
    return salt, dk.hex()


def verificar_clave(clave_ingresada: str, salt: str, hash_almacenado: str) -> bool:
    """
    Verifica una contraseña ingresada contra el hash almacenado.

    Usa secrets.compare_digest para comparación en tiempo constante,
    lo que previene "timing attacks" (ataques que miden microsegundos
    de diferencia para deducir cuántos caracteres coinciden).

    Retorna:
        True si la contraseña es correcta, False en cualquier otro caso.
    """
    _, hash_calculado = hash_clave(clave_ingresada, salt)
    # compare_digest tarda lo mismo sea cual sea la diferencia → seguro
    return secrets.compare_digest(hash_calculado, hash_almacenado)


def obtener_credenciales_operador(nombre_operador: str) -> dict | None:
    """
    Retorna el diccionario de credenciales (salt + hash) del operador.
    Nunca retorna la contraseña en texto plano.
    Retorna None si el operador no existe.
    """
    for cred in garita_usuarios:
        if cred['nombre'] == nombre_operador:
            return cred
    return None

# ============================================================
# SECCIÓN 5 · ENTRADA SEGURA CON LÍMITE DE CARACTERES
# ============================================================

def _leer_chars_unix(prompt: str, max_len: int, ocultar: bool) -> str:
    """
    Lee caracteres en modo raw (termios) en Unix/macOS.
    - Si ocultar=True, muestra '*' en lugar del carácter (contraseñas).
    - Bloquea silenciosamente al alcanzar max_len caracteres.
    - Soporta Backspace y Ctrl-C.
    """
    import termios, tty
    print(prompt, end='', flush=True)
    chars = []
    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)
    try:
        tty.setraw(fd)
        while True:
            ch = sys.stdin.read(1)
            if ch in ('\r', '\n'):
                # Fin de entrada
                print()
                break
            elif ch == '\x7f' or ch == '\x08':
                # Backspace: eliminar último carácter
                if chars:
                    chars.pop()
                    print('\b \b', end='', flush=True)
            elif ch == '\x03':
                # Ctrl-C
                raise KeyboardInterrupt
            elif ch < '\x20':
                # Ignorar otros caracteres de control (anti-injection)
                pass
            elif len(chars) < max_len:
                # Carácter válido dentro del límite
                chars.append(ch)
                print('*' if ocultar else ch, end='', flush=True)
            # Si ya llegamos a max_len: ignorar silenciosamente el carácter extra
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
    return ''.join(chars)


def _leer_chars_windows(prompt: str, max_len: int, ocultar: bool) -> str:
    """
    Lee caracteres con msvcrt en Windows.
    Misma lógica que la versión Unix pero usando la API de Windows.
    """
    import msvcrt
    print(prompt, end='', flush=True)
    chars = []
    while True:
        ch = msvcrt.getwch()
        if ch in ('\r', '\n'):
            print()
            break
        elif ch == '\x08':
            # Backspace
            if chars:
                chars.pop()
                print('\b \b', end='', flush=True)
        elif ch == '\x03':
            raise KeyboardInterrupt
        elif ord(ch) < 0x20:
            pass   # ignorar caracteres de control
        elif len(chars) < max_len:
            chars.append(ch)
            print('*' if ocultar else ch, end='', flush=True)
    return ''.join(chars)


def getpass_limitado(prompt: str = "Contraseña: ", max_len: int = MAX_LEN_PASSWORD) -> str:
    """
    Lee una contraseña de forma segura:
      • Muestra '*' por cada carácter (nunca el carácter real)
      • Bloquea al llegar a max_len (no permite más pulsaciones)
      • Soporta Backspace
      • Si termios/msvcrt no están disponibles, usa getpass estándar + truncado

    El límite de max_len impide que alguien intente tumbar el sistema
    enviando millones de caracteres por teclado.
    """
    try:
        if os.name == 'nt':
            return _leer_chars_windows(prompt, max_len, ocultar=True)
        else:
            return _leer_chars_unix(prompt, max_len, ocultar=True)
    except (ImportError, Exception):
        # Fallback: getpass estándar del sistema + truncado de seguridad
        import getpass as _gp
        pw = _gp.getpass(prompt)
        return pw[:max_len]


def input_seguro(prompt: str, max_len: int = MAX_LEN_TEXTO) -> str:
    """
    Lee una entrada de texto visible con límite duro de caracteres.
      • Muestra el texto mientras se escribe
      • Bloquea al llegar a max_len (caracteres extra son ignorados)
      • Elimina caracteres de control del resultado final
      • Fallback a input() estándar + truncado si termios no está

    Previene ataques DoS por entradas extremadamente largas.
    """
    try:
        if os.name == 'nt':
            raw = _leer_chars_windows(prompt, max_len, ocultar=False)
        else:
            raw = _leer_chars_unix(prompt, max_len, ocultar=False)
    except (ImportError, Exception):
        raw = input(prompt)[:max_len]
    # Sanitización: eliminar caracteres de control residuales
    return ''.join(c for c in raw if c >= ' ').strip()


def sanitizar_placa(placa: str) -> str:
    """
    Limpia y valida una placa de vehículo:
      • Convierte a mayúsculas
      • Elimina todo lo que no sea letra o número
      • Trunca a MAX_LEN_PLACA caracteres

    Retorna la placa sanitizada o cadena vacía si queda vacía.
    """
    placa = placa.upper().strip()
    placa = ''.join(c for c in placa if c.isalnum())
    return placa[:MAX_LEN_PLACA]


def validar_monto(valor_str: str) -> int | None:
    """
    Valida y convierte un monto a entero seguro.
    Rechaza:
      • Valores no numéricos
      • Valores menores a MIN_MONTO
      • Valores mayores a MAX_MONTO (anti-overflow)

    Retorna el entero válido o None si la validación falla.
    """
    try:
        monto = int(valor_str)
    except (ValueError, OverflowError):
        return None
    if monto < MIN_MONTO or monto > MAX_MONTO:
        return None
    return monto

# ============================================================
# SECCIÓN 6 · UTILIDADES DE INTERFAZ (sin cambios funcionales)
# ============================================================

def ancho_terminal(default=80):
    """Devuelve el ancho real de la terminal; si falla, retorna 80."""
    try:
        return shutil.get_terminal_size().columns
    except Exception:
        return default

def limpiar_pantalla():
    """Limpia la pantalla según el SO ('cls' / 'clear')."""
    os.system('cls' if os.name == 'nt' else 'clear')

def centrar(texto, ancho=None):
    """Centra un texto en el ancho de la terminal."""
    ancho = ancho or ancho_terminal()
    return texto.center(ancho)

def linea(char='─'):
    """Imprime una línea horizontal del ancho de la terminal."""
    print(char * ancho_terminal())

def espera_animacion(segundos=0.8, mensaje="Cargando"):
    """Animación de puntos durante 'segundos' tiempo total."""
    pasos = 6
    for i in range(pasos):
        dots = '.' * ((i % 3) + 1)
        print(f"\r{mensaje}{dots} ", end='', flush=True)
        time.sleep(segundos / pasos)
    print("\r" + " " * (len(mensaje) + 4), end='\r')

def barra_progreso(total=20, duracion=0.6, mensaje="Procesando"):
    """Barra de progreso visual en consola."""
    for i in range(total + 1):
        por  = int((i / total) * 100)
        barra = '█' * i + '-' * (total - i)
        print(f"\r{mensaje} |{barra}| {por:3d}%", end='', flush=True)
        time.sleep(duracion / total)
    print()

def confirmar(texto="¿Confirmar? (s/n): ") -> bool:
    """
    Solicita confirmación s/n con validación.
    Usa input_seguro para evitar entradas largas incluso en este campo.
    """
    while True:
        r = input_seguro(texto, max_len=3).lower()
        if r in ('s', 'n'):
            return r == 's'
        print("Ingrese 's' para sí o 'n' para no.")

def beep():
    """Emite una señal sonora de sistema."""
    print('\a', end='')

# ============================================================
# SECCIÓN 7 · REGISTRO DE EVENTOS
# ============================================================

def registrar_evento(funcion: str, mensaje: str):
    """
    Registra un evento en la lista de auditoría.

    ⚠ SEGURIDAD: nunca pasar contraseñas, hashes ni datos sensibles
    como parte del 'mensaje'. Los registros son visibles para operadores.
    """
    evento = {
        'fecha':   datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        'funcion': funcion[:50],       # limitar largo del nombre de función
        'mensaje': mensaje[:200]       # limitar largo del mensaje de evento
    }
    registro_eventos.append(evento)

def ver_registro_eventos():
    """Muestra todos los eventos de auditoría registrados."""
    banner_inicio()
    panel_usuario()
    print(centrar("REGISTRO DE EVENTOS"))
    linea()
    if not registro_eventos:
        print(centrar("No hay eventos registrados"))
        espera_animacion(0.6, "Volviendo")
        return
    for e in registro_eventos:
        print(f"{e['fecha']}  Función: {e['funcion']}  Mensaje: {e['mensaje']}")
        linea()
    input("ENTER para volver al menú")

# ============================================================
# SECCIÓN 8 · BANNER Y PANEL DE USUARIO
# ============================================================

def banner_inicio():
    """Dibuja el banner del sistema; limpia la pantalla antes."""
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
    """Muestra nombre del panel, operador y hora actual."""
    ancho = ancho_terminal()
    panel = nombre_panel_por_rol(operador_actual)
    print(centrar(panel, ancho))
    linea()
    print(centrar(f"Operador: {operador_actual}", ancho))
    print(centrar(f"Hora: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", ancho))
    linea()

def nombre_panel_por_rol(rol: str) -> str:
    """Retorna el título del panel según el rol del operador."""
    if rol == 'supervisor':
        return "PANEL SUPERVISOR - CONTROL TOTAL"
    if rol == 'cajero':
        return "PANEL CAJERO - OPERACIONES DE COBRO"
    return "PANEL OPERADOR"

# ============================================================
# SECCIÓN 9 · FUNCIONES DE DATOS
# ============================================================

def buscar_vehiculo_por_placa(placa: str) -> dict | None:
    """
    Busca un vehículo por placa (case-insensitive).
    La placa se sanitiza antes de buscar.
    """
    placa = sanitizar_placa(placa)
    if not placa:
        return None
    for v in vehiculos_registrados:
        if sanitizar_placa(v['placa']) == placa:
            return v
    return None

def calcular_vuelto(monto_pagado: int, tarifa: int) -> int:
    """Calcula el vuelto: pagado − tarifa."""
    return monto_pagado - tarifa

# ============================================================
# SECCIÓN 10 · OPERACIONES PRINCIPALES
# ============================================================

def ver_movimientos_peaje():
    """Muestra el historial de cobros registrados."""
    banner_inicio()
    panel_usuario()
    print(centrar("HISTORIAL DE MOVIMIENTOS"))
    linea()
    if not movimientos_peaje:
        print(centrar("Sin movimientos"))
        registrar_evento('ver_movimientos_peaje', 'Sin movimientos')
        time.sleep(3.0)
        return
    for i, m in enumerate(movimientos_peaje, start=1):
        print(f"[{i}] {m['fecha']}  Placa: {m['placa']}  Tipo: {m['tipo']}")
        print(f"     Tarifa: {m['tarifa']}  Pagado: {m['pagado']}  Vuelto: {m['vuelto']}")
        linea()
    input("Presione ENTER para volver al menú")


def cobrar_peaje():
    """
    Flujo de cobro de peaje con entradas validadas:
      • Placa sanitizada (solo alfanumérico, máx 10 chars)
      • Monto validado en rango [1, MAX_MONTO]
      • Tipo validado contra whitelist
    """
    banner_inicio()
    panel_usuario()
    print(centrar("COBRO DE PEAJE"))
    linea()

    # ── Entrada de placa con límite de caracteres ──
    placa_raw = input_seguro(
        "Ingrese placa del vehículo o ENTER para no registrado: ",
        max_len=MAX_LEN_PLACA
    )
    placa = sanitizar_placa(placa_raw)

    if placa:
        v = buscar_vehiculo_por_placa(placa)
        if v:
            print(f"Vehículo encontrado: {v['placa']}  "
                  f"Tipo: {v['tipo']}  Propietario: {v.get('propietario', '-')}")
            tipo = v['tipo']
        else:
            print("Vehículo no registrado.")
            if confirmar("¿Registrar ahora? (s/n): "):
                tipo = agregar_nuevo_vehiculo(placa_propuesta=placa, preguntar_tipo=True)
                if not tipo:
                    print("Registro cancelado")
                    espera_animacion(0.6, "Volviendo")
                    registrar_evento('cobrar_peaje', 'Registro cancelado por el operador')
                    return
            else:
                tipo = input_seguro(
                    "Ingrese tipo de vehículo (vehiculo/moto/camion): ",
                    max_len=10
                ).lower()
    else:
        tipo  = input_seguro(
            "Ingrese tipo de vehículo (vehiculo/moto/camion): ",
            max_len=10
        ).lower()
        placa_raw = input_seguro("Ingrese placa (o 'N/A'): ", max_len=MAX_LEN_PLACA)
        placa = sanitizar_placa(placa_raw) or 'NA'
        if placa and placa != 'NA':
            v_existente = buscar_vehiculo_por_placa(placa)
            if v_existente:
                print(f"La placa {placa} ya está registrada. Usando el registro existente.")
                tipo = v_existente['tipo']

    # ── Validación del tipo (whitelist) ──
    if tipo not in tarifas_peaje:
        print("Tipo de vehículo inválido.")
        espera_animacion(0.6, "Cancelando")
        registrar_evento('cobrar_peaje', 'Tipo de vehículo inválido ingresado')
        return

    tarifa = tarifas_peaje[tipo]
    print(f"Tarifa para {tipo}: {tarifa} pesos")

    # ── Monto con validación de rango ──
    pagado = None
    while pagado is None:
        raw = input_seguro("Ingrese monto entregado por el conductor: ", max_len=10)
        pagado = validar_monto(raw)
        if pagado is None:
            print(f"Ingrese un número entero válido entre {MIN_MONTO:,} y {MAX_MONTO:,}.")

    if pagado < tarifa:
        print("Monto insuficiente. Cobro no realizado.")
        espera_animacion(0.6, "Volviendo")
        registrar_evento('cobrar_peaje', f'Cobro no realizado para {placa}: monto insuficiente')
        return

    barra_progreso(20, 0.5, "Registrando cobro")
    vuelto = calcular_vuelto(pagado, tarifa)
    movimiento = {
        'fecha':  datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        'placa':  placa,
        'tipo':   tipo,
        'tarifa': tarifa,
        'pagado': pagado,
        'vuelto': vuelto
    }
    movimientos_peaje.append(movimiento)
    beep()
    print(f"Cobro registrado. Vuelto a entregar: {vuelto} pesos")
    registrar_evento('cobrar_peaje', f'Cobro exitoso placa {placa} tarifa {tarifa}')
    input("Presione ENTER para volver al menú")


def ajustar_tarifas_peaje():
    """
    Ajuste de tarifas:
      • Solo supervisor puede acceder
      • Requiere reconfirmación de contraseña (verificada con hash)
      • Tipo validado contra whitelist
      • Nueva tarifa validada en rango razonable
    """
    banner_inicio()
    panel_usuario()
    print(centrar("AJUSTE DE TARIFAS"))
    linea()

    # ── Control de acceso por rol ──
    if operador_actual != 'supervisor':
        print(centrar("Acceso denegado. Solo el supervisor puede editar tarifas."))
        espera_animacion(0.8, "Volviendo")
        registrar_evento('ajustar_tarifas_peaje', 'Acceso denegado')
        return

    # ── Reconfirmación de contraseña (con límite de caracteres) ──
    print("Se requiere confirmar su identidad.")
    clave_confirm = getpass_limitado(
        "Contraseña del supervisor: ",
        max_len=MAX_LEN_PASSWORD
    )
    cred = obtener_credenciales_operador('supervisor')
    if cred is None or not verificar_clave(clave_confirm, cred['salt'], cred['hash']):
        print("Contraseña incorrecta.")
        espera_animacion(0.8, "Cancelando")
        # ⚠ No se registra la clave ingresada en el evento
        registrar_evento('ajustar_tarifas_peaje', 'Verificación de identidad fallida')
        return

    if not tarifas_peaje:
        print(centrar("No hay tarifas definidas."))
        registrar_evento('ajustar_tarifas_peaje', 'No hay tarifas definidas')
        espera_animacion(0.6, "Volviendo")
        return

    print("Tarifas actuales:")
    for k, v in tarifas_peaje.items():
        print(f"  - {k}: {v} pesos")

    tipo = input_seguro("Tipo a ajustar (vehiculo/moto/camion): ", max_len=10).lower()
    if tipo not in tarifas_peaje:
        print("Tipo inválido.")
        espera_animacion(0.6, "Cancelando")
        registrar_evento('ajustar_tarifas_peaje', 'Tipo inválido en ajuste')
        return

    nueva = None
    while nueva is None:
        raw = input_seguro(f"Ingrese nueva tarifa para {tipo}: ", max_len=10)
        nueva = validar_monto(raw)
        if nueva is None:
            print(f"Ingrese un número entero válido entre {MIN_MONTO:,} y {MAX_MONTO:,}.")

    if confirmar(f"Confirmar cambio de {tipo} a {nueva} pesos (s/n): "):
        tarifas_peaje[tipo] = nueva
        barra_progreso(16, 0.6, "Aplicando cambio")
        print("Tarifa actualizada correctamente.")
        registrar_evento('ajustar_tarifas_peaje', f'Tarifa {tipo} → {nueva} pesos')
    else:
        print("Operación cancelada.")
        registrar_evento('ajustar_tarifas_peaje', 'Cambio cancelado por el operador')
    input("ENTER para volver al menú")


def agregar_nuevo_vehiculo(placa_propuesta: str = None, preguntar_tipo: bool = False):
    """
    Registra un vehículo nuevo.
      • Placa sanitizada (solo alfanumérico, máx MAX_LEN_PLACA)
      • Tipo validado contra whitelist
      • Propietario limitado a MAX_LEN_PROPIETARIO caracteres
    """
    banner_inicio()
    panel_usuario()
    print(centrar("REGISTRO DE VEHÍCULO"))
    linea()

    while True:
        if placa_propuesta:
            placa = sanitizar_placa(placa_propuesta)
            placa_propuesta = None
        else:
            raw = input_seguro("Ingrese placa: ", max_len=MAX_LEN_PLACA)
            placa = sanitizar_placa(raw)

        if not placa:
            print("Placa no puede estar vacía o contener solo caracteres inválidos.")
            if not confirmar("¿Desea intentar nuevamente? (s/n): "):
                registrar_evento('agregar_nuevo_vehiculo', 'Registro cancelado: placa vacía/inválida')
                return None
            continue

        if buscar_vehiculo_por_placa(placa):
            print(f"La placa {placa} ya está registrada.")
            if confirmar("¿Desea ingresar otra placa? (s/n): "):
                continue
            registrar_evento('agregar_nuevo_vehiculo', f'Registro cancelado: {placa} ya existente')
            return None

        # Advertencia si usan 'NA' (antes era 'N/A')
        if placa == 'NA':
            print("Ha ingresado 'NA' como placa. Esto puede impedir búsquedas futuras.")
            if not confirmar("¿Confirma usar 'NA' como placa? (s/n): "):
                if confirmar("¿Desea intentar con otra placa? (s/n): "):
                    continue
                registrar_evento('agregar_nuevo_vehiculo', "Registro cancelado: 'NA' no confirmado")
                return None

        tipo = input_seguro(
            "Ingrese tipo (vehiculo/moto/camion): ",
            max_len=10
        ).lower()

        if tipo not in tarifas_peaje:
            print("Tipo inválido.")
            if confirmar("¿Desea intentar nuevamente? (s/n): "):
                continue
            registrar_evento('agregar_nuevo_vehiculo', f'Registro cancelado: tipo inválido ({tipo})')
            return None

        propietario = input_seguro(
            "Ingrese propietario (opcional, ENTER para omitir): ",
            max_len=MAX_LEN_PROPIETARIO
        ) or '-'

        vehiculos_registrados.append({
            'placa':       placa,
            'tipo':        tipo,
            'propietario': propietario
        })
        barra_progreso(12, 0.5, "Registrando vehículo")
        print(f"Vehículo {placa} registrado como {tipo}.")
        registrar_evento('agregar_nuevo_vehiculo', f'Vehículo {placa} registrado como {tipo}')
        return tipo


def ver_vehiculos_registrados():
    """Muestra la lista de vehículos registrados."""
    banner_inicio()
    panel_usuario()
    print(centrar("VEHÍCULOS REGISTRADOS"))
    linea()
    if not vehiculos_registrados:
        print(centrar("No hay vehículos registrados."))
        registrar_evento('ver_vehiculos_registrados', 'Lista vacía')
        espera_animacion(0.6, "Volviendo")
        return
    for v in vehiculos_registrados:
        print(f"Placa: {v['placa']:10}  Tipo: {v['tipo']:8}  Propietario: {v.get('propietario', '-')}")
    linea()
    input("ENTER para volver al menú")


def mostrar_tarifas_peaje():
    """Muestra las tarifas vigentes."""
    banner_inicio()
    panel_usuario()
    print(centrar("TARIFAS VIGENTES"))
    linea()
    if not tarifas_peaje:
        print(centrar("No hay tarifas definidas."))
        registrar_evento('mostrar_tarifas_peaje', 'No hay tarifas definidas')
        espera_animacion(0.6, "Volviendo")
        return
    for k, v in tarifas_peaje.items():
        print(f"  - {k.capitalize():10} : {v} pesos")
    linea()
    input("ENTER para volver al menú")


def reporte_ingresos():
    """Reporte de ingresos totales agrupado por tipo de vehículo."""
    banner_inicio()
    panel_usuario()
    print(centrar("REPORTE DE INGRESOS"))
    linea()
    if not movimientos_peaje:
        print(centrar("No hay movimientos para generar reporte."))
        registrar_evento('reporte_ingresos', 'Sin movimientos')
        espera_animacion(0.6, "Volviendo")
        return

    totales       = {k: 0 for k in tarifas_peaje}
    conteo        = {k: 0 for k in tarifas_peaje}
    total_general = 0
    for m in movimientos_peaje:
        t = m['tipo']
        if t in totales:
            totales[t]  += m['tarifa']
            conteo[t]   += 1
            total_general += m['tarifa']

    for k in totales:
        print(f"  {k.capitalize():10}  Recaudado: {totales[k]:10,}  Pasos: {conteo[k]:4}")
    linea()
    print(f"  Total general recaudado: {total_general:,} pesos")
    registrar_evento('reporte_ingresos', f'Total: {total_general} pesos')
    input("ENTER para volver al menú")


def opcion_invalida():
    """Mensaje para opciones de menú no reconocidas."""
    print("Opción inválida.")
    time.sleep(0.8)
    registrar_evento('menu_principal', 'Opción inválida seleccionada')

# ============================================================
# SECCIÓN 11 · AUTENTICACIÓN SEGURA
# ============================================================

def autenticar_garita() -> bool:
    """
    Flujo de login con protecciones de seguridad:

    ┌─ Mejoras respecto a versión anterior ───────────────────┐
    │  • Usa verificar_clave() con PBKDF2 + tiempo constante  │
    │  • Retardo exponencial por cada intento fallido          │
    │  • Bloqueo de 30 s con cuenta regresiva al agotar       │
    │  • Los mensajes de error no revelan qué campo falló      │
    │  • getpass_limitado() bloquea contraseñas largas         │
    │  • input_seguro() limita el nombre de usuario            │
    └──────────────────────────────────────────────────────────┘

    Retorna True si el login fue exitoso, False si se agotaron los intentos.
    """
    global operador_actual
    limpiar_pantalla()
    banner_inicio()
    print(centrar("INICIO DE SESIÓN"))
    linea()

    intentos = 0

    while intentos < MAX_INTENTOS_LOGIN:
        # Entrada de usuario con límite de caracteres
        usuario = input_seguro("Nombre de operador: ", max_len=MAX_LEN_TEXTO)

        # Entrada de contraseña oculta y limitada en longitud
        clave = getpass_limitado(
            "Contraseña: ",
            max_len=MAX_LEN_PASSWORD
        )

        # ── Verificación segura ──────────────────────────────
        cred = obtener_credenciales_operador(usuario)
        if cred is not None and verificar_clave(clave, cred['salt'], cred['hash']):
            # Login exitoso
            operador_actual = usuario
            limpiar_pantalla()
            banner_inicio()
            print(centrar(nombre_panel_por_rol(operador_actual)))
            linea()
            print(centrar(f"Bienvenido, {operador_actual}"))
            if operador_actual == 'supervisor':
                print(centrar("Acceso completo: puede ajustar tarifas."))
            else:
                print(centrar("Acceso limitado: cobro y registro de vehículos."))
            linea()
            time.sleep(1.2)
            registrar_evento('autenticar_garita', f'Operador {operador_actual} autenticado')
            return True

        # ── Login fallido ────────────────────────────────────
        intentos += 1
        restante  = MAX_INTENTOS_LOGIN - intentos

        # ⚠ El mensaje NO dice si falló el usuario o la contraseña
        print("Credenciales incorrectas.")
        if restante > 0:
            # Retardo exponencial: 2^intento segundos (2s, 4s, 8s…)
            delay = 2 ** intentos
            print(f"Intentos restantes: {restante}. Espere {delay} segundo(s)...")
            time.sleep(delay)
        else:
            print("Intentos agotados.")

    # ── Bloqueo temporal con cuenta regresiva ────────────────
    print()
    print(centrar("⛔  ACCESO BLOQUEADO TEMPORALMENTE  ⛔"))
    registrar_evento('autenticar_garita', 'Bloqueo temporal activado tras 3 fallos')
    for restante in range(LOCKOUT_SEGUNDOS, 0, -1):
        print(f"\r  Sistema bloqueado. Intente de nuevo en {restante:2d} segundo(s)...",
              end='', flush=True)
        time.sleep(1)
    print()
    registrar_evento('autenticar_garita', 'Bloqueo temporal expirado')
    return False

# ============================================================
# SECCIÓN 12 · MENÚ PRINCIPAL
# ============================================================

def menu_principal():
    """
    Menú principal: despacha a cada función.
    La selección de opción está limitada a 3 caracteres para evitar entradas largas.
    """
    opciones_menu = {
        '1': ("Ver Movimientos",                    ver_movimientos_peaje),
        '2': ("Cobrar peaje",                        cobrar_peaje),
        '3': ("Ajustar tarifas (solo supervisor)",  ajustar_tarifas_peaje),
        '4': ("Agregar nuevo vehículo",              agregar_nuevo_vehiculo),
        '5': ("Ver vehículos registrados",           ver_vehiculos_registrados),
        '6': ("Mostrar tarifas",                     mostrar_tarifas_peaje),
        '7': ("Reporte de ingresos",                 reporte_ingresos),
        '8': ("Ver registro de eventos",             ver_registro_eventos),
        '0': ("Salir",                               None)
    }

    while True:
        limpiar_pantalla()
        banner_inicio()
        panel_usuario()
        print(centrar("MENÚ PRINCIPAL"))
        linea()
        for k, v in opciones_menu.items():
            print(f"  {k}) {v[0]}")
        linea()
        print("  Ingrese el número de opción y presione ENTER")
        # Limitar la selección del menú a 3 chars (anti-DoS)
        elec = input_seguro("Seleccione opción: ", max_len=3)

        if elec == '0':
            if confirmar("¿Desea salir del sistema? (s/n): "):
                print("Cerrando sesión...")
                espera_animacion(0.8, "Saliendo")
                registrar_evento('menu_principal', 'Cierre de sesión por el operador')
                break
            continue

        accion = opciones_menu.get(elec)
        if accion and accion[1]:
            accion[1]()
        else:
            opcion_invalida()

# ============================================================
# PUNTO DE ENTRADA
# ============================================================
if __name__ == "__main__":
    try:
        if autenticar_garita():
            menu_principal()
        else:
            print("Acceso denegado. Fin del programa.")
            registrar_evento('main', 'Acceso denegado al iniciar')
    except KeyboardInterrupt:
        # Salida limpia con Ctrl-C sin mostrar traceback
        print("\n\nSistema cerrado por el operador.")
        registrar_evento('main', 'Sistema cerrado con Ctrl-C')
