import re
import sys
import time
import unicodedata
from datetime import datetime

import keyboard
import pyautogui
import pyperclip
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys

CDP_PORT = 9222
GEMINI_URL = "gemini.google.com"
TEMPO_MAXIMO_RESPOSTA = 180  # segundos
INSTRUCAO = ("Não retorne nada além da resposta correta exatamente do jeito "
             "que ela está escrita, não precisa explicar nada.")

# --- Página da faculdade (editável) ---
SELETORES_ALTERNATIVA = [
    "input[type=radio]",
    "input[type=checkbox]",
    "[role=radio]",
    "[role=checkbox]",
    "label",
    "[class*='option']",
    "[class*='alternativ']",
    "[class*='resposta']",
    "[class*='choice']",
    "[class*='answer']",
]

PALAVRAS_CONFIRMAR = [
    "confirmar resposta",
    "confirmar",
    "confirm",
]

PALAVRAS_PROXIMA = [
    "próxima questão",
    "proxima questao",
    "próxima pergunta",
    "proxima pergunta",
    "próxima",
    "proxima",
    "avançar",
    "avancar",
    "continuar",
    "salvar e avançar",
    "salvar e avancar",
    "next question",
    "next",
]

ESPERA_BOTAO = 10  # segundos para confirmar e ir para a próxima questão

contador = 0
driver = None


# -----------------------------
# CONEXÃO COM O CHROME (CDP)
# -----------------------------
def porta_cdp_aberta() -> bool:
    try:
        import urllib.request

        with urllib.request.urlopen(
            f"http://127.0.0.1:{CDP_PORT}/json", timeout=2
        ) as resp:
            return resp.status == 200
    except Exception:
        return False


def conectar_chrome() -> bool:
    global driver
    if not porta_cdp_aberta():
        print("Chrome ainda não está com a porta de depuração aberta.")
        try:
            resposta = input(
                "Quer que eu feche e abra o Chrome automaticamente? [s/N] "
            ).strip().lower()
        except EOFError:
            resposta = ""
        if resposta != "s":
            print(
                "Então rode manualmente:  python iniciar_navegador.py"
            )
            return False

        from iniciar_navegador import relancar_chrome

        if not relancar_chrome():
            print("Não foi possível abrir a porta. Rode o programa de novo.")
            return False
        print("Conectando ao Chrome...")

    opcoes = Options()
    opcoes.debugger_address = f"127.0.0.1:{CDP_PORT}"
    driver = webdriver.Chrome(options=opcoes)
    print(f"Conectado ao Chrome. {len(driver.window_handles)} aba(s) aberta(s).")
    return True


def achar_aba(termo: str):
    for handle in driver.window_handles:
        driver.switch_to.window(handle)
        if termo in driver.current_url:
            return handle
    return None


# -----------------------------
# LEITURA DA PÁGINA DA FACULDADE
# -----------------------------
def ler_pergunta(curso_handle) -> str:
    driver.switch_to.window(curso_handle)

    texto = driver.execute_script("return document.body.innerText;") or ""

    # Recorta a partir do 1º número de 2 dígitos (01, 02...)
    resultado = re.search(r"\b\d{2}\b", texto)
    if resultado:
        texto = texto[resultado.end():]

    texto = " ".join(texto.split())
    return texto.strip()


# -----------------------------
# GEMINI
# -----------------------------
def acharc_caixa():
    for seletor in ("textarea", "[contenteditable='true']"):
        for el in driver.find_elements(By.CSS_SELECTOR, seletor):
            try:
                if el.is_displayed() and el.is_enabled():
                    return el
            except Exception:
                continue
    return None


def clicar(el) -> None:
    try:
        el.click()
    except Exception:
        driver.execute_script("arguments[0].click();", el)
    driver.execute_script("arguments[0].focus();", el)


def texto_do_elemento(resposta) -> str:
    js = """
    (e) => {
      let t = "";
      try { t = (e.innerText || "").trim(); } catch (err) {}
      if (!t && e.shadowRoot) {
        try { t = (e.shadowRoot.innerText || "").trim(); } catch (err) {}
      }
      if (!t) {
        let total = "";
        for (const k of e.querySelectorAll("*")) {
          if (k.innerText && k.innerText.trim()) total += k.innerText.trim() + "\n";
        }
        t = total.trim();
      }
      return t;
    }
    """
    try:
        return driver.execute_script(js, resposta) or ""
    except Exception:
        return resposta.text or ""


def limpar_resposta(texto: str) -> str:
    """Descarta cabeçalhos da interface (ex.: 'O Gemini disse:') e deixa
    apenas a resposta em si."""
    linhas = [linha.strip() for linha in (texto or "").splitlines()]

    # remove linhas vazias do início
    while linhas and not linhas[0]:
        linhas.pop(0)

    # remove cabeçalho que termina com "disse"
    while linhas and re.search(r"\bdisse\b\s*[:.\-–—]?\s*$", linhas[0], re.IGNORECASE):
        linhas.pop(0)

    return "\n".join(linhas).strip()


def esperar_resposta(modelos_inicial: int) -> str:
    """Espera a resposta aparecer e terminar de streamar."""
    def pegar():
        return driver.find_elements(By.CSS_SELECTOR, "model-response")

    ultimo_conhecido = ""
    inicio = time.time()

    while time.time() - inicio < TEMPO_MAXIMO_RESPOSTA:
        lista = pegar()
        if len(lista) > modelos_inicial:
            texto = texto_do_elemento(lista[modelos_inicial])
            if texto:
                if ultimo_conhecido and texto == ultimo_conhecido:
                    time.sleep(2)
                    novo = texto_do_elemento(pegar()[modelos_inicial])
                    if novo and novo == texto:
                        return texto
                ultimo_conhecido = texto
        time.sleep(2)

    if ultimo_conhecido:
        return ultimo_conhecido
    raise TimeoutError("Tempo esgotado aguardando a resposta do Gemini.")


# -----------------------------
# SELEÇÃO DA RESPOSTA NA FACULDADE
# -----------------------------
def normalizar(texto: str) -> str:
    texto = unicodedata.normalize("NFD", texto or "")
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", texto).strip().lower()


def texto_da_alternativa(el) -> str:
    """Texto de uma alternativa, resolvendo também o caso de input sem texto."""
    if el.tag_name.strip().lower() == "input":
        identificador = el.get_attribute("id")
        if identificador:
            try:
                label = driver.find_element(
                    By.CSS_SELECTOR, f"label[for='{identificador}']"
                )
                texto = label.text or ""
                if texto.strip():
                    return texto
            except Exception:
                pass
        atual = el
        for _ in range(4):
            pai = driver.execute_script(
                "return arguments[0].parentElement;", atual
            )
            if pai is None:
                break
            texto = pai.text or ""
            if texto.strip():
                return texto
            atual = pai
        return ""
    return el.text or ""


def achar_alternativa_por_texto(resposta: str):
    """Encontra o elemento da alternativa cujo texto bate com a resposta."""
    alvo = normalizar(resposta)
    if not alvo or len(alvo) < 3:
        return None

    candidatos = []
    for seletor in SELETORES_ALTERNATIVA:
        try:
            elementos = driver.find_elements(By.CSS_SELECTOR, seletor)
        except Exception:
            continue
        for el in elementos:
            try:
                if not el.is_displayed():
                    continue
            except Exception:
                continue
            texto = normalizar(texto_da_alternativa(el))
            if not texto:
                continue
            if texto == alvo:
                candidatos.append((0, len(texto), el))
            elif alvo in texto and len(alvo) >= 5:
                candidatos.append((1, len(texto), el))

    if not candidatos:
        return None

    candidatos.sort(key=lambda item: (item[0], item[1]))
    return candidatos[0][2]


def alternativa_marcada(el) -> bool:
    """Verifica se a alternativa ficou realmente marcada."""
    alvos = []
    try:
        alvos = el.find_elements(
            By.CSS_SELECTOR,
            "input[type=radio], input[type=checkbox]",
        )
    except Exception:
        alvos = []
    if not alvos and el.tag_name.strip().lower() == "input":
        alvos = [el]
    for alvo in alvos:
        try:
            if driver.execute_script("return arguments[0].checked;", alvo):
                return True
        except Exception:
            continue
    classe = (el.get_attribute("class") or "").lower()
    return any(
        marcador in classe
        for marcador in (
            "selected", "is-selected", "active", "is-active",
            "checked", "is-checked",
        )
    )


def clicar_alternativa(el) -> None:
    """Clique interno na alternativa, dando prioridade ao input radio/checkbox."""
    inputs = []
    try:
        inputs = el.find_elements(
            By.CSS_SELECTOR,
            "input[type=radio], input[type=checkbox]",
        )
    except Exception:
        inputs = []

    if inputs:
        alvo = inputs[0]
    elif el.tag_name.strip().lower() == "input":
        alvo = el
    else:
        alvo = el

    driver.execute_script(
        "arguments[0].scrollIntoView({block:'center', inline:'center'});",
        alvo,
    )
    try:
        alvo.click()
    except Exception:
        driver.execute_script("arguments[0].click();", alvo)
    driver.execute_script("arguments[0].focus();", alvo)


def selecionar_alternativa(resposta: str) -> bool:
    el = achar_alternativa_por_texto(resposta)
    if el is None:
        return False

    resumo = (el.text or "").strip()
    if len(resumo) > 80:
        resumo = resumo[:80] + "..."
    print(f"Alternativa encontrada: {resumo}")

    for _ in range(3):
        clicar_alternativa(el)
        time.sleep(0.4)
        if alternativa_marcada(el):
            return True
    return alternativa_marcada(el)


def botao_habilitado(botao) -> bool:
    """Retorna True se o botão está visível e não desabilitado."""
    classe = (botao.get_attribute("class") or "").lower()
    if (
        botao.get_attribute("disabled") is not None
        or (botao.get_attribute("aria-disabled") or "").lower()
        in ("true", "1")
        or "disabled" in classe
    ):
        return False
    try:
        return bool(botao.is_displayed())
    except Exception:
        return False


def clicar_na_tela(botao) -> None:
    driver.execute_script(
        "arguments[0].scrollIntoView({block:'center', inline:'center'});",
        botao,
    )
    try:
        botao.click()
    except Exception:
        driver.execute_script("arguments[0].click();", botao)


def clicar_proxima() -> bool:
    """Clica em 'Confirmar resposta' (se houver) e depois no botão
    'ir para a próxima questão' quando habilitado."""
    fim = time.time() + ESPERA_BOTAO
    confirmado = False

    while time.time() < fim:
        botoes = []
        for seletor in ("button", "[role=button]", "a.btn",
                        "input[type=submit]"):
            try:
                botoes += driver.find_elements(By.CSS_SELECTOR, seletor)
            except Exception:
                continue

        for botao in botoes:
            texto = normalizar(botao.text or "")
            if not texto or not botao_habilitado(botao):
                continue

            if not confirmado and any(
                palavra in texto for palavra in PALAVRAS_CONFIRMAR
            ):
                clicar_na_tela(botao)
                confirmado = True
                print("Botão 'Confirmar resposta' clicado.")
                break

            if confirmado and any(
                palavra in texto for palavra in PALAVRAS_PROXIMA
            ):
                clicar_na_tela(botao)
                return True

        time.sleep(0.5)
    return False


# -----------------------------
# FLUXO PRINCIPAL (F8)
# -----------------------------
def fluxo_f8():
    global contador, driver
    if driver is None:
        print("Sem conexão com o Chrome. Reinicie o programa.")
        return

    contador += 1
    print(f"\nExecução #{contador}")

    curso_handle = driver.current_window_handle

    try:
        pergunta = ler_pergunta(curso_handle)
        if not pergunta:
            print("Nada foi selecionado na página da faculdade.")
            return

        gemini_handle = achar_aba(GEMINI_URL)
        if gemini_handle is None:
            print("Aba do Gemini não encontrada. Abra https://gemini.google.com")
            return
        print("Aba do Gemini encontrada pela URL.")

        driver.switch_to.window(gemini_handle)

        caixa = acharc_caixa()
        if caixa is None:
            print("Campo de texto do Gemini não encontrado.")
            return

        clicar(caixa)

        # Cola a pergunta (rápido e confiável) e envia
        mensagem = INSTRUCAO + "\n\n" + pergunta
        pyperclip.copy(mensagem)
        time.sleep(0.2)
        pyautogui.hotkey("ctrl", "v")
        time.sleep(0.5)
        pyautogui.press("enter")
        print("Pergunta enviada. Aguardando resposta do Gemini...")

        modelos_inicial = len(
            driver.find_elements(By.CSS_SELECTOR, "model-response")
        )
        resposta = limpar_resposta(esperar_resposta(modelos_inicial))

        if not resposta:
            print("Resposta vazia recebida.")
            return

        pyperclip.copy(resposta)
        print(f"Resposta copiada ({len(resposta)} caracteres).")

        # Volta para a página da faculdade e busca a resposta
        driver.switch_to.window(curso_handle)
        time.sleep(0.3)
        pyautogui.hotkey("ctrl", "f")
        time.sleep(0.3)
        pyautogui.hotkey("ctrl", "v")
        print("Resposta colada na busca.")

        # Fecha a barra de busca para os cliques não serem atrapalhados
        time.sleep(0.3)
        pyautogui.press("esc")
        time.sleep(0.3)

# Seleciona a alternativa que contém a resposta
        if selecionar_alternativa(resposta):
            time.sleep(0.5)
            if clicar_proxima():
                print("Resposta confirmada e 'Ir para a próxima questão' "
                      "clicado.")
            else:
                print("Botão 'Confirmar resposta' / 'próxima questão' não "
                      "apareceu em tempo hábil.")
        else:
            print("Resposta não encontrada em nenhuma alternativa. "
                  "Nenhum clique foi feito.")

        print(f"Execução #{contador} finalizada.")

    except Exception as e:
        print(f"ERRO na execução #{contador}: {e}")

    finally:
        agora = datetime.now().strftime("%H:%M:%S")
        print(agora)


# -----------------------------
# REGISTRO DE TECLA
# -----------------------------
def main() -> None:
    if not conectar_chrome():
        sys.exit(1)

    print("Pressione F8 no Chrome, sobre a página da faculdade, para iniciar.")
    print("Se o Chrome acabou de ser aberto, entre no Google/Gemini e na "
          "faculdade 1 vez.")
    keyboard.add_hotkey("F8", fluxo_f8)

    # FUTURO: adicionar novas teclas aqui
    # keyboard.add_hotkey("F9", outra_funcao)
    # keyboard.add_hotkey("F10", outra_funcao)

    keyboard.wait()


if __name__ == "__main__":
    main()