from app.services.ai.tools.schema import SchemaField, ToolSchema


def test_schema_field_defaults():
    field = SchemaField(name="query", type="string")

    assert field.required is True
    assert field.description == ""
    assert field.default is None


def test_tool_schema_defaults_to_no_fields():
    schema = ToolSchema()

    assert schema.fields == ()
    assert schema.field_names() == ()
    assert schema.required_fields() == ()


def test_tool_schema_fields_is_coerced_to_a_tuple():
    schema = ToolSchema(fields=[SchemaField(name="a", type="string")])

    assert isinstance(schema.fields, tuple)


def test_field_names_returns_every_field_in_order():
    schema = ToolSchema(fields=(SchemaField(name="a", type="string"), SchemaField(name="b", type="integer")))

    assert schema.field_names() == ("a", "b")


def test_required_fields_excludes_optional_fields():
    schema = ToolSchema(
        fields=(
            SchemaField(name="required_field", type="string", required=True),
            SchemaField(name="optional_field", type="string", required=False),
        )
    )

    assert schema.required_fields() == ("required_field",)


def test_get_returns_the_matching_field():
    field = SchemaField(name="query", type="string")
    schema = ToolSchema(fields=(field,))

    assert schema.get("query") == field


def test_get_returns_none_for_an_unknown_field():
    assert ToolSchema().get("missing") is None
