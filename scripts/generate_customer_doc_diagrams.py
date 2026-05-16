from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


ASSETS = Path("docs/codex/v1/assets")
FONT_PATH = "C:/Windows/Fonts/msyh.ttc"
BOLD_PATH = "C:/Windows/Fonts/msyhbd.ttc"

COLORS = {
    "bg": "#F8FAFC",
    "text": "#1F2937",
    "muted": "#64748B",
    "blue": "#DBEAFE",
    "blue_border": "#2563EB",
    "green": "#DCFCE7",
    "green_border": "#16A34A",
    "orange": "#FFEDD5",
    "orange_border": "#EA580C",
    "purple": "#EDE9FE",
    "purple_border": "#7C3AED",
    "line": "#475569",
}


def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    path = BOLD_PATH if bold and Path(BOLD_PATH).exists() else FONT_PATH
    return ImageFont.truetype(path, size)


def box(draw: ImageDraw.ImageDraw, xy: tuple[int, int, int, int], title: str, subtitle: str = "", fill: str = "#FFFFFF", border: str = "#2563EB") -> None:
    draw.rounded_rectangle(xy, radius=16, fill=fill, outline=border, width=3)
    x1, y1, _, _ = xy
    draw.text((x1 + 18, y1 + 14), title, fill=COLORS["text"], font=font(24, True))
    y = y1 + 52
    for line in subtitle.split("\n"):
        if line:
            draw.text((x1 + 18, y), line, fill=COLORS["muted"], font=font(17))
            y += 25


def arrow(draw: ImageDraw.ImageDraw, start: tuple[int, int], end: tuple[int, int], text: str | None = None, dashed: bool = False) -> None:
    import math

    x1, y1 = start
    x2, y2 = end
    if dashed:
        dx, dy = x2 - x1, y2 - y1
        dist = (dx * dx + dy * dy) ** 0.5
        steps = max(1, int(dist // 18))
        for i in range(steps):
            if i % 2 == 0:
                a = i / steps
                b = min(1, (i + 0.65) / steps)
                draw.line((x1 + dx * a, y1 + dy * a, x1 + dx * b, y1 + dy * b), fill=COLORS["line"], width=3)
    else:
        draw.line((x1, y1, x2, y2), fill=COLORS["line"], width=3)
    angle = math.atan2(y2 - y1, x2 - x1)
    size = 11
    p1 = (x2 - size * math.cos(angle - math.pi / 6), y2 - size * math.sin(angle - math.pi / 6))
    p2 = (x2 - size * math.cos(angle + math.pi / 6), y2 - size * math.sin(angle + math.pi / 6))
    draw.polygon([end, p1, p2], fill=COLORS["line"])
    if text:
        tx = (x1 + x2) / 2
        ty = (y1 + y2) / 2 - 26
        bbox = draw.textbbox((0, 0), text, font=font(15))
        tw = bbox[2] - bbox[0]
        th = bbox[3] - bbox[1]
        draw.rounded_rectangle((tx - tw / 2 - 8, ty - 4, tx + tw / 2 + 8, ty + th + 8), radius=8, fill="#FFFFFF")
        draw.text((tx - tw / 2, ty), text, fill=COLORS["muted"], font=font(15))


def save_architecture() -> None:
    img = Image.new("RGB", (1600, 900), COLORS["bg"])
    draw = ImageDraw.Draw(img)
    draw.text((60, 40), "MVP 总体架构图", fill=COLORS["text"], font=font(34, True))
    draw.text((60, 88), "文档上传、异步清洗、向量入库、RAG 检索的最小闭环", fill=COLORS["muted"], font=font(20))
    box(draw, (80, 180, 350, 310), "业务系统", "上传文档\n发起检索", COLORS["blue"], COLORS["blue_border"])
    box(draw, (470, 160, 760, 330), "FastAPI 服务", "文件上传 API\n任务查询 API\nRAG 检索 API", COLORS["blue"], COLORS["blue_border"])
    box(draw, (900, 170, 1150, 300), "RabbitMQ", "清洗任务队列\n异步解耦", COLORS["orange"], COLORS["orange_border"])
    box(draw, (1260, 160, 1530, 330), "Python Worker", "解析 / 清洗\n切块 / Embedding\n写入索引", COLORS["orange"], COLORS["orange_border"])
    box(draw, (430, 470, 700, 610), "PostgreSQL", "文档 / 版本 / 任务\nchunk 元数据", COLORS["green"], COLORS["green_border"])
    box(draw, (760, 470, 1010, 610), "MinIO", "原始文件存储\n支持重建追溯", COLORS["green"], COLORS["green_border"])
    box(draw, (1080, 470, 1330, 610), "Qdrant", "向量存储\nTopK 语义召回", COLORS["green"], COLORS["green_border"])
    box(draw, (1250, 700, 1530, 820), "Embedding 模型", "本地 BGE / 通义\nOpenAI 兼容调用", COLORS["purple"], COLORS["purple_border"])
    arrow(draw, (350, 245), (470, 245), "HTTP")
    arrow(draw, (760, 245), (900, 235), "投递任务", dashed=True)
    arrow(draw, (1150, 235), (1260, 245), "消费任务", dashed=True)
    arrow(draw, (610, 330), (565, 470), "写元数据")
    arrow(draw, (650, 330), (850, 470), "存原文")
    arrow(draw, (1395, 330), (1205, 470), "写向量")
    arrow(draw, (1370, 700), (1380, 330), "生成向量")
    arrow(draw, (470, 280), (350, 280), "任务状态 / 检索结果")
    draw.text((80, 835), "说明：MVP 默认使用 Docker Compose 部署；Rerank 可选，本地 BGE reranker 已验证但不作为最小必选依赖。", fill=COLORS["muted"], font=font(18))
    img.save(ASSETS / "MVP总体架构图.png")


def save_ingestion_flow() -> None:
    img = Image.new("RGB", (1500, 820), COLORS["bg"])
    draw = ImageDraw.Draw(img)
    draw.text((60, 40), "文档入库流程图", fill=COLORS["text"], font=font(34, True))
    steps = [
        ("1 上传文件", "业务系统调用上传接口\n携带知识库与权限标签"),
        ("2 保存原文", "FastAPI 将文件写入 MinIO"),
        ("3 创建任务", "写入 document/version/job"),
        ("4 投递队列", "RabbitMQ 接收清洗任务"),
        ("5 异步处理", "Worker 解析、清洗、切块"),
        ("6 向量化", "调用 BGE/通义生成 Embedding"),
        ("7 写入索引", "chunk 写 PostgreSQL\nvector 写 Qdrant"),
        ("8 完成可检索", "job 状态变为 SUCCEEDED"),
    ]
    positions = [(70, 160), (430, 160), (790, 160), (1150, 160), (1150, 430), (790, 430), (430, 430), (70, 430)]
    fills = [COLORS["blue"], COLORS["green"], COLORS["green"], COLORS["orange"], COLORS["orange"], COLORS["purple"], COLORS["green"], COLORS["blue"]]
    borders = [COLORS["blue_border"], COLORS["green_border"], COLORS["green_border"], COLORS["orange_border"], COLORS["orange_border"], COLORS["purple_border"], COLORS["green_border"], COLORS["blue_border"]]
    for idx, (title, subtitle) in enumerate(steps):
        x, y = positions[idx]
        box(draw, (x, y, x + 280, y + 135), title, subtitle, fills[idx], borders[idx])
    for start, end in [((350, 228), (430, 228)), ((710, 228), (790, 228)), ((1070, 228), (1150, 228)), ((1290, 295), (1290, 430)), ((1150, 498), (1070, 498)), ((790, 498), (710, 498)), ((430, 498), (350, 498))]:
        arrow(draw, start, end)
    draw.text((70, 720), "客户侧关注点：上传成功只代表任务已创建；业务系统应继续查询 job 状态，待 SUCCEEDED 后再发起检索。", fill=COLORS["muted"], font=font(20))
    img.save(ASSETS / "MVP文档入库流程图.png")


def save_search_sequence() -> None:
    img = Image.new("RGB", (1600, 900), COLORS["bg"])
    draw = ImageDraw.Draw(img)
    draw.text((60, 40), "RAG 检索时序图", fill=COLORS["text"], font=font(34, True))
    participants = [("业务系统", 120), ("FastAPI", 420), ("Embedding", 720), ("Qdrant", 1020), ("PostgreSQL", 1320)]
    for name, x in participants:
        is_api = name in {"业务系统", "FastAPI"}
        box(draw, (x - 95, 120, x + 95, 180), name, "", COLORS["blue"] if is_api else COLORS["green"], COLORS["blue_border"] if is_api else COLORS["green_border"])
        draw.line((x, 180, x, 820), fill="#CBD5E1", width=2)
    y = 240
    sequence = [
        (120, 420, "1 提交 query / knowledge_base_ids"),
        (420, 720, "2 生成 query embedding"),
        (720, 420, "3 返回向量"),
        (420, 1020, "4 向量召回 TopK"),
        (1020, 420, "5 返回候选 chunk_id"),
        (420, 1320, "6 回查 chunk 内容与元数据"),
        (1320, 420, "7 返回片段 / 文档 / 版本"),
        (420, 420, "8 粗排、去重、打散、截断"),
        (420, 120, "9 返回命中片段与 search_plan"),
    ]
    for left, right, label in sequence:
        if left == right:
            draw.rounded_rectangle((left + 20, y - 18, left + 240, y + 42), radius=16, outline=COLORS["line"], width=3)
            draw.text((left + 34, y - 8), label, fill=COLORS["muted"], font=font(15))
        else:
            arrow(draw, (left, y), (right, y), label, dashed=left > right)
        y += 68
    draw.text((80, 835), "说明：MVP 返回知识片段，不直接生成大模型答案；业务系统可将片段作为上下文交给后续问答编排。", fill=COLORS["muted"], font=font(18))
    img.save(ASSETS / "MVP检索时序图.png")


if __name__ == "__main__":
    ASSETS.mkdir(parents=True, exist_ok=True)
    save_architecture()
    save_ingestion_flow()
    save_search_sequence()
    print("generated diagrams")
