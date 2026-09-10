import logging
from pathlib import Path
from typing import Optional

from llama_cpp import Llama

from ..config import CPU_THREADS, LLM_CONTEXT, LLM_MODEL

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = (
    "You are a Terraria Wiki expert. "
    "Always answer using in-game mechanics only. "
    "If the information is not in the wiki context, say that you don't know and do not make up an answer."
)


class LLM:
    """Qwen2.5-1.5B-Instruct via llama-cpp-python."""

    def __init__(
        self,
        model_path: Optional[Path] = None,
        n_ctx: int = LLM_CONTEXT,
        max_tokens: int = 256,
    ):
        self.model_path = model_path or LLM_MODEL
        if not self.model_path.exists():
            raise FileNotFoundError(f"LLM model not found at {self.model_path}")
        logger.info(f"Loading LLM from {self.model_path}...")
        self.model = Llama(
            model_path=str(self.model_path),
            n_ctx=n_ctx,
            n_threads=CPU_THREADS,
            verbose=False,
            n_batch=512,
        )
        self.max_tokens = max_tokens
        logger.info("LLM loaded.")

    def generate(self, question: str, context_chunks: list[str]) -> str:
        context = "\n\n".join(context_chunks)
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": f"Wiki context:\n{context}\n\nQuestion: {question}",
            },
        ]
        response = self.model.create_chat_completion(
            messages=messages,
            max_tokens=self.max_tokens,
            temperature=0.2,
            stop=["<|endoftext|>", "<|im_end|>", "<|im_start|>"],
        )
        answer = response["choices"][0]["message"]["content"].strip()
        logger.info(f"Answer: {answer}")
        return answer
