# Sistema de Peaje - Garita

Un sistema de peaje de consola pensado para operar con orden, control y seguridad. Esta version centraliza el acceso por roles, protege la autenticacion con MFA y guarda la informacion sensible cifrada por usuario.

## Lo que hace

- Control de acceso por roles directamente desde el menu.
- MFA con TOTP y configuracion mediante QR.
- Persistencia cifrada por usuario para datos sensibles.
- Backup codes, proteccion contra replay y rate limiting.
- Consulta de movimientos, vehiculos, tarifas y reportes del dia.

## Por que importa

Este proyecto no busca solo "funcionar". Busca dejar trazabilidad, evitar accesos improvisados y mantener la operacion mas limpia cuando el sistema crece o cuando varios usuarios lo usan al mismo tiempo.

## Requisitos

- Python 3.10 o superior.
- Dependencias instaladas desde `requirements.txt`.

## Instalacion

```bash
pip install -r requirements.txt
```

## Ejecucion

```bash
python PeajeV3.0.py
```

## Estructura del proyecto

- `PeajeV3.0.py`: programa principal.
- `requirements.txt`: dependencias del proyecto.
- `mfa_users/`: datos cifrados de usuarios MFA.
- `01_peaje.py` a `27_ySistema_peajeVillarV4.py`: historial ordenado de la primera version hasta las mas recientes.
- `srv/`: estructura auxiliar del sistema.

## Historial de versiones

El orden del historial en GitHub empieza en `01_peaje.py`, que viene de `peajev1/peaje.py`, y sigue con las versiones posteriores numeradas para que la evolucion del proyecto se vea de forma clara y cronologica.

## Detalles a tener en cuenta

- No subas al repositorio claves locales, archivos temporales ni datos generados en ejecucion.
- Si quieres ajustar el almacenamiento o la seguridad, revisa las variables de entorno al inicio de `PeajeV3.0.py`.

## En resumen

Si lo que quieres es un peaje con una capa de seguridad seria y una base clara para seguir creciendo, este es el punto de partida.