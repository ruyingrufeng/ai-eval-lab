#!/usr/bin/env python3
"""IP-Adapter 锁脸工作流生成器（RealVisXL + Flux 双版本）。

输入：
  - 参考脸图路径
  - seed
  - prompt（与盲评一致：编辑摄影肖像）
  - model key: realvisxl | flux

输出：
  - ComfyUI workflow JSON dict
"""
import uuid

from flux_presets import get_flux_preset


POSITIVE = (
    "professional editorial photograph of one fictional adult woman age 30, "
    "full body visible head to toe, standing beside a modern red armchair in "
    "a bright minimalist studio, wearing an opaque emerald green long-sleeve "
    "jumpsuit and black ankle boots, holding a closed yellow notebook in her "
    "left hand, a tall leafy plant on the right side, soft daylight from the "
    "left, realistic skin texture, natural anatomy, balanced composition, "
    "accurate green red yellow color separation, sharp photographic detail"
)
NEGATIVE = (
    "child, teenager, underage, age ambiguous, nude, transparent clothing, "
    "sexual content, violence, blood, multiple people, duplicate person, "
    "cropped feet, extra limbs, malformed hands, text, watermark, logo, "
    "anime, illustration, 3d render, oversaturated, blurry, low quality"
)


def _ascii_ref_path(reference_image: str) -> str:
    """ComfyUI LoadImage 只接受 ~/ComfyUI/input/ 里的文件名（不是完整路径）。

    把参考图复制到 input 目录，用纯 ASCII 文件名。
    """
    import os
    import shutil
    input_dir = "/Users/jacky/ComfyUI/input"
    cache = os.path.join(input_dir, "flux_ref.png")
    # Always refresh the cache. Reusing a previous task's flux_ref.png silently
    # applies the wrong identity reference and invalidates comparison runs.
    shutil.copy2(reference_image, cache)
    return "flux_ref.png"  # 只返回文件名，LoadImage 会自己拼 input 目录


def _nid() -> str:
    return str(uuid.uuid4())[:8]


def build_realvisxl_ipadapter_workflow(reference_image: str, seed: int,
                                       ipadapter_weight: float = 0.85,
                                       noise_strength: float = 0.0) -> dict:
    """RealVisXL V5 + IP-Adapter (SDXL vit-h) 锁脸。

    Args:
        reference_image: 参考脸图绝对路径
        seed: KSampler seed
        ipadapter_weight: 锁脸强度（0-1，默认 0.85）
        noise_strength: IP-Adapter noise 注入（0=完全锁脸，1=仅参考构图）

    Returns:
        ComfyUI workflow dict
    """
    ckpt = _nid()
    img_load = _nid()
    ip_loader = _nid()
    ip_apply = _nid()
    pos = _nid()
    neg = _nid()
    latent = _nid()
    sampler = _nid()
    vae = _nid()
    save = _nid()

    ascii_ref = _ascii_ref_path(reference_image)
    return {
        ckpt: {"class_type": "CheckpointLoaderSimple",
               "inputs": {"ckpt_name": "RealVisXL_V5.0_fp16.safetensors"}},
        img_load: {"class_type": "LoadImage",
                   "inputs": {"image": ascii_ref}},  # 路径转 ASCII，避开中文目录
        ip_loader: {"class_type": "IPAdapterUnifiedLoader",
                    "inputs": {"model": [ckpt, 0],  # MODEL 输出（index 0）
                               "preset": "PLUS (high strength)"}},  # SDXL 可用 preset
        ip_apply: {"class_type": "IPAdapterAdvanced",
                   "inputs": {
                       "ipadapter": [ip_loader, 1],  # IPADAPTER 输出（index 1）
                       "image": [img_load, 0],  # IMAGE 输出
                       "model": [ckpt, 0],  # MODEL 输出
                       "weight": ipadapter_weight,
                       "weight_type": "linear",
                       "combine_embeds": "concat",  # 必填
                       "embeds_scaling": "K+V",  # 必填
                       "start_at": 0.0,
                       "end_at": 1.0,
                       "noise": noise_strength,
                   }},
        pos: {"class_type": "CLIPTextEncode",
              "inputs": {"text": POSITIVE, "clip": [ckpt, 1]}},
        neg: {"class_type": "CLIPTextEncode",
              "inputs": {"text": NEGATIVE, "clip": [ckpt, 1]}},
        latent: {"class_type": "EmptyLatentImage",
                 "inputs": {"width": 768, "height": 1024, "batch_size": 1}},
        sampler: {"class_type": "KSampler",
                  "inputs": {"model": [ip_apply, 0],  # 注入 IP-Adapter 后的 model
                             "positive": [pos, 0],
                             "negative": [neg, 0],
                             "latent_image": [latent, 0],
                             "seed": seed,
                             "steps": 25,
                             "cfg": 6.5,
                             "sampler_name": "dpmpp_2m_sde",
                             "scheduler": "karras",
                             "denoise": 1.0}},
        vae: {"class_type": "VAEDecode",
              "inputs": {"samples": [sampler, 0], "vae": [ckpt, 2]}},
        save: {"class_type": "SaveImage",
               "inputs": {"images": [vae, 0],
                          "filename_prefix": f"ipadapter_realvisxl_seed{seed}"}},
    }


def build_flux_ipadapter_workflow(reference_image: str, seed: int,
                                   ipadapter_weight: float = 0.85,
                                   mode: str = "quality") -> dict:
    """Flux Q4 + IP-Adapter Flux 锁脸。

    身份相关任务默认使用 quality（FLUX.1-dev 20 步）；只有显式传入
    mode="fast" 才会使用 Schnell 4 步。

    节点：
      - IPAdapterFluxLoader: 加载 flux-ip-adapter.bin + clip_vision (siglip)
      - ApplyIPAdapterFlux: 注入 model + image + weight
    注意：Flux IP-Adapter 用专用节点，参数 start_percent / end_percent (0-1)
    """
    preset = get_flux_preset(mode)
    unet = _nid()
    clip = _nid()
    vae = _nid()
    img_load = _nid()
    ip_loader = _nid()
    ip_apply = _nid()
    pos = _nid()
    neg = _nid()
    latent = _nid()
    sampler = _nid()
    decode = _nid()
    save = _nid()
    ascii_ref = _ascii_ref_path(reference_image)
    return {
        unet: {"class_type": "UnetLoaderGGUF",
               "inputs": {"unet_name": preset["model"]}},
        clip: {"class_type": "DualCLIPLoaderGGUF",
               "inputs": {"clip_name1": "clip_l.safetensors",
                          "clip_name2": "t5-v1_1-xxl-encoder-Q5_K_M.gguf",
                          "type": "flux"}},
        vae: {"class_type": "VAELoader", "inputs": {"vae_name": "ae.safetensors"}},
        img_load: {"class_type": "LoadImage",
                   "inputs": {"image": ascii_ref}},
        ip_loader: {"class_type": "IPAdapterFluxLoader",
                    "inputs": {"ipadapter": "flux-ip-adapter.bin",
                               "clip_vision": "google/siglip-so400m-patch14-384",
                               "provider": "mps"}},  # Apple Silicon
        ip_apply: {"class_type": "ApplyIPAdapterFlux",
                   "inputs": {"model": [unet, 0],
                              "ipadapter_flux": [ip_loader, 0],
                              "image": [img_load, 0],
                              "weight": ipadapter_weight,
                              "start_percent": 0.0,
                              "end_percent": 1.0}},
        pos: {"class_type": "CLIPTextEncode",
              "inputs": {"text": POSITIVE, "clip": [clip, 0]}},
        neg: {"class_type": "CLIPTextEncode",
              "inputs": {"text": "", "clip": [clip, 0]}},
        latent: {"class_type": "EmptyLatentImage",
                 "inputs": {"width": 768, "height": 1024, "batch_size": 1}},
        sampler: {"class_type": "KSampler",
                  "inputs": {"model": [ip_apply, 0],
                             "positive": [pos, 0],
                             "negative": [neg, 0],
                             "latent_image": [latent, 0],
                             "seed": seed,
                             "steps": preset["steps"],
                             "cfg": preset["cfg"],
                             "sampler_name": preset["sampler_name"],
                             "scheduler": preset["scheduler"],
                             "denoise": 1.0}},
        decode: {"class_type": "VAEDecode",
                 "inputs": {"samples": [sampler, 0], "vae": [vae, 0]}},
        save: {"class_type": "SaveImage",
               "inputs": {"images": [decode, 0],
                          "filename_prefix": f"ipadapter_flux_seed{seed}"}},
    }


# 节点名快速参考（实际节点类型取决于 ComfyUI-IPAdapter-Flux 版本）
IPADAPTER_FLUX_NODES = {
    "load": "LoadIPAdapterFlux",  # 或 "IPAdapterFluxLoader"
    "apply": "ApplyIPAdapterFlux",  # 或 "IPAdapterFluxApply"
}
