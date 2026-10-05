"""Países (ISO 3166-1, código de 2 letras) com o nome em português — pro
tomador de fora do Brasil (05/10/2026). É o código que vai em `cPais` na
NFS-e (TSCodPaisISO: duas letras maiúsculas). A mesma lista está em
frontend/src/lib/paises.ts (a busca da tela); mudou aqui, mude lá."""

PAISES: dict[str, str] = {
    "AF": "Afeganistão", "ZA": "África do Sul", "AL": "Albânia", "DE": "Alemanha", "AD": "Andorra", "AO": "Angola",
    "AI": "Anguilla", "AQ": "Antártida", "AG": "Antígua e Barbuda", "SA": "Arábia Saudita", "DZ": "Argélia",
    "AR": "Argentina", "AM": "Armênia", "AW": "Aruba", "AU": "Austrália", "AT": "Áustria", "AZ": "Azerbaijão",
    "BS": "Bahamas", "BH": "Bahrein", "BD": "Bangladesh", "BB": "Barbados", "BY": "Belarus", "BE": "Bélgica",
    "BZ": "Belize", "BJ": "Benin", "BM": "Bermudas", "BO": "Bolívia", "BQ": "Bonaire, Santo Eustáquio e Saba",
    "BA": "Bósnia e Herzegovina", "BW": "Botsuana", "BN": "Brunei", "BG": "Bulgária", "BF": "Burkina Faso",
    "BI": "Burundi", "BT": "Butão", "CV": "Cabo Verde", "CM": "Camarões", "KH": "Camboja", "CA": "Canadá",
    "QA": "Catar", "KZ": "Cazaquistão", "TD": "Chade", "CL": "Chile", "CN": "China", "CY": "Chipre",
    "SG": "Singapura", "CO": "Colômbia", "KM": "Comores", "CG": "Congo", "CD": "Congo (República Democrática)",
    "KP": "Coreia do Norte", "KR": "Coreia do Sul", "CI": "Costa do Marfim", "CR": "Costa Rica", "HR": "Croácia",
    "CU": "Cuba", "CW": "Curaçao", "DK": "Dinamarca", "DJ": "Djibuti", "DM": "Dominica", "EG": "Egito",
    "SV": "El Salvador", "AE": "Emirados Árabes Unidos", "EC": "Equador", "ER": "Eritreia", "SK": "Eslováquia",
    "SI": "Eslovênia", "ES": "Espanha", "US": "Estados Unidos", "EE": "Estônia", "SZ": "Essuatíni", "ET": "Etiópia",
    "FJ": "Fiji", "PH": "Filipinas", "FI": "Finlândia", "FR": "França", "GA": "Gabão", "GM": "Gâmbia", "GH": "Gana",
    "GE": "Geórgia", "GI": "Gibraltar", "GD": "Granada", "GR": "Grécia", "GL": "Groenlândia", "GP": "Guadalupe",
    "GU": "Guam", "GT": "Guatemala", "GG": "Guernsey", "GY": "Guiana", "GF": "Guiana Francesa", "GN": "Guiné",
    "GQ": "Guiné Equatorial", "GW": "Guiné-Bissau", "HT": "Haiti", "NL": "Holanda (Países Baixos)", "HN": "Honduras",
    "HK": "Hong Kong", "HU": "Hungria", "YE": "Iêmen", "IM": "Ilha de Man", "KY": "Ilhas Cayman", "CK": "Ilhas Cook",
    "FO": "Ilhas Faroé", "FK": "Ilhas Malvinas (Falkland)", "MH": "Ilhas Marshall", "SB": "Ilhas Salomão",
    "TC": "Ilhas Turcas e Caicos", "VG": "Ilhas Virgens Britânicas", "VI": "Ilhas Virgens Americanas", "IN": "Índia",
    "ID": "Indonésia", "IR": "Irã", "IQ": "Iraque", "IE": "Irlanda", "IS": "Islândia", "IL": "Israel", "IT": "Itália",
    "JM": "Jamaica", "JP": "Japão", "JE": "Jersey", "JO": "Jordânia", "KI": "Kiribati", "KW": "Kuwait",
    "LA": "Laos", "LS": "Lesoto", "LV": "Letônia", "LB": "Líbano", "LR": "Libéria", "LY": "Líbia",
    "LI": "Liechtenstein", "LT": "Lituânia", "LU": "Luxemburgo", "MO": "Macau", "MK": "Macedônia do Norte",
    "MG": "Madagascar", "MY": "Malásia", "MW": "Malawi", "MV": "Maldivas", "ML": "Mali", "MT": "Malta",
    "MA": "Marrocos", "MQ": "Martinica", "MU": "Maurício", "MR": "Mauritânia", "MX": "México", "MM": "Mianmar",
    "FM": "Micronésia", "MZ": "Moçambique", "MD": "Moldávia", "MC": "Mônaco", "MN": "Mongólia", "ME": "Montenegro",
    "MS": "Montserrat", "NA": "Namíbia", "NR": "Nauru", "NP": "Nepal", "NI": "Nicarágua", "NE": "Níger",
    "NG": "Nigéria", "NO": "Noruega", "NC": "Nova Caledônia", "NZ": "Nova Zelândia", "OM": "Omã", "PW": "Palau",
    "PS": "Palestina", "PA": "Panamá", "PG": "Papua-Nova Guiné", "PK": "Paquistão", "PY": "Paraguai", "PE": "Peru",
    "PF": "Polinésia Francesa", "PL": "Polônia", "PR": "Porto Rico", "PT": "Portugal", "KE": "Quênia",
    "KG": "Quirguistão", "GB": "Reino Unido", "CF": "República Centro-Africana", "DO": "República Dominicana",
    "CZ": "República Tcheca", "RE": "Reunião", "RO": "Romênia", "RW": "Ruanda", "RU": "Rússia", "WS": "Samoa",
    "AS": "Samoa Americana", "SM": "San Marino", "LC": "Santa Lúcia", "KN": "São Cristóvão e Névis",
    "ST": "São Tomé e Príncipe", "VC": "São Vicente e Granadinas", "SN": "Senegal", "SL": "Serra Leoa", "RS": "Sérvia",
    "SC": "Seychelles", "SX": "Sint Maarten", "SY": "Síria", "SO": "Somália", "LK": "Sri Lanka", "SD": "Sudão",
    "SS": "Sudão do Sul", "SE": "Suécia", "CH": "Suíça", "SR": "Suriname", "TH": "Tailândia", "TW": "Taiwan",
    "TJ": "Tajiquistão", "TZ": "Tanzânia", "TL": "Timor-Leste", "TG": "Togo", "TO": "Tonga",
    "TT": "Trinidad e Tobago", "TN": "Tunísia", "TM": "Turcomenistão", "TR": "Turquia", "TV": "Tuvalu",
    "UA": "Ucrânia", "UG": "Uganda", "UY": "Uruguai", "UZ": "Uzbequistão", "VU": "Vanuatu", "VA": "Vaticano",
    "VE": "Venezuela", "VN": "Vietnã", "ZM": "Zâmbia", "ZW": "Zimbábue",
}


def nome_do_pais(codigo: str | None) -> str | None:
    """'ie' -> 'Irlanda'. Código que não está na lista volta como veio (em maiúsculas)."""
    codigo = (codigo or "").strip().upper()
    if not codigo:
        return None
    return PAISES.get(codigo, codigo)


def pais_valido(codigo: str | None) -> bool:
    """País de fora do Brasil que eu conheço (o Brasil não entra: aí é CNPJ)."""
    return (codigo or "").strip().upper() in PAISES
