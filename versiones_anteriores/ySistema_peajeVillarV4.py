# segurov7.py
# SISTEMA DE PEAJE - GARITA (Versión Segura v7.1 Integrada)
# Incluye:
# - Nuevo rol: jefe_cabinas (usuario: jefe_cabinas, clave inicial: 777)
# - Control de acceso por roles en menú
# - Vista y reporte del día para jefe de cabinas
# - Menú con indicación de roles permitidos por opción

import os
import sys
import time
import hashlib
import secrets
import shutil
import hmac
import json
from datetime import datetime

# Optional libs
try:
    from argon2 import PasswordHasher, exceptions as argon2_exceptions
    ARGON2_AVAILABLE = True
except Exception:
    ARGON2_AVAILABLE = False

try:
    import pyotp
    PYOTP_AVAILABLE = True
except Exception:
    PYOTP_AVAILABLE = False

try:
    import redis
    REDIS_AVAILABLE = True
except Exception:
    REDIS_AVAILABLE = False

# ============================================================
# CONFIGURACIÓN DE SEGURIDAD
# ============================================================
PEPPER = os.environ.get('PEAJE_PEPPER', None)
AUDIT_HMAC_KEY = os.environ.get('PEAJE_AUDIT_KEY', None)
REDIS_URL = os.environ.get('PEAJE_REDIS_URL', None)

ARGON2_TIME_COST = int(os.environ.get('PEAJE_ARGON2_TIME', 3))
ARGON2_MEMORY_COST = int(os.environ.get('PEAJE_ARGON2_MEMORY', 65536))
ARGON2_PARALLELISM = int(os.environ.get('PEAJE_ARGON2_PAR', 4))

TOTP_ISSUER = os.environ.get('PEAJE_TOTP_ISSUER', 'PeajeGarita')

MAX_INTENTOS_LOGIN = 3
LOCKOUT_SEGUNDOS = 30

# ============================================================
# VALIDACIONES
# ============================================================
MAX_LEN_PASSWORD    = 64
MAX_LEN_PLACA       = 10
MAX_LEN_TEXTO       = 50
MAX_LEN_PROPIETARIO = 60
MAX_MONTO           = 10_000_000
MIN_MONTO           = 1

# ============================================================
# BACKENDS OPCIONALES
# ============================================================
_redis = None
if REDIS_AVAILABLE and REDIS_URL:
    try:
        _redis = redis.from_url(REDIS_URL, decode_responses=True)
    except Exception:
        _redis = None

_in_memory_attempts = {}
_in_memory_audit = []
_in_memory_totp_secrets = {}

# ============================================================
# DATOS INICIALES
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
# ROLES Y AUTORIZACIÓN
# ============================================================
ROL_SUPERVISOR = "supervisor"
ROL_CAJERO = "cajero"
ROL_JEFE_CABINAS = "jefe_cabinas"

PERMISOS_MENU = {
    '1': [ROL_SUPERVISOR, ROL_CAJERO],                 # Cobrar peaje
    '2': [ROL_SUPERVISOR, ROL_JEFE_CABINAS],           # Ver movimientos
    '3': [ROL_SUPERVISOR],                             # Ver vehículos
    '4': [ROL_SUPERVISOR],                             # Mostrar tarifas
    '5': [ROL_SUPERVISOR],                             # Ajustar tarifas
    '6': [ROL_SUPERVISOR],                             # Registrar vehículo
    '7': [ROL_SUPERVISOR, ROL_JEFE_CABINAS],           # Reporte ingresos
    '8': [ROL_SUPERVISOR],                             # Registro de eventos
    '9': [ROL_SUPERVISOR],                             # Configurar MFA
    '0': [ROL_SUPERVISOR, ROL_CAJERO, ROL_JEFE_CABINAS]
}

def tiene_permiso(opcion: str, rol: str) -> bool:
    return rol in PERMISOS_MENU.get(opcion, [])

def etiqueta_roles(opcion: str) -> str:
    roles = PERMISOS_MENU.get(opcion, [])
    mapeo = {
        ROL_SUPERVISOR: "Supervisor",
        ROL_CAJERO: "Cajero",
        ROL_JEFE_CABINAS: "Jefe de Cabinas"
    }
    return ", ".join(mapeo[r] for r in roles)

# ============================================================
# UTILIDADES CRIPTO
# ============================================================
def _get_argon2_hasher():
    if not ARGON2_AVAILABLE:
        raise RuntimeError("argon2-cffi no está instalado. Instala 'argon2-cffi'.")
    return PasswordHasher(
        time_cost=ARGON2_TIME_COST,
        memory_cost=ARGON2_MEMORY_COST,
        parallelism=ARGON2_PARALLELISM
    )

def hash_clave(clave: str, salt: str = None) -> tuple[str, str]:
    # fallback PBKDF2
    if not ARGON2_AVAILABLE:
        if salt is None:
            salt = secrets.token_hex(16)
        dk = hashlib.pbkdf2_hmac(
            'sha256',
            (clave + (PEPPER or '')).encode('utf-8'),
            salt.encode('utf-8'),
            iterations=200_000
        )
        return salt, dk.hex()

    # Argon2
    if salt is None:
        salt = secrets.token_hex(16)
    ph = _get_argon2_hasher()
    combined = clave + (PEPPER or '') + salt
    h = ph.hash(combined)
    return salt, h

def verificar_clave(clave_ingresada: str, salt: str, hash_almacenado: str) -> bool:
    # Intentar Argon2 si está disponible y el hash parece Argon2
    if ARGON2_AVAILABLE and isinstance(hash_almacenado, str) and hash_almacenado.startswith("$argon2"):
        ph = _get_argon2_hasher()
        try:
            combined = clave_ingresada + (PEPPER or '') + salt
            ok = ph.verify(hash_almacenado, combined)
            try:
                if ph.check_needs_rehash(hash_almacenado):
                    registrar_evento('verificar_clave', 'Hash necesita rehash; marcar actualización')
            except Exception:
                pass
            return bool(ok)
        except argon2_exceptions.VerifyMismatchError:
            return False
        except Exception:
            return False

    # PBKDF2 (incluye compatibilidad con hashes heredados)
    _, hash_calculado = hash_clave_pbkdf2_compat(clave_ingresada, salt)
    return secrets.compare_digest(hash_calculado, hash_almacenado)

def hash_clave_pbkdf2_compat(clave: str, salt: str = None) -> tuple[str, str]:
    """
    Generador PBKDF2 fijo para compatibilidad.
    Lo usamos para validar usuarios viejos y para escenarios donde hash guardado no es Argon2.
    """
    if salt is None:
        salt = secrets.token_hex(16)
    dk = hashlib.pbkdf2_hmac(
        'sha256',
        (clave + (PEPPER or '')).encode('utf-8'),
        salt.encode('utf-8'),
        iterations=200_000
    )
    return salt, dk.hex()

# ============================================================
# CREDENCIALES
# ============================================================
garita_usuarios = [
    {
        'nombre': 'supervisor',
        'salt':   'f5a287e73e584b4ab0f7afa6f752b8ae',
        'hash':   '8e7b659d48c0c29dbb1b79a5c3f913a6bb3801556d011f538f4aedb01ba8ea46',
        'mfa_enabled': False
    },
    {
        'nombre': 'cajero',
        'salt':   '092a05e028b0d23f5e910cfbcf94e7d6',
        'hash':   'b564ad619d70b93b341a04670740e08998cb18f184fa54e0fd9259013433b7af',
        'mfa_enabled': False
    }
]

def obtener_credenciales_operador(nombre_operador: str):
    for cred in garita_usuarios:
        if cred['nombre'] == nombre_operador:
            return cred
    return None

def asegurar_usuario_jefe_cabinas():
    """
    Crea (si no existe) el usuario jefe_cabinas con clave inicial '777'
    usando el hasher del entorno actual.
    """
    global garita_usuarios
    existe = any(u['nombre'] == ROL_JEFE_CABINAS for u in garita_usuarios)
    if not existe:
        # Para evitar incompatibilidad con usuarios heredados, lo creamos con PBKDF2 compat.
        salt, h = hash_clave_pbkdf2_compat('777')
        garita_usuarios.append({
            'nombre': ROL_JEFE_CABINAS,
            'salt': salt,
            'hash': h,
            'mfa_enabled': False
        })
        registrar_evento('init', 'Usuario jefe_cabinas creado con clave inicial')

# ============================================================
# AUDITORÍA
# ============================================================
def _compute_audit_hmac(prev_hash: str, payload: str) -> str:
    key = (AUDIT_HMAC_KEY or 'dev_audit_key').encode('utf-8')
    data = (prev_hash + payload).encode('utf-8')
    return hmac.new(key, data, hashlib.sha256).hexdigest()

def registrar_evento(funcion: str, mensaje: str):
    evento = {
        'fecha':   datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        'funcion': funcion[:50],
        'mensaje': mensaje[:200]
    }
    prev = _in_memory_audit[-1]['hmac'] if _in_memory_audit else ''
    payload = json.dumps(evento, sort_keys=True, ensure_ascii=False)
    h = _compute_audit_hmac(prev, payload)
    registro = {'evento': evento, 'hmac': h}
    _in_memory_audit.append(registro)
    registro_eventos.append(evento)
    try:
        with open('audit_append_only.log', 'a', encoding='utf-8') as f:
            f.write(json.dumps(registro, ensure_ascii=False) + '\n')
    except Exception:
        pass

def ver_registro_eventos():
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
# RATE LIMITING
# ============================================================
def _get_attempts_key(user: str) -> str:
    return f"attempts:{user}"

def _get_now_ts() -> int:
    return int(time.time())

def registrar_intento_fallido(user: str):
    if _redis:
        key = _get_attempts_key(user)
        _redis.hincrby(key, 'count', 1)
        _redis.hsetnx(key, 'first_ts', _get_now_ts())
        _redis.expire(key, 3600)
    else:
        rec = _in_memory_attempts.get(user, {'count': 0, 'first_ts': _get_now_ts()})
        rec['count'] += 1
        _in_memory_attempts[user] = rec

def obtener_intentos(user: str) -> int:
    if _redis:
        key = _get_attempts_key(user)
        try:
            return int(_redis.hget(key, 'count') or 0)
        except Exception:
            return 0
    return _in_memory_attempts.get(user, {}).get('count', 0)

def resetear_intentos(user: str):
    if _redis:
        _redis.delete(_get_attempts_key(user))
    else:
        _in_memory_attempts.pop(user, None)

def esta_bloqueado(user: str):
    attempts = obtener_intentos(user)
    if attempts < MAX_INTENTOS_LOGIN:
        return False, 0
    if _redis:
        first_ts = int(_redis.hget(_get_attempts_key(user), 'first_ts') or 0)
    else:
        first_ts = _in_memory_attempts.get(user, {}).get('first_ts', _get_now_ts())
    elapsed = _get_now_ts() - first_ts
    if elapsed < LOCKOUT_SEGUNDOS:
        return True, LOCKOUT_SEGUNDOS - elapsed
    resetear_intentos(user)
    return False, 0

# ============================================================
# MFA
# ============================================================
def generar_totp_secret(usuario: str) -> str:
    if not PYOTP_AVAILABLE:
        raise RuntimeError("pyotp no instalado. Instala 'pyotp' para MFA.")
    secret = pyotp.random_base32()
    _in_memory_totp_secrets[usuario] = secret
    registrar_evento('generar_totp_secret', f'Secret TOTP generado para {usuario}')
    return secret

def verificar_totp(usuario: str, code: str) -> bool:
    if not PYOTP_AVAILABLE:
        return False
    secret = _in_memory_totp_secrets.get(usuario)
    if not secret:
        return False
    totp = pyotp.TOTP(secret)
    try:
        return totp.verify(code, valid_window=1)
    except Exception:
        return False

# ============================================================
# ENTRADAS SEGURAS
# ============================================================
def _leer_chars_unix(prompt: str, max_len: int, ocultar: bool) -> str:
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
                print()
                break
            elif ch in ('\x7f', '\x08'):
                if chars:
                    chars.pop()
                    print('\b \b', end='', flush=True)
            elif ch == '\x03':
                raise KeyboardInterrupt
            elif ch < '\x20':
                pass
            elif len(chars) < max_len:
                chars.append(ch)
                print('*' if ocultar else ch, end='', flush=True)
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
    return ''.join(chars)

def _leer_chars_windows(prompt: str, max_len: int, ocultar: bool) -> str:
    import msvcrt
    print(prompt, end='', flush=True)
    chars = []
    while True:
        ch = msvcrt.getwch()
        if ch in ('\r', '\n'):
            print()
            break
        elif ch == '\x08':
            if chars:
                chars.pop()
                print('\b \b', end='', flush=True)
        elif ch == '\x03':
            raise KeyboardInterrupt
        elif ord(ch) < 0x20:
            pass
        elif len(chars) < max_len:
            chars.append(ch)
            print('*' if ocultar else ch, end='', flush=True)
    return ''.join(chars)

def getpass_limitado(prompt: str = "Contraseña: ", max_len: int = MAX_LEN_PASSWORD) -> str:
    try:
        if os.name == 'nt':
            return _leer_chars_windows(prompt, max_len, ocultar=True)
        return _leer_chars_unix(prompt, max_len, ocultar=True)
    except Exception:
        import getpass as _gp
        return _gp.getpass(prompt)[:max_len]

def input_seguro(prompt: str, max_len: int = MAX_LEN_TEXTO) -> str:
    try:
        if os.name == 'nt':
            raw = _leer_chars_windows(prompt, max_len, ocultar=False)
        else:
            raw = _leer_chars_unix(prompt, max_len, ocultar=False)
    except Exception:
        raw = input(prompt)[:max_len]
    return ''.join(c for c in raw if c >= ' ').strip()

def sanitizar_placa(placa: str) -> str:
    placa = placa.upper().strip()
    placa = ''.join(c for c in placa if c.isalnum())
    return placa[:MAX_LEN_PLACA]

def validar_monto(valor_str: str):
    try:
        monto = int(valor_str)
    except (ValueError, OverflowError):
        return None
    if monto < MIN_MONTO or monto > MAX_MONTO:
        return None
    return monto

# ============================================================
# UI
# ============================================================
def ancho_terminal(default=80):
    try:
        return shutil.get_terminal_size().columns
    except Exception:
        return default

def limpiar_pantalla():
    os.system('cls' if os.name == 'nt' else 'clear')

def centrar(texto, ancho=None):
    ancho = ancho or ancho_terminal()
    return texto.center(ancho)

def linea(char='─'):
    print(char * ancho_terminal())

def espera_animacion(segundos=0.8, mensaje="Cargando"):
    pasos = 6
    for i in range(pasos):
        dots = '.' * ((i % 3) + 1)
        print(f"\r{mensaje}{dots} ", end='', flush=True)
        time.sleep(segundos / pasos)
    print("\r" + " " * (len(mensaje) + 4), end='\r')

def barra_progreso(total=20, duracion=0.6, mensaje="Procesando"):
    for i in range(total + 1):
        por = int((i / total) * 100)
        barra = '█' * i + '-' * (total - i)
        print(f"\r{mensaje} |{barra}| {por:3d}%", end='', flush=True)
        time.sleep(duracion / total)
    print()

def confirmar(texto="¿Confirmar? (s/n): ") -> bool:
    while True:
        r = input_seguro(texto, max_len=3).lower()
        if r in ('s', 'n'):
            return r == 's'
        print("Ingrese 's' para sí o 'n' para no.")

def beep():
    print('\a', end='')

# ============================================================
# OPERACIONES
# ============================================================
def buscar_vehiculo_por_placa(placa: str):
    placa = sanitizar_placa(placa)
    if not placa:
        return None
    for v in vehiculos_registrados:
        if sanitizar_placa(v['placa']) == placa:
            return v
    return None

def calcular_vuelto(monto_pagado: int, tarifa: int) -> int:
    return monto_pagado - tarifa

def _es_movimiento_de_hoy(fecha_str: str) -> bool:
    try:
        f = datetime.strptime(fecha_str, "%Y-%m-%d %H:%M:%S")
        return f.date() == datetime.now().date()
    except Exception:
        return False

def ver_movimientos_peaje():
    banner_inicio()
    panel_usuario()
    print(centrar("HISTORIAL DE MOVIMIENTOS"))
    linea()

    if operador_actual == ROL_JEFE_CABINAS:
        movimientos = [m for m in movimientos_peaje if _es_movimiento_de_hoy(m['fecha'])]
        print(centrar("MOVIMIENTOS DEL DÍA (JEFE DE CABINAS)"))
    else:
        movimientos = movimientos_peaje
        print(centrar("MOVIMIENTOS TOTALES"))
    linea()

    if not movimientos:
        print(centrar("Sin movimientos"))
        registrar_evento('ver_movimientos_peaje', f'Sin movimientos para rol {operador_actual}')
        time.sleep(2.0)
        return

    total = 0
    for i, m in enumerate(movimientos, start=1):
        print(f"[{i}] {m['fecha']}  Placa: {m['placa']}  Tipo: {m['tipo']}")
        print(f"     Tarifa: {m['tarifa']}  Pagado: {m['pagado']}  Vuelto: {m['vuelto']}")
        total += m['tarifa']
        linea()
    print(f"Total recaudado en esta vista: {total:,} pesos")
    input("Presione ENTER para volver al menú")

def cobrar_peaje():
    banner_inicio()
    panel_usuario()
    print(centrar("COBRO DE PEAJE"))
    linea()

    placa_raw = input_seguro("Ingrese placa del vehículo o ENTER para no registrado: ", max_len=MAX_LEN_PLACA)
    placa = sanitizar_placa(placa_raw)

    if placa:
        v = buscar_vehiculo_por_placa(placa)
        if v:
            print(f"Vehículo encontrado: {v['placa']}  Tipo: {v['tipo']}  Propietario: {v.get('propietario', '-')}")
            tipo = v['tipo']
        else:
            print("Vehículo no registrado.")
            if confirmar("¿Registrar ahora? (s/n): "):
                tipo = agregar_nuevo_vehiculo(placa_propuesta=placa)
                if not tipo:
                    print("Registro cancelado")
                    espera_animacion(0.6, "Volviendo")
                    registrar_evento('cobrar_peaje', 'Registro cancelado por el operador')
                    return
            else:
                tipo = input_seguro("Ingrese tipo de vehículo (vehiculo/moto/camion): ", max_len=10).lower()
    else:
        tipo = input_seguro("Ingrese tipo de vehículo (vehiculo/moto/camion): ", max_len=10).lower()
        placa_raw = input_seguro("Ingrese placa (o 'N/A'): ", max_len=MAX_LEN_PLACA)
        placa = sanitizar_placa(placa_raw) or 'NA'
        if placa != 'NA':
            v_existente = buscar_vehiculo_por_placa(placa)
            if v_existente:
                print(f"La placa {placa} ya está registrada. Usando registro existente.")
                tipo = v_existente['tipo']

    if tipo not in tarifas_peaje:
        print("Tipo de vehículo inválido.")
        espera_animacion(0.6, "Cancelando")
        registrar_evento('cobrar_peaje', 'Tipo de vehículo inválido')
        return

    tarifa = tarifas_peaje[tipo]
    print(f"Tarifa para {tipo}: {tarifa} pesos")

    pagado = None
    while pagado is None:
        raw = input_seguro("Ingrese monto entregado por el conductor: ", max_len=10)
        pagado = validar_monto(raw)
        if pagado is None:
            print(f"Ingrese entero válido entre {MIN_MONTO:,} y {MAX_MONTO:,}.")

    if pagado < tarifa:
        print("Monto insuficiente. Cobro no realizado.")
        espera_animacion(0.6, "Volviendo")
        registrar_evento('cobrar_peaje', f'Cobro fallido para {placa}: insuficiente')
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
    banner_inicio()
    panel_usuario()
    print(centrar("AJUSTE DE TARIFAS"))
    linea()

    if operador_actual != ROL_SUPERVISOR:
        print(centrar("Acceso denegado. Solo supervisor."))
        espera_animacion(0.8, "Volviendo")
        registrar_evento('ajustar_tarifas_peaje', 'Acceso denegado')
        return

    bloqueado, secs = esta_bloqueado('supervisor')
    if bloqueado:
        print(f"Cuenta bloqueada temporalmente. Intente en {secs} segundos.")
        registrar_evento('ajustar_tarifas_peaje', 'Intento durante bloqueo')
        espera_animacion(0.8, "Volviendo")
        return

    clave_confirm = getpass_limitado("Contraseña del supervisor: ", max_len=MAX_LEN_PASSWORD)
    cred = obtener_credenciales_operador('supervisor')
    if cred is None or not verificar_clave(clave_confirm, cred['salt'], cred['hash']):
        registrar_intento_fallido('supervisor')
        print("Contraseña incorrecta.")
        espera_animacion(0.8, "Cancelando")
        registrar_evento('ajustar_tarifas_peaje', 'Verificación fallida')
        return

    if cred.get('mfa_enabled'):
        if not PYOTP_AVAILABLE:
            print("MFA configurado pero pyotp no disponible.")
            registrar_evento('ajustar_tarifas_peaje', 'MFA no disponible')
            return
        code = input_seguro("Ingrese código MFA (TOTP): ", max_len=8)
        if not verificar_totp('supervisor', code):
            registrar_intento_fallido('supervisor')
            print("Código MFA inválido.")
            registrar_evento('ajustar_tarifas_peaje', 'MFA inválido')
            return

    resetear_intentos('supervisor')

    print("Tarifas actuales:")
    for k, v in tarifas_peaje.items():
        print(f"  - {k}: {v} pesos")

    tipo = input_seguro("Tipo a ajustar (vehiculo/moto/camion): ", max_len=10).lower()
    if tipo not in tarifas_peaje:
        print("Tipo inválido.")
        espera_animacion(0.6, "Cancelando")
        registrar_evento('ajustar_tarifas_peaje', 'Tipo inválido')
        return

    nueva = None
    while nueva is None:
        raw = input_seguro(f"Ingrese nueva tarifa para {tipo}: ", max_len=10)
        nueva = validar_monto(raw)
        if nueva is None:
            print(f"Ingrese entero válido entre {MIN_MONTO:,} y {MAX_MONTO:,}.")

    if confirmar(f"Confirmar cambio de {tipo} a {nueva} pesos (s/n): "):
        tarifas_peaje[tipo] = nueva
        barra_progreso(16, 0.6, "Aplicando cambio")
        print("Tarifa actualizada correctamente.")
        registrar_evento('ajustar_tarifas_peaje', f'Tarifa {tipo} → {nueva}')
    else:
        print("Operación cancelada.")
        registrar_evento('ajustar_tarifas_peaje', 'Cambio cancelado')
    input("ENTER para volver al menú")

def agregar_nuevo_vehiculo(placa_propuesta: str = None):
    banner_inicio()
    panel_usuario()
    print(centrar("REGISTRO DE VEHÍCULO"))
    linea()

    while True:
        if placa_propuesta:
            placa = sanitizar_placa(placa_propuesta)
            placa_propuesta = None
        else:
            placa = sanitizar_placa(input_seguro("Ingrese placa: ", max_len=MAX_LEN_PLACA))

        if not placa:
            print("Placa inválida.")
            if not confirmar("¿Desea intentar nuevamente? (s/n): "):
                registrar_evento('agregar_nuevo_vehiculo', 'Cancelado: placa inválida')
                return None
            continue

        if buscar_vehiculo_por_placa(placa):
            print(f"La placa {placa} ya está registrada.")
            if confirmar("¿Desea ingresar otra placa? (s/n): "):
                continue
            registrar_evento('agregar_nuevo_vehiculo', f'Cancelado: {placa} ya existe')
            return None

        tipo = input_seguro("Ingrese tipo (vehiculo/moto/camion): ", max_len=10).lower()
        if tipo not in tarifas_peaje:
            print("Tipo inválido.")
            if confirmar("¿Desea intentar nuevamente? (s/n): "):
                continue
            registrar_evento('agregar_nuevo_vehiculo', f'Cancelado: tipo inválido ({tipo})')
            return None

        propietario = input_seguro("Ingrese propietario (opcional): ", max_len=MAX_LEN_PROPIETARIO) or '-'

        vehiculos_registrados.append({
            'placa': placa,
            'tipo': tipo,
            'propietario': propietario
        })
        barra_progreso(12, 0.5, "Registrando vehículo")
        print(f"Vehículo {placa} registrado como {tipo}.")
        registrar_evento('agregar_nuevo_vehiculo', f'Vehículo {placa} registrado como {tipo}')
        return tipo

def ver_vehiculos_registrados():
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
    banner_inicio()
    panel_usuario()
    print(centrar("TARIFAS VIGENTES"))
    linea()
    if not tarifas_peaje:
        print(centrar("No hay tarifas definidas."))
        registrar_evento('mostrar_tarifas_peaje', 'No hay tarifas')
        espera_animacion(0.6, "Volviendo")
        return
    for k, v in tarifas_peaje.items():
        print(f"  - {k.capitalize():10} : {v} pesos")
    linea()
    input("ENTER para volver al menú")

def reporte_ingresos():
    banner_inicio()
    panel_usuario()
    print(centrar("REPORTE DE INGRESOS"))
    linea()
    if not movimientos_peaje:
        print(centrar("No hay movimientos para generar reporte."))
        registrar_evento('reporte_ingresos', 'Sin movimientos')
        espera_animacion(0.6, "Volviendo")
        return

    if operador_actual == ROL_JEFE_CABINAS:
        movimientos = [m for m in movimientos_peaje if _es_movimiento_de_hoy(m['fecha'])]
        print(centrar("REPORTE DEL DÍA - JEFE DE CABINAS"))
        linea()
    else:
        movimientos = movimientos_peaje

    totales = {k: 0 for k in tarifas_peaje}
    conteo = {k: 0 for k in tarifas_peaje}
    total_general = 0

    for m in movimientos:
        t = m['tipo']
        if t in totales:
            totales[t] += m['tarifa']
            conteo[t] += 1
            total_general += m['tarifa']

    for k in totales:
        print(f"  {k.capitalize():10}  Recaudado: {totales[k]:10,}  Pasos: {conteo[k]:4}")
    linea()
    print(f"  Total general recaudado: {total_general:,} pesos")
    registrar_evento('reporte_ingresos', f'Rol={operador_actual} Total={total_general}')
    input("ENTER para volver al menú")

def opcion_invalida():
    print("Opción inválida.")
    time.sleep(0.8)
    registrar_evento('menu_principal', 'Opción inválida')

# ============================================================
# BANNER
# ============================================================
def banner_inicio():
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
    ancho = ancho_terminal()
    print(centrar(nombre_panel_por_rol(operador_actual), ancho))
    linea()
    print(centrar(f"Operador: {operador_actual}", ancho))
    print(centrar(f"Hora: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", ancho))
    linea()

def nombre_panel_por_rol(rol: str) -> str:
    if rol == ROL_SUPERVISOR:
        return "PANEL SUPERVISOR - CONTROL TOTAL"
    if rol == ROL_CAJERO:
        return "PANEL CAJERO - OPERACIONES DE COBRO"
    if rol == ROL_JEFE_CABINAS:
        return "PANEL JEFE DE CABINAS - RECUENTO DIARIO"
    return "PANEL OPERADOR"

# ============================================================
# AUTENTICACIÓN
# ============================================================
def autenticar_garita() -> bool:
    global operador_actual
    banner_inicio()
    print(centrar("LOGIN - GARITA"))
    linea()

    nombre = input_seguro("Nombre de operador: ", max_len=30).strip()
    if not nombre:
        print("Nombre inválido.")
        registrar_evento('autenticar_garita', 'Nombre vacío')
        return False

    bloqueado, secs = esta_bloqueado(nombre)
    if bloqueado:
        print(f"Cuenta bloqueada temporalmente. Intente en {secs} segundos.")
        registrar_evento('autenticar_garita', f'Login bloqueado para {nombre}')
        return False

    clave = getpass_limitado("Contraseña: ", max_len=MAX_LEN_PASSWORD)
    cred = obtener_credenciales_operador(nombre)
    if cred is None or not verificar_clave(clave, cred['salt'], cred['hash']):
        registrar_intento_fallido(nombre)
        delay = min(2 ** obtener_intentos(nombre), 8)
        print("Credenciales incorrectas.")
        time.sleep(delay)
        registrar_evento('autenticar_garita', f'Login fallido para {nombre}')
        return False

    if cred.get('mfa_enabled'):
        if not PYOTP_AVAILABLE:
            print("MFA configurado pero no disponible.")
            registrar_evento('autenticar_garita', 'MFA no disponible')
            return False
        code = input_seguro("Código MFA (TOTP): ", max_len=8)
        if not verificar_totp(nombre, code):
            registrar_intento_fallido(nombre)
            print("Código MFA inválido.")
            registrar_evento('autenticar_garita', f'MFA inválido para {nombre}')
            return False

    resetear_intentos(nombre)
    operador_actual = nombre
    registrar_evento('autenticar_garita', f'Login exitoso para {nombre}')
    return True

# ============================================================
# MFA INTERACTIVO
# ============================================================
def configurar_mfa_interactivo():
    global garita_usuarios
    banner_inicio()
    panel_usuario()
    print(centrar("CONFIGURAR MFA (TOTP)"))
    linea()

    nombre = input_seguro("Operador a configurar MFA: ", max_len=30)
    cred = obtener_credenciales_operador(nombre)
    if not cred:
        print("Operador no encontrado.")
        registrar_evento('configurar_mfa', f'Operador {nombre} no encontrado')
        return
    if not PYOTP_AVAILABLE:
        print("pyotp no instalado. Instale pyotp para habilitar MFA.")
        registrar_evento('configurar_mfa', 'pyotp no disponible')
        return

    secret = generar_totp_secret(nombre)
    uri = pyotp.totp.TOTP(secret).provisioning_uri(name=nombre, issuer_name=TOTP_ISSUER)
    print("Se generó un secreto TOTP. Guarde este secreto en su app de autenticación.")
    print(f"Secret: {secret}")
    print(f"URI (para QR): {uri}")

    if confirmar("¿Habilitar MFA para este usuario ahora? (s/n): "):
        garita_usuarios = [{**u, 'mfa_enabled': True} if u['nombre'] == nombre else u for u in garita_usuarios]
        registrar_evento('configurar_mfa', f'MFA habilitado para {nombre}')
        print("MFA habilitado.")
    else:
        registrar_evento('configurar_mfa', f'MFA generado pero no habilitado para {nombre}')
        print("MFA no habilitado.")

# ============================================================
# MENÚ PRINCIPAL
# ============================================================
def menu_principal():
    while True:
        banner_inicio()
        panel_usuario()
        print(f"1) Cobrar peaje ({etiqueta_roles('1')})")
        print(f"2) Ver movimientos ({etiqueta_roles('2')})")
        print(f"3) Ver vehículos registrados ({etiqueta_roles('3')})")
        print(f"4) Mostrar tarifas ({etiqueta_roles('4')})")
        print(f"5) Ajustar tarifas ({etiqueta_roles('5')})")
        print(f"6) Registrar vehículo ({etiqueta_roles('6')})")
        print(f"7) Reporte de ingresos ({etiqueta_roles('7')})")
        print(f"8) Ver registro de eventos ({etiqueta_roles('8')})")
        print(f"9) Generar/Configurar MFA ({etiqueta_roles('9')})")
        print(f"0) Salir ({etiqueta_roles('0')})")

        opcion = input_seguro("Seleccione opción: ", max_len=2)

        if opcion not in PERMISOS_MENU:
            opcion_invalida()
            continue

        if not tiene_permiso(opcion, operador_actual):
            print("Acceso denegado para su rol.")
            registrar_evento('menu_principal', f'Acceso denegado rol={operador_actual} opcion={opcion}')
            time.sleep(1.0)
            continue

        if opcion == '1':
            cobrar_peaje()
        elif opcion == '2':
            ver_movimientos_peaje()
        elif opcion == '3':
            ver_vehiculos_registrados()
        elif opcion == '4':
            mostrar_tarifas_peaje()
        elif opcion == '5':
            ajustar_tarifas_peaje()
        elif opcion == '6':
            agregar_nuevo_vehiculo()
        elif opcion == '7':
            reporte_ingresos()
        elif opcion == '8':
            ver_registro_eventos()
        elif opcion == '9':
            configurar_mfa_interactivo()
        elif opcion == '0':
            print("Saliendo...")
            break

# ============================================================
# ARRANQUE
# ============================================================
if __name__ == '__main__':
    if not PEPPER:
        print("ADVERTENCIA: No se ha configurado PEPPER (PEAJE_PEPPER).")
    if not AUDIT_HMAC_KEY:
        print("ADVERTENCIA: No se ha configurado AUDIT_HMAC_KEY.")
    if not ARGON2_AVAILABLE:
        print("ADVERTENCIA: argon2-cffi no disponible. Se usará PBKDF2.")
    if not PYOTP_AVAILABLE:
        print("ADVERTENCIA: pyotp no disponible. MFA deshabilitado.")
    if REDIS_URL and not _redis:
        print("ADVERTENCIA: No se pudo conectar a Redis. Se usará memoria.")

    # Crear usuario jefe_cabinas si no existe
    asegurar_usuario_jefe_cabinas()

    # Loop de login
    while True:
        if autenticar_garita():
            menu_principal()
            break
        else:
            if not confirmar("¿Intentar login nuevamente? (s/n): "):
                break