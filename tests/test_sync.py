"""Contratos puros de mapeamento e adoção de Produtos."""

from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta, timezone
from decimal import Decimal

import pytest

from automation.config import PRODUCTS_HEADERS
from automation.models import (
    AmbiguousProductMatchError,
    ImportRecord,
    InvalidProductDataError,
    ProductRow,
    ProductSnapshot,
)
from automation.sync import (
    calculate_discount,
    data_signature,
    find_product_match,
    link_signature,
    map_snapshot_to_product_values,
    plan_publication,
)


def _record(**changes):
    values = [
        "auto-1", "Sim", "Sim", "Não", "9", "Automático",
        "https://www.mercadolivre.com.br/item/MLB123",
        "https://meli.la/current?b=2&a=1", "mercado_livre", "MLB123",
        "Nome importado", "Descrição importada", "Eletrônicos", "Áudio", "Físico",
        Decimal("149.90"), Decimal("199.90"), "25", "CUPOM", "2026-09-01",
        "", "", "", "", "", "REVISAR", "", 0,
        "https://meli.la/old", "", "", "",
    ]
    record, planned = ImportRecord.from_sheet_row(4, values)
    assert planned is None
    return replace(record, **changes)


def _snapshot(**changes):
    fields = {
        "partner": "mercado_livre",
        "external_id": "MLB123",
        "catalog_id": None,
        "source_url": "https://www.mercadolivre.com.br/item/MLB123",
        "affiliate_url": "https://meli.la/current?b=2&a=1",
        "name": "Produto de teste",
        "description": "Descrição de teste",
        "current_price": Decimal("149.90"),
        "previous_price": Decimal("199.90"),
        "currency": "BRL",
        "category": "Eletrônicos",
        "subcategory": "Áudio",
        "product_type": "Físico",
        "coupon": "CUPOM",
        "coupon_expires_at": datetime(2026, 9, 1, tzinfo=UTC),
        "images": tuple(f"https://images.example/{number}.jpg" for number in range(1, 5)),
        "available": True,
        "fetched_at": datetime(2026, 8, 30, 12, tzinfo=UTC),
    }
    fields.update(changes)
    return ProductSnapshot(**fields)


def _row(row_number=7, **changes):
    fields = {
        "row_number": row_number,
        "active": "Sim",
        "product_type": "Físico",
        "partner": "mercado_livre",
        "category": "Eletrônicos",
        "subcategory": "Áudio",
        "name": "Produto anterior",
        "description": "Descrição anterior",
        "price": Decimal("199.90"),
        "promotional_price": Decimal("149.90"),
        "coupon": "CUPOM",
        "offer_expires_at": "2026-09-01T00:00:00Z",
        "affiliate_url": "https://meli.la/old",
        "button_text": "Ver oferta na Mercado Livre",
        "video_url": "https://youtube.example/watch?v=keep",
        "image_1": "https://images.example/old-1.jpg",
        "image_2": "https://images.example/old-2.jpg",
        "image_3": "https://images.example/old-3.jpg",
        "image_4": "https://images.example/old-4.jpg",
        "order": "9",
        "featured": "Não",
        "reconstructed_external_id": "MLB123",
        "reconstructed_catalog_id": None,
    }
    fields.update(changes)
    return ProductRow(**fields)


def test_mapping_places_a_valid_promotion_in_the_two_price_columns():
    values = map_snapshot_to_product_values(_snapshot(), _record(), existing=None)

    assert len(values) == len(PRODUCTS_HEADERS) == 20
    assert values[7:9] == (Decimal("199.90"), Decimal("149.90"))
    assert calculate_discount(Decimal("149.90"), Decimal("199.90")) == 25


def test_discount_rounds_half_up_without_float_intermediates():
    assert calculate_discount(Decimal("75.50"), Decimal("100")) == 25
    assert calculate_discount(Decimal("75.49"), Decimal("100")) == 25
    assert calculate_discount(Decimal("74.50"), Decimal("100")) == 26


@pytest.mark.parametrize("current, previous", [
    (Decimal("0"), Decimal("10")),
    (Decimal("10"), Decimal("0")),
    (Decimal("10"), Decimal("10")),
    (Decimal("11"), Decimal("10")),
    (Decimal("NaN"), Decimal("10")),
    (Decimal("10"), Decimal("Infinity")),
])
def test_discount_refuses_nonpositive_nonfinite_or_nonpromotional_prices(current, previous):
    with pytest.raises(InvalidProductDataError):
        calculate_discount(current, previous)


def test_mapping_keeps_regular_price_decimal_and_blanks_promotion():
    values = map_snapshot_to_product_values(
        _snapshot(previous_price=None, coupon=None, coupon_expires_at=None), _record(), existing=None
    )

    assert values[7:11] == (Decimal("149.90"), "", "", "")
    assert isinstance(values[7], Decimal)


def test_mapping_preserves_human_video_and_missing_old_images_without_deletion():
    existing = _row()
    values = map_snapshot_to_product_values(_snapshot(images=("https://images.example/new.jpg",)), _record(), existing)

    assert values[13] == existing.video_url
    assert values[14:18] == (
        "https://images.example/new.jpg", existing.image_2, existing.image_3, existing.image_4,
    )


@pytest.mark.parametrize("images", [(), ("http://images.example/item.jpg",), ("not a url",)])
def test_mapping_refuses_new_product_without_a_valid_primary_https_image(images):
    with pytest.raises(InvalidProductDataError):
        map_snapshot_to_product_values(_snapshot(images=images), _record(), None)


def test_new_publication_with_no_valid_image_produces_no_sheet_update():
    with pytest.raises(InvalidProductDataError):
        plan_publication(_snapshot(images=()), _record(last_published_url="", affiliate_url=""), ())


def test_mapping_deduplicates_normalized_new_images_and_preserves_valid_adopted_primary():
    existing = _row(
        image_1="HTTPS://IMAGES.EXAMPLE/old.jpg#fragment",
        image_2="http://bad.example/old.jpg",
    )
    adopted = map_snapshot_to_product_values(_snapshot(images=()), _record(), existing)
    replaced = map_snapshot_to_product_values(
        _snapshot(images=(
            "HTTPS://IMAGES.EXAMPLE/new.jpg?b=2&a=1#fragment",
            "https://images.example/new.jpg?a=1&b=2",
        )),
        _record(),
        existing,
    )

    assert adopted[14] == "https://images.example/old.jpg"
    assert adopted[15] == ""
    assert adopted[16:18] == ("https://images.example/old-3.jpg", "https://images.example/old-4.jpg")
    assert replaced[14:18] == (
        "https://images.example/new.jpg?a=1&b=2", "",
        "https://images.example/old-3.jpg", "https://images.example/old-4.jpg",
    )


def test_mapping_refuses_adoption_without_new_or_existing_valid_primary_image():
    with pytest.raises(InvalidProductDataError):
        map_snapshot_to_product_values(
            _snapshot(images=()), _record(), _row(image_1="http://bad.example/image.jpg")
        )


def test_mapping_uses_original_affiliate_link_and_normalizes_default_or_custom_button():
    default_values = map_snapshot_to_product_values(_snapshot(), _record(button_text="  \t "), None)
    custom_values = map_snapshot_to_product_values(_snapshot(), _record(button_text="  Comprar\n agora  "), None)

    assert default_values[11:14] == (
        "https://meli.la/current?b=2&a=1", "Ver oferta na Mercado Livre", "",
    )
    assert custom_values[12] == "Comprar agora"


def test_mapping_gates_active_and_keeps_the_header_order_and_typed_expiry():
    values = map_snapshot_to_product_values(_snapshot(), _record(active="Não", publish="Sim"), None)

    assert values == (
        "Não", "Físico", "mercado_livre", "Eletrônicos", "Áudio", "Produto de teste",
        "Descrição de teste", Decimal("199.90"), Decimal("149.90"), "CUPOM",
        datetime(2026, 9, 1, tzinfo=UTC), "https://meli.la/current?b=2&a=1",
        "Ver oferta na Mercado Livre", "", "https://images.example/1.jpg",
        "https://images.example/2.jpg", "https://images.example/3.jpg",
        "https://images.example/4.jpg", "9", "Não",
    )


def test_data_signature_is_canonical_for_nested_mapping_decimal_and_timezone_equivalents():
    utc = datetime(2026, 8, 30, 15, 0, tzinfo=UTC)
    offset = utc.astimezone(timezone(timedelta(hours=-3)))
    first = {"b": [Decimal("10.00"), None, True], "a": {"when": utc}}
    second = {"a": {"when": offset}, "b": [Decimal("10.00"), None, True]}

    assert data_signature(first) == data_signature(second)
    assert data_signature(first) == "34eec51dfdd819fe24a1df28737ca1f315a224e2110c245032a522ba5bf12393"


def test_data_signature_preserves_decimal_scale_image_order_and_treats_naive_datetime_as_utc():
    point = datetime(2026, 8, 30, 15, 0)

    assert data_signature({"price": Decimal("10.0"), "images": ["one", "two"], "at": point}) == data_signature(
        {"at": point.replace(tzinfo=UTC), "images": ["one", "two"], "price": Decimal("10.0")}
    )
    assert data_signature({"price": Decimal("10.0")}) != data_signature({"price": Decimal("10.00")})
    assert data_signature({"images": ["one", "two"]}) != data_signature({"images": ["two", "one"]})


@dataclass
class _CustomPayload:
    value: object


def test_data_signature_rejects_custom_dataclasses_and_cycles_before_recursing():
    self_list = []
    self_list.append(self_list)
    self_mapping = {}
    self_mapping["self"] = self_mapping
    tuple_cycle_list = []
    tuple_cycle = (tuple_cycle_list,)
    tuple_cycle_list.append(tuple_cycle)

    for value in (
        _CustomPayload("custom"), self_list, self_mapping, tuple_cycle,
        {"bytes": b"nope"}, {"set": {"nope"}},
    ):
        with pytest.raises(InvalidProductDataError):
            data_signature(value)


def test_data_signature_keeps_type_boundaries_between_equal_looking_scalars_and_sequences():
    assert data_signature(True) != data_signature(1)
    assert data_signature("1") != data_signature(1)
    assert data_signature(["x"]) != data_signature(("x",))


@pytest.mark.parametrize("value", [object(), {1: "not-a-string-key"}, float("nan"), Decimal("NaN")])
def test_data_signature_rejects_unsupported_or_nonfinite_values(value):
    with pytest.raises(InvalidProductDataError):
        data_signature(value)


def test_link_signatures_use_the_security_normalization_without_link_disclosure():
    first = "HTTPS://MELI.LA/current?b=2&a=1#fragment"
    equivalent = "https://meli.la/current?a=1&b=2"

    assert link_signature(first) == link_signature(equivalent)
    assert link_signature(first) != link_signature("https://meli.la/other?a=1&b=2")
    with pytest.raises(Exception) as raised:
        link_signature("https://user:secret@meli.la/private?token=not-for-output")
    assert "secret" not in str(raised.value)
    assert "not-for-output" not in str(raised.value)


def test_match_uses_last_published_link_before_current_link_or_identity():
    record = _record(last_published_url="https://meli.la/old", affiliate_url="https://meli.la/current")
    old_match = _row(7, affiliate_url="https://meli.la/old", reconstructed_external_id="OTHER")
    current_match = _row(8, affiliate_url="https://meli.la/current", reconstructed_external_id="MLB123")

    assert find_product_match(record, (old_match, current_match)) is old_match


def test_match_falls_through_to_current_link_then_normalized_partner_external_id():
    record = _record(last_published_url="", affiliate_url="https://meli.la/current")
    current_match = _row(8, affiliate_url="HTTPS://MELI.LA/current#ignored", reconstructed_external_id="OTHER")
    id_match = _row(9, affiliate_url="https://meli.la/else", partner="  MERCADO_LIVRE ", reconstructed_external_id=" mlb123 ")

    assert find_product_match(record, (current_match, id_match)) is current_match
    assert find_product_match(replace(record, affiliate_url=""), (id_match,)) is id_match


def test_match_never_uses_substrings_or_empty_identity_values():
    record = _record(last_published_url="", affiliate_url="", external_id="MLB123")
    lookalike = _row(7, reconstructed_external_id="xMLB123x", affiliate_url="https://meli.la/lookalike")
    empty = _row(8, partner="", reconstructed_external_id="", affiliate_url="")

    assert find_product_match(record, (lookalike, empty)) is None


def test_match_refuses_an_ambiguous_tier_before_considering_lower_tiers():
    record = _record(last_published_url="https://meli.la/old")
    first = _row(7, affiliate_url="https://meli.la/old", reconstructed_external_id="other")
    second = _row(8, affiliate_url="https://meli.la/old#fragment", reconstructed_external_id="MLB123")

    with pytest.raises(AmbiguousProductMatchError):
        find_product_match(record, (first, second))


def test_match_refuses_ambiguous_current_link_or_identity_tiers_independently():
    current_record = _record(last_published_url="", affiliate_url="https://meli.la/current")
    current_rows = (
        _row(7, affiliate_url="https://meli.la/current", reconstructed_external_id="OTHER"),
        _row(8, affiliate_url="https://meli.la/current#fragment", reconstructed_external_id="MLB123"),
    )
    identity_record = _record(last_published_url="", affiliate_url="")
    identity_rows = (
        _row(7, affiliate_url="https://meli.la/first"),
        _row(8, affiliate_url="https://meli.la/second"),
    )

    with pytest.raises(AmbiguousProductMatchError):
        find_product_match(current_record, current_rows)
    with pytest.raises(AmbiguousProductMatchError):
        find_product_match(identity_record, identity_rows)


def test_match_refuses_duplicate_or_invalid_product_row_identity():
    first = _row(7)
    with pytest.raises(AmbiguousProductMatchError):
        find_product_match(_record(), (first, replace(first, affiliate_url="https://meli.la/other")))
    with pytest.raises(AmbiguousProductMatchError):
        find_product_match(_record(), (_row(True),))


def test_publication_plans_an_update_for_adoption_without_erasing_preserved_values():
    record = _record(last_published_url="https://meli.la/old")
    update, = plan_publication(_snapshot(), record, (_row(),))

    assert update.range_name == "'Produtos'!A7:T7"
    assert len(update.values) == 1
    assert len(update.values[0]) == 20
    assert update.values[0][11] == "https://meli.la/current?b=2&a=1"
    assert update.values[0][13] == "https://youtube.example/watch?v=keep"


def test_publication_plans_the_next_row_for_create_and_no_writes_for_noop_or_unapproved_record():
    snapshot = _snapshot()
    record = _record(last_published_url="", affiliate_url="https://meli.la/current?b=2&a=1")
    create, = plan_publication(snapshot, record, (_row(7, affiliate_url="https://meli.la/other", reconstructed_external_id="OTHER"),))
    matching_values = map_snapshot_to_product_values(snapshot, record, _row(7, affiliate_url=snapshot.affiliate_url, video_url=""))
    exact = _row(7, affiliate_url=snapshot.affiliate_url, video_url="", **{
        "active": matching_values[0], "product_type": matching_values[1], "partner": matching_values[2],
        "category": matching_values[3], "subcategory": matching_values[4], "name": matching_values[5],
        "description": matching_values[6], "price": matching_values[7], "promotional_price": matching_values[8],
        "coupon": matching_values[9], "offer_expires_at": "2026-09-01T00:00:00Z", "button_text": matching_values[12],
        "image_1": matching_values[14], "image_2": matching_values[15], "image_3": matching_values[16],
        "image_4": matching_values[17], "order": matching_values[18], "featured": matching_values[19],
    })

    assert create.range_name == "'Produtos'!A8:T8"
    assert plan_publication(snapshot, record, (exact,)) == ()
    assert plan_publication(snapshot, replace(record, publish="Não"), ()) == ()


def test_publication_rejects_invalid_domain_objects_before_planning_a_write():
    with pytest.raises(InvalidProductDataError):
        plan_publication(_snapshot(), object(), ())


def test_publication_compares_expiry_semantically_and_rejects_malformed_existing_expiry():
    snapshot = _snapshot(
        coupon_expires_at=datetime(2026, 8, 31, 21, tzinfo=timezone(timedelta(hours=-3)))
    )
    record = _record(last_published_url="", affiliate_url="https://meli.la/current?b=2&a=1")
    desired = map_snapshot_to_product_values(
        snapshot, record, _row(affiliate_url=snapshot.affiliate_url, video_url="")
    )
    equal = _row(affiliate_url=snapshot.affiliate_url, video_url="", **{
        "active": desired[0], "product_type": desired[1], "partner": desired[2],
        "category": desired[3], "subcategory": desired[4], "name": desired[5],
        "description": desired[6], "price": desired[7], "promotional_price": desired[8],
        "coupon": desired[9], "offer_expires_at": "2026-09-01T00:00:00Z",
        "button_text": desired[12], "image_1": desired[14], "image_2": desired[15],
        "image_3": desired[16], "image_4": desired[17], "order": desired[18],
        "featured": desired[19],
    })

    assert plan_publication(snapshot, record, (equal,)) == ()
    assert plan_publication(snapshot, record, (replace(equal, offer_expires_at="2026-09-01"),)) == ()
    changed, = plan_publication(
        snapshot, record, (replace(equal, offer_expires_at="2026-09-02"),)
    )
    assert changed.range_name == "'Produtos'!A7:T7"
    with pytest.raises(InvalidProductDataError):
        plan_publication(snapshot, record, (replace(equal, offer_expires_at="tomorrow"),))
    with pytest.raises(InvalidProductDataError):
        plan_publication(
            snapshot, record, (replace(equal, offer_expires_at="2026-09-01 00:00:00Z"),)
        )


@pytest.mark.parametrize("invalid_rows", [None, 3, "not rows", b"not rows", (_row(7), object())])
def test_matching_and_publication_reject_invalid_product_row_collections(invalid_rows):
    record = _record()
    with pytest.raises(InvalidProductDataError):
        find_product_match(record, invalid_rows)
    with pytest.raises(InvalidProductDataError):
        plan_publication(_snapshot(), record, invalid_rows)


def test_matching_and_publication_reject_generator_product_rows_outside_sequence_contract():
    with pytest.raises(InvalidProductDataError):
        find_product_match(_record(), (_row() for _ in range(1)))
    with pytest.raises(InvalidProductDataError):
        plan_publication(_snapshot(), _record(), (_row() for _ in range(1)))
