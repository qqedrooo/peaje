# SISTEMA DE PEAJE - GARITA
# Versión reforzada con validaciones, limitadores y manejo de errores.
# - Límite general de 15 caracteres para entradas de texto.
# - Solo se permiten letras y números en campos alfanuméricos.
# - Validación centralizada de entradas.
# - Manejo defensivo de errores en autenticación, cobro, registro y reportes.

import os
import time
import getpass
import re
from datetime import datetime
import shutil

# -------------------------
# Configuración inicial
# -------------------------
garita_usuarios = [{'supervisor': '123'}, {'cajero': '321'}]

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
# Constantes de seguridad
# -------------------------
MAX_CARACTERES = 15
MAX_INTENTOS_LOGIN = 3
TIPOS_VALIDOS = {'vehiculo', 'moto', 'camion'}

# -------------------------
# Utilidades de seguridad y validación
# -------------------------
def validar_texto_seguro(texto, max_len=MAX_CARACTERES, permitir_espacios=False):
    """
    Valida texto alfanumérico con límite de longitud.
    No permite caracteres especiales.
    """
    try:
        if texto is None:
            return False
        texto = str(texto).strip()
        if not texto:
            return False
        if len(texto) > max_len:
            return False
        patron = r'^[A-Za-z0-9 ]{1,' + str(max_len) + r'}$' if permitir_espacios else r'^[A-Za-z0-9]{1,' + str(max_len) + r'}$'
        return re.fullmatch(patron, texto) is not None
    except Exception:
        return False

def validar_tipo(tipo):
    """
    Valida que el tipo pertenezca a la lista permitida.
    """
    try:
        if tipo is None:
            return False
        return str(tipo).strip().lower() in TIPOS_VALIDOS
    except Exception:
        return False

def validar_numero_entero(valor, minimo=None, maximo=None):
    """
    Valida un número entero y opcionalmente verifica rango.
    """
    try:
        n = int(str(valor).strip())
        if minimo is not None and n < minimo:
            return None
        if maximo is not None and n > maximo:
            return None
        return n
    except Exception:
        return None

def entrada_segura(prompt, max_len=MAX_CARACTERES, permitir_espacios=False, en_mayusculas=False, en_minusculas=False):
    """
    Solicita entrada segura al usuario con validación centralizada.
    """
    while True:
        try:
            dato = input(prompt)
            if dato is None:
                print("Entrada inválida.")
                continue
            dato = dato.strip()
            if en_mayusculas:
                dato = dato.upper()
            if en_minusculas:
                dato = dato.lower()
            if not validar_texto_seguro(dato, max_len=max_len, permitir_espacios=permitir_espacios):
                print(f"Entrada inválida. Solo se permiten letras y números, máximo {max_len} caracteres.")
                continue
            return dato
        except KeyboardInterrupt:
            print("\nOperación cancelada por el usuario.")
            return None
        except EOFError:
            print("\nNo se recibió entrada.")
            return None
        except Exception:
            print("Error inesperado al leer la entrada.")
            return None

def confirmar(texto="¿Confirmar? (s/n): "):
    """
    Solicita confirmación segura.
    """
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
    ancho = ancho or ancho_terminal()
    try:
        return str(texto).center(ancho)
    except Exception:
        return str(texto)

def linea(char='─'):
    try:
        print(char * ancho_terminal())
    except Exception:
        print('-' * 80)

def espera_animacion(segundos=0.8, mensaje="Cargando"):
    try:
        pasos = 6
        for i in range(pasos):
            dots = '.' * ((i % 3) + 1)
            print(f"\r{mensaje}{dots} ", end='', flush=True)
            time.sleep(segundos / pasos)
        print("\r" + " " * (len(mensaje) + 4), end='\r')
    except Exception:
        print()

def barra_progreso(total=20, duracion=0.6, mensaje="Procesando"):
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

def registrar_evento(funcion, mensaje):
    try:
        evento = {
            'fecha': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            'funcion': str(funcion)[:MAX_CARACTERES],
            'mensaje': str(mensaje)[:200]
        }
        registro_eventos.append(evento)
    except Exception:
        pass

# -------------------------
# Banner y panel
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
        print("SISTEMA DE PEAJE - GARITA\n")

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
# Funciones de datos
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

def obtener_clave_operador(nombre_operador):
    try:
        for cred in garita_usuarios:
            if nombre_operador in cred:
                return cred[nombre_operador]
        return None
    except Exception:
        return None

# -------------------------
# Registro de eventos
# -------------------------
def ver_registro_eventos():
    try:
        banner_inicio()
        panel_usuario()
        print(centrar("REGISTRO DE EVENTOS"))
        linea()
        if not registro_eventos:
            print(centrar("No hay eventos registrados"))
            espera_animacion(0.6, "Volviendo")
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
# Operaciones principales
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

def agregar_nuevo_vehiculo(placa_propuesta=None, preguntar_tipo=False):
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
                placa = entrada_segura("Ingrese placa: ", max_len=MAX_CARACTERES, en_mayusculas=True)
                if placa is None:
                    return None

            if not validar_texto_seguro(placa):
                print("Placa inválida. Solo letras y números, máximo 15 caracteres.")
                if not confirmar("¿Desea intentar nuevamente? (s/n): "):
                    registrar_evento('agregar_nuevo_vehiculo', 'Registro cancelado: placa inválida')
                    return None
                continue

            if buscar_vehiculo_por_placa(placa):
                print(f"La placa {placa} ya está registrada.")
                if confirmar("¿Desea ingresar otra placa? (s/n): "):
                    continue
                registrar_evento('agregar_nuevo_vehiculo', f'Registro cancelado: placa {placa} ya existente')
                return None

            if preguntar_tipo:
                tipo = input("Ingrese tipo (vehiculo/moto/camion): ").strip().lower()
            else:
                tipo = input("Ingrese tipo (vehiculo/moto/camion): ").strip().lower()

            if not validar_tipo(tipo):
                print("Tipo inválido.")
                if confirmar("¿Desea intentar nuevamente el registro? (s/n): "):
                    continue
                registrar_evento('agregar_nuevo_vehiculo', f'Registro cancelado: tipo inválido ({tipo})')
                return None

            propietario = input("Ingrese propietario (opcional, máx. 15 caracteres): ").strip()
            if propietario:
                if not validar_texto_seguro(propietario, max_len=MAX_CARACTERES, permitir_espacios=True):
                    print("Propietario inválido. Solo letras, números y espacios, máximo 15 caracteres.")
                    if not confirmar("¿Desea intentar nuevamente? (s/n): "):
                        registrar_evento('agregar_nuevo_vehiculo', 'Registro cancelado: propietario inválido')
                        return None
                    continue
            else:
                propietario = '-'

            vehiculos_registrados.append({
                'placa': placa,
                'tipo': tipo,
                'propietario': propietario[:MAX_CARACTERES]
            })
            barra_progreso(12, 0.5, "Registrando vehículo")
            print(f"Vehículo {placa} registrado como {tipo}")
            registrar_evento('agregar_nuevo_vehiculo', f'Vehículo {placa} registrado como {tipo}')
            return tipo
    except Exception as e:
        registrar_evento('agregar_nuevo_vehiculo', f'Error: {e}')
        print("Error al registrar vehículo.")
        return None

def cobrar_peaje():
    try:
        banner_inicio()
        panel_usuario()
        print(centrar("COBRO DE PEAJE"))
        linea()

        placa = input("Ingrese placa del vehículo o ENTER para no registrado: ").strip().upper()
        if placa and len(placa) > MAX_CARACTERES:
            print("Placa demasiado larga. Máximo 15 caracteres.")
            registrar_evento('cobrar_peaje', 'Placa demasiado larga')
            return

        tipo = None

        if placa:
            v = buscar_vehiculo_por_placa(placa)
            if v:
                print(f"Vehículo encontrado: {v.get('placa','-')}  Tipo: {v.get('tipo','-')}  Propietario: {v.get('propietario','-')}")
                tipo = v.get('tipo')
            else:
                print("Vehículo no registrado.")
                if confirmar("¿Registrar ahora? (s/n): "):
                    tipo = agregar_nuevo_vehiculo(placa_propuesta=placa, preguntar_tipo=True)
                    if not tipo:
                        print("Registro cancelado")
                        espera_animacion(0.6, "Volviendo")
                        registrar_evento('cobrar_peaje', f'Registro de placa {placa} cancelado')
                        return
                else:
                    tipo = input("Ingrese tipo de vehículo (vehiculo/moto/camion): ").strip().lower()
        else:
            tipo = input("Ingrese tipo de vehículo (vehiculo/moto/camion): ").strip().lower()
            placa = input("Ingrese placa (o 'N/A'): ").strip().upper() or 'N/A'
            if placa != 'N/A' and len(placa) > MAX_CARACTERES:
                print("Placa demasiado larga.")
                registrar_evento('cobrar_peaje', 'Placa demasiado larga')
                return
            if placa != 'N/A' and buscar_vehiculo_por_placa(placa):
                print(f"La placa {placa} ya está registrada. Usando el registro existente.")
                v = buscar_vehiculo_por_placa(placa)
                tipo = v.get('tipo')

        if not validar_tipo(tipo):
            print("Tipo inválido.")
            espera_animacion(0.6, "Cancelando")
            registrar_evento('cobrar_peaje', 'Tipo inválido ingresado')
            return

        tarifa = tarifas_peaje.get(tipo)
        if tarifa is None:
            print("No existe tarifa para ese tipo.")
            registrar_evento('cobrar_peaje', 'Tipo sin tarifa')
            return

        print(f"Tarifa para {tipo}: {tarifa} pesos")

        while True:
            try:
                pagado = int(input("Ingrese monto entregado por el conductor: ").strip())
                if pagado < 0:
                    print("El monto no puede ser negativo.")
                    continue
                break
            except ValueError:
                print("Ingrese un número entero válido.")
            except Exception:
                print("Error al leer el monto.")

        if pagado < tarifa:
            print("Monto insuficiente. Cobro no realizado.")
            espera_animacion(0.6, "Volviendo")
            registrar_evento('cobrar_peaje', f'Cobro no realizado para placa {placa}: monto insuficiente')
            return

        barra_progreso(20, 0.5, "Registrando cobro")
        vuelto = calcular_vuelto(pagado, tarifa)
        movimiento = {
            'fecha': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            'placa': placa[:MAX_CARACTERES],
            'tipo': tipo,
            'tarifa': tarifa,
            'pagado': pagado,
            'vuelto': vuelto
        }
        movimientos_peaje.append(movimiento)
        beep()
        print(f"Cobro registrado. Vuelto a entregar: {vuelto} pesos")
        registrar_evento('cobrar_peaje', f'Cobro registrado para placa {placa}, tarifa {tarifa}')
        input("Presione ENTER para volver al menú")
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
            print(centrar("Acceso denegado. Solo supervisor puede editar tarifas"))
            espera_animacion(0.8, "Volviendo")
            registrar_evento('ajustar_tarifas_peaje', 'Acceso denegado')
            return

        clave_confirm = getpass.getpass("Ingrese contraseña del supervisor para confirmar: ").strip()
        if clave_confirm != obtener_clave_operador('supervisor'):
            print("Contraseña incorrecta")
            espera_animacion(0.8, "Cancelando")
            registrar_evento('ajustar_tarifas_peaje', 'Contraseña incorrecta')
            return

        print("Tarifas actuales:")
        for k, v in tarifas_peaje.items():
            print(f" - {k}: {v} pesos")

        tipo = input("Tipo a ajustar (vehiculo/moto/camion): ").strip().lower()
        if not validar_tipo(tipo):
            print("Tipo inválido")
            espera_animacion(0.6, "Cancelando")
            registrar_evento('ajustar_tarifas_peaje', 'Tipo inválido al ajustar')
            return

        while True:
            try:
                nueva = int(input(f"Ingrese nueva tarifa para {tipo}: ").strip())
                if nueva < 0:
                    print("La tarifa no puede ser negativa.")
                    continue
                break
            except ValueError:
                print("Ingrese un número entero válido")
            except Exception:
                print("Error al leer la tarifa")

        if confirmar(f"Confirmar cambio de {tipo} a {nueva} pesos? (s/n): "):
            tarifas_peaje[tipo] = nueva
            barra_progreso(16, 0.6, "Aplicando cambio")
            print("Tarifa actualizada correctamente")
            registrar_evento('ajustar_tarifas_peaje', f'Tarifa de {tipo} cambiada a {nueva}')
        else:
            print("Operación cancelada")
            registrar_evento('ajustar_tarifas_peaje', 'Cambio de tarifa cancelado')
        input("ENTER para volver al menú")
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
            registrar_evento('ver_vehiculos_registrados', 'No hay vehículos registrados')
            espera_animacion(0.6, "Volviendo")
            return
        for v in vehiculos_registrados:
            print(f"Placa: {str(v.get('placa','-'))[:15]:15}  Tipo: {str(v.get('tipo','-'))[:10]:10}  Propietario: {v.get('propietario','-')}")
        linea()
        input("ENTER para volver al menú")
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
        if not tarifas_peaje:
            print(centrar("No hay tarifas definidas"))
            registrar_evento('mostrar_tarifas_peaje', 'No hay tarifas definidas')
            espera_animacion(0.6, "Volviendo")
            return
        for k, v in tarifas_peaje.items():
            print(f" - {k.capitalize():10} : {v} pesos")
        linea()
        input("ENTER para volver al menú")
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
            print(centrar("No hay movimientos para generar reporte"))
            registrar_evento('reporte_ingresos', 'No hay movimientos para generar reporte')
            espera_animacion(0.6, "Volviendo")
            return

        totales = {k: 0 for k in tarifas_peaje}
        conteo = {k: 0 for k in tarifas_peaje}
        total_general = 0

        for m in movimientos_peaje:
            t = m.get('tipo')
            if t in totales:
                totales[t] += int(m.get('tarifa', 0))
                conteo[t] += 1
                total_general += int(m.get('tarifa', 0))

        for k in totales:
            print(f"{k.capitalize():10} Recaudado: {totales[k]:8}  Pasos: {conteo[k]:3}")
        linea()
        print(f"Total general recaudado: {total_general} pesos")
        registrar_evento('reporte_ingresos', f'Reporte generado. Total: {total_general} pesos')
        input("ENTER para volver al menú")
    except Exception as e:
        registrar_evento('reporte_ingresos', f'Error: {e}')
        print("Error al generar reporte.")
        input("ENTER para volver")

def opcion_invalida():
    try:
        print("Opción inválida")
        time.sleep(0.8)
        registrar_evento('menu_principal', 'Opción inválida seleccionada')
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
            usuario = input("Nombre de operador: ").strip().lower()
            clave = getpass.getpass("Contraseña: ").strip()

            if not validar_texto_seguro(usuario, max_len=MAX_CARACTERES, permitir_espacios=False):
                print("Usuario inválido. Solo letras y números, máximo 15 caracteres.")
                intentos += 1
                continue

            if not validar_texto_seguro(clave, max_len=MAX_CARACTERES, permitir_espacios=False):
                print("Contraseña inválida. Solo letras y números, máximo 15 caracteres.")
                intentos += 1
                continue

            clave_almacenada = obtener_clave_operador(usuario)

            if clave_almacenada is not None and clave_almacenada == clave:
                operador_actual = usuario
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
                intentos += 1
                restante = MAX_INTENTOS_LOGIN - intentos
                print("Operador o contraseña incorrectos.")
                if restante:
                    print(f"Intentos restantes: {restante}")
                else:
                    print("Se han agotado los intentos.")
                time.sleep(1.0)

        registrar_evento('autenticar_garita', 'Autenticación fallida: se agotaron intentos')
        return False
    except Exception as e:
        registrar_evento('autenticar_garita', f'Error: {e}')
        print("Error en autenticación.")
        return False

# -------------------------
# Menú principal
# -------------------------
def menu_principal():
    try:
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

            if elec == '0':
                if confirmar("¿Desea salir del sistema? (s/n): "):
                    print("Cerrando sesión...")
                    espera_animacion(0.8, "Saliendo")
                    registrar_evento('menu_principal', 'Cierre de sesión por el operador')
                    break
                else:
                    continue

            accion = opciones_menu.get(elec)
            if accion and accion[1]:
                accion[1]()
            else:
                opcion_invalida()
    except Exception as e:
        registrar_evento('menu_principal', f'Error: {e}')
        print("Error en el menú principal.")

# -------------------------
# Entrada principal
# -------------------------
if __name__ == "__main__":
    if autenticar_garita():
        menu_principal()
    else:
        print("Acceso denegado. Fin del programa.")
        registrar_evento('main', 'Acceso denegado al iniciar el programa')