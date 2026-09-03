# Ventas y captación

## Captación, beneficios y comisiones

La existencia de una `Captacion` no modifica automáticamente `Cita.costo`.
`Cita.costo` es un importe administrativo y manual que conserva el valor
capturado por el usuario.

Los beneficios o descuentos informativos vigentes se resuelven mediante
`ReglaBeneficioReferido` y `clinica/services_beneficios.py`, de acuerdo con las
reglas configuradas. El porcentaje de beneficio es independiente de
`CodigoCaptacion.porcentaje_comision` y no debe confundirse con él.

La generación formal de comisiones no utiliza
`Cita.importe_servicio_snapshot` como base vigente. La base formal procede de
`CobroCita.importe_esperado`, conforme al flujo formal de pagos y comisiones.

El saldo pendiente y el saldo a favor permanecen pendientes de definición
funcional; no forman parte de la implementación actual.
