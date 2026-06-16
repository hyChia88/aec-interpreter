"""Modal deployment for the AEC Interpreter VLM workers.

This is the deployable replacement for the frozen old-repo source:
`master_thesis/mscd_demo/training/inference.py`.

It exposes the two Modal classes used by this refactored repo:
  - G8ModelPredictor: canonical LoRA6 G8 extraction endpoint used by the live backend.
  - BaseVLMReranker: zero-shot Qwen2.5-VL baseline used by eval/vlm_reranker_baseline.py.

The large artifacts are intentionally not committed. G8 loads its adapter from the
`mscd-checkpoints` Modal Volume by default:
  /checkpoints/mscd-lora-v6-g8-posctx-dim/best

Deploy:
  modal deploy deploy/vlm_modal_app.py
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path

import modal

APP_NAME = "mscd-vlm-lora3-inference"
BASE_MODEL = "unsloth/Qwen2.5-VL-7B-Instruct-bnb-4bit"
ADAPTER_PATH_G8 = os.getenv("ADAPTER_PATH_G8", "/checkpoints/mscd-lora-v6-g8-posctx-dim/best")

app = modal.App(APP_NAME)

inference_image = (
    modal.Image.debian_slim(python_version="3.11")
    .apt_install("git")
    .pip_install(
        "unsloth",
        "qwen-vl-utils",
        "datasets==4.3.0",
        "hf-transfer",
    )
    .run_commands(
        "pip install --no-deps --force-reinstall "
        "'unsloth @ git+https://github.com/unslothai/unsloth.git'"
    )
    .pip_install("transformers==4.56.2")
    .run_commands("pip install --no-deps trl==0.22.2")
    .env({"HF_HOME": "/model_cache"})
)

model_cache = modal.Volume.from_name("mscd-model-cache", create_if_missing=True)
checkpoint_vol = modal.Volume.from_name("mscd-checkpoints", create_if_missing=True)

_SYSTEM_PROMPT_G7 = (
    "You are a construction site assistant that extracts IFC search constraints "
    "from multimodal evidence. Use the floorplan and site photo to reason about "
    "storey, element type, position context, and spatial relations. Output valid "
    "JSON only with fields storey_name, ifc_class, space_name, target_name_keyword, "
    "position_context, and spatial_relations. Each spatial relation must use "
    "predicate/object_type and may include object_subtype, direction, object_material, "
    "confidence. Only include direction, object_subtype, or position_context when "
    "supported by the visual or topological evidence. Do not guess. Return JSON only."
)

_RERANK_SYSTEM = (
    "You ground a marked building element to its record in a BIM database. You are given a "
    "site photo and a floorplan in which the target element is marked, followed by a numbered "
    "list of candidate database records. Exactly one candidate is the marked element. Use "
    "the photo and marked floorplan position to decide. Reply with JSON only: "
    "{\"ranking\": [candidate numbers from most to least likely]}."
)


def _pil_images(image_bytes_list: list[bytes]):
    import io
    from PIL import Image

    return [Image.open(io.BytesIO(b)).convert("RGB") for b in image_bytes_list]


def _parse_json(raw_output: str) -> tuple[dict | None, bool]:
    try:
        parsed = json.loads(raw_output)
    except json.JSONDecodeError:
        return None, False
    return parsed if isinstance(parsed, dict) else None, True


@app.cls(
    image=inference_image,
    gpu="A100",
    volumes={"/model_cache": model_cache, "/checkpoints": checkpoint_vol},
    container_idle_timeout=1800,
)
class G8ModelPredictor:
    """Canonical LoRA6 G8 position-context extractor used by eval/live_infer.py."""

    @modal.enter()
    def load_model(self):
        from peft import PeftModel
        from transformers import AutoProcessor
        from unsloth import FastVisionModel

        print(f"Loading base model: {BASE_MODEL}")
        self.model, _tokenizer = FastVisionModel.from_pretrained(BASE_MODEL, load_in_4bit=True)

        print(f"Loading G8 adapter from {ADAPTER_PATH_G8}...")
        assert os.path.isdir(ADAPTER_PATH_G8), f"Adapter not found: {ADAPTER_PATH_G8}"
        self.model = PeftModel.from_pretrained(self.model, ADAPTER_PATH_G8)
        FastVisionModel.for_inference(self.model)
        self.processor = AutoProcessor.from_pretrained(BASE_MODEL)
        print("G8 model loaded.")

    @modal.method()
    def predict(
        self,
        image_bytes_list: list[bytes],
        chat_text: str = "",
        metadata_text: str = "",
    ) -> dict:
        return self._predict_core(_pil_images(image_bytes_list), chat_text, metadata_text)

    def _predict_core(self, pil_images: list, chat_text: str, metadata_text: str) -> dict:
        import torch

        content_parts = [{"type": "image", "image": img} for img in pil_images]
        text_parts = []
        if metadata_text:
            text_parts.append(metadata_text)
        if chat_text:
            text_parts.append(f"[Chat Log]\n{chat_text}")
        if text_parts:
            content_parts.append({"type": "text", "text": "\n".join(text_parts)})

        messages = [
            {"role": "system", "content": _SYSTEM_PROMPT_G7},
            {"role": "user", "content": content_parts},
        ]
        input_text = self.processor.apply_chat_template(
            messages, tokenize=False, add_generation_prompt=True
        )
        proc_kwargs = dict(text=[input_text], add_special_tokens=False, return_tensors="pt")
        if pil_images:
            proc_kwargs["images"] = pil_images
        inputs = self.processor(**proc_kwargs).to(self.model.device)

        with torch.no_grad():
            output_ids = self.model.generate(
                **inputs, max_new_tokens=320, do_sample=False, use_cache=True
            )
        trimmed = output_ids[0][len(inputs.input_ids[0]) :]
        raw_output = self.processor.decode(trimmed, skip_special_tokens=True).strip()
        parsed, valid_json = _parse_json(raw_output)
        return {"raw_output": raw_output, "parsed": parsed, "valid_json": valid_json}


@app.cls(
    image=inference_image,
    gpu="A100",
    volumes={"/model_cache": model_cache, "/checkpoints": checkpoint_vol},
    container_idle_timeout=1800,
)
class BaseVLMReranker:
    """Zero-shot Qwen2.5-VL reranker baseline, no LoRA adapter."""

    @modal.enter()
    def load_model(self):
        from transformers import AutoProcessor
        from unsloth import FastVisionModel

        print(f"Loading base model (no adapter): {BASE_MODEL}")
        self.model, _tokenizer = FastVisionModel.from_pretrained(BASE_MODEL, load_in_4bit=True)
        FastVisionModel.for_inference(self.model)
        self.processor = AutoProcessor.from_pretrained(BASE_MODEL)
        print("Base VLM reranker loaded.")

    @modal.method()
    def rerank(
        self,
        image_bytes_list: list[bytes],
        candidates: list[str],
        note_text: str = "",
        metadata_text: str = "",
        max_new_tokens: int = 512,
    ) -> dict:
        import torch

        pil_images = _pil_images(image_bytes_list)
        cand_block = "\n".join(f"[{i}] {c}" for i, c in enumerate(candidates))

        content_parts = [{"type": "image", "image": img} for img in pil_images]
        text_parts = []
        if metadata_text:
            text_parts.append(metadata_text)
        if note_text:
            text_parts.append(f"[Site Note]\n{note_text}")
        text_parts.append(f"[Candidates]\n{cand_block}")
        content_parts.append({"type": "text", "text": "\n".join(text_parts)})

        messages = [
            {"role": "system", "content": _RERANK_SYSTEM},
            {"role": "user", "content": content_parts},
        ]
        input_text = self.processor.apply_chat_template(
            messages, tokenize=False, add_generation_prompt=True
        )
        proc_kwargs = dict(text=[input_text], add_special_tokens=False, return_tensors="pt")
        if pil_images:
            proc_kwargs["images"] = pil_images
        inputs = self.processor(**proc_kwargs).to(self.model.device)

        with torch.no_grad():
            output_ids = self.model.generate(
                **inputs, max_new_tokens=max_new_tokens, do_sample=False, use_cache=True
            )
        trimmed = output_ids[0][len(inputs.input_ids[0]) :]
        raw_output = self.processor.decode(trimmed, skip_special_tokens=True).strip()

        n = len(candidates)
        order: list = []
        valid_json = False
        try:
            parsed = json.loads(raw_output)
            valid_json = True
            if isinstance(parsed, dict):
                order = list(parsed.get("ranking") or parsed.get("order") or [])
            elif isinstance(parsed, list):
                order = parsed
        except json.JSONDecodeError:
            order = re.findall(r"\d+", raw_output)

        seen, ranking = set(), []
        for x in order:
            try:
                i = int(x)
            except (TypeError, ValueError):
                continue
            if 0 <= i < n and i not in seen:
                seen.add(i)
                ranking.append(i)
        return {"raw_output": raw_output, "ranking": ranking, "valid_json": valid_json}


@app.local_entrypoint()
def test_g8(chat: str = "There's a crack on the window next to the railing, third floor"):
    metadata = (
        "[4D Task Status] TASK_0001: Window inspection - IN_PROGRESS\n"
        "[Project Phase] Interior Fit-out\n"
        "[Location] 3 - Third Floor"
    )
    result = G8ModelPredictor().predict.remote(
        image_bytes_list=[],
        chat_text=chat,
        metadata_text=metadata,
    )
    print(json.dumps(result, indent=2))
