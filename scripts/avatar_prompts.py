#!/usr/bin/env python3
"""数字人外形测试 prompt 定义（人物一致性 / 多服装 / 多视角 / 内容尺度）。

参考脸图：results/aesthetic/20260812-blind/flux/seed_0007.png（Flux 95 分封面级）
"""

# ============ 人物一致性（基础）============
# 沿用盲评 prompt，单一站姿，10 seed 测稳定性
CONSISTENCY_POSITIVE = (
    "professional editorial photograph of one fictional adult woman age 30, "
    "full body visible head to toe, standing beside a modern red armchair in "
    "a bright minimalist studio, wearing an opaque emerald green long-sleeve "
    "jumpsuit and black ankle boots, holding a closed yellow notebook in her "
    "left hand, a tall leafy plant on the right side, soft daylight from the "
    "left, realistic skin texture, natural anatomy, balanced composition, "
    "accurate green red yellow color separation, sharp photographic detail"
)
CONSISTENCY_NEGATIVE = (
    "child, teenager, underage, age ambiguous, nude, transparent clothing, "
    "sexual content, violence, blood, multiple people, duplicate person, "
    "cropped feet, extra limbs, malformed hands, text, watermark, logo, "
    "anime, illustration, 3d render, oversaturated, blurry, low quality"
)

# ============ 多服装一致性（5 套）============
# 同一参考脸 + 不同服装 + 同一场景（极简工作室背景，聚焦服装）
CLOTHING_TESTS = {
    "casual": {
        "name": "休闲装",
        "positive": (
            "professional photograph of one fictional adult woman age 30, "
            "standing in bright minimalist studio, wearing casual everyday "
            "outfit: white cotton t-shirt, blue denim jeans, white sneakers, "
            "natural relaxed pose, soft daylight from the left, realistic "
            "skin texture, full body visible head to toe, e-commerce fashion "
            "photography style"
        ),
    },
    "business": {
        "name": "职业装",
        "positive": (
            "professional photograph of one fictional adult woman age 30, "
            "standing in bright minimalist studio, wearing elegant business "
            "attire: tailored black blazer, white silk blouse, black pencil "
            "skirt, black high heels, confident professional pose, soft "
            "daylight from the left, realistic skin texture, full body "
            "visible head to toe, corporate portrait style"
        ),
    },
    "formal": {
        "name": "礼服",
        "positive": (
            "professional photograph of one fictional adult woman age 30, "
            "standing in bright minimalist studio, wearing elegant evening "
            "gown in deep burgundy red, fitted bodice with subtle beading, "
            "flowing floor-length skirt, classic updo hairstyle, graceful "
            "pose, soft daylight from the left, realistic skin texture, "
            "full body visible head to toe, formal event photography"
        ),
    },
    "sport": {
        "name": "运动装",
        "positive": (
            "professional photograph of one fictional adult woman age 30, "
            "standing in bright minimalist studio, wearing modern athletic "
            "wear: black sports bra, high-waisted black leggings, white "
            "running shoes, athletic but feminine pose, soft daylight from "
            "the left, realistic skin texture, full body visible head to "
            "toe, fitness brand photography"
        ),
    },
    "loungewear": {
        "name": "睡衣/家居服",
        "positive": (
            "professional photograph of one fictional adult woman age 30, "
            "standing in bright minimalist studio, wearing elegant loungewear: "
            "soft pink silk pajama set with long sleeves and pants, relaxed "
            "home pose, soft daylight from the left, realistic skin texture, "
            "full body visible head to toe, lifestyle photography"
        ),
    },
}

CLOTHING_NEGATIVE = (
    "child, teenager, underage, age ambiguous, transparent clothing, "
    "sexual content, violence, blood, multiple people, duplicate person, "
    "cropped feet, extra limbs, malformed hands, text, watermark, logo, "
    "anime, illustration, 3d render, oversaturated, blurry, low quality"
)


# ============ 多视角/多表情（5 视角）============
VIEW_TESTS = {
    "front": {
        "name": "正面",
        "positive": (
            "professional portrait photograph of one fictional adult woman "
            "age 30, facing camera directly, head and shoulders visible, "
            "neutral soft smile, soft daylight from the left, studio "
            "background, realistic skin texture, sharp focus on eyes, "
            "commercial headshot quality"
        ),
    },
    "side": {
        "name": "侧面 90 度",
        "positive": (
            "professional portrait photograph of one fictional adult woman "
            "age 30, side profile view facing right, head and shoulders "
            "visible, soft daylight from the left, studio background, "
            "realistic skin texture, sharp facial profile detail, "
            "commercial headshot quality"
        ),
    },
    "three_quarter": {
        "name": "45 度",
        "positive": (
            "professional portrait photograph of one fictional adult woman "
            "age 30, three quarter view facing slightly right, head and "
            "shoulders visible, gentle smile, soft daylight from the left, "
            "studio background, realistic skin texture, sharp focus on eyes, "
            "commercial headshot quality"
        ),
    },
    "back": {
        "name": "背面",
        "positive": (
            "professional photograph of one fictional adult woman age 30, "
            "back view facing away from camera, head and upper back visible, "
            "hair detail visible, soft daylight from the left, studio "
            "background, realistic skin texture, sharp focus on hair and "
            "clothing detail, fashion photography style"
        ),
    },
    "closeup": {
        "name": "特写",
        "positive": (
            "extreme close-up portrait photograph of one fictional adult "
            "woman age 30, face fills the frame from chin to forehead, "
            "neutral soft expression, soft daylight from the left, studio "
            "background, realistic skin texture with visible pores, sharp "
            "focus on eyes and lips, beauty photography quality"
        ),
    },
}

VIEW_NEGATIVE = (
    "child, teenager, underage, age ambiguous, deformed face, asymmetric, "
    "extra eyes, extra mouth, malformed, blurry, low quality, text, "
    "watermark, multiple people, duplicate"
)


# ============ 内容尺度（3 档，仅 Flux）============
SCALE_TIERS = {
    "casual": {
        "name": "日常（家居服）",
        "description": "基础尺度——确认 Flux 能做日常不出错",
        "positive": (
            "professional lifestyle photograph of one fictional adult woman "
            "age 30, standing in bright modern apartment, wearing casual "
            "home loungewear (soft cotton t-shirt and shorts), soft natural "
            "light from window, relaxed pose, realistic skin texture, full "
            "body visible, magazine editorial quality"
        ),
        "negative": (
            "child, minor, underage, teen, loli, shota, infant, toddler, "
            "violence, blood, weapon"
        ),
    },
    "fashion": {
        "name": "时尚（泳衣）",
        "description": "性感尺度——确认 Flux 能处理暴露但不违规内容",
        "positive": (
            "professional fashion photograph of one fictional adult woman "
            "age 30, standing on tropical beach at golden hour, wearing "
            "stylish modest one-piece swimsuit in deep blue, athletic but "
            "tasteful pose, ocean and palm tree background, realistic skin "
            "texture, swimwear editorial quality"
        ),
        "negative": (
            "child, minor, underage, teen, loli, shota, infant, toddler, "
            "nude, topless, see-through, explicit, sexual act, violence, "
            "blood, weapon"
        ),
    },
    "artistic": {
        "name": "艺术性大尺度",
        "description": "边界尺度——确认 Flux 在艺术性裸体上不崩（参考文艺复兴）",
        "positive": (
            "artistic tasteful nude portrait of one fictional adult woman "
            "age 30, soft pose with arms strategically placed, soft warm "
            "window light from left, classical fine art style reminiscent "
            "of renaissance paintings, museum gallery quality, elegant and "
            "respectful, full body visible"
        ),
        "negative": (
            "child, minor, underage, teen, loli, shota, infant, toddler, "
            "porn, explicit sexual content, close-up genitals, sexual act, "
            "violence, gore, blood, weapon, torture, dismemberment"
        ),
    },
}
