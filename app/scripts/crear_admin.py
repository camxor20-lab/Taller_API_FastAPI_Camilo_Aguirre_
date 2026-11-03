import getpass
import sys
from sqlalchemy import func, select
from app.core.database import SessionLocal
from app.core.security import hashear_password
from app.models.usuario import RolUsuario, Usuario


def crear_primer_admin():
    print("=== Creación del Primer Administrador ===")
    if not sys.stdin.isatty():
        line = sys.stdin.readline()
        email = line.strip().lower()
    else:
        email = input("Email: ").strip().lower()

    if not email:
        print("El email es obligatorio.")
        return

    with SessionLocal() as db:
        existente = db.scalar(
            select(Usuario).where(func.lower(Usuario.email) == email)
        )
        if existente:
            print(f"El usuario con email '{email}' ya existe. No se realizaron cambios.")
            return

        if not sys.stdin.isatty():
            nombre = sys.stdin.readline().strip().title()
        else:
            nombre = input("Nombre completo: ").strip().title()

        if not nombre:
            print("El nombre es obligatorio.")
            return

        if not sys.stdin.isatty():
            password = sys.stdin.readline().strip()
        else:
            password = getpass.getpass("Contraseña: ")

        if len(password) < 8:
            print("La contraseña debe tener al menos 8 caracteres.")
            return

        nuevo_admin = Usuario(
            email=email,
            nombre=nombre,
            password_hash=hashear_password(password),
            rol=RolUsuario.admin,
            activo=True,
            intentos_fallidos=0,
            bloqueado_hasta=None,
            socio_id=None
        )
        db.add(nuevo_admin)
        db.commit()
        print(f"¡Administrador '{email}' creado exitosamente!")


if __name__ == "__main__":
    crear_primer_admin()
