# ElizabethAI 🎙️

**ElizabethAI** é uma assistente de inteligência artificial local, desenvolvida em Python para Windows, com interação por voz, integração com modelos de linguagem e ferramentas de automação.

O projeto é uma adaptação do **JarvisAI**, criado por **PanPenek**, com personalizações na identidade da assistente, reconhecimento de voz, síntese de fala e integrações locais.

## Funcionalidades

- 🎤 Reconhecimento de comandos de voz.
- 🧠 Integração com modelos de linguagem locais pelo Ollama.
- 🔊 Respostas faladas utilizando Kitsune TTS.
- 👂 Ativação por palavra-chave personalizada com openWakeWord.
- 💾 Sistema de memória e gerenciamento de contexto.
- 🖥️ Ferramentas para automação e interação com o computador.
- 🌐 Integrações com serviços e pesquisas na internet.
- ⌨️ Atalhos para controlar a assistente.

Algumas funcionalidades dependem de configurações, modelos e serviços adicionais.

## Tecnologias

| Tecnologia | Utilização |
|---|---|
| Python | Linguagem principal |
| Ollama | Execução local de modelos de linguagem |
| Whisper | Transcrição de áudio |
| Kitsune TTS | Síntese de voz |
| openWakeWord | Detecção de palavra de ativação |
| OpenVINO | Aceleração de inferência |
| Git | Versionamento |

## Requisitos

- Windows.
- Python compatível com as dependências do projeto.
- Ollama instalado e configurado.
- Microfone e dispositivo de saída de áudio.
- Modelos de voz e ativação configurados separadamente.

## Instalação

Clone o repositório e entre na pasta do projeto:

```bash
git clone URL_DO_REPOSITORIO
cd ElizabethAI
```

Execute o instalador:

```bat
install.bat
```

O instalador cria o ambiente virtual, instala as dependências e prepara os modelos padrão do openWakeWord.

Caso necessário, crie o arquivo `config.yaml` utilizando `config.example.yaml` como referência.

Configure o Ollama e os modelos adicionais antes de iniciar a assistente.

## Execução

No Windows:

```bat
start.bat
```

Ou, com o ambiente virtual ativado:

```bash
python -m elizabeth.main
```

## Modelos personalizados

**Este repositório disponibiliza somente o código-fonte.**

Os seguintes arquivos não estão incluídos:

- Modelo personalizado de ativação `emilia.onnx`.
- Modelo de síntese de voz `kitsune39M.onnx`.
- Arquivos de configuração e recursos associados aos modelos.
- Dados de treinamento, gravações e arquivos privados.

Para utilizar as funcionalidades de voz, é necessário obter modelos compatíveis e configurar os caminhos esperados pelo projeto.

O código pode exigir adaptações para funcionar com modelos diferentes.

## Segurança

A ElizabethAI possui ferramentas capazes de interagir com o sistema operacional.

Execute o projeto apenas em ambientes confiáveis, revise as permissões das ferramentas e não exponha a interface de controle à internet.

Nunca publique senhas, chaves de API ou arquivos de configuração privados.

## Origem e créditos

Este projeto foi desenvolvido a partir do **JarvisAI**, de **PanPenek**.

Repositório original: `PanPenek/jarvis`, no GitHub.

A ElizabethAI é uma adaptação independente e não deve ser confundida com o projeto original.

Os créditos pela implementação original pertencem aos respectivos autores.

## Licenciamento

O README do projeto-base indica a licença MIT, mas não foi encontrado um arquivo de licença completo no repositório original durante a preparação desta adaptação.

Os termos de redistribuição do código derivado precisam ser esclarecidos antes de sua publicação pública.

## Estado do projeto

Projeto pessoal em desenvolvimento, utilizado para aprendizado e experimentação com inteligência artificial local, processamento de voz e automação em Python.

A instalação em outros computadores ainda não foi validada integralmente.