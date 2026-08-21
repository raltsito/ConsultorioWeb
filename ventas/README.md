# Ventas y captación

## Descuento de captación

El descuento de captación está implementado y es permanente: corresponde al
25% para cualquier servicio cuando el paciente tiene una captación aprobada.
La regla se encuentra centralizada en `clinica/pricing.py`.

Los importes relacionados conservan significados distintos:

- `Servicio.precio` es el precio público vigente del servicio.
- `Cita.importe_servicio_snapshot` es el importe histórico del servicio después
  del descuento aplicable y constituye la base comisionable.
- `MovimientoEconomicoCita.importe` es el movimiento económico registrado. No
  necesariamente coincide con el precio público del servicio.

Sobre el importe histórico del servicio se aplica el porcentaje de comisión
aprobado por Dirección. Los snapshots y las comisiones históricas no se
recalculan cuando posteriormente cambia el precio público.

El saldo pendiente y el saldo a favor permanecen pendientes de definición
funcional; no forman parte de la implementación actual.
