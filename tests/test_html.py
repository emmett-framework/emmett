from emmett.html import asis, cat, tag


def test_tag_self_closed():
    br = tag.br()
    assert str(br) == "<br />"


def test_tag_non_closed():
    p = tag.p()
    assert str(p) == "<p></p>"


def test_tag_components():
    t = tag.div(tag.p(), tag.p())
    assert str(t) == "<div><p></p><p></p></div>"


def test_tag_attributes():
    d = tag.div(_class="test", _id="test", _test="test")
    assert str(d) == '<div class="test" id="test" test="test"></div>'


def test_tag_attributes_dict():
    d = tag.div(_class="test", _hx={"foo": "bar"})
    assert str(d) == '<div class="test" hx-foo="bar"></div>'


def test_tag_attributes_data():
    d1 = tag.div(data={"foo": "bar"})
    d2 = tag.div(_data={"foo": "bar"})
    assert str(d1) == str(d2) == '<div data-foo="bar"></div>'


def test_cat():
    t = cat(tag.p(), tag.p())
    assert str(t) == "<p></p><p></p>"


def test_asis():
    t = asis('{foo: "bar"}')
    assert str(t) == '{foo: "bar"}'
