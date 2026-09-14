import os
import subprocess
import time
import urllib.request

CDP_PORT = 9222
PASTA = os.path.dirname(os.path.abspath(__file__))
PERFIL_CHROME = os.path.join(PASTA, "perfil_chrome")

CAMINHOS_CHROME = [
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
]

IMAGENS_CHROME = [
    "chrome.exe",
    "chrome_crashpad_handler.exe",
    "chrome_proxy.exe",
]


def localizar_chrome() -> str:
    for caminho in CAMINHOS_CHROME:
        if os.path.exists(caminho):
            return caminho
    return "chrome"


def chrome_rodando() -> bool:
    resultado = subprocess.run(
        ["tasklist", "/FI", "IMAGENAME eq chrome.exe"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="ignore",
    )
    return "chrome.exe" in resultado.stdout


def mata_todo_chrome() -> None:
    for imagem in IMAGENS_CHROME:
        subprocess.run(
            ["taskkill", "/IM", imagem, "/T", "/F"], capture_output=True
        )

    # Espera TODOS os processos do Chrome realmente saírem
    for _ in range(30):
        if not chrome_rodando():
            return
        time.sleep(0.5)


def porta_cdp_aberta() -> bool:
    try:
        with urllib.request.urlopen(
            f"http://127.0.0.1:{CDP_PORT}/json", timeout=2
        ) as resp:
            return resp.status == 200
    except Exception:
        return False


def relancar_chrome() -> bool:
    print("Fechando o Chrome...")
    mata_todo_chrome()
    time.sleep(2)

    chrome = localizar_chrome()
    print("Abrindo o Chrome com a porta de depuração...")

    subprocess.Popen(
        [
            chrome,
            f"--remote-debugging-port={CDP_PORT}",
            f"--user-data-dir={PERFIL_CHROME}",
        ]
    )

    for segundo in range(1, 31):
        time.sleep(1)
        if porta_cdp_aberta():
            print(f"Chrome pronto (porta {CDP_PORT} aberta).")
            print("ATENÇÃO: entre no Google/Gemini e na faculdade UMA vez "
                  "nesse Chrome.")
            return True
        if segundo % 5 == 0:
            print(f"Aguardando o Chrome abrir... ({segundo}s)")

    print(f"Não foi possível abrir a porta {CDP_PORT}.")
    return False


if __name__ == "__main__":
    print("Isso fecha TODAS as janelas do Chrome e abre um Chrome especial "
          "para o programa.")
    print("Nesse Chrome, você fará login no Google/Gemini e na faculdade "
          "uma única vez.")
    resposta = input("Continuar? [s/N] ").strip().lower()
    if resposta == "s":
        relancar_chrome()
    else:
        print("Cancelado.")