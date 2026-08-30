#!/usr/bin/env python3
"""跨 prompt 场景盲评 prompt 定义（4 场景 × 2 模型）。

每个场景给出：
  - name: 场景名
  - positive_realvisxl: RealVisXL 用 prompt
  - negative_realvisxl: RealVisXL negative
  - positive_flux: Flux 用 prompt（无 negative）
  - sampler_realvisxl: {steps, cfg, sampler, scheduler}
  - sampler_flux: {steps, cfg, sampler, scheduler}（Flux 强制 cfg=1.0）
  - width, height
"""

SCENES = {
    "product": {
        "name": "产品图（白底产品）",
        "description": "单个产品居中，纯色背景，专业灯光",
        "positive_realvisxl": (
            "professional product photograph of a single modern minimalist "
            "ceramic coffee mug in matte white, centered on pure white seamless "
            "background, soft studio lighting from upper left, subtle ground "
            "shadow, no people, no text, sharp focus, clean commercial style, "
            "high resolution product photography, e-commerce ready"
        ),
        "negative_realvisxl": (
            "people, person, hand, multiple objects, cluttered, watermark, "
            "text, blurry, low quality, harsh shadow, anime, illustration"
        ),
        "positive_flux": (
            "professional product photograph of a single modern minimalist "
            "ceramic coffee mug in matte white, centered on pure white seamless "
            "background, soft studio lighting from upper left, subtle ground "
            "shadow, no people, no text, sharp focus, clean commercial style, "
            "high resolution product photography, e-commerce ready"
        ),
        "sampler_realvisxl": {"steps": 25, "cfg": 6.5, "sampler_name": "dpmpp_2m_sde", "scheduler": "karras"},
        "sampler_flux": {"steps": 20, "cfg": 1.0, "sampler_name": "euler", "scheduler": "simple"},
        "width": 1024, "height": 1024,
    },
    "landscape": {
        "name": "风景照（城市天际线）",
        "description": "现代城市天际线日落",
        "positive_realvisxl": (
            "breathtaking landscape photograph of modern city skyline at golden "
            "hour sunset, dramatic warm orange and pink sky, glass skyscrapers "
            "reflecting sunlight, river in foreground, sharp architectural "
            "detail, photographic style, high resolution, vivid colors, "
            "magazine cover quality"
        ),
        "negative_realvisxl": (
            "people, person, text, watermark, blurry, low quality, "
            "oversaturated, anime, illustration, 3d render"
        ),
        "positive_flux": (
            "breathtaking landscape photograph of modern city skyline at golden "
            "hour sunset, dramatic warm orange and pink sky, glass skyscrapers "
            "reflecting sunlight, river in foreground, sharp architectural "
            "detail, photographic style, high resolution, vivid colors, "
            "magazine cover quality"
        ),
        "sampler_realvisxl": {"steps": 25, "cfg": 6.5, "sampler_name": "dpmpp_2m_sde", "scheduler": "karras"},
        "sampler_flux": {"steps": 20, "cfg": 1.0, "sampler_name": "euler", "scheduler": "simple"},
        "width": 1024, "height": 576,  # 16:9 横图（封面常用）
    },
    "abstract": {
        "name": "抽象艺术（几何 + 色彩）",
        "description": "现代抽象几何艺术",
        "positive_realvisxl": (
            "modern abstract geometric art composition, bold contrasting colors "
            "in deep purple magenta teal and gold, layered translucent shapes, "
            "minimalist design, editorial illustration style, clean lines, "
            "high contrast, contemporary gallery poster"
        ),
        "negative_realvisxl": (
            "people, person, face, photo, realistic, watermark, text, "
            "low quality, blurry, cluttered, childish"
        ),
        "positive_flux": (
            "modern abstract geometric art composition, bold contrasting colors "
            "in deep purple magenta teal and gold, layered translucent shapes, "
            "minimalist design, editorial illustration style, clean lines, "
            "high contrast, contemporary gallery poster"
        ),
        "sampler_realvisxl": {"steps": 25, "cfg": 6.5, "sampler_name": "dpmpp_2m_sde", "scheduler": "karras"},
        "sampler_flux": {"steps": 20, "cfg": 1.0, "sampler_name": "euler", "scheduler": "simple"},
        "width": 1024, "height": 1024,
    },
    "interior": {
        "name": "室内场景（现代咖啡馆）",
        "description": "现代极简咖啡馆一角",
        "positive_realvisxl": (
            "interior photograph of a modern minimalist cafe corner, warm "
            "wooden table in foreground, single ceramic cup with latte art, "
            "soft window light from right side, blurred background with "
            "plants and bookshelves, no people visible, cozy atmosphere, "
            "lifestyle photography, magazine editorial quality"
        ),
        "negative_realvisxl": (
            "people, person, face, crowd, cluttered, messy, watermark, "
            "text, blurry, low quality, oversaturated"
        ),
        "positive_flux": (
            "interior photograph of a modern minimalist cafe corner, warm "
            "wooden table in foreground, single ceramic cup with latte art, "
            "soft window light from right side, blurred background with "
            "plants and bookshelves, no people visible, cozy atmosphere, "
            "lifestyle photography, magazine editorial quality"
        ),
        "sampler_realvisxl": {"steps": 25, "cfg": 6.5, "sampler_name": "dpmpp_2m_sde", "scheduler": "karras"},
        "sampler_flux": {"steps": 20, "cfg": 1.0, "sampler_name": "euler", "scheduler": "simple"},
        "width": 1024, "height": 768,
    },
}


# 内容尺度盲评（仅 Flux，3 档）
SCALE_TIERS = {
    "casual": {
        "name": "日常（家居服）",
        "description": "基础尺度，确认 Flux 能做日常不出错",
        "positive": (
            "professional lifestyle photograph of a fictional adult woman age "
            "30, standing in bright modern apartment, wearing casual home "
            "loungewear, soft natural light from window, relaxed pose, "
            "realistic skin texture, magazine editorial quality"
        ),
        "sampler": {"steps": 20, "cfg": 1.0, "sampler_name": "euler", "scheduler": "simple"},
        "width": 768, "height": 1024,
    },
    "fashion": {
        "name": "性感（泳衣）",
        "description": "性感尺度，确认 Flux 能处理暴露但不违规内容",
        "positive": (
            "professional fashion photograph of a fictional adult woman age "
            "30, standing on tropical beach, wearing stylish modest swimsuit, "
            "golden hour sunlight, ocean background, athletic but tasteful "
            "pose, realistic skin texture, swimwear editorial quality"
        ),
        "sampler": {"steps": 20, "cfg": 1.0, "sampler_name": "euler", "scheduler": "simple"},
        "width": 768, "height": 1024,
    },
    "artistic": {
        "name": "艺术性大尺度",
        "description": "边界尺度，确认 Flux 在艺术性裸体上不崩",
        "positive": (
            "artistic nude portrait photograph of a fictional adult woman "
            "age 30, tasteful pose with arms strategically placed, soft "
            "natural light from window, classical fine art style reminiscent "
            "of renaissance paintings, museum quality, elegant and respectful"
        ),
        "negative": (
            "child, minor, underage, teen, loli, shota, infant, toddler, "
            "porn, explicit, close-up of genitals, sexual act, violence, "
            "gore, blood, weapon"
        ),
        "sampler": {"steps": 20, "cfg": 1.0, "sampler_name": "euler", "scheduler": "simple"},
        "width": 768, "height": 1024,
    },
}
