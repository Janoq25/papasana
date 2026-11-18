"""Alcance de datos por rol (filtrado por filas).

- todo:   todos los registros.
- region: parcelas cuyo ubigeo pertenece al departamento asignado al usuario (2 primeros dígitos).
- propio: parcelas creadas por el usuario o que tiene asignadas.
"""

from sqlalchemy import Select, false, func, or_, select

from app.models import Parcel, ParcelAssignment, User


def parcel_scope_clause(user: User):
    scope = user.role.data_scope
    if scope == "todo":
        return None
    if scope == "region":
        if not user.region_code:
            return false()
        return func.left(Parcel.region_code, 2) == user.region_code[:2]
    assigned = select(ParcelAssignment.parcel_id).where(ParcelAssignment.user_id == user.id)
    return or_(Parcel.created_by == user.id, Parcel.id.in_(assigned))


def apply_parcel_scope(stmt: Select, user: User) -> Select:
    clause = parcel_scope_clause(user)
    return stmt if clause is None else stmt.where(clause)


def can_access_parcel(db, user: User, parcel_id: int) -> bool:
    stmt = apply_parcel_scope(select(Parcel.id).where(Parcel.id == parcel_id), user)
    return db.scalar(stmt) is not None
