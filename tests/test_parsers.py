from services.parsers import clean_number, parse_godot, parse_goldfr


def test_clean_number_fr():
    assert clean_number("3 580,25 €") == 3580.25
    assert clean_number("-3,48 %") == -3.48


def test_parse_godot_minimal():
    raw = '''
    <input name="pxAU" id="pxAU" value="682.50">
    Cours et cotation du 20 Francs Marianne Coq en temps réel : 678.70 €
    Valeur intrinsèque : 656.44 €
    Prime : 3.36 %
    '''
    quote = parse_godot(raw)
    assert quote.achat == 682.50
    assert quote.cotation == 678.70
    assert quote.intrinseque == 656.44
    assert quote.prime == 3.36
    assert quote.spread == 3.80


def test_parse_goldfr_minimal():
    raw = '''
    Cours boursable du Napoléon 20 Frs (Louis d'Or) 655.10 €
    -3.48 % (-23,60 €)
    Once d'or 3 490.83 €
    '''
    quote = parse_goldfr(raw)
    assert quote.achat == 655.10
    assert quote.prime == -3.48
    assert quote.once_eur == 3490.83
