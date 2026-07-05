# SISTEMA DE PEAJE - GARITA
# Versión estabilizada para evitar crasheos en VS Code.
# Cambios clave:
# - Login sin getpass
# - Validación estricta de 15 caracteres máximos
# - Solo letras y números en usuario y contraseña
# - Manejo defensivo de errores
# - Funciones de entrada seguras

import os
import time
import re
from datetime import datetime
import shutil

# -------------------------
# Configuración inicial
# -------------------------
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

# -------------------------
# Constantes
# -------------------------
MAX_CARACTERES = 15
MAX_INTENTOS_LOGIN = 3
TIPOS_VALIDOS = {'vehiculo', 'moto', 'camion'}

# -------------------------
# Validaciones
# -------------------------
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

def pedir_texto_seguro(prompt, max_len=MAX_CARACTERES, permitir_espacios=False, mayus=False, minus=False):
    while True:
        try:
            dato = input(prompt)
            if dato is None:
                print("Entrada inválida.")
                continue

            dato = str(dato).strip()

            if mayus:
                dato = dato.upper()
            if minus:
                dato = dato.lower()

            if not validar_texto_seguro(dato, max_len=max_len, permitir_espacios=permitir_espacios):
                print(f"Solo se permiten letras y números. Máximo {max_len} caracteres.")
                continue

            return dato

        except KeyboardInterrupt:
            print("\nOperación cancelada.")
            return None
        except EOFError:
            print("\nNo se recibió entrada.")
            return None
        except Exception:
            print("Error al leer la entrada.")
            return None

def pedir_contraseña_segura(prompt="Contraseña: "):
    """
    En esta versión se usa input normal para evitar crasheos de getpass en VS Code.
    """
    while True:
        try:
            clave = input(prompt)
            if clave is None:
                print("Entrada inválida.")
                continue
            clave = str(clave).strip()

            if not validar_texto_seguro(clave, max_len=MAX_CARACTERES):
                print(f"Contraseña inválida. Solo letras y números, máximo {MAX_CARACTERES} caracteres.")
                continue

            return clave

        except KeyboardInterrupt:
            print("\nOperación cancelada.")
            return None
        except EOFError:
            print("\nNo se recibió contraseña.")
            return None
        except Exception:
            print("Error al leer la contraseña.")
            return None

def confirmar(texto="¿Confirmar? (s/n): "):
    while True:
        try:
            r = input(texto).strip().lower()
            if r in ('s', 'n'):
                return r == 's'
            print("Ingrese 's' para sí o 'n' para no.")
        except KeyboardInterrupt:
            print("\nOperación cancelada.")
            return False
        except EOFError:
            print("\nNo se recibió confirmación.")
            return False
        except Exception:
            print("Error leyendo confirmación.")
            return False

def validar_numero_entero(valor, minimo=None, maximo=None):
    try:
        n = int(str(valor).strip())
        if minimo is not None and n < minimo:
            return None
        if maximo is not None and n > maximo:
            return None
        return n
    except Exception:
        return None

# -------------------------
# Utilidades visuales
# -------------------------
def ancho_terminal(default=80):
    try:
        return shutil.get_terminal_size().columns
    except Exception:
        return default

def limpiar_pantalla():
    try:
        os.system('cls' if os.name == 'nt' else 'clear')
    except Exception:
        pass

def centrar(texto, ancho=None):
    try:
        ancho = ancho or ancho_terminal()
        return str(texto).center(ancho)
    except Exception:
        return str(texto)

def linea(char='─'):
    try:
        print(char * ancho_terminal())
    except Exception:
        print('-' * 80)

def espera_animacion(segundos=0.6, mensaje="Cargando"):
    try:
        pasos = 6
        for i in range(pasos):
            dots = '.' * ((i % 3) + 1)
            print(f"\r{mensaje}{dots} ", end='', flush=True)
            time.sleep(segundos / pasos)
        print("\r" + " " * (len(mensaje) + 4), end='\r')
    except Exception:
        print()

def barra_progreso(total=20, duracion=0.5, mensaje="Procesando"):
    try:
        total = max(1, int(total))
        for i in range(total + 1):
            por = int((i / total) * 100)
            barra = '█' * i + '-' * (total - i)
            print(f"\r{mensaje} |{barra}| {por:3d}%", end='', flush=True)
            time.sleep(duracion / total)
        print()
    except Exception:
        print()

def beep():
    try:
        print('\a', end='')
    except Exception:
        pass

# -------------------------
# Eventos
# -------------------------
def registrar_evento(funcion, mensaje):
    try:
        registro_eventos.append({
            'fecha': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            'funcion': str(funcion)[:MAX_CARACTERES],
            'mensaje': str(mensaje)[:200]
        })
    except Exception:
        pass

def ver_registro_eventos():
    try:
        banner_inicio()
        panel_usuario()
        print(centrar("REGISTRO DE EVENTOS"))
        linea()
        if not registro_eventos:
            print(centrar("No hay eventos registrados"))
            espera_animacion(0.5, "Volviendo")
            return
        for e in registro_eventos:
            print(f"{e.get('fecha','-')}  Función: {e.get('funcion','-')}  Mensaje: {e.get('mensaje','-')}")
            linea()
        input("ENTER para volver al menú")
    except Exception as e:
        registrar_evento('ver_registro_eventos', f'Error: {e}')
        print("Error al mostrar eventos.")
        input("ENTER para volver")

# -------------------------
# Banner
# -------------------------
def banner_inicio():
    try:
        limpiar_pantalla()
        ancho = ancho_terminal()
        if ancho < 20:
            ancho = 80
        print('╔' + '═' * (ancho - 2) + '╗')
        print('║' + ' ' * (ancho - 2) + '║')
        print('║' + centrar('SISTEMA DE PEAJE - GARITA', ancho - 2) + '║')
        print('║' + centrar('Control de Acceso y Cobro', ancho - 2) + '║')
        print('║' + ' ' * (ancho - 2) + '║')
        print('╚' + '═' * (ancho - 2) + '╝')
        print()
    except Exception:
        print("SISTEMA DE PEAJE - GARITA")

def nombre_panel_por_rol(rol):
    if rol == 'supervisor':
        return "PANEL SUPERVISOR - CONTROL TOTAL"
    if rol == 'cajero':
        return "PANEL CAJERO - OPERACIONES DE COBRO"
    return "PANEL OPERADOR"

def panel_usuario():
    try:
        ancho = ancho_terminal()
        panel = nombre_panel_por_rol(operador_actual)
        print(centrar(panel, ancho))
        linea()
        print(centrar(f"Operador: {operador_actual if operador_actual else 'No autenticado'}", ancho))
        print(centrar(f"Hora: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", ancho))
        linea()
    except Exception:
        pass

# -------------------------
# Usuarios
# -------------------------
def buscar_usuario(nombre_usuario):
    try:
        for cred in garita_usuarios:
            if nombre_usuario in cred:
                return cred
        return None
    except Exception:
        return None

def obtener_clave_operador(nombre_operador):
    try:
        cred = buscar_usuario(nombre_operador)
        if cred:
            return cred.get(nombre_operador)
        return None
    except Exception:
        return None

# -------------------------
# Vehículos
# -------------------------
def buscar_vehiculo_por_placa(placa):
    try:
        if not placa:
            return None
        placa = str(placa).strip().upper()
        for v in vehiculos_registrados:
            if str(v.get('placa', '')).upper() == placa:
                return v
        return None
    except Exception:
        return None

def calcular_vuelto(monto_pagado, tarifa):
    try:
        return int(monto_pagado) - int(tarifa)
    except Exception:
        return 0

# -------------------------
# Funciones principales
# -------------------------
def ver_movimientos_peaje():
    try:
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
            print(f"[{i}] {m.get('fecha','-')}  Placa: {m.get('placa','-')}  Tipo: {m.get('tipo','-')}")
            print(f"     Tarifa: {m.get('tarifa',0)}  Pagado: {m.get('pagado',0)}  Vuelto: {m.get('vuelto',0)}")
            linea()
        input("Presione ENTER para volver al menú")
    except Exception as e:
        registrar_evento('ver_movimientos_peaje', f'Error: {e}')
        print("Error al mostrar movimientos.")
        input("ENTER para volver")

def agregar_nuevo_vehiculo(placa_propuesta=None):
    try:
        banner_inicio()
        panel_usuario()
        print(centrar("REGISTRO DE VEHÍCULO"))
        linea()

        while True:
            if placa_propuesta:
                placa = str(placa_propuesta).strip().upper()
                placa_propuesta = None
            else:
                placa = pedir_texto_seguro("Ingrese placa: ", max_len=MAX_CARACTERES, mayus=True)
                if placa is None:
                    return None

            if not validar_texto_seguro(placa):
                print("Placa inválida.")
                if not confirmar("¿Intentar nuevamente? (s/n): "):
                    registrar_evento('agregar_nuevo_vehiculo', 'Placa inválida')
                    return None
                continue

            if buscar_vehiculo_por_placa(placa):
                print("La placa ya está registrada.")
                if not confirmar("¿Desea ingresar otra placa? (s/n): "):
                    registrar_evento('agregar_nuevo_vehiculo', f'Placa existente {placa}')
                    return None
                continue

            tipo = input("Ingrese tipo (vehiculo/moto/camion): ").strip().lower()
            if not validar_tipo(tipo):
                print("Tipo inválido.")
                if not confirmar("¿Intentar nuevamente? (s/n): "):
                    registrar_evento('agregar_nuevo_vehiculo', f'Tipo inválido {tipo}')
                    return None
                continue

            propietario = input("Ingrese propietario (opcional, máx. 15): ").strip()
            if propietario and not validar_texto_seguro(propietario, max_len=MAX_CARACTERES, permitir_espacios=True):
                print("Propietario inválido.")
                if not confirmar("¿Intentar nuevamente? (s/n): "):
                    registrar_evento('agregar_nuevo_vehiculo', 'Propietario inválido')
                    return None
                continue
            if not propietario:
                propietario = '-'

            vehiculos_registrados.append({
                'placa': placa,
                'tipo': tipo,
                'propietario': propietario[:MAX_CARACTERES]
            })

            barra_progreso(12, 0.4, "Registrando vehículo")
            print(f"Vehículo {placa} registrado como {tipo}")
            registrar_evento('agregar_nuevo_vehiculo', f'Vehículo {placa} registrado')
            input("ENTER para volver")
            return tipo

    except Exception as e:
        registrar_evento('agregar_nuevo_vehiculo', f'Error: {e}')
        print("Error al registrar vehículo.")
        input("ENTER para volver")
        return None

def cobrar_peaje():
    try:
        banner_inicio()
        panel_usuario()
        print(centrar("COBRO DE PEAJE"))
        linea()

        placa = input("Ingrese placa o ENTER para no registrado: ").strip().upper()
        if placa and len(placa) > MAX_CARACTERES:
            print("Placa demasiado larga.")
            registrar_evento('cobrar_peaje', 'Placa demasiado larga')
            return

        tipo = None

        if placa:
            v = buscar_vehiculo_por_placa(placa)
            if v:
                print(f"Vehículo encontrado: {v.get('placa','-')}  Tipo: {v.get('tipo','-')}")
                tipo = v.get('tipo')
            else:
                print("Vehículo no registrado.")
                if confirmar("¿Registrar ahora? (s/n): "):
                    tipo = agregar_nuevo_vehiculo(placa_propuesta=placa)
                    if not tipo:
                        return
                else:
                    tipo = input("Ingrese tipo (vehiculo/moto/camion): ").strip().lower()
        else:
            tipo = input("Ingrese tipo (vehiculo/moto/camion): ").strip().lower()
            placa = input("Ingrese placa (o 'N/A'): ").strip().upper() or 'N/A'

        if not validar_tipo(tipo):
            print("Tipo inválido.")
            registrar_evento('cobrar_peaje', 'Tipo inválido')
            return

        tarifa = tarifas_peaje.get(tipo)
        if tarifa is None:
            print("No existe tarifa para ese tipo.")
            registrar_evento('cobrar_peaje', 'Tipo sin tarifa')
            return

        print(f"Tarifa para {tipo}: {tarifa} pesos")

        while True:
            try:
                pagado = int(input("Ingrese monto entregado: ").strip())
                if pagado < 0:
                    print("No puede ser negativo.")
                    continue
                break
            except ValueError:
                print("Ingrese un número entero válido.")
            except Exception:
                print("Error leyendo monto.")

        if pagado < tarifa:
            print("Monto insuficiente.")
            registrar_evento('cobrar_peaje', 'Monto insuficiente')
            return

        barra_progreso(20, 0.5, "Registrando cobro")
        vuelto = calcular_vuelto(pagado, tarifa)

        movimientos_peaje.append({
            'fecha': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            'placa': placa[:MAX_CARACTERES],
            'tipo': tipo,
            'tarifa': tarifa,
            'pagado': pagado,
            'vuelto': vuelto
        })

        beep()
        print(f"Cobro registrado. Vuelto: {vuelto} pesos")
        registrar_evento('cobrar_peaje', f'Cobro registrado para {placa}')
        input("ENTER para volver")
    except Exception as e:
        registrar_evento('cobrar_peaje', f'Error: {e}')
        print("Error al realizar el cobro.")
        input("ENTER para volver")

def ajustar_tarifas_peaje():
    try:
        banner_inicio()
        panel_usuario()
        print(centrar("AJUSTE DE TARIFAS"))
        linea()

        if operador_actual != 'supervisor':
            print("Acceso denegado.")
            registrar_evento('ajustar_tarifas_peaje', 'Acceso denegado')
            time.sleep(1)
            return

        clave_confirm = pedir_contraseña_segura("Ingrese contraseña del supervisor: ")
        if clave_confirm != obtener_clave_operador('supervisor'):
            print("Contraseña incorrecta.")
            registrar_evento('ajustar_tarifas_peaje', 'Contraseña incorrecta')
            return

        print("Tarifas actuales:")
        for k, v in tarifas_peaje.items():
            print(f" - {k}: {v}")

        tipo = input("Tipo a ajustar (vehiculo/moto/camion): ").strip().lower()
        if not validar_tipo(tipo):
            print("Tipo inválido.")
            return

        while True:
            try:
                nueva = int(input(f"Nueva tarifa para {tipo}: ").strip())
                if nueva < 0:
                    print("No puede ser negativa.")
                    continue
                break
            except ValueError:
                print("Ingrese un número entero válido.")

        if confirmar("¿Confirmar cambio? (s/n): "):
            tarifas_peaje[tipo] = nueva
            print("Tarifa actualizada.")
            registrar_evento('ajustar_tarifas_peaje', f'{tipo} -> {nueva}')
        else:
            print("Operación cancelada.")
        input("ENTER para volver")
    except Exception as e:
        registrar_evento('ajustar_tarifas_peaje', f'Error: {e}')
        print("Error al ajustar tarifas.")
        input("ENTER para volver")

def ver_vehiculos_registrados():
    try:
        banner_inicio()
        panel_usuario()
        print(centrar("VEHÍCULOS REGISTRADOS"))
        linea()
        if not vehiculos_registrados:
            print(centrar("No hay vehículos registrados"))
            return
        for v in vehiculos_registrados:
            print(f"Placa: {str(v.get('placa','-'))[:15]:15}  Tipo: {str(v.get('tipo','-'))[:10]:10}  Propietario: {v.get('propietario','-')}")
        linea()
        input("ENTER para volver")
    except Exception as e:
        registrar_evento('ver_vehiculos_registrados', f'Error: {e}')
        print("Error al mostrar vehículos.")
        input("ENTER para volver")

def mostrar_tarifas_peaje():
    try:
        banner_inicio()
        panel_usuario()
        print(centrar("TARIFAS VIGENTES"))
        linea()
        for k, v in tarifas_peaje.items():
            print(f" - {k.capitalize():10} : {v} pesos")
        linea()
        input("ENTER para volver")
    except Exception as e:
        registrar_evento('mostrar_tarifas_peaje', f'Error: {e}')
        print("Error al mostrar tarifas.")
        input("ENTER para volver")

def reporte_ingresos():
    try:
        banner_inicio()
        panel_usuario()
        print(centrar("REPORTE DE INGRESOS"))
        linea()
        if not movimientos_peaje:
            print("No hay movimientos.")
            registrar_evento('reporte_ingresos', 'Sin movimientos')
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
            print(f"{k.capitalize():10} Recaudado: {totales[k]:8}  Pasos: {conteo[k]:3}")
        linea()
        print(f"Total general recaudado: {total_general} pesos")
        registrar_evento('reporte_ingresos', f'Total {total_general}')
        input("ENTER para volver")
    except Exception as e:
        registrar_evento('reporte_ingresos', f'Error: {e}')
        print("Error al generar reporte.")
        input("ENTER para volver")

def opcion_invalida():
    try:
        print("Opción inválida")
        time.sleep(0.8)
        registrar_evento('menu_principal', 'Opción inválida')
    except Exception:
        pass

# -------------------------
# Autenticación
# -------------------------
def autenticar_garita():
    global operador_actual
    try:
        limpiar_pantalla()
        banner_inicio()
        print(centrar("INICIO DE SESIÓN"))
        linea()

        intentos = 0
        while intentos < MAX_INTENTOS_LOGIN:
            usuario = pedir_texto_seguro("Nombre de operador: ", max_len=MAX_CARACTERES, minus=True)
            if usuario is None:
                return False

            clave = pedir_contraseña_segura("Contraseña: ")
            if clave is None:
                return False

            if not validar_texto_seguro(usuario, max_len=MAX_CARACTERES):
                print("Usuario inválido.")
                intentos += 1
                continue

            if not validar_texto_seguro(clave, max_len=MAX_CARACTERES):
                print("Contraseña inválida.")
                intentos += 1
                continue

            clave_almacenada = obtener_clave_operador(usuario)
            if clave_almacenada is not None and clave_almacenada == clave:
                operador_actual = usuario
                limpiar_pantalla()
                banner_inicio()
                print(centrar(nombre_panel_por_rol(operador_actual)))
                linea()
                print(centrar(f"Bienvenido, {operador_actual}"))
                linea()
                registrar_evento('autenticar_garita', f'Operador {operador_actual} autenticado')
                time.sleep(1)
                return True
            else:
                intentos += 1
                restante = MAX_INTENTOS_LOGIN - intentos
                print("Operador o contraseña incorrectos.")
                if restante:
                    print(f"Intentos restantes: {restante}")
                else:
                    print("Se han agotado los intentos.")
                time.sleep(1)

        registrar_evento('autenticar_garita', 'Autenticación fallida')
        return False
    except Exception as e:
        registrar_evento('autenticar_garita', f'Error: {e}')
        print("Error en autenticación.")
        return False

# -------------------------
# Menú usuarios
# -------------------------
def menu_usuarios():
    try:
        while True:
            banner_inicio()
            panel_usuario()
            print(centrar("GESTIÓN DE USUARIOS"))
            linea()
            print("1) Crear usuario")
            print("2) Listar usuarios")
            print("3) Eliminar usuario")
            print("0) Volver")
            linea()
            op = input("Seleccione opción: ").strip()

            if op == '1':
                agregar_usuario()
            elif op == '2':
                listar_usuarios()
            elif op == '3':
                eliminar_usuario()
            elif op == '0':
                return
            else:
                opcion_invalida()
    except Exception as e:
        registrar_evento('menu_usuarios', f'Error: {e}')
        print("Error en gestión de usuarios.")
        input("ENTER para volver")

def agregar_usuario():
    try:
        banner_inicio()
        panel_usuario()
        print(centrar("CREAR USUARIO"))
        linea()

        usuario = pedir_texto_seguro("Nuevo usuario: ", max_len=MAX_CARACTERES, minus=True)
        if usuario is None:
            return
        if buscar_usuario(usuario):
            print("Ese usuario ya existe.")
            return

        clave = pedir_contraseña_segura("Nueva contraseña: ")
        if clave is None:
            return

        if not validar_texto_seguro(clave, max_len=MAX_CARACTERES):
            print("Contraseña inválida.")
            return

        rol = input("Rol (supervisor/cajero): ").strip().lower()
        if rol not in ('supervisor', 'cajero'):
            print("Rol inválido.")
            return

        garita_usuarios.append({usuario: clave})
        registrar_evento('agregar_usuario', f'Usuario {usuario} creado')
        print("Usuario creado correctamente.")
        input("ENTER para volver")
    except Exception as e:
        registrar_evento('agregar_usuario', f'Error: {e}')
        print("Error al crear usuario.")
        input("ENTER para volver")

def listar_usuarios():
    try:
        banner_inicio()
        panel_usuario()
        print(centrar("USUARIOS REGISTRADOS"))
        linea()
        for cred in garita_usuarios:
            for usuario in cred:
                print(f"Usuario: {usuario}")
        linea()
        input("ENTER para volver")
    except Exception as e:
        registrar_evento('listar_usuarios', f'Error: {e}')
        print("Error al listar usuarios.")
        input("ENTER para volver")

def eliminar_usuario():
    try:
        banner_inicio()
        panel_usuario()
        print(centrar("ELIMINAR USUARIO"))
        linea()

        usuario = pedir_texto_seguro("Usuario a eliminar: ", max_len=MAX_CARACTERES, minus=True)
        if usuario is None:
            return

        if usuario in ('supervisor', 'cajero'):
            print("No se permite eliminar usuarios base.")
            return

        for i, cred in enumerate(garita_usuarios):
            if usuario in cred:
                if confirmar(f"¿Eliminar usuario {usuario}? (s/n): "):
                    del garita_usuarios[i]
                    registrar_evento('eliminar_usuario', f'Usuario {usuario} eliminado')
                    print("Usuario eliminado.")
                else:
                    print("Operación cancelada.")
                input("ENTER para volver")
                return

        print("Usuario no encontrado.")
        input("ENTER para volver")
    except Exception as e:
        registrar_evento('eliminar_usuario', f'Error: {e}')
        print("Error al eliminar usuario.")
        input("ENTER para volver")

# -------------------------
# Menú principal
# -------------------------
def menu_principal():
    try:
        while True:
            limpiar_pantalla()
            banner_inicio()
            panel_usuario()
            print(centrar("MENÚ PRINCIPAL"))
            linea()
            print(" 1) Ver Movimientos")
            print(" 2) Cobrar peaje")
            print(" 3) Ajustar tarifas (solo supervisor)")
            print(" 4) Agregar nuevo vehículo")
            print(" 5) Ver vehículos registrados")
            print(" 6) Mostrar tarifas")
            print(" 7) Reporte de ingresos")
            print(" 8) Ver registro de eventos")
            print(" 9) Gestionar usuarios")
            print(" 0) Salir")
            linea()

            elec = input("Seleccione opción: ").strip()

            if elec == '0':
                if confirmar("¿Desea salir del sistema? (s/n): "):
                    print("Cerrando sesión...")
                    espera_animacion(0.8, "Saliendo")
                    registrar_evento('menu_principal', 'Cierre de sesión')
                    break
                continue

            elif elec == '1':
                ver_movimientos_peaje()
            elif elec == '2':
                cobrar_peaje()
            elif elec == '3':
                ajustar_tarifas_peaje()
            elif elec == '4':
                agregar_nuevo_vehiculo()
            elif elec == '5':
                ver_vehiculos_registrados()
            elif elec == '6':
                mostrar_tarifas_peaje()
            elif elec == '7':
                reporte_ingresos()
            elif elec == '8':
                ver_registro_eventos()
            elif elec == '9':
                if operador_actual == 'supervisor':
                    menu_usuarios()
                else:
                    print("Solo el supervisor puede gestionar usuarios.")
                    time.sleep(1.5)
            else:
                opcion_invalida()

    except Exception as e:
        registrar_evento('menu_principal', f'Error: {e}')
        print("Error en el menú principal.")

# -------------------------
# Entrada principal
# -------------------------
if __name__ == "__main__":
    try:
        if autenticar_garita():
            menu_principal()
        else:
            print("Acceso denegado. Fin del programa.")
            registrar_evento('main', 'Acceso denegado al iniciar el programa')
    except Exception as e:
        print(f"Error fatal controlado: {e}")