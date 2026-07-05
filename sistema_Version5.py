# SISTEMA DE PEAJE - GARITA
# Versión final endurecida para evitar crasheos por entradas largas y parpadeos.
# Cambios principales:
# - Entrada de menú limitada y validada
# - No usa getpass
# - No limpia pantalla en bucles de error
# - Todas las entradas de texto pasan por limitadores
# - Máximo 15 caracteres para texto alfanumérico
# - Rechaza caracteres especiales
# - Evita bucles visuales agresivos

import os
import time
import re
from datetime import datetime
import shutil

# =========================
# CONFIGURACIÓN INICIAL
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
ROLES_VALIDOS = {'supervisor', 'cajero'}
OPCIONES_MENU_VALIDAS = {'0','1','2','3','4','5','6','7','8','9'}

# =========================
# VALIDACIÓN Y ENTRADAS
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
        patron = rf'^[A-Za-z0-9 ]{{1,{max_len}}}$' if permitir_espacios else rf'^[A-Za-z0-9]{{1,{max_len}}}$'
        return re.fullmatch(patron, texto) is not None
    except Exception:
        return False

def validar_tipo(tipo):
    try:
        return str(tipo).strip().lower() in TIPOS_VALIDOS
    except Exception:
        return False

def validar_rol(rol):
    try:
        return str(rol).strip().lower() in ROLES_VALIDOS
    except Exception:
        return False

def leer_texto_limitado(prompt, permitir_espacios=False, mayus=False, minus=False):
    while True:
        try:
            texto = input(prompt)
            if texto is None:
                print("Entrada inválida.")
                continue

            texto = str(texto).strip()

            if len(texto) > MAX_CARACTERES:
                print("Máximo 15 caracteres.")
                continue

            if mayus:
                texto = texto.upper()
            if minus:
                texto = texto.lower()

            if permitir_espacios:
                patron = r'^[A-Za-z0-9 ]{1,15}$'
            else:
                patron = r'^[A-Za-z0-9]{1,15}$'

            if not re.fullmatch(patron, texto):
                print("Solo se permiten letras y números.")
                continue

            return texto

        except KeyboardInterrupt:
            print("\nOperación cancelada.")
            return None
        except EOFError:
            print("\nEntrada finalizada.")
            return None
        except Exception:
            print("Error al leer entrada.")
            return None

def leer_entero_seguro(prompt, minimo=None, maximo=None):
    while True:
        try:
            valor = input(prompt).strip()
            n = int(valor)
            if minimo is not None and n < minimo:
                print(f"El valor no puede ser menor que {minimo}.")
                continue
            if maximo is not None and n > maximo:
                print(f"El valor no puede ser mayor que {maximo}.")
                continue
            return n
        except ValueError:
            print("Ingrese un número entero válido.")
        except KeyboardInterrupt:
            print("\nOperación cancelada.")
            return None
        except EOFError:
            print("\nEntrada finalizada.")
            return None
        except Exception:
            print("Error al leer número.")
            return None

def leer_opcion_menu(prompt="Seleccione opción: "):
    while True:
        try:
            op = input(prompt).strip()

            if len(op) > 2:
                print("Solo se permite una opción corta.")
                continue

            if op not in OPCIONES_MENU_VALIDAS:
                print("Opción inválida.")
                continue

            return op

        except KeyboardInterrupt:
            print("\nOperación cancelada.")
            return '0'
        except EOFError:
            print("\nEntrada finalizada.")
            return '0'
        except Exception:
            print("Error leyendo opción.")
            return '0'

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

# =========================
# UTILIDADES VISUALES
# =========================
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

def espera_animacion(segundos=0.4, mensaje="Cargando"):
    try:
        pasos = 4
        for i in range(pasos):
            dots = '.' * ((i % 3) + 1)
            print(f"\r{mensaje}{dots} ", end='', flush=True)
            time.sleep(segundos / pasos)
        print("\r" + " " * (len(mensaje) + 4), end='\r')
    except Exception:
        print()

def barra_progreso(total=10, duracion=0.25, mensaje="Procesando"):
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

# =========================
# EVENTOS
# =========================
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
        print("\nREGISTRO DE EVENTOS")
        linea()
        if not registro_eventos:
            print("No hay eventos registrados")
            return
        for e in registro_eventos:
            print(f"{e.get('fecha','-')}  Función: {e.get('funcion','-')}  Mensaje: {e.get('mensaje','-')}")
            linea()
        input("ENTER para volver")
    except Exception as e:
        registrar_evento('ver_registro_eventos', f'Error: {e}')
        print("Error al mostrar eventos.")

# =========================
# BANNER
# =========================
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

# =========================
# USUARIOS
# =========================
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

def agregar_usuario():
    try:
        banner_inicio()
        panel_usuario()
        print(centrar("CREAR USUARIO"))
        linea()

        usuario = leer_texto_limitado("Nuevo usuario: ", minus=True)
        if usuario is None:
            return

        if buscar_usuario(usuario):
            print("Ese usuario ya existe.")
            input("ENTER para volver")
            return

        clave = leer_texto_limitado("Nueva contraseña: ")
        if clave is None:
            return

        rol = leer_texto_limitado("Rol (supervisor/cajero): ", minus=True)
        if rol is None or not validar_rol(rol):
            print("Rol inválido.")
            input("ENTER para volver")
            return

        garita_usuarios.append({usuario: clave})
        registrar_evento('agregar_usuario', f'Usuario {usuario} creado')
        print("Usuario creado correctamente.")
        input("ENTER para volver")
    except Exception as e:
        registrar_evento('agregar_usuario', f'Error: {e}')
        print("Error al crear usuario.")

def eliminar_usuario():
    try:
        banner_inicio()
        panel_usuario()
        print(centrar("ELIMINAR USUARIO"))
        linea()

        usuario = leer_texto_limitado("Usuario a eliminar: ", minus=True)
        if usuario is None:
            return

        if usuario in ('supervisor', 'cajero'):
            print("No se permite eliminar usuarios base.")
            input("ENTER para volver")
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

# =========================
# VEHÍCULOS Y COBRO
# =========================
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

def ver_movimientos_peaje():
    try:
        banner_inicio()
        panel_usuario()
        print(centrar("HISTORIAL DE MOVIMIENTOS"))
        linea()
        if not movimientos_peaje:
            print(centrar("Sin movimientos"))
            registrar_evento('ver_movimientos_peaje', 'Sin movimientos')
            time.sleep(1.5)
            return
        for i, m in enumerate(movimientos_peaje, start=1):
            print(f"[{i}] {m.get('fecha','-')}  Placa: {m.get('placa','-')}  Tipo: {m.get('tipo','-')}")
            print(f"     Tarifa: {m.get('tarifa',0)}  Pagado: {m.get('pagado',0)}  Vuelto: {m.get('vuelto',0)}")
            linea()
        input("ENTER para volver al menú")
    except Exception as e:
        registrar_evento('ver_movimientos_peaje', f'Error: {e}')
        print("Error al mostrar movimientos.")

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
                placa = leer_texto_limitado("Ingrese placa: ", mayus=True)
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

            tipo = leer_texto_limitado("Ingrese tipo (vehiculo/moto/camion): ", minus=True)
            if tipo is None or not validar_tipo(tipo):
                print("Tipo inválido.")
                if not confirmar("¿Intentar nuevamente? (s/n): "):
                    registrar_evento('agregar_nuevo_vehiculo', 'Tipo inválido')
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

            barra_progreso(8, 0.2, "Registrando vehículo")
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
                    tipo = leer_texto_limitado("Ingrese tipo (vehiculo/moto/camion): ", minus=True)
        else:
            tipo = leer_texto_limitado("Ingrese tipo (vehiculo/moto/camion): ", minus=True)
            placa = leer_texto_limitado("Ingrese placa (o N/A): ", mayus=True)
            if placa is None:
                placa = 'N/A'

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

        pagado = leer_entero_seguro("Ingrese monto entregado: ", minimo=0)
        if pagado is None:
            return

        if pagado < tarifa:
            print("Monto insuficiente.")
            registrar_evento('cobrar_peaje', 'Monto insuficiente')
            return

        barra_progreso(10, 0.25, "Registrando cobro")
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

        clave_confirm = leer_texto_limitado("Ingrese contraseña del supervisor: ")
        if clave_confirm != obtener_clave_operador('supervisor'):
            print("Contraseña incorrecta.")
            registrar_evento('ajustar_tarifas_peaje', 'Contraseña incorrecta')
            return

        print("Tarifas actuales:")
        for k, v in tarifas_peaje.items():
            print(f" - {k}: {v}")

        tipo = leer_texto_limitado("Tipo a ajustar (vehiculo/moto/camion): ", minus=True)
        if not validar_tipo(tipo):
            print("Tipo inválido.")
            return

        nueva = leer_entero_seguro(f"Nueva tarifa para {tipo}: ", minimo=0)
        if nueva is None:
            return

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
            input("ENTER para volver")
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
        time.sleep(0.4)
        registrar_evento('menu_principal', 'Opción inválida')
    except Exception:
        pass

# =========================
# AUTENTICACIÓN
# =========================
def autenticar_garita():
    global operador_actual
    try:
        limpiar_pantalla()
        banner_inicio()
        print(centrar("INICIO DE SESIÓN"))
        linea()

        intentos = 0
        while intentos < MAX_INTENTOS_LOGIN:
            usuario = leer_texto_limitado("Nombre de operador: ", minus=True)
            if usuario is None:
                return False

            clave = leer_texto_limitado("Contraseña: ")
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
                time.sleep(0.8)

        registrar_evento('autenticar_garita', 'Autenticación fallida')
        return False
    except Exception as e:
        registrar_evento('autenticar_garita', f'Error: {e}')
        print("Error en autenticación.")
        return False

# =========================
# MENÚ USUARIOS
# =========================
def menu_usuarios():
    try:
        while True:
            print("\nGESTIÓN DE USUARIOS")
            linea()
            print("1) Crear usuario")
            print("2) Listar usuarios")
            print("3) Eliminar usuario")
            print("0) Volver")
            linea()
            op = leer_opcion_menu("Seleccione opción: ")

            if op == '1':
                agregar_usuario()
            elif op == '2':
                listar_usuarios()
            elif op == '3':
                eliminar_usuario()
            elif op == '0':
                return
    except Exception as e:
        registrar_evento('menu_usuarios', f'Error: {e}')
        print("Error en gestión de usuarios.")
        input("ENTER para volver")

# =========================
# MENÚ PRINCIPAL
# =========================
def menu_principal():
    try:
        while True:
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

            elec = leer_opcion_menu("Seleccione opción: ")

            if elec == '0':
                if confirmar("¿Desea salir del sistema? (s/n): "):
                    print("Cerrando sesión...")
                    espera_animacion(0.6, "Saliendo")
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
                    time.sleep(1.0)
    except Exception as e:
        registrar_evento('menu_principal', f'Error: {e}')
        print("Error en el menú principal.")

# =========================
# ENTRADA PRINCIPAL
# =========================
if __name__ == "__main__":
    try:
        if autenticar_garita():
            menu_principal()
        else:
            print("Acceso denegado. Fin del programa.")
            registrar_evento('main', 'Acceso denegado al iniciar el programa')
    except Exception as e:
        print(f"Error fatal controlado: {e}")