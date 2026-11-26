"""Stage-3 report in the same voice and layout as the first project PDF."""
from __future__ import annotations

from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

pdfmetrics.registerFont(TTFont("Body", r"C:\Windows\Fonts\times.ttf"))
pdfmetrics.registerFont(TTFont("Body-Bold", r"C:\Windows\Fonts\timesbd.ttf"))
pdfmetrics.registerFont(TTFont("Body-Italic", r"C:\Windows\Fonts\timesi.ttf"))

INK = colors.HexColor("#111111")
RULE = colors.HexColor("#B9B9B9")
HEAD_BG = colors.HexColor("#F3F3F3")

styles = getSampleStyleSheet()
styles.add(ParagraphStyle(
    "DocTitle", fontName="Body-Bold", fontSize=16, leading=20,
    alignment=TA_CENTER, textColor=INK, spaceAfter=8,
))
styles.add(ParagraphStyle(
    "DocAuthors", fontName="Body", fontSize=12, leading=16,
    alignment=TA_CENTER, textColor=INK, spaceAfter=2,
))
styles.add(ParagraphStyle(
    "DocSub", fontName="Body", fontSize=11, leading=14,
    alignment=TA_CENTER, textColor=INK, spaceAfter=12,
))
styles.add(ParagraphStyle(
    "H1", fontName="Body-Bold", fontSize=13, leading=16,
    textColor=INK, spaceBefore=12, spaceAfter=6,
))
styles.add(ParagraphStyle(
    "BodyJust", fontName="Body", fontSize=11, leading=15,
    alignment=TA_JUSTIFY, textColor=INK, spaceAfter=8,
))
styles.add(ParagraphStyle(
    "Cell", fontName="Body", fontSize=9, leading=12, textColor=INK,
))
styles.add(ParagraphStyle(
    "CellHead", fontName="Body-Bold", fontSize=9, leading=12, textColor=INK,
))
styles.add(ParagraphStyle(
    "Sign", fontName="Body", fontSize=11, leading=16, spaceBefore=6, textColor=INK,
))


def P(text: str) -> Paragraph:
    return Paragraph(text, styles["BodyJust"])


def cell(text: str, head: bool = False) -> Paragraph:
    return Paragraph(str(text), styles["CellHead"] if head else styles["Cell"])


def table(headers: list[str], rows: list[list[str]], widths: list[float]) -> Table:
    data = [[cell(h, head=True) for h in headers]]
    for row in rows:
        data.append([cell(value) for value in row])
    tbl = Table(data, colWidths=widths, repeatRows=1)
    cmds = [
        ("BACKGROUND", (0, 0), (-1, 0), HEAD_BG),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("GRID", (0, 0), (-1, -1), 0.4, RULE),
    ]
    tbl.setStyle(TableStyle(cmds))
    return tbl


def footer(canvas, doc) -> None:
    canvas.saveState()
    canvas.setFont("Body", 10)
    canvas.setFillColor(INK)
    canvas.drawCentredString(A4[0] / 2, 1.15 * cm, str(doc.page))
    canvas.restoreState()


def build(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    doc = SimpleDocTemplate(
        str(path),
        pagesize=A4,
        leftMargin=2.2 * cm,
        rightMargin=2.2 * cm,
        topMargin=1.9 * cm,
        bottomMargin=1.8 * cm,
        title="Agent do odpowiadania na pytania dotyczące trendów i zależności w publikacjach naukowych",
        author="Mateusz Jamroż, Szymon Kiełtyka",
    )
    usable = A4[0] - 4.4 * cm
    story: list = []

    story.append(Paragraph(
        "Agent do odpowiadania na pytania dotyczące trendów i zależności w publikacjach naukowych",
        styles["DocTitle"],
    ))
    story.append(Paragraph("Autorzy: Mateusz Jamroż, Szymon Kiełtyka", styles["DocAuthors"]))
    story.append(Paragraph("Etap 3. Stan wdrożenia modułów. Spotkanie 19.11.2026.", styles["DocSub"]))

    story.append(Paragraph("Stan wdrożenia", styles["H1"]))
    story.append(P(
        "Etap obejmuje wdrożenie modułów, z których w pierwszym dokumencie składała się aplikacja. "
        "Aplikacja działa lokalnie, na komputerze autorów. Użytkownik końcowy prowadzi rozmowę w oknie. "
        "Analityk danych osobnym kodem przygotował pełny zbiór: wczytał plik, policzył wektory, "
        "przypisał kierunki i zbudował bazę wektorową. Te dwa tory dalej są osobne. Pytanie w oknie "
        "nie uruchamia ponownego liczenia wektorów."
    ))
    story.append(P(
        "Zbiór liczy 621&nbsp;515 publikacji. Plik JSONL ma 1&nbsp;979&nbsp;261&nbsp;045 bajtów. "
        "W rekordzie są identyfikator, tytuł, rok, DOI, abstrakty, słowa kluczowe i autorzy. "
        "Metadane leżą w lokalnej bazie SQLite. Wektory leżą w lokalnej bazie Chroma. Jest ich tyle "
        "samo co publikacji, po jednym na pracę. Żadnego rekordu nie pominięto."
    ))
    story.append(P(
        "Autor jest łączony po ORCID. Gdy go brakuje, używany jest uuid, a następnie identyfikator "
        "autora z rekordu. Ten sam klucz powtórzony przy jednej publikacji jest zapisywany raz. "
        "Osoby o tym samym imieniu i nazwisku, ale różnych identyfikatorach, pozostają oddzielone. "
        "Profil pokazuje dopasowane osoby i ich prace."
    ))

    story.append(Paragraph("Liczenie wektorów", styles["H1"]))
    story.append(P(
        "Wektory całego zbioru policzyliśmy raz, w sesji Kaggle, na dwóch kartach NVIDIA Tesla T4. "
        "Każda karta ma 16&nbsp;GB pamięci. Sesja służyła tylko do tego obliczenia. Po zakończeniu "
        "pliki pobraliśmy na komputer autorów. Rozmowa z agentem nie łączy się z Kaggle i nie wymaga "
        "dostępu do tej sesji."
    ))
    story.append(P(
        "Modelem embeddingowym jest BAAI/bge-m3, z biblioteki sentence-transformers. Wybraliśmy go, "
        "bo pytanie bywa po polsku, a abstrakt po angielsku. Model obsługuje oba języki, przyjmuje "
        "do 8192 tokenów i zwraca wektor o 1024 wymiarach. W kodzie ten limit jest ustawiony wprost, "
        "żeby biblioteka nie skróciła tekstu do krótszego, domyślnego progu."
    ))
    story.append(P(
        "Inne modele odpadły przy pełnym zbiorze. multilingual-e5-large dobrze radzi sobie z krótkim "
        "tekstem polskim, ale przy 512 tokenach uciąłby przygotowany opis publikacji. "
        "multilingual-e5-base ma ten sam limit. all-mpnet-base-v2 i all-MiniLM-L6-v2 są nastawione "
        "głównie na angielski. W plikach wektorów i przy późniejszym pytaniu jest więc tylko BAAI/bge-m3."
    ))
    story.append(table(
        ["Model", "Użycie przy pełnym zbiorze"],
        [
            ["BAAI/bge-m3", "użyty na Kaggle i przy pytaniu; 1024 wymiary, do 8192 tokenów"],
            ["multilingual-e5-large", "odrzucony: limit 512 tokenów ucina tekst publikacji"],
            ["multilingual-e5-base", "odrzucony: ten sam limit"],
            ["all-mpnet-base-v2", "odrzucony: model głównie angielski"],
            ["all-MiniLM-L6-v2", "odrzucony: model głównie angielski"],
        ],
        [usable * 0.38, usable * 0.62],
    ))
    story.append(Spacer(1, 8))
    story.append(P(
        "Na wejście modelu idzie jeden tekst na publikację. Składa się z tytułu, wszystkich dostępnych "
        "abstraktów i wszystkich słów kluczowych. Zbędne odstępy są ściągane, a całość jest obcinana "
        "do 3200 znaków. Publikacji nie dzielimy na kilka fragmentów. Wektory są znormalizowane, "
        "a w bazie porównujemy je cosinusowo. Nie dopisujemy przedrostków przed pytaniem ani przed "
        "tekstem publikacji."
    ))
    story.append(P(
        "Na kartach liczenie szło w dokładności float16, żeby partia zmieściła się w pamięci T4. "
        "Na dysk zapisaliśmy float32. Wielkość partii wynosiła 16 tekstów na kartę. Pracowały obie karty. "
        "To samo kodowanie, tym samym modelem i z tą samą normalizacją, liczy później wektor pytania "
        "na komputerze autorów. Przy pytaniu powstaje jeden wektor."
    ))
    story.append(table(
        ["Parametr", "Wartość"],
        [
            ["Miejsce obliczenia", "Kaggle, dwie karty NVIDIA Tesla T4, po 16 GB"],
            ["Model", "BAAI/bge-m3, sentence-transformers"],
            ["Wymiar wektora", "1024"],
            ["Porównanie", "cosinus, wektory znormalizowane"],
            ["Długość kontekstu", "8192 tokenów"],
            ["Tekst jednej publikacji", "tytuł, abstrakty i słowa kluczowe, do 3200 znaków"],
            ["Wektorów na publikację", "1"],
            ["Liczenie / zapis", "float16 / float32"],
            ["Partia na kartę", "16, obie karty"],
            ["Rekordy przetworzone", "621 515, żaden niepominięty"],
            ["Czas", "6514 sekund"],
            ["Pliki", "63 pary vectors i ids; ostatni plik ma 1515 wierszy"],
        ],
        [usable * 0.36, usable * 0.64],
    ))
    story.append(Spacer(1, 8))
    story.append(P(
        "Zadanie przetworzyło 621&nbsp;515 rekordów i trwało 6514 sekund, czyli około godziny i 49 minut. "
        "Wynik jest w 63 parach plików. Wektory leżą w plikach od vectors_00000.npy do vectors_00062.npy, "
        "a identyfikatory w odpowiadających plikach ids. Pełny plik ma 10&nbsp;000 wierszy. Ostatni ma "
        "1515 wierszy. W pliku identyfikatorów jest jeden identyfikator publikacji na linię, w tej samej "
        "kolejności co wiersze wektorów. Obok jest metadata.json z nazwą modelu, wymiarem, normalizacją, "
        "sposobem porównania, typem liczb, kartami, wielkością partii, limitami, liczbą rekordów i czasem."
    ))
    story.append(P(
        "Kolejność była jedna. Najpierw ten sam plik JSONL trafił do sesji Kaggle. Potem model policzył "
        "wektory. Pliki zeszły na dysk lokalny. Dopiero tutaj powstały tabele SQLite, grupy kierunków "
        "i kolekcja w Chromie. Skrypt wstawiał gotowe wektory. Przy budowie indeksu nie wołał modelu drugi raz."
    ))
    story.append(P(
        "W Chromie kolekcja nazywa się publications. Przy wektorze zapisany jest identyfikator publikacji, "
        "tytuł, rok, DOI, numer i nazwa kierunku oraz autorzy. Identyfikator fragmentu to identyfikator "
        "publikacji z końcówką „::0”, bo wektor jest jeden. Ten sam tekst, który poszedł do modelu, "
        "zostaje przy wektorze i służy też wyszukiwaniu słownemu. Rozmowa startuje lokalnie: API na "
        "porcie 8000 i okno w Streamlit. Pierwsze uruchomienie dociąga wagi BAAI/bge-m3, jeśli nie ma "
        "ich jeszcze na dysku. Kaggle w tym uruchomieniu nie bierze udziału."
    ))

    story.append(Paragraph("Klasyfikacja kierunków", styles["H1"]))
    story.append(P(
        "W danych nie ma gotowej nazwy dziedziny. Kierunek jest grupą publikacji o podobnych wektorach. "
        "Na pełnym zbiorze użyliśmy metody MiniBatchKMeans. Liczba grup wynosi 6. Ziarno generatora "
        "wynosi 42, więc przy tych samych wektorach podział się powtarza. Partia uczenia ma 4096 wektorów, "
        "a inicjalizacja jest powtarzana trzykrotnie. Nazwa grupy powstaje z trzech najczęstszych słów "
        "kluczowych prac, które do niej wpadły. Jest to etykieta pomocnicza, a nie pole ze zbioru."
    ))
    story.append(table(
        ["Parametr", "Wartość"],
        [
            ["Metoda", "MiniBatchKMeans"],
            ["Liczba grup", "6"],
            ["Ziarno", "42"],
            ["Wielkość partii", "4096"],
            ["Powtórzenia startu", "3"],
            ["Dane", "zapisane wektory BAAI/bge-m3"],
            ["Nazwa grupy", "trzy najczęstsze słowa kluczowe"],
        ],
        [usable * 0.36, usable * 0.64],
    ))
    story.append(Spacer(1, 8))
    story.append(table(
        ["Grupa", "Nazwa ze słów kluczowych", "Liczba publikacji"],
        [
            ["0", "the / Poland / education", "131 609"],
            ["1", "Energy / Biofield / Trivedi", "79 209"],
            ["2", "Poland / the / sustainable development", "149 497"],
            ["3", "mechanical properties / microstructure / and", "88 590"],
            ["4", "Poland / COVID-19 / children", "77 492"],
            ["5", "machine learning / and / the", "95 118"],
        ],
        [usable * 0.14, usable * 0.60, usable * 0.26],
    ))
    story.append(Spacer(1, 8))
    story.append(P(
        "Suma liczebności wynosi 621&nbsp;515. Skuteczność tego podziału ocenimy później. Sposób oceny "
        "dopiero ustalamy. Do tego czasu pytanie o kierunki korzysta z zapisanego podziału na sześć grup "
        "i z nazw ułożonych ze słów kluczowych."
    ))
    story.append(P(
        "W kodzie jest też klasyfikator oparty na TF-IDF i regresji logistycznej. Miałby przewidywać "
        "etykietę wziętą z pierwszych słów pierwszego słowa kluczowego tej samej pracy. Na pełnych "
        "621&nbsp;515 rekordach nie był uczony. Zbiór nie ma oficjalnych etykiet dziedzin, więc kierunków "
        "w odpowiedziach z niego nie bierzemy."
    ))
    story.append(table(
        ["Parametr", "Wartość"],
        [
            ["Cechy", "TF-IDF, do 5000 cech, pary słów"],
            ["Klasyfikator", "regresja logistyczna"],
            ["Liczba przejść", "1000"],
            ["Wagi klas", "wyrównane"],
            ["Część testowa", "30 procent"],
            ["Ziarno podziału", "42"],
            ["Użycie na pełnym zbiorze", "nieuczony; kierunki biorą się z grup"],
        ],
        [usable * 0.36, usable * 0.64],
    ))
    story.append(Spacer(1, 8))

    story.append(Paragraph("Wyszukiwanie, zestawienia i odpowiedź", styles["H1"]))
    story.append(P(
        "Pytanie o treść jest zamieniane na wektor modelem BAAI/bge-m3 i porównywane z wektorami "
        "publikacji. Obok działa wyszukiwanie słowne BM25, które lepiej trzyma dokładny tytuł, nazwisko "
        "i rzadki termin. Oba wyniki są łączone metodą RRF, bez porównywania niezgodnych skal punktów. "
        "Domyślnie aplikacja zwraca 10 publikacji. W oknie można tę liczbę ustawić od 1 do 15 i dodać filtr roku. "
        "Odpowiedź podaje tytuł, rok i DOI, gdy jest w rekordzie, oraz wskazuje te prace jako źródła."
    ))
    story.append(P(
        "Zestawienia liczone są w SQLite, bo sam wektor nie poda liczebności w latach. Trend kierunku "
        "bierze lata z zakresu 1900–2026. Rok spoza tego zakresu zostaje w bazie i nie wchodzi do szeregu. "
        "Wzorzec rozwoju porównuje pierwszy i ostatni punkt. Zmiana powyżej 10% to wzrost, poniżej 10% "
        "w drugą stronę to spadek, w pozostałym zakresie poziom jest podobny. Jeden rok w szeregu nie jest "
        "opisywany jako trend wieloletni. Osobno aplikacja podaje najliczniejsze kierunki, profil autora, "
        "współautorów i autorów danego kierunku. Brak osoby w zbiorze jest mówiony wprost."
    ))
    story.append(P(
        "Zdanie układa lokalny model llama3.2:3b, przez API na tym samym komputerze. Temperatura wynosi 0,2, "
        "a odpowiedź jest krótka. Model dostaje już policzone wiersze i znalezione źródła. Nie jest źródłem "
        "faktów o zbiorze. Gdy nie odpowie, zdanie składa się wprost z tych samych wierszy. Odpowiedź jest "
        "w języku pytania, po polsku albo po angielsku."
    ))
    story.append(table(
        ["Parametr", "Wartość"],
        [
            ["Model", "llama3.2:3b"],
            ["Dostęp", "lokalne API na tym samym komputerze"],
            ["Temperatura", "0,2"],
            ["Kontekst", "2048 tokenów"],
            ["Długość odpowiedzi", "do 512 tokenów"],
            ["Czas oczekiwania", "90 sekund"],
            ["Gdy model nie odpowie", "zdanie składa się wprost z wyników"],
        ],
        [usable * 0.36, usable * 0.64],
    ))
    story.append(Spacer(1, 8))
    story.append(P(
        "Użytkownik może prowadzić wiele czatów i wracać do każdego z nich. Przy nowym czacie zaznacza, "
        "czy ma on dostać historię innego czatu. Dopytanie w rodzaju „a kto to napisał” opiera się na pracy "
        "albo osobie z dostępnej historii. Gdy historii nie da się rozstrzygnąć, aplikacja mówi o tym "
        "i czeka na doprecyzowanie. Pusta wypowiedź, powitanie i pytanie spoza publikacji nie zmieniają bazy. "
        "Przy liczebności kierunków i szeregu lat w oknie jest też wykres."
    ))
    story.append(P(
        "Sprawdzenie kodu idzie lokalnie, bez kontenerów. Zestaw testów obejmuje klucz autora, tekst "
        "z polskiego i angielskiego abstraktu, rozpoznanie rodzaju pytania, wzorzec wzrostu i spadku "
        "oraz odcięcie lat 1900–2026. Jest też plik z pytaniami na małym zbiorze próbnym. Ocena "
        "wyszukiwania na pełnym indeksie i ocena skuteczności podziału na grupy są przed nami. "
        "Ich sposobu jeszcze nie zamykamy w tym dokumencie."
    ))

    story.append(Paragraph("Co jeszcze dodajemy", styles["H1"]))
    story.append(P(
        "Moduły rozmowy, wyszukiwania i zestawień są wdrożone. Wektory BAAI/bge-m3 z Kaggle zostają. "
        "Nie liczymy ich drugi raz. Zostały prace, które były w planie i których jeszcze nie domknęliśmy."
    ))
    story.append(P(
        "Skuteczność podziału na sześć grup ocenimy osobno. Sposób tej oceny dopiero ustalamy. "
        "Gdy będzie ustalony, zdecydujemy, czy zostaje sześć grup i obecne nazwy, czy zmieniamy liczbę grup "
        "albo regułę nazywania. Jeśli przypisanie trzeba będzie policzyć od nowa, zrobimy to z zapisanych "
        "wektorów, bez drugiej sesji Kaggle, i zaktualizujemy kierunki w SQLite oraz w Chromie."
    ))
    story.append(P(
        "Do pełnych 621&nbsp;515 publikacji przygotujemy pytania po polsku i po angielsku. Przy każdym "
        "wskażemy publikacje, które powinny się pojawić. Porównamy trzy warianty: samo wyszukiwanie słowne, "
        "samo wyszukiwanie wektorem BAAI/bge-m3 oraz połączenie, które jest w aplikacji. Osobna część "
        "zestawu to pytanie po polsku przy abstrakcie po angielsku, bo pod ten przypadek wybraliśmy ten model. "
        "Sprawdzenie ma pokazać, czy właściwa praca jest wśród pierwszych wyników."
    ))
    story.append(P(
        "Liczby z odpowiedzi porównamy z zapytaniem wykonanym bezpośrednio na danych: liczba prac w kierunku, "
        "ranking kierunków i lata w szeregu. Do układania zdań podłączony jest llama3.2:3b. Na tych samych "
        "pytaniach porównamy go z Qwen3 4B i Qwen3 8B. Zostawimy najmniejszy model, który trzyma się "
        "przekazanych rekordów, nie dopisuje publikacji ani liczb spoza wyniku i da się go prowadzić "
        "na komputerze autorów. Do czasu tego porównania rozmowa zostaje przy llama3.2:3b."
    ))
    story.append(P(
        "Na pełnym indeksie zmierzymy też czas startu, zużycie pamięci i czas jednego pytania o treść, "
        "o trend i o autora. Pomiar zrobimy na komputerze autorów, bez kart użytych do liczenia wektorów "
        "na Kaggle. Ma z niego być widać, czy rozmowę da się prowadzić bez długiej przerwy między zdaniami."
    ))
    story.append(Spacer(1, 4))
    story.append(table(
        ["Zadanie", "Stan", "Uwaga"],
        [
            ["Wczytanie pełnego pliku", "ukończone", "621 515 rekordów w SQLite"],
            ["Wektory BAAI/bge-m3 na Kaggle", "ukończone", "dwie karty T4, 6514 sekund, 0 pominiętych"],
            ["Baza Chroma", "ukończona", "gotowe wektory, bez ponownego liczenia"],
            ["Podział na sześć grup", "wdrożony", "sposób oceny skuteczności jeszcze otwarty"],
            ["Wyszukiwanie i okno rozmowy", "wdrożone", "porównanie trzech wariantów przed nami"],
            ["Porównanie modeli językowych", "przed nami", "teraz llama3.2:3b; obok Qwen3 4B i Qwen3 8B"],
            ["Czas i pamięć na pełnym zbiorze", "przed nami", "pomiar na komputerze autorów"],
        ],
        [usable * 0.38, usable * 0.20, usable * 0.42],
    ))

    story.append(Paragraph("Przypadki użycia", styles["H1"]))
    story.append(P(
        "Przypadki z pierwszego dokumentu są w kodzie i da się je przejść na pełnym zbiorze. "
        "Poniżej jest stan każdego z nich."
    ))
    story.append(table(
        ["ID", "Przypadek", "Stan"],
        [
            ["PU-01", "Wczytanie zbioru", "Zrobione. W SQLite i w Chromie jest 621 515 publikacji. Gdy pliku nie ma, baza pozostaje bez zmian."],
            ["PU-02", "Znalezienie prac po treści", "Działa. Pytanie idzie wektorem BAAI/bge-m3 i wyszukiwaniem słownym. Ocena na pełnym indeksie jest przed nami."],
            ["PU-03", "Dominujące kierunki", "Działa na sześciu zapisanych grupach. Sposób oceny tego podziału dopiero ustalamy."],
            ["PU-04", "Wzorzec rozwoju kierunku", "Działa. Lata 1900–2026. Jeden rok nie jest nazywany trendem wieloletnim."],
            ["PU-05", "Autorzy wskazanej pracy", "Działa. Aplikacja podaje osoby zapisane przy rekordzie."],
            ["PU-06", "Dorobek osoby", "Działa. Widać dopasowane osoby, ich publikacje, lata i kierunki. Brak osoby jest mówiony wprost."],
            ["PU-07", "Autorzy kierunku", "Działa na pracach przypisanych do grupy."],
            ["PU-08", "Dopytanie", "Działa w historii czatu. Gdy rekordu nie da się ustalić, aplikacja prosi o doprecyzowanie."],
            ["PU-09", "Wiele czatów", "Działa. Nowy czat może dostać historię innego czatu albo zacząć bez niej."],
            ["PU-10", "Wypowiedź pusta albo spoza zbioru", "Działa. Baza pozostaje bez zmian. Przy powitaniu aplikacja proponuje pytania o publikacje."],
        ],
        [usable * 0.12, usable * 0.28, usable * 0.60],
    ))

    story.append(Spacer(1, 16))
    story.append(Paragraph(
        "Podpis promotora (akceptacja etapu 3): ................................................",
        styles["Sign"],
    ))
    story.append(Paragraph("Data: ................................................", styles["Sign"]))

    doc.build(story, onFirstPage=footer, onLaterPages=footer)


if __name__ == "__main__":
    targets = [
        Path(r"C:\Users\matja\Downloads\Lab 3 (19.11.2026)\Agent do odpowiadania na pytania dotyczące trendów i zależności w publikacjach naukowych.pdf"),
        Path(__file__).resolve().parents[1] / "docs" / "Etap 3 - Agent do odpowiadania na pytania dotyczące trendów i zależności w publikacjach naukowych.pdf",
    ]
    for target in targets:
        build(target)
        print(target)
