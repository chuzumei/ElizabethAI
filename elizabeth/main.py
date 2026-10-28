from __future__ import annotations
import json
import re
import time
import threading
from datetime import datetime
from pathlib import Path
import yaml
import numpy as np
import sounddevice as sd
import ollama
from openai import OpenAI

from elizabeth.wake import listen_for_wake_word
from elizabeth.stt import record_until_silence, transcribe_audio, set_abort_event
from elizabeth.tts import speak, speak_streamed, is_speaking, stop_speaking
from elizabeth.context import ContextManager
from elizabeth.memory import Memory
from elizabeth.persona import get_persona_prompt
from elizabeth.tools.router import TOOL_SCHEMAS, dispatch

_MAX_TOOL_LOOPS = 15
_CONFIG_PATH = Path(__file__).parent.parent / "config.yaml"

# Global abort Ã¢â‚¬â€ Esc sets this, stops everything (speech + tool loop + follow-up)
_abort = threading.Event()
set_abort_event(_abort)  # Let STT check abort during recording
# Global mute Ã¢â‚¬â€ INSERT toggles this, skips TTS when set
_muted = threading.Event()

# --- Message bus: push events to all connected web clients ---
_event_listeners: list = []  # list of callables: fn(event_dict)


def register_event_listener(fn) -> None:
    _event_listeners.append(fn)


def _broadcast(event: dict) -> None:
    for fn in _event_listeners:
        try:
            fn(event)
        except Exception:
            pass


class _Aborted(Exception):
    """Raised when user hits Esc to abort the current action."""
    pass


def abort_all() -> None:
    """Stop everything Elizabeth is doing right now."""
    _abort.set()
    stop_speaking()
    _broadcast({"type": "status", "message": "Stopped."})


def _is_stop_command(text: str) -> bool:
    """Check if transcribed text is a voice stop command."""
    cleaned = text.strip().lower().rstrip(".,!?")
    return cleaned in {
        "stop", "elizabeth stop", "hey elizabeth stop",
        "cancel", "abort", "shut up", "be quiet", "nevermind", "never mind",
    }


def _check_abort() -> None:
    """Raise _Aborted if user requested abort."""
    if _abort.is_set():
        raise _Aborted()


def is_muted() -> bool:
    return _muted.is_set()


def toggle_mute() -> None:
    if _muted.is_set():
        _muted.clear()
        _broadcast({"type": "mute", "muted": False})
        print("[Elizabeth] Unmuted.")
    else:
        _muted.set()
        stop_speaking()
        _broadcast({"type": "mute", "muted": True})
        print("[Elizabeth] Muted.")


def _speak_if_unmuted(text: str) -> None:
    """Speak text only if not muted."""
    if not _muted.is_set():
        from elizabeth.wake import pause_wake_mic, resume_wake_mic
        pause_wake_mic()
        try:
            speak(text)
        finally:
            resume_wake_mic()


def _speak_streamed_if_unmuted(text: str) -> None:
    """Speak streamed text only if not muted."""
    if not _muted.is_set():
        from elizabeth.wake import pause_wake_mic, resume_wake_mic
        pause_wake_mic()
        try:
            speak_streamed(text)
        finally:
            resume_wake_mic()


# --- OpenAI client cache (keyed by base_url) ---
_openai_clients: dict[str, OpenAI] = {}


def _get_openai_client(base_url: str, api_key: str = "lm-studio") -> OpenAI:
    if base_url not in _openai_clients:
        _openai_clients[base_url] = OpenAI(
            base_url=base_url, api_key=api_key, timeout=60.0,
        )
    return _openai_clients[base_url]


memory = Memory()
context = ContextManager(on_summary=memory.save_conversation_summary)

_recent_summaries = memory.get_recent_summaries(1)
if _recent_summaries:
    context._summary = f"[Earlier context: {_recent_summaries[0]}]"


def _skills_prompt() -> str:
    from elizabeth.skills.registry import registry
    from elizabeth.skills import builtin  # noqa: F401

    lines = ["SKILLS DISPONÃƒÂVEIS:"]
    for skill in registry.all():
        tools = ", ".join(skill["tools"]) if skill["tools"] else "sem ferramentas diretas"
        lines.append(
            f"- {skill['name']}: {skill['description']} "
            f"Ferramentas: {tools}."
        )

    return "\n".join(lines)


def _system_prompt() -> str:
    from zoneinfo import ZoneInfo

    dt = datetime.now(ZoneInfo("America/Sao_Paulo"))

    weekdays = [
        "segunda-feira",
        "terÃƒÂ§a-feira",
        "quarta-feira",
        "quinta-feira",
        "sexta-feira",
        "sÃƒÂ¡bado",
        "domingo",
    ]

    months = [
        "janeiro",
        "fevereiro",
        "marÃƒÂ§o",
        "abril",
        "maio",
        "junho",
        "julho",
        "agosto",
        "setembro",
        "outubro",
        "novembro",
        "dezembro",
    ]

    now = (
        f"{weekdays[dt.weekday()]}, "
        f"{dt.day:02d} de {months[dt.month - 1]} de {dt.year}, "
        f"{dt:%H:%M}, fuso America/Sao_Paulo"
    )
    return (
        "VocÃƒÂª ÃƒÂ© Elizabeth, uma assistente pessoal de IA totalmente autÃƒÂ´noma, "
        "com visÃƒÂ£o de tela e controle do computador. "
        "VocÃƒÂª pertence ao seu dono e deve ajudÃƒÂ¡-lo de forma direta, natural e eficiente. "
        "Seja concisa, confiante, prestativa e amigÃƒÂ¡vel. "
        "RESPONDA SEMPRE EM PORTUGUÃƒÅ S DO BRASIL, independentemente do idioma usado na pergunta, "
        "a menos que seu dono peÃƒÂ§a explicitamente outro idioma.\n\n"

        f"{get_persona_prompt()}\n\n"

        "FLUXO AUTÃƒâ€NOMO PARA TAREFAS DE INTERFACE:\n"
        "1. focus_window Ã¢â‚¬â€ trazer o aplicativo para frente\n"
        "2. find_on_screen Ã¢â‚¬â€ localizar textos ou botÃƒÂµes na tela\n"
        "3. click_at Ã¢â‚¬â€ clicar nas coordenadas encontradas\n"
        "4. Aguarde 1-2 segundos para a interface atualizar e entÃƒÂ£o use read_screen ou find_on_screen para verificar\n"
        "5. Repita atÃƒÂ© a tarefa terminar. VocÃƒÂª pode encadear atÃƒÂ© 15 chamadas de ferramentas.\n\n"

        "DICAS:\n"
        "- Depois de clicar, sempre verifique se o resultado esperado aconteceu.\n"
        "- Se um texto nÃƒÂ£o for encontrado, tente scroll_screen e depois find_on_screen novamente.\n"
        "- Para digitar em campos, primeiro use click_at no campo e depois type_text.\n"
        "- Use press_key para atalhos de teclado (ctrl+t, alt+f4 etc.).\n"
        "- Se uma ferramenta falhar, tente novamente uma vez antes de desistir.\n\n"

        f"Data e hora atuais: {now}.\n\n" + _skills_prompt()
    )


def _load_config() -> dict:
    with open(_CONFIG_PATH) as f:
        return yaml.safe_load(f)


def _save_config(cfg: dict) -> None:
    with open(_CONFIG_PATH, "w") as f:
        yaml.dump(cfg, f, default_flow_style=False, sort_keys=False)


def get_providers() -> dict:
    """Return the providers dict from config."""
    cfg = _load_config()
    return cfg.get("llm", {}).get("providers", {})


def get_active_provider() -> str:
    """Return the active provider key."""
    cfg = _load_config()
    return cfg.get("llm", {}).get("active_provider", "ollama")


def set_active_provider(provider_key: str) -> bool:
    """Switch the active provider. Returns True on success."""
    cfg = _load_config()
    providers = cfg.get("llm", {}).get("providers", {})
    if provider_key not in providers:
        return False
    cfg["llm"]["active_provider"] = provider_key
    _save_config(cfg)
    _broadcast({"type": "provider_changed", "provider": provider_key})
    return True


def _play_beep() -> None:
    """Short beep to signal processing has started."""
    try:
        t = np.linspace(0, 0.12, int(24000 * 0.12), endpoint=False)
        tone = 0.3 * np.sin(2 * np.pi * 600 * t).astype(np.float32)
        sd.play(tone, samplerate=24000)
        sd.wait()
    except Exception:
        pass


def _strip_think(text: str) -> str:
    """Remove <think>...</think> blocks from LLM output."""
    return re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()


def _parse_tool_args(raw) -> dict:
    """OpenAI returns JSON string, Ollama returns dict. Handle both."""
    if isinstance(raw, str):
        return json.loads(raw)
    return raw


def _call_openai_provider(provider_cfg: dict, temperature: float, full_messages: list[dict]) -> str:
    """Call any OpenAI-compatible provider (LM Studio, NVIDIA NIM, etc.)."""
    model = provider_cfg["model"]
    base_url = provider_cfg["base_url"]
    api_key = provider_cfg.get("api_key", "lm-studio")
    client = _get_openai_client(base_url, api_key)
    tool_count = 0
    for _ in range(_MAX_TOOL_LOOPS):
        _check_abort()
        resp = client.chat.completions.create(
            model=model,
            messages=full_messages,
            tools=TOOL_SCHEMAS,
            temperature=temperature,
        )
        msg = resp.choices[0].message
        if msg.tool_calls:
            full_messages.append(msg.model_dump())
            for tc in msg.tool_calls:
                _check_abort()
                args = _parse_tool_args(tc.function.arguments)
                tool_count += 1
                _broadcast({"type": "tool", "name": tc.function.name, "args": args})
                if tool_count == 4:
                    _speak_if_unmuted("Working on it.")
                result = _exec_tool_with_retry(tc.function.name, args)
                print(f"[Tool: {tc.function.name}] {result[:120]}")
                _broadcast({"type": "tool_result", "name": tc.function.name, "result": result[:200]})
                full_messages.append({
                    "role": "tool",
                    "content": result,
                    "tool_call_id": tc.id,
                })
        else:
            return _strip_think(msg.content or "Done.")
    return "Done."


def _call_ollama_provider(provider_cfg: dict, temperature: float, full_messages: list[dict]) -> str:
    """Call Ollama provider."""
    model = provider_cfg["model"]
    tool_count = 0
    for _ in range(_MAX_TOOL_LOOPS):
        _check_abort()
        response = ollama.chat(
            model=model,
            messages=full_messages,
            tools=TOOL_SCHEMAS,
            think=True,
            keep_alive="30m",
        )

        try:
            print(
                f"[Ollama] prompt_tokens={response.prompt_eval_count} "
                f"prompt_time={response.prompt_eval_duration / 1e9:.2f}s "
                f"output_tokens={response.eval_count} "
                f"generation_time={response.eval_duration / 1e9:.2f}s "
                f"total={response.total_duration / 1e9:.2f}s"
            )
        except Exception:
            pass
        if response.message.tool_calls:
            full_messages.append(response.message.model_dump())
            for tc in response.message.tool_calls:
                _check_abort()
                args = _parse_tool_args(tc.function.arguments)
                tool_count += 1
                _broadcast({"type": "tool", "name": tc.function.name, "args": args})
                if tool_count == 4:
                    _speak_if_unmuted("Working on it.")
                result = _exec_tool_with_retry(tc.function.name, args)
                print(f"[Tool: {tc.function.name}] {result[:120]}")
                _broadcast({"type": "tool_result", "name": tc.function.name, "result": result[:200]})
                full_messages.append({
                    "role": "tool",
                    "content": result,
                    "name": tc.function.name,
                })
        else:
            return _strip_think(response.message.content or "Done.")
    return "Done."


def _call_llm(full_messages: list[dict]) -> str:
    """Route to the active provider."""
    cfg = _load_config()
    llm_cfg = cfg["llm"]
    temperature = llm_cfg.get("temperature", 0.7)
    active = llm_cfg.get("active_provider", "ollama")
    providers = llm_cfg.get("providers", {})
    provider = providers.get(active, {})
    ptype = provider.get("type", "ollama")

    if ptype == "openai":
        return _call_openai_provider(provider, temperature, full_messages)
    else:
        return _call_ollama_provider(provider, temperature, full_messages)


def _exec_tool_with_retry(name: str, args: dict) -> str:
    """Execute a tool, retry once on failure."""
    result = dispatch(name, args)
    if result.startswith("Tool '") and "failed:" in result:
        time.sleep(0.5)
        result = dispatch(name, args)
    return result


def handle_wake() -> None:
    """Called when wake word is detected. Full pipeline: listen Ã¢â€ â€™ think Ã¢â€ â€™ speak."""
    _abort.clear()
    try:
        _handle_wake_inner()
    except _Aborted:
        print("[Elizabeth] Aborted.")
    except Exception as e:
        import traceback
        print(f"[ERROR] {e}")
        traceback.print_exc()
        if not _abort.is_set():
            _speak_if_unmuted("Sorry, something went wrong.")
    finally:
        _abort.clear()
        _broadcast({"type": "status", "message": "Ready."})
        print("[Elizabeth] Listening for wake word...")


def _handle_wake_inner() -> None:
    if is_speaking():
        stop_speaking()
    print("[Elizabeth] Wake word detected!")
    _broadcast({"type": "status", "message": "Wake."})
    print("[Elizabeth] Recording...")
    _broadcast({"type": "status", "message": "Listening..."})

    # O STT agora consome o mesmo fluxo contÃƒÂ­nuo do wake word.
    # NÃƒÂ£o pausamos mais o microfone aqui.
    t_record = time.perf_counter()
    audio = record_until_silence()
    print(f"[Tempo] GravaÃƒÂ§ÃƒÂ£o: {time.perf_counter() - t_record:.2f}s")

    _check_abort()
    print(f"[Elizabeth] Recorded {len(audio)/16000:.1f}s of audio, transcribing...")

    t_stt = time.perf_counter()
    user_text = transcribe_audio(audio)
    print(f"[Tempo] STT: {time.perf_counter() - t_stt:.2f}s")

    import re
    user_text = re.sub(
        r"^\s*(?:em[iÃ­]lia|elizabeth)[\s,.:;!?-]*",
        "",
        user_text,
        flags=re.IGNORECASE,
    ).strip()
    if not user_text.strip():
        print("[Elizabeth] Transcription empty Ã¢â‚¬â€ didn't catch anything.")
        _speak_if_unmuted("I didn't catch that.")
        _broadcast({"type": "status", "message": "Ready."})
        return
    print(f"[You] {user_text}")

    if _is_stop_command(user_text):
        abort_all()
        print("[Elizabeth] Stopped. (voice)")
        raise _Aborted()

    t_process = time.perf_counter()
    response_text = _process_request(user_text)
    print(f"[Tempo] LLM + contexto/memÃƒÂ³ria: {time.perf_counter() - t_process:.2f}s")
    _check_abort()

    print(f"[Elizabeth] {response_text}")
    _broadcast({"type": "status", "message": "Speaking..."})

    t_tts = time.perf_counter()
    _speak_streamed_if_unmuted(response_text)
    print(f"[Tempo] TTS + reproduÃƒÂ§ÃƒÂ£o: {time.perf_counter() - t_tts:.2f}s")


def _quick_response(user_text: str):
    """Responde comandos simples sem chamar o LLM."""
    import re
    import unicodedata
    from datetime import datetime

    text = unicodedata.normalize("NFD", user_text.lower())
    text = "".join(c for c in text if unicodedata.category(c) != "Mn")
    text = re.sub(r"[^a-z0-9 ]", " ", text)
    text = " ".join(text.split())

    if re.fullmatch(
        r"(?:me diga |pode me dizer |voce sabe )?"
        r"(?:que horas sao|quantas horas sao|qual e a hora|me diga as horas|horas)",
        text,
    ):
        now = datetime.now()
        return f"Agora s?o {now.hour} horas e {now.minute:02d} minutos."

    if re.fullmatch(
        r"(?:me diga |pode me dizer )?"
        r"(?:que dia e hoje|qual e a data de hoje|qual a data de hoje|data de hoje)",
        text,
    ):
        now = datetime.now()
        return f"Hoje ? dia {now.day} de {now.month:02d} de {now.year}."

    return None


def _process_request(user_text: str) -> str:
    """Build context, call LLM, update memory. Returns response text."""
    _check_abort()
    _play_beep()

    quick = _quick_response(user_text)
    if quick is not None:
        _broadcast({"type": "user", "text": user_text})
        print("[Emilia] Resposta rapida (sem Qwen).")
        return quick
    _broadcast({"type": "user", "text": user_text})
    _broadcast({"type": "status", "message": "Thinking..."})

    t_memory_search = time.perf_counter()
    facts = memory.search_facts(user_text)
    print(f"[Tempo] Busca memÃƒÂ³ria: {time.perf_counter() - t_memory_search:.2f}s")

    messages = context.get_messages()
    if facts:
        facts_block = (
            "CONTEXTO RELEVANTE DA MEMÃƒâ€œRIA:\n"
            + "\n".join(f"- {fact}" for fact in facts)
            + "\nUse essas informaÃƒÂ§ÃƒÂµes apenas quando forem relevantes para o pedido atual."
        )
        messages = [{"role": "system", "content": facts_block}] + messages
    messages.append({"role": "user", "content": user_text})

    full_messages = [{"role": "system", "content": _system_prompt()}] + messages

    try:
        t_llm = time.perf_counter()
        response_text = _call_llm(full_messages)
        print(f"[Tempo] Ollama/LLM: {time.perf_counter() - t_llm:.2f}s")
    except _Aborted:
        raise
    except Exception as e:
        print(f"[WARN] Primary provider failed ({e}), trying Ollama fallback")
        cfg = _load_config()
        ollama_provider = cfg["llm"]["providers"].get("ollama", {"model": "qwen3:8b"})
        response_text = _call_ollama_provider(ollama_provider, cfg["llm"].get("temperature", 0.7), full_messages)

    t_memory_save = time.perf_counter()
    context.add("user", user_text)
    context.add("assistant", response_text)
    memory.extract_and_store_facts(response_text, user_text)
    print(f"[Tempo] Salvar contexto/memÃƒÂ³ria: {time.perf_counter() - t_memory_save:.2f}s")

    _broadcast({"type": "response", "text": response_text})
    return response_text



def _keyboard_listener() -> None:
    """Windows: Esc = abortar, F2 = falar, Insert = mute."""
    from pynput import keyboard

    def on_press(key):
        if key == keyboard.Key.esc:
            abort_all()
            print("\n[Elizabeth] Stopped. (Esc)")

        elif key == keyboard.Key.insert:
            toggle_mute()

        elif key == keyboard.Key.f2:
            print("\n[Elizabeth] Estou ouvindo...")
            from elizabeth.wake import start_stt_capture
            start_stt_capture()
            handle_wake()

    print("[Keyboard] Atalhos do Windows ativados.")
    with keyboard.Listener(on_press=on_press) as listener:
        listener.join()


def _handle_typed_command(text: str) -> None:
    """Process a typed command (same as voice, but from keyboard)."""
    _abort.clear()
    print(f"[You] {text}")
    try:
        response = _process_request(text)
        print(f"[Elizabeth] {response}")
        _speak_streamed_if_unmuted(response)
    except _Aborted:
        print("[Elizabeth] Stopped.")
    finally:
        _abort.clear()


def main() -> None:

    print("[Elizabeth] Starting up...")
    print("[Elizabeth] Keys: Esc = parar | F2 = falar manualmente | INSERT = mute/unmute")


    threading.Thread(target=_keyboard_listener, daemon=True).start()

    # PrÃƒÂ©-carrega o Whisper em segundo plano para a primeira conversa ser rÃƒÂ¡pida
    def _preload_stt():
        try:
            from elizabeth.stt import _get_model
            print("[STT] PrÃƒÂ©-carregando modelo...")
            _get_model()
            print("[STT] Modelo pronto.")
        except Exception as e:
            print(f"[STT] Falha no prÃƒÂ©-carregamento: {e}")

    threading.Thread(
        target=_preload_stt,
        daemon=True,
        name="stt-preloader",
    ).start()

    # Carrega a Qwen em segundo plano para evitar espera na primeira pergunta
    def _preload_ollama():
        try:
            import time
            t = time.perf_counter()
            print("[Ollama] Pre-carregando Qwen...")
            ollama.generate(
                model="qwen3:8b",
                keep_alive="30m",
            )
            print(f"[Ollama] Qwen pronta em {time.perf_counter() - t:.2f}s")
        except Exception as e:
            print(f"[Ollama] Falha no pre-carregamento: {e}")

    threading.Thread(
        target=_preload_ollama,
        daemon=True,
        name="ollama-preloader",
    ).start()

    # Reconhecimento de comandos pelo Whisper
    from elizabeth.voice_listener import listen_for_commands

    threading.Thread(
        target=listen_for_commands,
        args=(_handle_typed_command,),
        daemon=True,
        name="whisper-listener",
    ).start()


    _speak_if_unmuted("OlÃƒÂ¡. Elizabeth estÃƒÂ¡ online.")
    print("[Elizabeth] Online. Diga \"Elizabeth\" para falar comigo.")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n[Elizabeth] Encerrando.")
        _abort.set()

        from elizabeth.wake import stop_wake_listener
        stop_wake_listener()
        time.sleep(0.3)


if __name__ == "__main__":
    main()

