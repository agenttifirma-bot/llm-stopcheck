# llm-stopcheck

**EN:** A tiny, dependency-free Python library and CLI that catches *silent* LLM failures: a response
with HTTP 200 that is cut off at `max_tokens`, empty because a reasoning model spent its whole budget
thinking, content-filtered, or missing a finish reason. It returns a stable error code and a retry hint
instead of letting half an answer flow downstream.

## Miksi

LLM-kutsu voi onnistua (HTTP 200) ja silti olla käyttökelvoton. Oikea tapaus: reasoning-malli käytti
koko `max_tokens`-budjetin ajatteluun, `content` oli tyhjä ja `finish_reason` oli `length`. Päivittäinen
raportti lähetettiin ilman tiivistystä, eikä mikään kertonut miksi. `llm-stopcheck` muuttaa vastauksen
pieneksi tuomioksi (`Verdict`), jonka koodi on vakaa ja jonka voi kirjata lokiin ja hälyttää.

## Asennus

```
pip install .
```

Ei riippuvuuksia, Python 3.10+.

## Käyttö

```python
import llm_stopcheck as sc

response = client.chat.completions.create(..., max_tokens=3000)

verdict = sc.check(response, max_tokens=3000)   # ei koskaan heitä poikkeusta
if not verdict.ok:
    log.error(sc.format_record(verdict, model="gpt-x"))
    if verdict.hint == sc.HINT_RAISE_MAX_TOKENS:
        ...  # yritä uudelleen isommalla rajalla

text = sc.ensure(response)  # palauttaa tekstin tai heittää TruncatedError / EmptyOutputError / ...
```

Toimii jäsennetyllä OpenAI-yhteensopivalla JSONilla (OpenAI, LiteLLM, OpenRouter, vLLM, Ollama,
DeepSeek) sekä olioilla, joilla on `model_dump()` tai `to_dict()`. Lisäksi `native_finish_reason`
tarkistetaan: LiteLLM/OpenRouter voi normalisoida `MAX_TOKENS`-lopetuksen muotoon `stop`.

## Koodit

| code | merkitys | hint |
|---|---|---|
| `ok` | kunnossa (varoitukset `near_limit` / `at_limit`) | - |
| `truncated` | token-raja täyttyi, vastaus katkesi | `raise_max_tokens` |
| `truncated_empty` | raja täyttyi, sisältö tyhjä | `raise_max_tokens` |
| `reasoning_exhausted` | budjetti meni ajatteluun, vastausta ei tullut | `raise_max_tokens` |
| `tool_call_truncated` | työkalukutsun argumentit keskeneräiset | `raise_max_tokens` |
| `empty_output` | normaali lopetus mutta tyhjä sisältö | `retry` |
| `content_filtered` | palveluntarjoajan suodatin esti | `fail` |
| `refusal` | malli kieltäytyi | `fail` |
| `missing_finish_reason` | ei finish_reasonia (katkennut?) | `retry` |
| `unknown_finish_reason` | tuntematon arvo | `retry` |
| `malformed_response` | vastaus ei ole odotettua muotoa | `retry` |

## CLI

```
llm-stopcheck response.json --max-tokens 3000
curl ... | llm-stopcheck - --json
```

Tulostus: `stopcheck=reasoning_exhausted finish=length native=- tokens=3000/3000 reasoning_tokens=3000 hint=raise_max_tokens`.
Poistumiskoodi 0 = ok, 1 = epäonnistunut tuomio, 2 = käyttö- tai lukuvirhe.

`format_record` puhdistaa arvot (vain ASCII, ei rivinvaihtoja, `=` korvataan), joten lokirivin
väärentäminen mallin tuotoksella ei onnistu.

## Vaihtoehtoja ja miksi tämä

Tarkistus löytyy yleensä kehyskohtaisina korjauksina tai blogiohjeina, ei pienenä erillisenä kirjastona.
Tämä on tarkoituksella pieni: ei riippuvuuksia, ei verkkoa, ei kehysriippuvuutta. Hälytys (Telegram,
healthchecks.io) jätetään kutsujan tehtäväksi; `format_record` ja poistumiskoodit riittävät sen kytkemiseen.

## Testit

```
python -m unittest discover -s tests -t .
```

## Lisenssi

MIT
