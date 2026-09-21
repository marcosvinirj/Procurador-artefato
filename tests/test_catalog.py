"""O seed e as traducoes andam juntos: um produto novo sem etiqueta aparecia
no site com o nome cru da base de dados, e uma categoria nova com o slug."""

import re
from pathlib import Path

from core.discovery import CATEGORY_SEEDS

ROOT = Path(__file__).resolve().parent.parent
SEED = (ROOT / "supabase" / "schema.sql").read_text(encoding="utf-8")
I18N = (ROOT / "app" / "lib" / "i18n.tsx").read_text(encoding="utf-8")
ROWS = re.findall(r"\('([^']+)',\s*'([^']+)',\s*'([^']+)',\s*'\{([^}]*)\}'\)", SEED)
LOCALES = ("en", "pt", "es")


def block(start: str, end: str) -> str:
    return I18N[I18N.index(start) : I18N.index(end, I18N.index(start))]


def test_seed_tem_produtos_e_keywords_unicas():
    keywords = [keyword for _, _, keyword, _ in ROWS]
    assert len(keywords) > 40
    assert len(set(keywords)) == len(keywords)


def test_cada_categoria_tem_etiqueta_nos_tres_idiomas():
    categories = {category for _, category, _, _ in ROWS}
    labels = block("export const CATEGORY_LABEL", "export function categoryLabel")
    for locale in LOCALES:
        line = labels[labels.index(f"  {locale}: {{") :].split("\n")[0]
        assert categories <= set(re.findall(r"(\w+):", line)), (locale, line)


def test_cada_produto_tem_nome_em_ingles():
    """EN e a lingua por omissao: sem entrada, o site mostra o nome em portugues."""
    names = set(re.findall(r"^    '([^']+)':", block("const NAME_LABEL", "  pt: {"), re.M))
    assert {name for name, _, _, _ in ROWS} <= names


def test_sementes_da_descoberta_usam_categorias_que_existem():
    categories = {category for _, category, _, _ in ROWS}
    assert {category for _, category in CATEGORY_SEEDS} <= categories
