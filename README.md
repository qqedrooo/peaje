# Sistema de Peaje - Garita

Aplicacion de consola para gestion de peaje con control de acceso por roles, autentificacion MFA, persistencia cifrada por usuario y registro de eventos.

## Caracteristicas

- Control de acceso por roles en el menu.
- Autenticacion MFA con TOTP y opcion de configuracion QR.
- Persistencia por usuario en ficheros cifrados.
- Backup codes, proteccion contra replay y rate limiting.
- Reportes y consulta de movimientos, vehiculos y tarifas.

## Requisitos

- Python 3.10 o superior.
- Dependencias instaladas desde `requirements.txt`.

## Instalacion

```bash
pip install -r requirements.txt
```

## Ejecucion

```bash
python v11.py
```

## Estructura

- `v11.py`: programa principal.
- `requirements.txt`: dependencias del proyecto.
- `mfa_users/`: datos cifrados de usuarios MFA.
- `srv/`: estructura auxiliar del sistema.

## Notas

- No subas al repositorio las claves locales ni archivos temporales generados en ejecucion.
- Si quieres cambiar el almacenamiento o los parametros de seguridad, revisa las variables de entorno definidas al inicio de `v11.py`.