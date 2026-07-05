
# SISTEMA DE PEAJE - GARITA 
# Incluye:
# - Control de acceso por roles en menú
# - Vista y reporte del día para jefe de cabinas
# - Menú con indicación de roles permitidos por opción
# - Autenticación con MFA (TOTP) y opción para configurar MFA (QR)
# - Persistencia por usuario en ficheros cifrados, backup codes, replay protection y rate limiting

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

# QR code lib (optional)
try:
    import qrcode
    QRCODE_AVAILABLE = True
except Exception:
    QRCODE_AVAILABLE = False

# Optional: cryptography for encrypting TOTP secrets at rest
try:
    from cryptography.fernet import Fernet, InvalidToken
    CRYPTO_AVAILABLE = True
except Exception:
    CRYPTO_AVAILABLE = False

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
# Nota: ya no usamos _in_memory_totp_secrets para persistencia; queda para compatibilidad si hace falta.
_in_memory_totp_secrets = {}

# ============================================================
# MFA por usuario: configuración de almacenamiento en ficheros cifrados
# ============================================================
# Directorio donde se guardan los ficheros por usuario
MFA_USER_DIR = os.environ.get('PEAJE_MFA_USER_DIR', 'mfa_users')
os.makedirs(MFA_USER_DIR, exist_ok=True)

# Parámetros TOTP rate-limit
_in_memory_totp_attempts = {}  # {user: {'count': int, 'first_ts': int}}
TOTP_MAX_INTENTOS = int(os.environ.get('PEAJE_TOTP_MAX_INTENTOS', 5))
TOTP_LOCKOUT_SEGUNDOS = int(os.environ.get('PEAJE_TOTP_LOCKOUT', 60))

FERNET_KEY_FILE = os.environ.get(
    'PEAJE_FERNET_KEY_FILE',
    os.path.join(os.path.expanduser('~'), '.peaje_garita', 'fernet.key')
)

# Helpers para Fernet con clave local persistida
def _derive_fernet():
    if not CRYPTO_AVAILABLE:
        raise RuntimeError("cryptography no está instalado. No se pueden cifrar secretos MFA en disco.")

    if os.path.exists(FERNET_KEY_FILE):
        with open(FERNET_KEY_FILE, 'rb') as f:
            key = f.read().strip()
        return Fernet(key)

    os.makedirs(os.path.dirname(FERNET_KEY_FILE), exist_ok=True)
    key = Fernet.generate_key()
    tmp = FERNET_KEY_FILE + '.tmp'
    with open(tmp, 'wb') as f:
        f.write(key)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, FERNET_KEY_FILE)
    try:
        import stat
        os.chmod(FERNET_KEY_FILE, stat.S_IRUSR | stat.S_IWUSR)
    except Exception:
        pass
    return Fernet(key)

# File locking helpers (Unix/Windows)
def _acquire_file_lock(f):
    try:
        if os.name == 'nt':
            import msvcrt
            msvcrt.locking(f.fileno(), msvcrt.LK_LOCK, 1)
        else:
            import fcntl
            fcntl.flock(f.fileno(), fcntl.LOCK_EX)
    except Exception:
        pass

def _release_file_lock(f):
    try:
        if os.name == 'nt':
            import msvcrt
            try:
                f.seek(0)
                msvcrt.locking(f.fileno(), msvcrt.LK_UNLCK, 1)
            except Exception:
                pass
        else:
            import fcntl
            fcntl.flock(f.fileno(), fcntl.LOCK_UN)
    except Exception:
        pass

def _user_file_path(usuario: str) -> str:
    safe = ''.join(c for c in usuario if c.isalnum() or c in ('-', '_')).lower()
    return os.path.join(MFA_USER_DIR, f"{safe}.enc")

def _atomic_write(path: str, data: bytes):
    import stat
    tmp = path + '.tmp'
    with open(tmp, 'wb') as f:
        f.write(data)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)
    try:
        os.chmod(path, stat.S_IRUSR | stat.S_IWUSR)
    except Exception:
        pass

def _load_user_entry(usuario: str) -> dict:
    path = _user_file_path(usuario)
    if not os.path.exists(path):
        return {}
    f = open(path, 'rb')
    try:
        _acquire_file_lock(f)
        raw = f.read()
    finally:
        _release_file_lock(f)
        f.close()

    try:
        fernet = _derive_fernet()
        raw = fernet.decrypt(raw)
    except InvalidToken:
        return {}
    except Exception:
        return {}
    try:
        return json.loads(raw.decode('utf-8'))
    except Exception:
        return {}

def _save_user_entry(usuario: str, entry: dict) -> bool:
    path = _user_file_path(usuario)
    raw = json.dumps(entry, ensure_ascii=False).encode('utf-8')
    try:
        fernet = _derive_fernet()
        raw = fernet.encrypt(raw)
    except Exception:
        return False
    try:
        _atomic_write(path, raw)
        return True
    except Exception:
        return False

def _delete_user_entry(usuario: str) -> bool:
    path = _user_file_path(usuario)
    try:
        if os.path.exists(path):
            os.remove(path)
        return True
    except Exception:
        return False

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
    if not ARGON2_AVAILABLE:
        raise RuntimeError("argon2-cffi no está instalado. No se pueden crear nuevos hashes de contraseñas de forma segura.")

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
# RATE LIMITING (login)
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
# MFA HELPERS: backup codes, hashing
# ============================================================
def _hash_backup_code(code: str) -> str:
    return hashlib.sha256(code.encode('utf-8')).hexdigest()

def generar_backup_codes(n=8):
    codes = []
    for _ in range(n):
        c = secrets.token_urlsafe(8)
        codes.append(c)
    return codes

# ============================================================
# MFA (TOTP) - generación persistente por usuario y verificación robusta
# ============================================================
def generar_totp_secret(usuario: str) -> tuple[str, str, list]:
    """
    Genera y persiste un secreto TOTP para usuario en su fichero.
    Retorna (secret, provisioning_uri, backup_codes_list)
    """
    if not PYOTP_AVAILABLE:
        raise RuntimeError("pyotp no instalado. Instala 'pyotp' para MFA.")
    secret = pyotp.random_base32()
    backup_codes = generar_backup_codes(8)
    backup_hashes = [_hash_backup_code(c) for c in backup_codes]

    entry = {
        'secret': secret,
        'last_used': None,
        'backup_hashes': backup_hashes,
        'mfa_enabled': False,
        'updated_at': datetime.now().isoformat()
    }
    ok = _save_user_entry(usuario, entry)
    if not ok:
        registrar_evento('generar_totp_secret', f'Fallo al persistir secreto para {usuario}')
        raise RuntimeError("No se pudo persistir secreto MFA.")
    registrar_evento('generar_totp_secret', f'Secret TOTP generado (fichero) para {usuario}')
    uri = pyotp.totp.TOTP(secret).provisioning_uri(name=usuario, issuer_name=TOTP_ISSUER)
    return secret, uri, backup_codes

def mostrar_qr_mfa(usuario: str, uri: str):
    if not QRCODE_AVAILABLE:
        print("La librería 'qrcode' no está disponible.")
        print("Copia manualmente la URI siguiente en tu app MFA o usa la opción de escaneo por URI:")
        print(uri)
        return

    try:
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=2,
            border=2,
        )
        qr.add_data(uri)
        qr.make(fit=True)

        print("Escanea este QR con Google Authenticator o Authy:")
        try:
            qr.print_ascii(invert=True)
        except Exception:
            print("No se pudo imprimir el QR en consola. Usa la URI siguiente:")
            print(uri)
    except Exception:
        print("No se pudo generar el QR. Copia manualmente la URI siguiente en tu app MFA:")
        print(uri)

def verificar_totp(usuario: str, code: str) -> bool:
    """
    Verifica código TOTP o backup code usando fichero por usuario.
    Implementa replay protection y rate limiting en memoria.
    """
    if not PYOTP_AVAILABLE:
        return False

    # Rate-limit en memoria
    rec = _in_memory_totp_attempts.get(usuario, {'count': 0, 'first_ts': _get_now_ts()})
    if _get_now_ts() - rec['first_ts'] > TOTP_LOCKOUT_SEGUNDOS:
        rec = {'count': 0, 'first_ts': _get_now_ts()}
    if rec['count'] >= TOTP_MAX_INTENTOS:
        return False

    entry = _load_user_entry(usuario)
    secret = entry.get('secret')
    if not secret:
        return False

    code_clean = code.strip()
    if not code_clean:
        return False

    # Backup codes (heurística: más largos)
    if not code_clean.isdigit() and len(code_clean) > 8:
        h = _hash_backup_code(code_clean)
        if h in entry.get('backup_hashes', []):
            entry['backup_hashes'].remove(h)
            entry['updated_at'] = datetime.now().isoformat()
            _save_user_entry(usuario, entry)
            _in_memory_totp_attempts.pop(usuario, None)
            registrar_evento('verificar_totp', f'Backup code usado para {usuario}')
            return True

    if not code_clean.isdigit() or len(code_clean) != 6:
        rec['count'] += 1
        _in_memory_totp_attempts[usuario] = rec
        return False

    totp = pyotp.TOTP(secret)
    try:
        ok = totp.verify(code_clean, valid_window=1)
        if not ok:
            rec['count'] += 1
            _in_memory_totp_attempts[usuario] = rec
            return False

        period = int(time.time() // 30)
        last_used = entry.get('last_used')
        if last_used is not None and int(last_used) >= period:
            # OTP ya usado (replay)
            return False

        entry['last_used'] = period
        entry['updated_at'] = datetime.now().isoformat()
        _save_user_entry(usuario, entry)
        _in_memory_totp_attempts.pop(usuario, None)
        registrar_evento('verificar_totp', f'TOTP verificado para {usuario}')
        return True
    except Exception:
        rec['count'] += 1
        _in_memory_totp_attempts[usuario] = rec
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
        valor = valor_str.strip().replace(',', '')
        if not valor.isdigit():
            return None
        monto = int(valor)
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
# OPERACIONES (sin cambios funcionales)
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
# CONFIGURAR MFA (UI)
# ============================================================
def configurar_mfa(usuario: str):
    banner_inicio()
    panel_usuario()
    print(centrar("CONFIGURAR MFA (TOTP)"))
    linea()

    cred = obtener_credenciales_operador(usuario)
    if cred is None:
        print("Usuario no encontrado.")
        registrar_evento('configurar_mfa', f'Usuario {usuario} no existe')
        return

    if not PYOTP_AVAILABLE:
        print("pyotp no disponible. Instala 'pyotp' para MFA.")
        registrar_evento('configurar_mfa', 'pyotp no disponible')
        return

    entry = _load_user_entry(usuario)
    reutilizando_pendiente = bool(entry.get('secret')) and not entry.get('mfa_enabled')

    # Reutilizar el secreto pendiente si ya existe, para no volver a generar QR ni backup codes.
    if reutilizando_pendiente:
        secret = entry['secret']
        uri = pyotp.totp.TOTP(secret).provisioning_uri(name=usuario, issuer_name=TOTP_ISSUER)
        backup_codes = []
        print("Hay una configuración MFA pendiente. Se reutiliza el mismo QR y secreto.")
    else:
        # Generar secreto persistido y backup codes
        secret, uri, backup_codes = generar_totp_secret(usuario)

    # Mostrar QR o URI
    if QRCODE_AVAILABLE:
        try:
            mostrar_qr_mfa(usuario, uri)
            print("Escanéalo con Google Authenticator o Authy.")
        except Exception:
            print("No se pudo generar el archivo QR. Copia manualmente la URI siguiente en tu app MFA:")
            print(uri)
    else:
        print("La librería 'qrcode' no está disponible.")
        print("Copia manualmente la URI siguiente en tu app MFA o usa la opción de escaneo por URI:")
        print(uri)

    if backup_codes:
        print("IMPORTANTE: Anota estos códigos de recuperación en un lugar seguro. Se mostrarán solo ahora.")
        for c in backup_codes:
            print("  -", c)
    else:
        print("IMPORTANTE: Ya existe una configuración MFA pendiente; no se regeneran códigos de recuperación.")
    print()
    print("Luego ingresa el código de 6 dígitos para verificar y activar MFA.")
    code = input_seguro("Ingrese código MFA: ", max_len=8)
    if verificar_totp(usuario, code):
        # activar MFA en credenciales y persistir
        cred['mfa_enabled'] = True
        # también marcar en fichero
        entry = _load_user_entry(usuario)
        entry['mfa_enabled'] = True
        entry['updated_at'] = datetime.now().isoformat()
        _save_user_entry(usuario, entry)
        print("✅ MFA habilitado correctamente.")
        registrar_evento('configurar_mfa', f'MFA habilitado para {usuario}')
    else:
        # conservar el secreto pendiente para reintentar sin regenerar QR.
        entry = _load_user_entry(usuario)
        if entry:
            entry['mfa_enabled'] = False
            entry['updated_at'] = datetime.now().isoformat()
            _save_user_entry(usuario, entry)
        print("❌ Código inválido. MFA no habilitado.")
        registrar_evento('configurar_mfa', f'MFA fallido para {usuario}')

def _autorizar_supervisor_para_override(motivo: str) -> bool:
    print("Se requiere autorización de supervisor para continuar.")
    print(f"Motivo: {motivo}")
    usuario_sup = input_seguro("Supervisor usuario: ", max_len=30)
    if usuario_sup != ROL_SUPERVISOR:
        print("Supervisor inválido.")
        registrar_evento('override_supervisor', f'Usuario de override inválido: {usuario_sup}')
        return False

    cred_sup = obtener_credenciales_operador(ROL_SUPERVISOR)
    if cred_sup is None:
        print("Supervisor no encontrado.")
        registrar_evento('override_supervisor', 'Supervisor no encontrado')
        return False

    if esta_bloqueado(ROL_SUPERVISOR)[0]:
        print("Cuenta de supervisor bloqueada temporalmente.")
        registrar_evento('override_supervisor', 'Supervisor bloqueado')
        return False

    clave_sup = getpass_limitado("Contraseña supervisor: ", max_len=MAX_LEN_PASSWORD)
    if not verificar_clave(clave_sup, cred_sup['salt'], cred_sup['hash']):
        registrar_intento_fallido(ROL_SUPERVISOR)
        print("Autorización de supervisor inválida.")
        registrar_evento('override_supervisor', 'Clave supervisor inválida')
        return False

    if cred_sup.get('mfa_enabled'):
        if not PYOTP_AVAILABLE:
            print("MFA de supervisor no disponible.")
            registrar_evento('override_supervisor', 'MFA supervisor no disponible')
            return False
        code_sup = input_seguro("Código MFA supervisor: ", max_len=8)
        if not verificar_totp(ROL_SUPERVISOR, code_sup):
            registrar_intento_fallido(ROL_SUPERVISOR)
            print("Código MFA de supervisor inválido.")
            registrar_evento('override_supervisor', 'MFA supervisor inválido')
            return False

    resetear_intentos(ROL_SUPERVISOR)
    registrar_evento('override_supervisor', f'Override autorizado para {motivo}')
    return True

# ============================================================
# AUTENTICACIÓN (INTEGRADA CON MFA)
# ============================================================
def autenticar_garita() -> bool:
    global operador_actual
    banner_inicio()
    print(centrar("AUTENTICACIÓN - GARITA"))
    linea()
    nombre = input_seguro("Usuario: ", max_len=30)
    if not nombre:
        print("Usuario vacío.")
        return False
    cred = obtener_credenciales_operador(nombre)
    if cred is None:
        print("Usuario no encontrado.")
        registrar_evento('autenticar_garita', f'Usuario {nombre} no existe')
        return False

    bloqueado, secs = esta_bloqueado(nombre)
    if bloqueado:
        print(f"Cuenta bloqueada temporalmente. Intente en {secs} segundos.")
        registrar_evento('autenticar_garita', f'Intento login durante bloqueo para {nombre}')
        return False

    clave = getpass_limitado("Contraseña: ", max_len=MAX_LEN_PASSWORD)
    if not verificar_clave(clave, cred['salt'], cred['hash']):
        registrar_intento_fallido(nombre)
        print("Credenciales inválidas.")
        registrar_evento('autenticar_garita', f'Credenciales inválidas para {nombre}')

        # Para cajero y jefe de cabinas, permitir autorización de supervisor en caso de error.
        if nombre in (ROL_CAJERO, ROL_JEFE_CABINAS):
            if _autorizar_supervisor_para_override(f'Intento fallido de {nombre}'):
                operador_actual = nombre
                resetear_intentos(nombre)
                registrar_evento('autenticar_garita', f'Override de supervisor para {nombre}')
                return True
        return False

    # Para todos los usuarios, si todavía no hay MFA, se fuerza la configuración en este mismo login.
    if not cred.get('mfa_enabled'):
        print("MFA no configurado. Debes activarlo para continuar con el acceso.")
        configurar_mfa(nombre)
        if not cred.get('mfa_enabled'):
            registrar_intento_fallido(nombre)
            print("No se pudo activar MFA.")
            registrar_evento('autenticar_garita', f'MFA no habilitado para {nombre}')
            return False

    # Si el usuario tiene MFA habilitado, pedir TOTP
    if cred.get('mfa_enabled'):
        if not PYOTP_AVAILABLE:
            print("MFA configurado pero pyotp no disponible.")
            registrar_evento('autenticar_garita', f'MFA no disponible para {nombre}')
            return False
        code = input_seguro("Código MFA (6 dígitos): ", max_len=6)
        if not verificar_totp(nombre, code):
            registrar_intento_fallido(nombre)
            print("Código MFA inválido.")
            registrar_evento('autenticar_garita', f'MFA inválido para {nombre}')
            return False

    # Login exitoso
    resetear_intentos(nombre)
    operador_actual = nombre
    registrar_evento('autenticar_garita', f'Login exitoso para {nombre}')
    return True

# ============================================================
# MENÚ PRINCIPAL (simplificado)
# ============================================================
def mostrar_menu():
    banner_inicio()
    panel_usuario()
    print("Menú principal:")
    print("1 - Cobrar peaje".ljust(40) + f"Roles: {etiqueta_roles('1')}")
    print("2 - Ver movimientos".ljust(40) + f"Roles: {etiqueta_roles('2')}")
    print("3 - Ver vehículos".ljust(40) + f"Roles: {etiqueta_roles('3')}")
    print("4 - Mostrar tarifas".ljust(40) + f"Roles: {etiqueta_roles('4')}")
    print("5 - Ajustar tarifas".ljust(40) + f"Roles: {etiqueta_roles('5')}")
    print("6 - Registrar vehículo".ljust(40) + f"Roles: {etiqueta_roles('6')}")
    print("7 - Reporte ingresos".ljust(40) + f"Roles: {etiqueta_roles('7')}")
    print("8 - Registro de eventos".ljust(40) + f"Roles: {etiqueta_roles('8')}")
    print("9 - Configurar MFA".ljust(40) + f"Roles: {etiqueta_roles('9')}")
    print("0 - Salir".ljust(40) + f"Roles: {etiqueta_roles('0')}")
    linea()

def main_loop():
    asegurar_usuario_jefe_cabinas()
    if not autenticar_garita():
        return
    while True:
        mostrar_menu()
        opcion = input_seguro("Seleccione opción: ", max_len=2)
        if opcion == '1' and tiene_permiso('1', operador_actual):
            cobrar_peaje()
        elif opcion == '2' and tiene_permiso('2', operador_actual):
            ver_movimientos_peaje()
        elif opcion == '3' and tiene_permiso('3', operador_actual):
            ver_vehiculos_registrados()
        elif opcion == '4' and tiene_permiso('4', operador_actual):
            mostrar_tarifas_peaje()
        elif opcion == '5' and tiene_permiso('5', operador_actual):
            ajustar_tarifas_peaje()
        elif opcion == '6' and tiene_permiso('6', operador_actual):
            agregar_nuevo_vehiculo()
        elif opcion == '7' and tiene_permiso('7', operador_actual):
            reporte_ingresos()
        elif opcion == '8' and tiene_permiso('8', operador_actual):
            ver_registro_eventos()
        elif opcion == '9' and tiene_permiso('9', operador_actual):
            configurar_mfa(operador_actual)
        elif opcion == '0':
            print("Saliendo...")
            break
        else:
            opcion_invalida()

if __name__ == "__main__":
    try:
        main_loop()
    except KeyboardInterrupt:
        print("\nSaliendo por interrupción del usuario.")
