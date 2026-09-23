"""Vigia de lojas da Etsy: so propoe o que e novo na loja e ja vende, nunca
repete o que ja se conhece, e nenhuma falha de uma loja derruba as outras."""

import json
import uuid

import httpx
import pytest
from fastapi.testclient import TestClient

from api import index
from core import auth, db, shops, sources

NOW = 1_790_000_000
DAY = shops.DAY
CRON = {"Authorization": "Bearer segredo"}
ADMIN = {"Authorization": "Bearer admin"}


class FakeEtsy:
    """Responde por caminho: lojas, listagens ativas de uma loja, avaliacoes."""

    def __init__(self, shops_found=None, listings=None, reviews=None, boom=False):
        self.shops_found, self.listings, self.reviews, self.boom = shops_found, listings, reviews, boom
        self.calls: list[str] = []

    def get(self, url, params=None, headers=None):
        self.calls.append(url)
        if self.boom:
            raise httpx.ConnectTimeout("sem rede")
        if url.endswith("/reviews"):
            payload = self.reviews
        elif url.endswith("/listings/active"):
            payload = self.listings
        else:
            payload = self.shops_found
        request = httpx.Request("GET", url)
        if payload is None:
            return httpx.Response(500, text="erro", request=request)
        return httpx.Response(200, text=json.dumps({"count": len(payload), "results": payload}), request=request)

    def close(self):
        pass


def listing(listing_id, title, days_ago):
    return {"listing_id": listing_id, "title": title, "original_creation_timestamp": NOW - days_ago * DAY}


def reviews(*listing_ids):
    return [{"listing_id": i, "create_timestamp": NOW - DAY} for i in listing_ids]


@pytest.fixture(autouse=True)
def chave(monkeypatch):
    monkeypatch.setenv("ETSY_API_KEY", "keystring:secret")


@pytest.mark.parametrize(
    "text,name",
    [
        ("LojaDaAna", "LojaDaAna"),
        ("  LojaDaAna  ", "LojaDaAna"),
        ("https://www.etsy.com/shop/LojaDaAna", "LojaDaAna"),
        ("https://www.etsy.com/pt/shop/LojaDaAna?ref=simple-shop-header-name", "LojaDaAna"),
        ("etsy.com/shop/Loja3D", "Loja3D"),
        ("loja da ana", None),  # espacos: nao e nome de loja
        ("https://outro-site.com/shop/Loja", None),
        ("javascript:alert(1)", None),
        ("a" * 41, None),
        ("", None),
    ],
)
def test_nome_da_loja(text, name):
    assert shops.shop_name_from(text) == name


@pytest.mark.parametrize(
    "title,term",
    [
        ("Chibi Dragon Figure 3D Printed | Desk Decor, Gift for Her", "chibi dragon figure"),
        ("Mechanical Dragon Egg Box - Surprise Container", "mechanical dragon egg box"),
        ("Kitsune Mask, Japanese Fox Mask, Cosplay", "kitsune mask"),
        ("Mom&#39;s Plant Pot (Large)", "mom plant pot"),  # entidade HTML da API
        ("Custom 3D Printed Dragon Egg Box With Lid For Dice", "dragon egg box lid"),
        ("3D Printed Gift", None),  # nada identifica um produto
        ("Planter", None),  # uma palavra e categoria, nao produto
    ],
)
def test_titulo_vira_termo_de_mercado(title, term):
    assert shops.title_term(title) == term


def test_encontra_so_a_loja_com_o_nome_exato():
    found = [{"shop_id": 1, "shop_name": "LojaDaAnaStore"}, {"shop_id": 2, "shop_name": "LojaDaAna"}]
    assert shops.find_shop(FakeEtsy(shops_found=found), "lojadaana") == {"shop_id": 2, "shop_name": "LojaDaAna"}


@pytest.mark.parametrize(
    "client",
    [FakeEtsy(shops_found=[{"shop_id": 1, "shop_name": "Outra"}]), FakeEtsy(boom=True), FakeEtsy(shops_found=None)],
)
def test_loja_inexistente_ou_etsy_em_baixo(client):
    assert shops.find_shop(client, "LojaDaAna") is None


def test_lancamentos_que_ja_vendem_mais_avaliados_primeiro():
    client = FakeEtsy(
        listings=[
            listing(1, "Novo com pouca venda", 10),
            listing(2, "Novo que vende muito", 20),
            listing(3, "Novo que vende", 30),
            listing(4, "Antigo que vende muito", 400),  # fora da janela de lancamento
            listing(5, "Novo sem vendas", 5),
        ],
        reviews=reviews(1, 2, 2, 2, 2, 3, 3, 4, 4, 4, 4, 4),
    )
    rising = shops.rising_listings(client, 42, NOW)
    assert [(n, item["listing_id"]) for n, item in rising] == [(4, 2), (2, 3)]  # a 1 tem so uma avaliacao


def test_loja_sem_lancamentos_recentes_poupa_o_pedido_das_avaliacoes():
    client = FakeEtsy(listings=[listing(1, "Antigo", 300)], reviews=reviews(1, 1, 1))
    assert shops.rising_listings(client, 42, NOW) == []
    assert not any(url.endswith("/reviews") for url in client.calls)


@pytest.mark.parametrize(
    "client",
    [FakeEtsy(boom=True), FakeEtsy(listings=None), FakeEtsy(listings=[listing(1, "Novo", 1)], reviews=None)],
)
def test_falha_da_etsy_nao_derruba(client):
    assert shops.rising_listings(client, 42, NOW) == []


def test_sem_chave_nao_pede_nada(monkeypatch):
    monkeypatch.delenv("ETSY_API_KEY")
    client = FakeEtsy(listings=[listing(1, "Novo", 1)])
    assert shops.rising_listings(client, 42, NOW) == []
    assert shops.find_shop(client, "Loja") is None
    assert client.calls == []


# --- rotas -------------------------------------------------------------------

WATCHED = [
    {"id": str(uuid.uuid4()), "shop_id": 10, "shop_name": "AnimeLab", "category": "geek"},
    {"id": str(uuid.uuid4()), "shop_id": 20, "shop_name": "CasaPrint", "category": "decoracao"},
]
MODELS = [
    {"id": "m1", "keyword": "kitsune mask", "synonyms": [], "category": "geek", "status": "active"},
    {"id": "m2", "keyword": "moon lamp", "synonyms": [], "category": "decoracao", "status": "rejected"},
]


@pytest.fixture
def api(monkeypatch):
    monkeypatch.setenv("CRON_SECRET", "segredo")
    admin = auth.Viewer(user_id="a", email="a@x.y", is_admin=True)
    monkeypatch.setattr(auth, "viewer_from_authorization", lambda h: admin if h == "Bearer admin" else auth.ANONYMOUS)
    monkeypatch.setattr(db, "list_shops", lambda: WATCHED)
    monkeypatch.setattr(db, "fetch_model_rows", lambda *a, **k: MODELS)
    written = {"candidates": [], "added": [], "removed": []}
    monkeypatch.setattr(db, "insert_candidates", lambda rows: written["candidates"].extend(rows) or len(rows))
    monkeypatch.setattr(
        db, "add_shop", lambda sid, name, cat: written["added"].append((sid, name, cat)) or {"id": "novo"}
    )
    monkeypatch.setattr(db, "remove_shop", lambda rid: written["removed"].append(rid) or rid == WATCHED[0]["id"])
    monkeypatch.setattr(sources, "http_client", FakeEtsy)
    return TestClient(index.app), written


def test_vigia_propoe_lancamentos_novos_na_categoria_da_loja(api, monkeypatch):
    client, written = api
    per_shop = {
        10: [
            (9, listing(1, "Kitsune Mask, Fox Mask", 5)),  # ja conhecido
            (7, listing(2, "Chibi Dragon Figure | Anime Gift", 5)),
            (5, listing(3, "Oni Demon Mask - Cosplay", 5)),
            (4, listing(4, "Anime Sword Stand", 5)),
            (3, listing(5, "Manga Shelf Divider", 5)),  # passa do limite por loja
        ],
        20: [
            (6, listing(6, "Aquarius Moon Lamp", 5)),  # variacao de um rejeitado
            (4, listing(7, "Ceramic Look Wall Planter", 5)),
        ],
    }
    monkeypatch.setattr(shops, "rising_listings", lambda _c, shop_id, _now: per_shop[shop_id])

    body = client.get("/api/watch", headers=CRON).json()

    assert body == {"shops_checked": 2, "candidates_proposed": 4}
    assert [(c["keyword"], c["category"], c["source"]) for c in written["candidates"]] == [
        ("chibi dragon figure", "geek", "etsy_shop:AnimeLab"),
        ("oni demon mask", "geek", "etsy_shop:AnimeLab"),
        ("anime sword stand", "geek", "etsy_shop:AnimeLab"),
        ("ceramic look wall planter", "decoracao", "etsy_shop:CasaPrint"),
    ]
    assert all(c["status"] == "pending" for c in written["candidates"])


def test_uma_loja_em_baixo_nao_trava_as_outras(api, monkeypatch):
    client, written = api

    def rising(_c, shop_id, _now):
        if shop_id == 10:
            raise RuntimeError("loja rebentou")
        return [(3, listing(1, "Ceramic Look Wall Planter", 5))]

    monkeypatch.setattr(shops, "rising_listings", rising)
    body = client.post("/api/admin/watch", headers=ADMIN).json()
    assert body["candidates_proposed"] == 1


def test_admin_adiciona_loja_resolvida_na_etsy(api, monkeypatch):
    client, written = api
    monkeypatch.setattr(shops, "find_shop", lambda _c, name: {"shop_id": 77, "shop_name": "AnimeLab"})
    response = client.post(
        "/api/admin/shops", json={"shop": "https://www.etsy.com/shop/animelab", "category": "geek"}, headers=ADMIN
    )
    assert response.status_code == 200
    assert written["added"] == [(77, "AnimeLab", "geek")]


@pytest.mark.parametrize(
    "body,status,detail",
    [
        ({"shop": "loja com espacos", "category": "geek"}, 422, "invalid_shop"),
        ({"shop": "AnimeLab", "category": "inventada"}, 422, "invalid_category"),
        ({"shop": "LojaQueNaoExiste", "category": "geek"}, 404, "shop_not_found"),
    ],
)
def test_admin_nao_grava_loja_invalida(api, monkeypatch, body, status, detail):
    client, written = api
    monkeypatch.setattr(shops, "find_shop", lambda _c, name: None)
    response = client.post("/api/admin/shops", json=body, headers=ADMIN)
    assert (response.status_code, response.json()["detail"]) == (status, detail)
    assert written["added"] == []


def test_admin_lista_e_remove_lojas(api):
    client, written = api
    listed = client.get("/api/admin/shops", headers=ADMIN).json()
    assert [s["shop_name"] for s in listed["shops"]] == ["AnimeLab", "CasaPrint"]
    assert listed["categories"] == ["decoracao", "geek"]

    assert client.delete(f"/api/admin/shops/{WATCHED[0]['id']}", headers=ADMIN).status_code == 200
    assert client.delete(f"/api/admin/shops/{uuid.uuid4()}", headers=ADMIN).status_code == 404
