# Redragon K617 Fizz - Controlador RGB Python

Controlador de efectos LED para el teclado Redragon K617 Fizz (parte del combo S143).

## Hardware
- **Teclado**: Redragon K617 Fizz (60%, RGB, hot-swap, switches Red)
- **Chip**: SinoWealth
- **VID**: 0x258A | **PID**: 0x0049

## Requisitos
```
pip install hidapi
```
> En Windows: instalar Zadig y reemplazar driver de MI_01 con WinUSB

## Uso
```python
python redragon_k617.py
```

## Efectos soportados
| Código | Efecto |
|--------|--------|
| 0x00 | Apagado |
| 0x01 | Estático |
| 0x02 | Respiración |
| 0x03 | Ola |
| 0x04 | Reactivo |
| 0x05 | Ripple |
| 0x06 | Estrellas |
| 0x07 | Neon |
| 0x08 | Lluvia |
| 0x09 | Sombra |
| 0x20 | Custom (por tecla) |

## Protocolo HID
- Paquetes de 1032 bytes, Report ID 0x06
- Sync markers (0x5A 0xA5) en offsets 14, 78, 137
- Interfaz objetivo: MI_01 (vendor config)

## Estado
Proyecto en pausa. Driver WinUSB necesario para evitar bloqueo de Windows en interfaz HID.

## Fecha
2026-11-13
