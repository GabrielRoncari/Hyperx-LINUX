# HyperX Linux

Painel de controle para **headsets, mouses, teclados e microfones HyperX no Linux**: bateria, mute e
monitoramento do microfone (sidetone), equalizador, desligamento automático, DPI, taxa de polling,
iluminação e mais. É um substituto não oficial do NGENUITY, que só existe para Windows.

[English](README.md) · [Aparelhos suportados](SUPPORTED.md) · [Como contribuir](CONTRIBUTING.md)

> Sem vínculo com a HP ou a HyperX. "HyperX" e "NGENUITY" são marcas da HP Inc., citadas aqui só para
> dizer com qual hardware o programa funciona.

## O que tem

- **App GTK 4 / libadwaita** com a cara do NGENUITY 3: barra lateral com cada aparelho e suas funções,
  uma prévia ao vivo do aparelho (o teclado mostra a luz que está mostrando) e um painel de funções
  embaixo (Iluminação, Teclas, Áudio, Áudio espacial, Botões, Configurações). Cada página é montada a
  partir do driver do aparelho.
- **Ícone na bandeja**: mostra a bateria e tem atalho para mutar o microfone.
- **Notificações**: bateria baixa, carga completa, microfone mutado, aparelho conectado ou desligado.
- **Motor de áudio para headsets**, a versão Linux do que o NGENUITY faz: áudio espacial 7.1 virtual,
  equalizador por software e processamento de voz no microfone (redução de ruído e eco, passa-altas,
  as predefinições de microfone do NGENUITY), feito no computador pelo PipeWire
  ([docs/audio.md](docs/audio.md)).
- **Outras ações para os botões do headset**: o botão multifunção (1, 2 ou 3 toques), o volume e o
  mudo podem disparar um atalho, uma tecla de mídia, um macro, um comando, ou ligar/desligar o
  microfone, o monitoramento ou o áudio espacial. O NGENUITY só oferece isso no Cloud Alpha 2; aqui
  funciona em todo headset cujos botões chegam ao computador como teclas de mídia.
- **Linha de comando**: para scripts e barras de status.
- **`hyperx-linux diag`**: relatório só de leitura para anexar numa issue e ajudar a suportar
  aparelhos novos.

Tudo é aplicado direto no aparelho via `hidraw`, e o motor de áudio pelo PipeWire. Nada roda como
root.

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

O **Alloy Origins 65** tem tudo o que o NGENUITY oferece para ele:
- os 14 efeitos de iluminação: estático, respiração, ciclo de cores, onda, alternado, varredura,
  confete, sol, crepúsculo, empilhar, ampulheta e os reativos esmaecer, explosão, implosão e chama
  HyperX;
- salvar a iluminação no teclado para funcionar sem o app, e brilho;
- modo jogo com bloqueio de Alt+Tab / Alt+F4 / Shift+Tab / Ctrl+Esc;
- remapeamento de teclas (inclusive com Fn) e teclas de Fn lock;
- macros gravados no teclado, que você também pode gravar digitando;
- como no NGENUITY, a página **desenha o teclado**: dá para pintar as teclas com cores próprias (por
  exemplo o teclado todo vermelho e o WASD verde, ou uma onda com o WASD fixo) e clicar numa tecla
  para escolher o que ela faz.

O **Alloy Origins 60**, o **Alloy Origins** e o **Alloy Elite 2** têm as mesmas funções, cada um com o
protocolo do seu módulo no NGENUITY. A iluminação deles foi confirmada por outros projetos; o que
grava na memória do teclado fica experimental até alguém confirmar.

## Instalar

Uma linha, em qualquer distro com GTK 4 (Ubuntu 22.04+, Debian 12+, Fedora, Arch, openSUSE,
Pop!_OS, Mint 21+, Void, Alpine…):

```sh
curl -fsSL https://raw.githubusercontent.com/GabrielRoncari/Hyperx-LINUX/main/install.sh | sh
```

Só isso: ele baixa o app, instala o que falta pelo gerenciador de pacotes da distro (Python,
PyGObject, GTK 4, libadwaita), as regras udev, o comando `hyperx-linux`, o atalho no menu e a
entrada que abre o app na bandeja ao entrar. Pede a senha uma vez (`sudo`, `doas` ou `run0`). Rode a
mesma linha de novo para atualizar, ou termine com `| sh -s -- --uninstall` para remover tudo.

Daí em diante os aparelhos são plug and play. Se algum aparecer como *Sem permissão* (por exemplo, um
aparelho que uma versão nova passou a suportar), clique em *Permitir acesso* na página dele: o app
pede a sua senha na janela do sistema e o aparelho aparece em instantes.

| Seu sistema | Como |
|---|---|
| Ubuntu 22.04+, Debian 12+, Fedora, Arch/Manjaro, openSUSE Tumbleweed, Pop!_OS, Mint 21+, Void, Alpine, Solus… | a linha acima, ou o [install.sh de um clone](#a-partir-de-um-clone) |
| Gentoo | instale os pacotes abaixo você mesmo e depois rode o install.sh |
| Debian 11, Ubuntu 20.04 e outros sem GTK 4 | [Flatpak](#com-flatpak) para a janela (o install.sh ainda instala a linha de comando) |
| Fedora Silverblue/Kinoite, Bazzite, SteamOS e outros sistemas imutáveis | [Flatpak](#com-flatpak) |
| NixOS | o install.sh mostra a linha para pôr no `configuration.nix` |

### A partir de um clone

```sh
git clone https://github.com/GabrielRoncari/Hyperx-LINUX.git
cd Hyperx-LINUX
./install.sh            # opções: --no-autostart, --no-deps, --uninstall
```

O `install.sh` é `sh` POSIX puro (bash, dash, BusyBox). Com `--no-deps` ele não mexe nos seus
pacotes; estes são os que ele instalaria (só a linha de comando precisa apenas de Python 3.8+):

```sh
sudo apt install python3-gi python3-gi-cairo gir1.2-gtk-4.0 gir1.2-adw-1     # Debian, Ubuntu, Pop!_OS, Mint
sudo dnf install python3-gobject python3-cairo gobject-introspection gtk4 libadwaita   # Fedora
sudo pacman -S python-gobject python-cairo gtk4 libadwaita                   # Arch, Manjaro, EndeavourOS
sudo zypper install python313-gobject python313-gobject-cairo typelib-1_0-Gtk-4_0 typelib-1_0-Adw-1   # openSUSE (python3XX = seu Python)
sudo xbps-install python3-gobject python3-cairo gtk4 libadwaita              # Void
doas apk add py3-gobject3 py3-cairo gtk4.0 libadwaita                        # Alpine
emerge dev-python/pygobject dev-python/pycairo gui-libs/gtk gui-libs/libadwaita  # Gentoo
```

Para usar num virtualenv, o [requirements.txt](requirements.txt) lista os pacotes Python (GTK 4 e
libadwaita continuam vindo da distro; o arquivo explica os detalhes).

**Sem systemd** (Void, Artix, Devuan, Gentoo com OpenRC, Alpine…) a tag `uaccess` não funciona, então
o install.sh cria o grupo `hyperx`, coloca você nele e escreve as regras para esse grupo. Saia e
entre de novo na sessão depois.

### Com Flatpak

Baixe o `hyperx-linux.flatpak` na página de [Releases](https://github.com/GabrielRoncari/Hyperx-LINUX/releases)
e instale (o runtime do GNOME vem do Flathub):

```sh
flatpak remote-add --user --if-not-exists flathub https://dl.flathub.org/repo/flathub.flatpakrepo
flatpak install --user hyperx-linux.flatpak
```

Um Flatpak não consegue instalar regras udev sozinho, então rode isto uma vez (o app também mostra
esse comando quando está sem permissão):

```sh
flatpak run io.github.gabrielroncari.HyperXLinux udev-rules | sudo tee /etc/udev/rules.d/70-hyperx-linux.rules
sudo udevadm control --reload-rules && sudo udevadm trigger --subsystem-match=hidraw --action=change
```

Sem systemd, use `udev-rules --group hyperx` e entre no grupo
(`sudo groupadd -r hyperx && sudo usermod -aG hyperx $USER`).

O instalador foi testado de verdade, instalando as dependências, no Debian 12, Ubuntu 22.04, Fedora, openSUSE Tumbleweed, Arch, Void e Alpine 3.20. Testado com Python 3.8 a 3.14 e com GTK/libadwaita 4.6/1.1 (Ubuntu 22.04), 4.8/1.2 (Debian 12),
4.12/1.4 (openSUSE Leap 15.6, RHEL 9) e 4.22/1.9 (versões atuais). Em bibliotecas mais antigas
alguns widgets são mais simples, mas as funções são as mesmas.

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
- gravações na memória do aparelho que você não pediu.

Nos mouses, só o slot de RAM é usado. Na iluminação, só o modo "direto", que é volátil. A exceção é a família
**Alloy Origins**: quando você salva a iluminação, remapeia teclas, cria macros ou muda o modo jogo, o
teclado grava isso nos próprios perfis com os mesmos comandos do NGENUITY (testados num Origins 65;
experimentais no Origins 60, Origins e Elite 2). O 60 e o 65 têm o botão *Restaurar configurações de
fábrica*.

**Botões do headset:** para dar outra ação a um botão, o app lê o dispositivo de entrada do próprio
headset (só as teclas de mídia dele) e o segura enquanto houver botão remapeado. Ele também usa o
`uinput` para repassar os outros botões e digitar as teclas escolhidas. As regras udev liberam os
dois. O `uinput` deixa programas do usuário logado criarem teclados virtuais, a mesma regra que o
Steam instala. Se não quiser, apague a linha do `uinput` em `/etc/udev/rules.d/70-hyperx-linux.rules`:
as ações que digitam teclas e o repasse do volume param, comandos e liga/desliga continuam.

**Atenção em alguns teclados:** no Alloy Origins, Elite 2 e Origins 60/65, o Linux só aceita os
comandos de luz pela interface do próprio teclado. Por isso, a regra udev também permite que
programas do seu usuário leiam as teclas digitadas nesse teclado. O OpenRGB tem a mesma limitação.

## O que não dá

- **Cancelamento ativo de ruído** em fones que não têm ANC de fábrica. No Cloud III S, a análise do
  firmware mostrou que o chip não tem o módulo
  ([docs/devices/cloud3s-firmware.md](docs/devices/cloud3s-firmware.md)).
- **DTS Headphone:X e HEAR360 SONAMI**, que fazem o áudio espacial do NGENUITY, são licenciados por
  produto. O motor de áudio daqui faz o mesmo trabalho com medições abertas de uma cabeça artificial
  (MIT KEMAR), então o som é diferente ([docs/audio.md](docs/audio.md)).
- **Ganho do microfone:** é controle de áudio USB normal; use as configurações de som do sistema.

## Créditos

A interface segue o layout e a paleta do NGENUITY 3.1 (lidos do XAML compilado dele; nenhuma arte da
HP está incluída) e usa a fonte [Exo 2](https://github.com/googlefonts/Exo-2.0) (SIL Open Font
License). O áudio espacial usa as medições MIT KEMAR de Bill Gardner e Keith Martin (1995). Os
protocolos têm as fontes citadas em cada driver e em [docs/devices](docs/devices).

## Licença

[GPL-3.0-or-later](LICENSE).
