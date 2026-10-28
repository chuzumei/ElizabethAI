from __future__ import annotations
import hashlib
from datetime import datetime, timezone
from pathlib import Path

import chromadb
from sqlalchemy import create_engine, text

_CONFIG_PATH = Path(__file__).parent.parent / "config.yaml"


def _resolve_path(raw: str) -> Path:
    """Resolve a path that may be relative (relative to the repo root = config dir)."""
    p = Path(raw)
    if p.is_absolute():
        return p
    return (_CONFIG_PATH.parent / raw).resolve()


class Memory:
    def __init__(
        self,
        db_path: str | None = None,
        chroma_path: str | None = None,
        top_k: int | None = None,
    ):
        import yaml

        _cfg_top_k = 3  # default if config not available
        if db_path is None or chroma_path is None:
            with open(_CONFIG_PATH) as f:
                cfg = yaml.safe_load(f)["memory"]
            db_path = db_path or str(_resolve_path(cfg["db_path"]))
            chroma_path = chroma_path or str(_resolve_path(cfg["chroma_path"]))
            _cfg_top_k = cfg.get("top_k", 3)
        else:
            # paths provided directly (e.g. from tests); try to read top_k from config
            try:
                with open(_CONFIG_PATH) as f:
                    cfg = yaml.safe_load(f)["memory"]
                _cfg_top_k = cfg.get("top_k", 3)
            except Exception:
                pass

        self._top_k: int = top_k if top_k is not None else _cfg_top_k

        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        Path(chroma_path).mkdir(parents=True, exist_ok=True)

        self._engine = create_engine(f"sqlite:///{db_path}")
        # ChromaDB: usar CPU no modelo de embeddings ONNX.
        from chromadb.utils.embedding_functions.onnx_mini_lm_l6_v2 import ONNXMiniLM_L6_V2
        from chromadb.api.types import DefaultEmbeddingFunction

        def _cpu_embedding(self, input):
            return ONNXMiniLM_L6_V2(
                preferred_providers=["CPUExecutionProvider"]
            )(input)

        DefaultEmbeddingFunction.__call__ = _cpu_embedding

        self._chroma = chromadb.PersistentClient(path=chroma_path)
        self._facts = self._chroma.get_or_create_collection("facts")
        self._setup_db()

    def _setup_db(self) -> None:
        with self._engine.connect() as conn:
            conn.execute(text(
                "CREATE TABLE IF NOT EXISTS summaries "
                "(id INTEGER PRIMARY KEY, content TEXT, created_at TEXT)"
            ))
            conn.commit()

    def store_fact(self, fact: str) -> None:
        """Store a semantic fact. Identical facts are deduplicated by hash ID."""
        fact_id = hashlib.md5(fact.encode()).hexdigest()
        self._facts.upsert(ids=[fact_id], documents=[fact])

    def search_facts(self, query: str, top_k: int | None = None) -> list[str]:
        """Return semantically relevant facts for the query."""
        k = top_k if top_k is not None else self._top_k
        count = self._facts.count()
        if count == 0:
            return []
        results = self._facts.query(query_texts=[query], n_results=min(k, count))
        return [d for d in results.get("documents", [[]])[0] if d]

    def save_conversation_summary(self, summary: str) -> None:
        with self._engine.connect() as conn:
            conn.execute(
                text("INSERT INTO summaries (content, created_at) VALUES (:c, :t)"),
                {"c": summary, "t": datetime.now(timezone.utc).isoformat()}
            )
            conn.commit()

    def get_recent_summaries(self, n: int = 5) -> list[str]:
        with self._engine.connect() as conn:
            rows = conn.execute(
                text("SELECT content FROM summaries ORDER BY id DESC LIMIT :n"),
                {"n": n}
            ).fetchall()
        return [r[0] for r in rows]

    @staticmethod
    def _clean_fact(message: str) -> str:
        """Normalize a memory-worthy message into a cleaner persistent fact."""
        fact = " ".join(message.strip().split())

        prefixes = [
            "lembre que ", "lembre disso: ", "lembra que ",
            "não esqueça que ", "não esquece que ",
            "guarde isso: ", "salve isso: ",
            "remember that ", "remember this: ",
            "don't forget that ", "keep in mind that ",
        ]

        lower = fact.lower()
        for prefix in prefixes:
            if lower.startswith(prefix):
                fact = fact[len(prefix):].strip()
                break

        separators = [
            ", mas ", " mas ",
            ", porém ", " porém ",
            ", contudo ", " contudo ",
            ", só que ", " só que ",
            "; mas ", "; porém ",
        ]

        lower = fact.lower()
        cuts = [
            lower.find(separator)
            for separator in separators
            if lower.find(separator) != -1
        ]
        if cuts:
            fact = fact[:min(cuts)].strip()

        return fact.strip(" .,:;!?")

    def extract_and_store_facts(self, assistant_response: str, user_message: str) -> None:
        """Store durable user facts/preferences while avoiding temporary intentions."""
        message = user_message.strip()
        lower = message.lower()

        explicit_memory = [
            "remember that", "remember this", "don't forget", "keep in mind",
            "lembre que", "lembre disso", "lembra que", "não esqueça",
            "não esquece", "guarde isso", "salve isso",
        ]

        durable_facts = [
            "my name is", "i work", "i like", "i hate", "i love", "i prefer",
            "i live", "i study", "i own", "my favorite", "my birthday",
            "my project", "my computer", "call me", "i usually", "i always",
            "i never",
            "meu nome é", "me chamo", "eu trabalho", "eu gosto", "eu odeio",
            "eu amo", "eu prefiro", "eu moro", "eu estudo", "meu favorito",
            "minha favorita", "meu aniversário", "meu projeto",
            "meu computador", "pode me chamar", "normalmente eu",
            "eu sempre", "eu nunca",
        ]

        if any(t in lower for t in explicit_memory):
            fact = self._clean_fact(message)
            if fact:
                self.store_fact(fact)
            return

        if any(t in lower for t in durable_facts):
            fact = self._clean_fact(message)
            if fact:
                self.store_fact(fact)
