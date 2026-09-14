# Autoluno

Automatiza perguntas de provas online: copia a questão da página da faculdade,
envia para o Gemini (pelo navegador), recebe a resposta, marca a alternativa
correta e avança para a próxima questão.

## Como instalar (em qualquer computador)

1. Instale o [Python](https://www.python.org/downloads/) 3.12+ (marque
   "Add Python to PATH" durante a instalação).
2. Instale o **Google Chrome**.
3. Baixe/configuração do projeto e, na pasta dele, rode:

```
pip install -r requirements.txt
```

## Como usar

1. Dê dois cliques em `iniciar.bat` (ou rode `python main.py`).
2. Se for solicitado, digite `s` para o programa abrir o Chrome automaticamente.
3. No Chrome que abriu, faça login na sua conta Google e abra
   `gemini.google.com` (aba 1) e a página da faculdade (aba 2) — isso **só na
   primeira vez** neste computador.
4. Clique na aba da faculdade e pressione **F8**.

O programa:
- Lê a questão da página;
- Manda para o Gemini com a instrução de retornar apenas a resposta correta;
- Cola a resposta na busca (`Ctrl+F`);
- Marca a alternativa que corresponde à resposta;
- Clica em "Confirmar resposta" e depois em "Ir para a próxima questão";
- **Repete sozinho** para a próxima questão enquanto houver, até acabar a
  lista. Para encerrar, pressione **Ctrl+C** no terminal.

## Arquivos

| Arquivo                 | Função                                        |
|-------------------------|-----------------------------------------------|
| `main.py`               | Programa principal (tecla F8)                 |
| `iniciar_navegador.py`  | Abre o Chrome com porta de depuração (CDP)    |
| `iniciar.bat`           | Duplo clique para rodar o programa            |
| `requirements.txt`      | Dependências Python                           |

## Observações

- O programa usa o seu navegador Chrome para acessar o Gemini; por isso ele
  precisa abrir o Chrome com "porta de depuração" (perfil próprio em
  `perfil_chrome/`). Essa pasta **não** é versionada.
- Na primeira execução em cada computador, é preciso logar no Google/Gemini e
  na faculdade dentro do Chrome aberto pelo programa.