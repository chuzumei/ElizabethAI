from __future__ import annotations

from collections import deque
from pathlib import Path
import threading
import time
import yaml

from elizabeth.llm import chat

_CONFIG_PATH = Path(__file__).parent.parent / "config.yaml"


def _load_config():
    with open(_CONFIG_PATH, encoding="utf-8") as f:
        return yaml.safe_load(f)


class ContextManager:
    def __init__(
        self,
        max_messages: int | None = None,
        summarize_after: int | None = None,
        on_summary=None,
    ):
        cfg = _load_config()["context"]
        self.max_messages = max_messages if max_messages is not None else cfg["max_messages"]
        self.summarize_after = summarize_after if summarize_after is not None else cfg["summarize_after"]

        if not 1 <= self.summarize_after <= self.max_messages:
            raise ValueError("Invalid context configuration")

        self._window = deque()
        self._summary = None
        self._on_summary = on_summary
        self._lock = threading.RLock()
        self._summarizing = False
        self._pending = []

    def add(self, role: str, content: str) -> None:
        with self._lock:
            self._window.append({"role": role, "content": content})

            if len(self._window) >= self.summarize_after and not self._summarizing:
                self._summarizing = True
                threading.Thread(
                    target=self._compress_oldest,
                    daemon=True,
                    name="ElizabethContextSummary",
                ).start()

    def _compress_oldest(self) -> None:
        try:
            while True:
                with self._lock:
                    if len(self._window) < self.summarize_after:
                        return

                    half = max(1, len(self._window) // 2)
                    batch = [self._window.popleft() for _ in range(half)]
                    self._pending = batch
                    previous = self._summary or ""

                text = "\n".join(
                    f"{m['role']}: {m['content']}" for m in batch
                )

                prompt = (
                    "Atualize o resumo acumulado desta conversa em português do Brasil, "
                    "de forma factual e compacta. Preserve nomes, preferências, decisões, "
                    "tarefas em andamento e detalhes importantes. Não invente informações.\n\n"
                    f"RESUMO ANTERIOR:\n{previous or '(nenhum)'}\n\n"
                    f"NOVAS MENSAGENS:\n{text}"
                )

                t0 = time.perf_counter()
                try:
                    summary = chat([{"role": "user", "content": prompt}])
                except Exception as exc:
                    with self._lock:
                        self._window.extendleft(reversed(batch))
                        self._pending = []
                    print(f"[Context] Falha ao resumir: {exc}")
                    return

                with self._lock:
                    self._summary = f"[Earlier context: {summary}]"
                    self._pending = []

                print(f"[Tempo] Resumo contexto (background): {time.perf_counter() - t0:.2f}s")

                if self._on_summary:
                    try:
                        self._on_summary(summary)
                    except Exception as exc:
                        print(f"[Context] Falha ao salvar resumo: {exc}")

        finally:
            with self._lock:
                self._summarizing = False

    def get_messages(self) -> list[dict]:
        with self._lock:
            messages = list(self._pending) + list(self._window)
            if self._summary:
                messages = [{"role": "system", "content": self._summary}] + messages
            return messages

    def clear(self) -> None:
        with self._lock:
            self._window.clear()
            self._summary = None
