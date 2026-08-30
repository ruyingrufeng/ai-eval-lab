#!/usr/bin/env python3
"""Shared Flux production presets and ComfyUI workflow builder."""

from __future__ import annotations

from copy import deepcopy


FLUX_PRESETS = {
    "fast": {
        "model": "flux1-schnell-Q4_K_S.gguf",
        "steps": 4,
        "cfg": 1.0,
        "sampler_name": "euler",
        "scheduler": "simple",
        "use_for": "构图探索、批量候选和普通配图",
    },
    "quality": {
        "model": "flux1-dev-Q4_K_S.gguf",
        "steps": 20,
        "cfg": 1.0,
        "sampler_name": "euler",
        "scheduler": "simple",
        "use_for": "最终人像、身份一致性、复杂物件和高质量成片",
    },
}


def get_flux_preset(mode: str = "fast") -> dict:
    try:
        return deepcopy(FLUX_PRESETS[mode])
    except KeyError as exc:
        choices = ", ".join(FLUX_PRESETS)
        raise ValueError(f"unknown Flux mode {mode!r}; expected one of: {choices}") from exc


def build_flux_workflow(
    prompt: str,
    seed: int,
    *,
    mode: str = "fast",
    width: int = 768,
    height: int = 1024,
    filename_prefix: str = "flux/fast",
) -> dict:
    preset = get_flux_preset(mode)
    return {
        "1": {"class_type": "UnetLoaderGGUF", "inputs": {"unet_name": preset["model"]}},
        "2": {"class_type": "DualCLIPLoaderGGUF", "inputs": {
            "clip_name1": "clip_l.safetensors",
            "clip_name2": "t5-v1_1-xxl-encoder-Q5_K_M.gguf",
            "type": "flux",
        }},
        "3": {"class_type": "VAELoader", "inputs": {"vae_name": "ae.safetensors"}},
        "4": {"class_type": "CLIPTextEncode", "inputs": {"clip": ["2", 0], "text": prompt}},
        "5": {"class_type": "CLIPTextEncode", "inputs": {"clip": ["2", 0], "text": ""}},
        "6": {"class_type": "EmptyLatentImage", "inputs": {
            "width": width, "height": height, "batch_size": 1,
        }},
        "7": {"class_type": "KSampler", "inputs": {
            "model": ["1", 0], "seed": seed, "steps": preset["steps"], "cfg": preset["cfg"],
            "sampler_name": preset["sampler_name"], "scheduler": preset["scheduler"],
            "positive": ["4", 0], "negative": ["5", 0], "latent_image": ["6", 0], "denoise": 1.0,
        }},
        "8": {"class_type": "VAEDecode", "inputs": {"samples": ["7", 0], "vae": ["3", 0]}},
        "9": {"class_type": "SaveImage", "inputs": {"filename_prefix": filename_prefix, "images": ["8", 0]}},
    }
