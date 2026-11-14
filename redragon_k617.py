#!/usr/bin/env python3
"""
Redragon K617 Fizz RGB Controller
===================================
VID: 0x258A  PID: 0x0049  (SinoWealth chip)
Protocolo reverse-engineered del K621 (misma familia de chips).

Uso:
  python redragon_k617.py color 255 0 0           # Rojo
  python redragon_k617.py effect breathing --r 0 --g 255 --b 0
  python redragon_k617.py brightness 80
  python redragon_k617.py off
  python redragon_k617.py demo

Requisitos:
  pip install hid
  Ejecutar como Administrador en Windows.
"""

import hid
import time
import sys
import argparse

# ── Identificación del dispositivo ──────────────────────────────────────────
VID = 0x258A
PID = 0x0049

# ── Protocolo ───────────────────────────────────────────────────────────────
WRITE_REPORT_ID   = 0x06
WRITE_PACKET_SIZE = 1032   # bytes totales del paquete HID
QUERY_REPORT_ID   = 0x05
QUERY_PACKET_SIZE = 8

# Sub-comandos (byte[1]) y magic bytes (byte[2])
CMD_LED   = (0x03, 0xC6)
CMD_REMAP = (0x04, 0xD8)
CMD_MACRO = (0x05, 0xC5)   # ⚠ magic no verificado

# Marcadores de sincronía requeridos por el firmware
SYNC = (0x5A, 0xA5)

# Códigos de efecto (byte[21])
EFFECTS = {
    'off':        0x00,
    'static':     0x01,
    'breathing':  0x02,
    'wave':       0x03,
    'reactive':   0x04,
    'ripple':     0x05,
    'stars':      0x06,
    'neon':       0x07,
    'rain':       0x08,
    'shadow':     0x09,
    'custom':     0x20,   # per-key RGB
}


class RedragonK617:
    """Controlador principal del Redragon K617 Fizz."""

    def __init__(self):
        self.device = None

    # ── Conexión ─────────────────────────────────────────────────────────────

    def connect(self):
        """Busca la interfaz vendor (usage_page 0xFF00) y la abre."""
        devs = hid.enumerate(VID, PID)
        if not devs:
            raise RuntimeError(
                f"Teclado no encontrado (VID={VID:#06x} PID={PID:#06x}).\n"
                "  → ¿Está conectado?\n"
                "  → Ejecuta como Administrador en Windows."
            )

        # Preferir interfaz vendor (control de LEDs)
        target = next((d for d in devs if d.get('usage_page') == 0xFF00), None)
        if not target:
            target = next((d for d in devs if d.get('interface_number') == 1), None)
        if not target:
            target = devs[0]
            print("[WARN] Interfaz vendor no detectada; usando primera disponible.")

        self.device = hid.device()
        self.device.open_path(target['path'])
        self.device.set_nonblocking(1)
        name = target.get('product_string') or 'Redragon K617'
        print(f"[OK] Conectado: {name}")
        return self

    def disconnect(self):
        if self.device:
            self.device.close()
            self.device = None

    def __enter__(self):  return self.connect()
    def __exit__(self, *_): self.disconnect()

    # ── Construcción de paquetes ──────────────────────────────────────────────

    def _build_packet(self, subcmd: int, magic: int) -> bytearray:
        """Crea un paquete base de 1032 bytes con los marcadores de sincronía."""
        pkt = bytearray(WRITE_PACKET_SIZE)
        pkt[0] = WRITE_REPORT_ID
        pkt[1] = subcmd
        pkt[2] = magic
        # Tres marcadores de sincronía requeridos por el protocolo
        for base in (14, 78, 137):
            pkt[base]     = SYNC[0]
            pkt[base + 1] = SYNC[1]
        return pkt

    def _send(self, pkt: bytearray):
        """Envía el paquete vía HID write."""
        if not self.device:
            raise RuntimeError("No conectado. Llama a connect() primero.")
        result = self.device.write(bytes(pkt))
        if result < 0:
            raise RuntimeError(f"Error HID write: {self.device.error()}")
        time.sleep(0.05)
        return result

    # ── Control de LEDs ──────────────────────────────────────────────────────

    def set_effect(self, effect: str = 'static',
                   r: int = 255, g: int = 255, b: int = 255,
                   brightness: int = 70, speed: int = 50):
        """
        Aplica un efecto de iluminación.

        Args:
            effect:     Nombre del efecto (ver EFFECTS).
            r, g, b:    Color base 0-255.
            brightness: Brillo 0-100.
            speed:      Velocidad 0-100 (100 = más rápido).
        """
        if effect not in EFFECTS:
            raise ValueError(f"Efecto desconocido '{effect}'. Opciones: {list(EFFECTS)}")

        brt = int(max(0, min(100, brightness)) / 100 * 0x7F)
        spd = int((1 - max(0, min(100, speed)) / 100) * 0xFF)

        pkt = self._build_packet(*CMD_LED)
        pkt[21] = EFFECTS[effect]
        pkt[22] = brt
        pkt[28] = spd & 0xFF
        pkt[29] = (spd >> 8) & 0xFF
        pkt[36] = r & 0xFF
        pkt[37] = g & 0xFF
        pkt[38] = b & 0xFF

        self._send(pkt)
        print(f"[LED] {effect.upper():12s} RGB=({r:3},{g:3},{b:3})  "
              f"Brillo={brightness}%  Velocidad={speed}%")

    def set_color(self, r: int, g: int, b: int, brightness: int = 70):
        """Atajo: color estático."""
        self.set_effect('static', r, g, b, brightness)

    def set_brightness(self, level: int):
        """Ajusta solo el brillo (0-100) manteniendo color blanco."""
        self.set_effect('static', 255, 255, 255, level)

    def off(self):
        """Apaga todos los LEDs."""
        self.set_effect('off')

    def set_per_key_rgb(self, key_colors: dict):
        """
        Iluminación per-tecla personalizada.

        Args:
            key_colors: {indice_tecla: (r, g, b)}
                        Índices 0-61 para layout 60%.
                        ⚠ Mapeo de índices NO verificado en K617.
        """
        pkt = self._build_packet(*CMD_LED)
        pkt[21] = EFFECTS['custom']
        pkt[22] = 0x7F  # brillo máximo en modo custom

        for idx, (r, g, b) in key_colors.items():
            if 0 <= idx <= 61:
                off = 106 + idx * 3
                if off + 2 < WRITE_PACKET_SIZE:
                    pkt[off]     = r & 0xFF
                    pkt[off + 1] = g & 0xFF
                    pkt[off + 2] = b & 0xFF

        self._send(pkt)
        print(f"[LED] Per-key RGB: {len(key_colors)} teclas configuradas  ⚠ índices no verificados")

    # ── Remapeo de teclas ────────────────────────────────────────────────────

    def remap_key(self, original_hid: int, replacement_hid: int):
        """
        Remapea una tecla.
        ⚠ ADVERTENCIA: Formato de paquete NO verificado en hardware.
                        Puede resetear el teclado si los bytes 96-105 son incorrectos.

        Args:
            original_hid:    Código HID original  (ej. 0x04 = tecla A)
            replacement_hid: Código HID de destino (ej. 0x05 = tecla B)
        """
        print("[WARN] remap_key: protocolo NO verificado. Úsalo bajo tu riesgo.")
        pkt = self._build_packet(*CMD_REMAP)
        # Entrada de mapeo: 4 bytes [original, replacement, 0x00, 0x00]
        # ⚠ Offset exacto dentro de la matriz de 1024 bytes está sin confirmar
        pkt[3] = original_hid
        pkt[4] = replacement_hid
        pkt[5] = 0x00
        pkt[6] = 0x00
        self._send(pkt)
        print(f"[REMAP] HID {original_hid:#04x} → {replacement_hid:#04x}")

    # ── Macros ───────────────────────────────────────────────────────────────

    def program_macro(self, slot: int, actions: list):
        """
        Programa una macro en un slot de memoria.
        ⚠ ADVERTENCIA: Formato de paquete NO verificado en hardware.

        Args:
            slot:    0-11 (12 slots disponibles).
            actions: Lista de dicts:
                     {'hid': 0x04, 'down': True, 'delay_ms': 50}
                     'down'=True  → tecla presionada
                     'down'=False → tecla soltada
        """
        if not 0 <= slot <= 11:
            raise ValueError("Slot debe ser 0-11")
        print(f"[WARN] program_macro: protocolo NO verificado. Úsalo bajo tu riesgo.")

        pkt = self._build_packet(*CMD_MACRO)
        pkt[3] = slot & 0xFF

        offset = 4
        for action in actions[:32]:
            if offset + 4 >= WRITE_PACKET_SIZE:
                break
            pkt[offset]     = action.get('hid', 0) & 0xFF
            pkt[offset + 1] = 0x00 if action.get('down', True) else 0x01
            delay = action.get('delay_ms', 50)
            pkt[offset + 2] = delay & 0xFF
            pkt[offset + 3] = (delay >> 8) & 0xFF
            offset += 4

        self._send(pkt)
        print(f"[MACRO] Slot {slot}: {len(actions)} acciones programadas")

    # ── Demos ─────────────────────────────────────────────────────────────────

    def demo_colors(self, pause: float = 1.5):
        """Cicla por varios colores para verificar que el controlador funciona."""
        colors = [
            ("Rojo",     255,   0,   0),
            ("Verde",      0, 255,   0),
            ("Azul",       0,   0, 255),
            ("Cyan",       0, 255, 255),
            ("Magenta",  255,   0, 255),
            ("Amarillo", 255, 255,   0),
            ("Blanco",   255, 255, 255),
        ]
        print("[DEMO] Iniciando ciclo de colores...")
        for name, r, g, b in colors:
            print(f"  {name}")
            self.set_color(r, g, b)
            time.sleep(pause)
        print("[DEMO] Finalizado.")

    def demo_effects(self, pause: float = 3.0):
        """Muestra todos los efectos disponibles."""
        print("[DEMO] Recorriendo efectos...")
        for name in EFFECTS:
            if name in ('off', 'custom'):
                continue
            print(f"  {name}")
            self.set_effect(name, r=0, g=150, b=255, brightness=80, speed=60)
            time.sleep(pause)
        print("[DEMO] Finalizado.")


# ── CLI ──────────────────────────────────────────────────────────────────────

def build_parser():
    p = argparse.ArgumentParser(
        prog='redragon_k617',
        description='Controlador RGB para Redragon K617 Fizz',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos:
  python redragon_k617.py color 255 0 0
  python redragon_k617.py color 0 255 128 --brightness 90
  python redragon_k617.py effect breathing --r 255 --g 100 --b 0 --speed 40
  python redragon_k617.py effect wave
  python redragon_k617.py brightness 50
  python redragon_k617.py off
  python redragon_k617.py demo colors
  python redragon_k617.py demo effects
""")
    sub = p.add_subparsers(dest='cmd', metavar='COMANDO')

    # color
    pc = sub.add_parser('color', help='Color estático RGB')
    pc.add_argument('r', type=int, metavar='R', help='Rojo 0-255')
    pc.add_argument('g', type=int, metavar='G', help='Verde 0-255')
    pc.add_argument('b', type=int, metavar='B', help='Azul 0-255')
    pc.add_argument('--brightness', type=int, default=70, metavar='N',
                    help='Brillo 0-100 (default: 70)')

    # effect
    pe = sub.add_parser('effect', help='Efecto de iluminación')
    pe.add_argument('name', choices=list(EFFECTS.keys()), metavar='NOMBRE')
    pe.add_argument('--r', type=int, default=0,   help='Rojo 0-255')
    pe.add_argument('--g', type=int, default=150, help='Verde 0-255')
    pe.add_argument('--b', type=int, default=255, help='Azul 0-255')
    pe.add_argument('--brightness', type=int, default=70)
    pe.add_argument('--speed',      type=int, default=50)

    # brightness
    pb = sub.add_parser('brightness', help='Ajustar solo brillo')
    pb.add_argument('level', type=int, metavar='N', help='0-100')

    # off
    sub.add_parser('off', help='Apagar LEDs')

    # demo
    pd = sub.add_parser('demo', help='Demos visuales')
    pd.add_argument('tipo', choices=['colors', 'effects'],
                    nargs='?', default='colors')

    return p


def main():
    parser = build_parser()
    args = parser.parse_args()

    if not args.cmd:
        parser.print_help()
        sys.exit(0)

    try:
        with RedragonK617() as kbd:
            if args.cmd == 'color':
                kbd.set_color(args.r, args.g, args.b, args.brightness)
            elif args.cmd == 'effect':
                kbd.set_effect(args.name, args.r, args.g, args.b,
                               args.brightness, args.speed)
            elif args.cmd == 'brightness':
                kbd.set_brightness(args.level)
            elif args.cmd == 'off':
                kbd.off()
            elif args.cmd == 'demo':
                if args.tipo == 'colors':
                    kbd.demo_colors()
                else:
                    kbd.demo_effects()

    except RuntimeError as e:
        print(f"\n[ERROR] {e}")
        sys.exit(1)
    except KeyboardInterrupt:
        print("\n[Interrumpido]")
    except Exception as e:
        print(f"\n[ERROR inesperado] {e}")
        import traceback; traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
