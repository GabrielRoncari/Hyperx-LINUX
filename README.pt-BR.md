# HyperX Linux

Painel de controle para **headsets, mouses, teclados e microfones HyperX no Linux**: bateria, mute e
monitoramento do microfone (sidetone), equalizador, desligamento automático, DPI, taxa de polling,
iluminação e mais. É um substituto não oficial do NGENUITY, que só existe para Windows.

[English](README.md) · [Aparelhos suportados](SUPPORTED.md) · [Como contribuir](CONTRIBUTING.md)

> Sem vínculo com a HP ou a HyperX. "HyperX" e "NGENUITY" são marcas da HP Inc., citadas aqui só para
> dizer com qual hardware o programa funciona.

## O que tem

- **App GTK 4 / libadwaita**: lista todos os aparelhos HyperX conectados e monta uma página de
  configurações para cada um a partir do seu driver.
- **Ícone na bandeja**: mostra a bateria e tem atalho para mutar o microfone.
- **Notificações**: bateria baixa, carga completa, microfone mutado, aparelho conectado ou desligado.
- **Linha de comando**: para scripts e barras de status.
- **`hyperx-linux diag`**: relatório só de leitura para anexar numa issue e ajudar a suportar
  aparelhos novos.

Tudo é aplicado direto no aparelho via `hidraw`. Nada roda como root.

## Aparelhos

São **55 drivers**, cobrindo:
- **headsets:** famílias Cloud III S/III/II/Alpha/Flight/Stinger;
- **mouses:** família Pulsefire Haste 2, Saga Pro, Dart, Haste Wireless, Surge, Core, Raid…;
- **teclados:** famílias Alloy Origins/Elite/Rise, Origins 2 65, Eve 1800;
- **outros:** QuadCast 2 / 2 S e Fury Ultra.

A tabela completa está em [SUPPORTED.md](SUPPORTED.md).

Cada driver tem um **nível de suporte**:
- **verified:** testado no aparelho pelos mantenedores.
- **community:** protocolo confirmado em hardware por outro projeto ou usuário.
- **experimental:** derivado do software oficial ou sem confirmação. Lê, mas **só altera
  configurações** depois de você ligar *Preferências → Permitir drivers experimentais* (ou usar
  `--experimental` no terminal).

## Instalar

Requisitos: Python 3.10+. Para a janela, GTK 4.12+ e libadwaita 1.5+ (Ubuntu 24.04, Fedora 39,
Debian 13, Arch ou mais novos).

```sh
sudo apt install python3-gi gir1.2-gtk-4.0 gir1.2-adw-1   # Debian, Ubuntu, Pop!_OS
git clone https://github.com/GabrielRoncari/Hyperx-LINUX.git
cd Hyperx-LINUX
./install.sh            # ou ./install.sh --no-autostart; para remover: ./install.sh --uninstall
```

## Usar

```sh
hyperx-linux                  # janela
hyperx-linux status           # todas as configurações
hyperx-linux set sidetone on
hyperx-linux set eq bass
hyperx-linux diag             # relatório para issue
```

## Segurança

Os drivers **nunca** mandam:
- atualização de firmware nem comandos de bootloader;
- reset de fábrica;
- gravações em flash/EEPROM.

Nos mouses, só o slot de RAM é usado. Na iluminação de teclados e microfones, só o modo "direto",
que é volátil.

**Atenção em alguns teclados:** no Alloy Origins, Elite 2 e Origins 60/65, o Linux só aceita os
comandos de luz pela interface do próprio teclado. Por isso, a regra udev também permite que
programas do seu usuário leiam as teclas digitadas nesse teclado. O OpenRGB tem a mesma limitação.

## O que não dá

- **Cancelamento ativo de ruído** em fones que não têm ANC de fábrica. No Cloud III S, a análise do
  firmware mostrou que o chip não tem o módulo
  ([docs/devices/cloud3s-firmware.md](docs/devices/cloud3s-firmware.md)).
- **DTS e o "Audio Engine" do NGENUITY:** são processamento no Windows, não no aparelho.
- **Ganho do microfone:** é controle de áudio USB normal; use as configurações de som do sistema.

## Licença

[GPL-3.0-or-later](LICENSE).
