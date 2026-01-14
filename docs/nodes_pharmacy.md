# 1️⃣ Modelo de Nodos (State Machine Conversacional)

## 🧠 Concepto base

Cada nodo representa un estado lógico.

El usuario puede saltar de nodo en cualquier momento.

La transición puede darse por:
- Botón
- Texto libre (NLU / intent detection)

## 📌 Nodo START / IDENTIFY_USER

### Responsabilidad
- Detectar usuario por teléfono (Plex)
- Vincular `phone_number` → `account_id`

### Entradas
- Número de teléfono
- Texto libre inicial

### Salidas
- `MAIN_MENU`
- `CHANGE_ACCOUNT` (si hay múltiples cuentas)

## 📌 Nodo MAIN_MENU

### Mensaje
> Hola [Nombre] 👋
> Soy el asistente de [Farmacia].
> Podés escribirme o elegir una opción 👇

### Botones
- CONSULTAR_DEUDA
- PAGAR_DEUDA
- VER_OTRA_CUENTA

### Intenciones detectables
- consultar_deuda
- pagar_deuda
- ver_otra_cuenta
- info_farmacia
- pagar_monto

### Transiciones

| Intención / Botón | Nodo destino |
|-------------------|--------------|
| consultar_deuda | SHOW_DEBT |
| pagar_deuda | PAY_DEBT_MENU |
| pagar_monto | PARTIAL_PAYMENT |
| ver_otra_cuenta | CHANGE_ACCOUNT |
| info_farmacia | PHARMACY_INFO |

## 📌 Nodo SHOW_DEBT

### Responsabilidad
- Mostrar saldo total
- Mostrar resumen de facturas

### Botones
- VER_DETALLE_FACTURA
- PAGAR_DEUDA_COMPLETA
- PAGO_PARCIAL
- VOLVER_MENU

### Transiciones

| Acción | Nodo |
|--------|------|
| ver_detalle_factura | INVOICE_DETAIL |
| pagar_deuda_completa | FULL_PAYMENT |
| pago_parcial | PARTIAL_PAYMENT |
| volver | MAIN_MENU |

## 📌 Nodo INVOICE_DETAIL

### Responsabilidad
- Mostrar comprobante (sin medicamentos)

### Campos
- Número
- Fecha
- Monto

### Botones
- PAGAR_DEUDA
- VOLVER_DEUDA
- MENU_PRINCIPAL

## 📌 Nodo PAY_DEBT_MENU

### Responsabilidad
- Mostrar deuda resumida
- Elegir tipo de pago

### Botones
- PAGO_COMPLETO
- PAGO_PARCIAL
- MENU_PRINCIPAL

## 📌 Nodo FULL_PAYMENT

### Responsabilidad
- Confirmar monto total
- Generar link de pago

### Botones
- CONFIRMAR_PAGO
- CANCELAR
- MENU_PRINCIPAL

## 📌 Nodo PARTIAL_PAYMENT

### Responsabilidad
- Solicitar monto
- Validar monto
- Generar link

### Entradas
- Monto por texto o botón

### Botones
- CONFIRMAR
- CAMBIAR_MONTO
- MENU_PRINCIPAL

## 📌 Nodo CHANGE_ACCOUNT

### Responsabilidad
- Solicitar nueva cuenta
- Re-vincular contexto

### Transición
- Vuelve a MAIN_MENU

## 📌 Nodo PHARMACY_INFO

### Responsabilidad
- Mostrar info general de la farmacia

## 🔁 Transición Global (override)

Desde cualquier nodo, si se detecta intención:
- consultar_deuda
- pagar_deuda
- pagar_monto
- ver_otra_cuenta

➡️ se salta directamente al nodo correspondiente
