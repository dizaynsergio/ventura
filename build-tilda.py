#!/usr/bin/env python3
"""
Собирает из index.html кусок кода для блока T123 в Tilda.

Что делает:
  1. префиксует все классы vn- — чтобы не столкнуться с CSS Тильды
  2. глобальные селекторы (*, body, a, img) заворачивает в .vn
  3. три маски логотипа вшивает в код как data:URI — их не надо загружать
     и Тильда не пережмёт им альфа-канал
  4. фото и видео заменяет на плейсхолдеры __U01__ … — вместо них
     подставляются ссылки с static.tildacdn.com

Запуск:  python3 build-tilda.py
Результат: tilda/ventura-block.html + tilda/upload/ (что грузить в Тильду)
"""
import base64, mimetypes, re, shutil
from pathlib import Path

ROOT = Path(__file__).parent
SRC  = ROOT / "index.html"
OUT  = ROOT / "tilda"
UP   = OUT / "upload"

# маски логотипа — вшиваем прямо в код
INLINE = ["assets/mask-letters.webp", "assets/mask-subtext.webp", "assets/mask-pink.webp"]

# всё остальное грузится в Тильду; порядок = порядок плейсхолдеров
UPLOAD = [
    "assets/hero.gif",          # анимация в буквах логотипа
    "assets/archive/01.jpg",    # гала, танцовщицы
    "assets/archive/02.jpg",    # Vogue Philippines
    "assets/archive/03.jpg",    # фотобудка
    "assets/archive/04.jpg",    # маркет
    "assets/archive/05.jpg",    # поп-ап, стена писем
    "assets/archive/06.jpg",    # стикеры и коктейли
    "assets/team/angeeeliin.jpg",
    "assets/team/babyy_yodaaa.jpg",
    "assets/team/csekoriy.jpg",
    "assets/team/ddynasties_.jpg",
    "assets/team/denjeu.jpg",
]

# Классы берём из атрибутов class= в разметке, а не из CSS.
# Регулярка по CSS цепляла всё, что стоит после точки: расширения файлов
# (mask.webp -> mask.vn-webp) и куски доменов (tildacdn.com -> tildacdn.vn-com).
# В разметке двусмысленности нет. "in" добавляется скриптом на лету, поэтому руками.
def collect_classes(html: str) -> list[str]:
    names = set()
    for m in re.finditer(r'class="([^"]*)"', html):
        names.update(m.group(1).split())
    names.add("in")
    names.discard("vn")
    return sorted(names, key=len, reverse=True)   # длинные первыми, чтобы не съесть префикс


def data_uri(path: Path) -> str:
    mime = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    return f"data:{mime};base64," + base64.b64encode(path.read_bytes()).decode()


def prefix_css(css: str, classes) -> str:
    css = re.sub(r"\.(" + "|".join(map(re.escape, classes)) + r")\b", r".vn-\1", css)
    css = css.replace("@keyframes run", "@keyframes vn-run").replace("animation:run ", "animation:vn-run ")
    # глобальные селекторы -> внутрь .vn, чтобы не задеть блоки Тильды
    css = css.replace("*{box-sizing:border-box;margin:0;padding:0}",
                      ".vn,.vn *,.vn *::before,.vn *::after{box-sizing:border-box;margin:0;padding:0}")
    css = css.replace("body{", ".vn{").replace("body::before{", ".vn::before{")
    css = css.replace("img,video{", ".vn img,.vn video{")
    css = css.replace("\na{color:inherit}", "\n.vn a{color:inherit}")
    css = css.replace("h1,h2,h3{", ".vn h1,.vn h2,.vn h3{")
    return css


def prefix_html(html: str, classes) -> str:
    def repl(m):
        names = " ".join(f"vn-{c}" if c in classes else c for c in m.group(1).split())
        return f'class="{names}"'
    return re.sub(r'class="([^"]*)"', repl, html)


def main(base=""):
    src = SRC.read_text()

    head, rest = src.split("<style>", 1)
    css, body = rest.split("</style>", 1)
    body = body.split("<body>", 1)[1].split("</body>", 1)[0]

    # ССЫЛКИ ПОДСТАВЛЯЕМ ДО ПРЕФИКСОВ: иначе путь уже испорчен и не совпадёт
    # маски: с --base ссылаемся на них по URL, иначе вшиваем в код.
    # T123 не принимает блок длиннее 120 000 символов, а три маски в base64 — это 127 КБ.
    for rel in INLINE:
        if base:
            css = css.replace(f"url('{rel}')", f"url('{base}{rel}')")
        else:
            css = css.replace(f"url('{rel}')", f"url('{data_uri(ROOT / rel)}')")

    for i, rel in enumerate(UPLOAD, 1):
        token = (base + rel) if base else f"__U{i:02d}__"
        css = css.replace(rel, token)
        body = body.replace(rel, token)

    classes = collect_classes(body)
    css = prefix_css(css, classes)
    body = prefix_html(body, classes)

    body = body.replace("classList.add('in')", "classList.add('vn-in')")
    body = body.replace("querySelectorAll('.rise')", "querySelectorAll('.vn-rise')")

    fonts = re.search(r'<link href="https://fonts\.googleapis[^>]*>', head).group(0)

    OUT.mkdir(exist_ok=True)
    name = "ventura-block-live.html" if base else "ventura-block.html"
    (OUT / name).write_text(
        "<!-- VENTURA — вставить целиком в блок T123 (HTML-код).\n"
        "     В настройках блока: ширина контейнера 100%, отступы 0.\n"
        + ("     Медиа отдаётся с GitHub Pages, ничего дозагружать не нужно. -->\n"
           if base else
           "     Плейсхолдеры __U01__ … заменить на ссылки из Тильды. -->\n")
        + fonts + "\n<style>" + css + "</style>\n\n"
        '<div class="vn">' + body.replace("\n", "\n  ") + "</div>\n"
    )

    if UP.exists():
        shutil.rmtree(UP)
    UP.mkdir(parents=True)
    lines = []
    for i, rel in enumerate(UPLOAD, 1):
        src_f = ROOT / rel
        dst = UP / f"{i:02d}-{src_f.name}"
        shutil.copy(src_f, dst)
        lines.append(f"__U{i:02d}__  {dst.name}  ({src_f.stat().st_size // 1024} KB)")
    (OUT / "upload-list.txt").write_text("\n".join(lines) + "\n")

    # страховка: префикс не должен был залезть внутрь ссылок
    out_text = (OUT / name).read_text()
    broken = re.findall(r"[\w./:-]*\.vn-(?:webp|jpg|jpeg|png|gif|mp4|com|io|ru)\b", out_text)
    assert not broken, f"префикс залез в ссылки: {broken[:3]}"
    if base:
        assert out_text.count(base) >= len(INLINE) + len(UPLOAD), "часть ссылок не подставилась"

    size = (OUT / name).stat().st_size
    print(f"tilda/{name} — {size // 1024} KB (маски " + ("ссылками" if base else "вшиты") + ")")
    print(f"tilda/upload/ — {len(UPLOAD)} файлов на загрузку")
    print("\n".join(lines))


if __name__ == "__main__":
    import sys
    # с аргументом --base URL медиа подставляется абсолютными ссылками,
    # без него остаются плейсхолдеры __U01__ …
    base = ""
    if "--base" in sys.argv:
        base = sys.argv[sys.argv.index("--base") + 1].rstrip("/") + "/"
    main(base)
