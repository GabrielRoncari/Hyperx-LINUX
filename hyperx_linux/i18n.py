"""Tiny translation table: English in the code, other languages here.

Add a language by adding a dict and a prefix in LANGS. Missing keys fall back to English.
"""
from __future__ import annotations

import os

PT_BR = {
    # groups
    "Battery": "Bateria",
    "Microphone": "Microfone",
    "Audio": "Áudio",
    "Lighting": "Iluminação",
    "Performance": "Desempenho",
    "Power": "Energia",
    "System": "Sistema",
    "Device": "Dispositivo",
    "Preferences": "Preferências",
    # headset controls
    "Mute microphone": "Mutar microfone",
    "Same as the button on the headset": "O mesmo que o botão no fone",
    "Microphone monitoring": "Monitoramento do microfone",
    "Hear your own voice (sidetone)": "Ouvir a própria voz no fone (sidetone)",
    "Monitoring volume": "Volume do monitoramento",
    "Mute audio": "Mutar áudio",
    "Silences the headset speakers": "Silencia os alto-falantes do fone",
    "Equalizer": "Equalizador",
    "Automatic power off": "Desligar automaticamente",
    "After this much silence": "Após ficar em silêncio por esse tempo",
    "After this much inactivity": "Após ficar inativo por esse tempo",
    "Never": "Nunca",
    "Voice prompts": "Avisos de voz",
    "Headset voice on power on, mute, low battery": "Voz do fone ao ligar, mutar, bateria fraca",
    "Color": "Cor",
    "Firmware": "Firmware",
    "Custom": "Personalizado",
    "Factory (not changed yet)": "De fábrica (ainda não alterado)",
    "Re-applied on reconnect": "Reaplicado ao reconectar",
    "Flat": "Plano",
    "Bass": "Graves",
    "Treble": "Agudos",
    "V-shape": "V",
    "Voice": "Voz",
    # lighting / performance
    "Brightness": "Brilho",
    "Effect": "Efeito",
    "Static": "Estático",
    "Breathing": "Respiração",
    "Spectrum cycle": "Ciclo de cores",
    "Wave": "Onda",
    "Off": "Desligado",
    "Polling rate": "Taxa de polling",
    "DPI": "DPI",
    "Game mode": "Modo jogo",
    "Disables the Windows key": "Desativa a tecla Windows",
    "Microphone gain": "Ganho do microfone",
    # status / app
    "Connected": "Conectado",
    "Charging": "Carregando",
    "Fully charged": "Carga completa",
    "Discharging": "Descarregando",
    "Headset off": "Fone desligado",
    "Device off or out of range": "Aparelho desligado ou fora de alcance",
    "The receiver is connected. Turn the device on or bring it closer.":
        "O receptor está conectado. Ligue o aparelho ou aproxime-o.",
    "No HyperX device found": "Nenhum aparelho HyperX encontrado",
    "Plug in a HyperX headset, receiver, mouse, keyboard or microphone.":
        "Conecte um headset, receptor, mouse, teclado ou microfone HyperX.",
    "Reading…": "Lendo…",
    "Devices": "Aparelhos",
    "Refresh": "Reler",
    "About": "Sobre",
    "Quit": "Sair",
    "Open": "Abrir",
    "Show in tray only": "Iniciar só na bandeja",
    "Desktop notifications": "Notificações na área de trabalho",
    "Notify when the microphone is muted": "Avisar ao mutar o microfone",
    "Low battery warning (%)": "Avisar bateria baixa em (%)",
    "Allow experimental drivers": "Permitir drivers experimentais",
    "Lets drivers that nobody has tested on real hardware change settings":
        "Deixa drivers que ninguém testou em hardware real mudarem configurações",
    "Not supported yet": "Ainda sem suporte",
    "Run “hyperx-linux diag” and open an issue with the output to help add it.":
        "Rode “hyperx-linux diag” e abra uma issue com a saída para ajudar a adicionar.",
    "Tested on real hardware": "Testado em hardware real",
    "Confirmed by the community, not tested by the maintainers":
        "Confirmado pela comunidade, não testado pelos mantenedores",
    "Experimental: not confirmed on real hardware, changes are disabled":
        "Experimental: não confirmado em hardware real, alterações desativadas",
    "Experimental: not confirmed on real hardware": "Experimental: não confirmado em hardware real",
    "Report results": "Relatar resultado",
    "Low battery: {level}%": "Bateria baixa: {level}%",
    "Charge it soon.": "Coloque para carregar.",
    "Microphone muted": "Microfone mutado",
    "Microphone on": "Microfone ativo",
    "{name} connected": "{name} conectado",
    "{name} disconnected": "{name} desconectado",
    "Battery {level}%": "Bateria {level}%",
    "charging": "carregando",
    "mic muted": "mic mutado",
    "No permission to access the device": "Sem permissão para acessar o aparelho",
    "Install the udev rules: run install.sh or see the README.":
        "Instale as regras udev: rode install.sh ou veja o README.",
    "Linux control panel for HyperX peripherals (unofficial).":
        "Painel de controle para periféricos HyperX no Linux (não oficial).",
    "Interface": "Interface",
    "Model": "Modelo",
    "Driver": "Driver",
    "Receiver": "Receptor",
    "Charging/firmware interface: use the receiver": "Interface de carga/firmware: use o receptor",
    'Kept while the app runs': 'Mantida enquanto o app estiver aberto',
    'Current DPI stage': 'Estágio de DPI atual',
    'DPI stage': 'Estágio de DPI',
    'Lift-off distance': 'Distância de lift-off',
    'Game / chat balance': 'Equilíbrio jogo / chat',
    '−5 all game, +5 all chat': '−5 só jogo, +5 só chat',
    'Equalizer preset': 'Preset do equalizador',
    'Preset 1': 'Preset 1',
    'Preset 2': 'Preset 2',
    'Preset 3': 'Preset 3',
    'Noise gate': 'Noise gate',
    'Cuts background noise when you are not talking': 'Corta o ruído de fundo quando você não está falando',
    'Use the button on the headset': 'Use o botão do fone',
    'Flip the microphone up to mute': 'Levante o microfone para mutar',
    'Estimated from the battery voltage': 'Estimada pela tensão da bateria',
    'Only the voltage is known for this model': 'Neste modelo só a tensão é conhecida',
    'Noise cancelling': 'Cancelamento de ruído',
    'On': 'Ligado',
    'Transparency': 'Transparência',
    'LED brightness': 'Brilho do LED',
    'USB': 'USB',
    'Firmware update mode: not opened': 'Modo de atualização de firmware: não é aberto',
    'HyperX device': 'Aparelho HyperX',
}

LANGS = (("pt", PT_BR),)


def _pick() -> dict[str, str]:
    for var in ("LANGUAGE", "LC_ALL", "LC_MESSAGES", "LANG"):
        value = os.environ.get(var, "")
        if value:
            lang = value.split(":")[0].lower()
            for prefix, table in LANGS:
                if lang.startswith(prefix):
                    return table
            return {}
    return {}


_TABLE = _pick()


def number(value: float, digits: int = 2) -> str:
    """Decimal with the locale's separator (comma in Portuguese)."""
    text = f"{value:.{digits}f}"
    return text.replace(".", ",") if _TABLE is PT_BR else text


def _(text: str, **kw) -> str:
    out = _TABLE.get(text, text)
    return out.format(**kw) if kw else out
