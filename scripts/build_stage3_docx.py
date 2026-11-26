"""Stage-3 report as a Word file, in the same shape as the first PDF."""
from __future__ import annotations

from pathlib import Path

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

FACE = "Calibri"
INK = RGBColor(0x11, 0x11, 0x11)


def font(run, name: str, size: float, bold: bool = False) -> None:
    run.font.name = name
    run.font.size = Pt(size)
    run.bold = bold
    run.font.color.rgb = INK
    r_pr = run._element.get_or_add_rPr()
    r_fonts = r_pr.find(qn("w:rFonts"))
    if r_fonts is None:
        r_fonts = OxmlElement("w:rFonts")
        r_pr.append(r_fonts)
    for attr in ("w:ascii", "w:hAnsi", "w:cs", "w:eastAsia"):
        r_fonts.set(qn(attr), name)


def paragraph(doc: Document, text: str, *, size=11, bold=False, center=False, before=0, after=8, justify=True):
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(before)
    p.paragraph_format.space_after = Pt(after)
    p.paragraph_format.line_spacing = 1.12
    if center:
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    elif justify:
        p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    run = p.add_run(text)
    font(run, FACE, size, bold)
    return p


def heading(doc: Document, text: str) -> None:
    paragraph(doc, text, size=14, bold=True, justify=False, before=14, after=6)


def shade(cell, color: str) -> None:
    tc = cell._tc
    tc_pr = tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:fill"), color)
    shd.set(qn("w:val"), "clear")
    tc_pr.append(shd)


def borders(cell) -> None:
    tc = cell._tc
    tc_pr = tc.get_or_add_tcPr()
    lines = OxmlElement("w:tcBorders")
    for edge in ("top", "left", "bottom", "right"):
        el = OxmlElement(f"w:{edge}")
        el.set(qn("w:val"), "single")
        el.set(qn("w:sz"), "4")
        el.set(qn("w:space"), "0")
        el.set(qn("w:color"), "B9B9B9")
        lines.append(el)
    tc_pr.append(lines)


def cell_text(cell, text: str, *, bold=False, size=10.5) -> None:
    cell.text = ""
    p = cell.paragraphs[0]
    p.paragraph_format.space_before = Pt(1)
    p.paragraph_format.space_after = Pt(1)
    p.paragraph_format.line_spacing = 1.05
    run = p.add_run(text)
    font(run, FACE, size, bold)
    borders(cell)
    tc = cell._tc
    tc_pr = tc.get_or_add_tcPr()
    v_align = OxmlElement("w:vAlign")
    v_align.set(qn("w:val"), "top")
    tc_pr.append(v_align)


def add_table(doc: Document, headers: list[str], rows: list[list[str]], widths: list[float]) -> None:
    table = doc.add_table(rows=1 + len(rows), cols=len(headers))
    table.autofit = False
    table.allow_autofit = False
    for i, header in enumerate(headers):
        cell_text(table.rows[0].cells[i], header, bold=True)
        shade(table.rows[0].cells[i], "F3F3F3")
    for r, row in enumerate(rows, start=1):
        for c, value in enumerate(row):
            cell_text(table.rows[r].cells[c], value)
    for row in table.rows:
        for cell, width in zip(row.cells, widths):
            cell.width = Cm(width)
    doc.add_paragraph().paragraph_format.space_after = Pt(4)


def build(path: Path) -> None:
    doc = Document()
    section = doc.sections[0]
    section.page_width = Cm(21.0)
    section.page_height = Cm(29.7)
    section.left_margin = Cm(2.3)
    section.right_margin = Cm(2.3)
    section.top_margin = Cm(2.0)
    section.bottom_margin = Cm(2.0)
    normal = doc.styles["Normal"]
    normal.font.name = FACE
    normal.font.size = Pt(11)
    r_pr = normal.element.get_or_add_rPr()
    r_fonts = r_pr.find(qn("w:rFonts"))
    if r_fonts is None:
        r_fonts = OxmlElement("w:rFonts")
        r_pr.append(r_fonts)
    for attr in ("w:ascii", "w:hAnsi", "w:cs", "w:eastAsia"):
        r_fonts.set(qn(attr), FACE)

    usable = 16.4
    paragraph(
        doc,
        "Agent do odpowiadania na pytania dotyczące trendów i zależności w publikacjach naukowych",
        size=16,
        bold=True,
        center=True,
        after=8,
        justify=False,
    )
    paragraph(doc, "Autorzy: Mateusz Jamroż, Szymon Kiełtyka", size=12, center=True, after=2, justify=False)
    paragraph(
        doc,
        "Etap 3. Stan wdrożenia modułów. Spotkanie 19.11.2026.",
        size=12,
        center=True,
        after=10,
        justify=False,
    )

    heading(doc, "Stan wdrożenia")
    paragraph(
        doc,
        "Przygotowano aplikację do odpowiadania na pytania dotyczące publikacji naukowych. Aplikacja działa "
        "lokalnie, na komputerze autorów. Występują w niej dwie role: użytkownik końcowy oraz analityk danych.",
    )
    heading(doc, "Role")
    paragraph(
        doc,
        "Użytkownik końcowy zadaje pytania w oknie rozmowy. Korzysta z przygotowanej bazy. Pytanie nie powoduje "
        "ponownego obliczania wektorów ani przebudowy indeksu.",
    )
    paragraph(
        doc,
        "Analityk danych nie korzysta z okna rozmowy. Przygotowanie zbioru uruchamia kodem pomocniczym. Do jego "
        "zadań należy wczytanie pliku publikacji, obliczenie wektorów, przypisanie kategorii oraz zbudowanie bazy "
        "wektorowej. Wczytanie zbioru i baza wektorowa zostały wykonane: w bazach SQLite i Chroma znajduje się "
        "621 515 publikacji. Grupowanie na kategorie jest nadal opracowywane i również należy do analityka danych. "
        "Zostanie dokończone na zapisanych wektorach. Podczas rozmowy system korzysta z przygotowanych danych. "
        "Zestawienia liczbowe, w tym liczba publikacji w kierunku i szereg lat, są wyznaczane w bazie SQLite "
        "w odpowiedzi na pytanie użytkownika.",
    )
    add_table(
        doc,
        ["Rola", "Zakres", "Stan"],
        [
            ["Użytkownik końcowy", "rozmowa: treść publikacji, kierunki, trendy, autorzy", "wdrożona"],
            ["Analityk danych", "wczytanie zbioru, wektory, kategorie, baza wektorowa", "przygotowanie zbioru wykonane; grupowanie na kategorie w trakcie"],
        ],
        [usable * 0.24, usable * 0.40, usable * 0.36],
    )
    paragraph(
        doc,
        "Zbiór obejmuje 621 515 publikacji zapisanych w jednym pliku JSONL o rozmiarze 1 979 261 045 bajtów. "
        "Z rekordu wykorzystywane są identyfikator, tytuł, rok, DOI, abstrakty, słowa kluczowe oraz autorzy. "
        "Metadane przechowywane są w bazie SQLite, a wektory w bazie Chroma. Każdej publikacji odpowiada jeden wektor. "
        "Podczas obliczeń nie pominięto żadnego rekordu.",
    )
    paragraph(
        doc,
        "Autorów identyfikuje się przede wszystkim na podstawie numeru ORCID. W przypadku jego braku stosowany jest "
        "identyfikator uuid, a następnie identyfikator autora zapisany w rekordzie. Jeżeli ten sam klucz wystąpi "
        "dwukrotnie przy jednej publikacji, zachowywane jest pierwsze wystąpienie. Osoby o tym samym imieniu i nazwisku, "
        "lecz o różnych identyfikatorach, traktowane są odrębnie. W profilu prezentowana jest dopasowana osoba wraz z jej publikacjami.",
    )

    heading(doc, "Obliczanie wektorów")
    paragraph(
        doc,
        "Wektory dla całego zbioru obliczono jednorazowo na platformie Kaggle, z wykorzystaniem dwóch kart "
        "NVIDIA Tesla T4 o pamięci 16 GB każda. Platforma posłużyła wyłącznie do tego zadania. Uzyskane pliki "
        "przeniesiono na komputer lokalny. Dalsze działanie aplikacji, w tym prowadzenie rozmowy, odbywa się lokalnie.",
    )
    paragraph(
        doc,
        "Zastosowano model BAAI/bge-m3 z biblioteki sentence-transformers. Model wybrano ze względu na możliwość "
        "porównania pytania w języku polskim z abstraktem w języku angielskim. Obsługuje oba języki, przyjmuje do "
        "8192 tokenów i zwraca wektor o 1024 wymiarach. Maksymalną długość kontekstu ustawiono jawnie, ponieważ "
        "domyślna konfiguracja biblioteki może obciąć tekst znacznie wcześniej.",
    )
    paragraph(
        doc,
        "Pozostałe rozważane modele nie zostały użyte do pełnego zbioru. Model "
        "multilingual-e5-large dobrze reprezentuje krótki tekst polski, jednak ograniczenie do 512 tokenów "
        "powodowałoby obcięcie przygotowanego opisu publikacji. Model multilingual-e5-base ma identyczne ograniczenie. "
        "Modele all-mpnet-base-v2 oraz all-MiniLM-L6-v2 są przeznaczone przede wszystkim do języka angielskiego. "
        "W plikach wektorów oraz przy kodowaniu pytania stosowany jest zatem model BAAI/bge-m3.",
    )
    add_table(
        doc,
        ["Model", "Decyzja"],
        [
            ["BAAI/bge-m3", "zastosowany na platformie Kaggle oraz przy kodowaniu pytania; 1024 wymiary, do 8192 tokenów"],
            ["multilingual-e5-large", "niewykorzystany: ograniczenie do 512 tokenów obcina opis publikacji"],
            ["multilingual-e5-base", "niewykorzystany z tego samego powodu"],
            ["all-mpnet-base-v2", "niewykorzystany: model przeznaczony przede wszystkim do języka angielskiego"],
            ["all-MiniLM-L6-v2", "niewykorzystany: model przeznaczony przede wszystkim do języka angielskiego"],
        ],
        [usable * 0.38, usable * 0.62],
    )
    paragraph(
        doc,
        "Na wejście modelu podawany jest jeden tekst dla publikacji, złożony z tytułu, wszystkich abstraktów "
        "występujących w rekordzie oraz wszystkich słów kluczowych. Nadmiarowe odstępy są usuwane, a tekst jest "
        "ograniczany do 3200 znaków. Publikacji nie dzieli się na fragmenty. Wektory są normalizowane i porównywane "
        "w bazie miarą kosinusową. Nie stosuje się przedrostków typu query ani passage.",
    )
    paragraph(
        doc,
        "Obliczenia na kartach graficznych wykonano w precyzji float16, aby partia danych mieściła się w pamięci karty T4. "
        "Na dysk zapisano wartości w precyzji float32. Wielkość partii wynosiła 16 tekstów na kartę, a obie karty "
        "pracowały równolegle. Pytanie użytkownika jest kodowane później tym samym modelem, lokalnie, i również "
        "reprezentowane jednym wektorem.",
    )
    add_table(
        doc,
        ["Parametr", "Wartość"],
        [
            ["Miejsce obliczenia", "Kaggle, dwie karty NVIDIA Tesla T4, po 16 GB"],
            ["Model", "BAAI/bge-m3, sentence-transformers"],
            ["Wymiar wektora", "1024"],
            ["Porównanie", "kosinus, wektory znormalizowane"],
            ["Długość kontekstu", "8192 tokenów"],
            ["Tekst jednej publikacji", "tytuł, abstrakty i słowa kluczowe, do 3200 znaków"],
            ["Wektorów na publikację", "1"],
            ["Liczenie / zapis", "float16 / float32"],
            ["Wielkość partii", "16 tekstów na kartę, obie karty równolegle"],
            ["Liczba rekordów", "621 515, bez pominięć"],
            ["Czas obliczeń", "6514 sekund, około 1 godziny i 49 minut"],
            ["Pliki wynikowe", "63 pary plików wektorów i identyfikatorów; ostatni plik zawiera 1515 wierszy"],
        ],
        [usable * 0.36, usable * 0.64],
    )
    paragraph(
        doc,
        "Uzyskano 63 pary plików, od vectors_00000.npy do vectors_00062.npy, oraz odpowiadające im listy identyfikatorów. "
        "Pełny plik zawiera 10 000 wierszy, a ostatni 1515. Identyfikator w pliku tekstowym odpowiada wierszowi wektora "
        "o tym samym indeksie. Plik metadata.json zawiera nazwę modelu, wymiar, informację o normalizacji, sposób "
        "porównania, typ liczb, użyte karty, wielkość partii, przyjęte limity, liczbę rekordów oraz czas obliczeń.",
    )
    paragraph(
        doc,
        "Następnie, na komputerze lokalnym, wczytano plik JSONL do bazy SQLite i wstawiono wektory do bazy Chroma. "
        "Przy wektorach zapisano także wynik próbnego grupowania. Podczas wstawiania wektory nie były obliczane ponownie.",
    )
    paragraph(
        doc,
        "W kolekcji publications przy wektorze zapisywane są identyfikator publikacji, tytuł, rok, DOI, wynik próbnego "
        "grupowania oraz autorzy. Identyfikator kończy się przyrostkiem ::0, ponieważ publikacji odpowiada jeden wektor. "
        "Ten sam tekst jest wykorzystywany w wyszukiwaniu słownym. Aplikację uruchamia się lokalnie: interfejs API "
        "na porcie 8000 oraz okno Streamlit. Przy pierwszym uruchomieniu, jeżeli wagi modelu BAAI/bge-m3 nie znajdują "
        "się na dysku, są pobierane automatycznie.",
    )

    heading(doc, "Grupowanie na kategorie")
    paragraph(
        doc,
        "W danych źródłowych nie występuje oficjalna nazwa dziedziny. Metoda grupowania publikacji na kategorie "
        "jest jeszcze w trakcie opracowania. Kategoria ma odpowiadać grupie publikacji o zbliżonej treści. "
        "Dalsze obliczenia będą prowadzone na zapisanych wektorach, bez ponownego liczenia ich na platformie Kaggle.",
    )
    paragraph(
        doc,
        "Do tej pory sprawdzono grupowanie wektorów modelu BAAI/bge-m3 algorytmem MiniBatchKMeans. Próbę wykonano "
        "na pełnym zbiorze, przy sześciu grupach. Parametry tej próby przedstawiono poniżej.",
    )
    add_table(
        doc,
        ["Parametr", "Wartość"],
        [
            ["Metoda", "MiniBatchKMeans"],
            ["Liczba grup w próbie", "6"],
            ["Ziarno losowe", "42"],
            ["Wielkość partii", "4096"],
            ["Liczba inicjalizacji", "3"],
            ["Dane wejściowe", "zapisane wektory modelu BAAI/bge-m3"],
            ["Próba nazwy", "trzy najczęstsze słowa kluczowe danej grupy"],
        ],
        [usable * 0.36, usable * 0.64],
    )
    paragraph(
        doc,
        "Nazwy próbowano układać z trzech najczęstszych słów kluczowych w grupie. Tego sposobu nie przyjęto jako "
        "ostatecznych nazw kategorii. Obie próby grupowania oceniono na tej samej próbce 5040 publikacji, złożonej "
        "z 80 losowych wierszy z każdego pliku wektorów, przy ziarnie 42. Wyniki są słabe.",
    )
    paragraph(
        doc,
        "Pierwsza metoda to MiniBatchKMeans dopasowany do pełnego zbioru, przy sześciu grupach. Na próbce silhouette "
        "wynosi 0,0375, przy skali od −1 do 1, gdzie wyższa wartość oznacza lepiej rozdzielone grupy. Davies–Bouldin "
        "wynosi 5,6395, a niższa wartość oznacza lepszy podział. Calinski–Harabasz wynosi 91,11. Publikacja jest średnio "
        "podobna do środka własnej grupy na poziomie kosinusa 0,6597, ale tylko o 0,0395 bliższa własnej grupie niż "
        "najbliższej obcej. Nazwa grupy zgadza się ze słowem kluczowym pracy w 6,25% przypadków.",
    )
    add_table(
        doc,
        ["Miara", "MiniBatchKMeans, 6 grup"],
        [
            ["Silhouette", "0,0375"],
            ["Davies–Bouldin", "5,6395"],
            ["Calinski–Harabasz", "91,11"],
            ["Średni kosinus do środka grupy", "0,6597"],
            ["Margines do obcej grupy", "0,0395"],
            ["Zgodność nazwy ze słowem kluczowym", "6,25%"],
        ],
        [usable * 0.62, usable * 0.38],
    )
    paragraph(
        doc,
        "Druga metoda to KMeans dopasowany tylko do tej próbki, bez zmiany podziału zapisanego w bazie. Sprawdzono "
        "4, 6, 8 i 12 grup. Silhouette pozostaje bliskie zeru, a Davies–Bouldin powyżej 5. Zwiększenie liczby grup "
        "nie daje czytelniejszego podziału.",
    )
    add_table(
        doc,
        ["Liczba grup", "Silhouette", "Davies–Bouldin", "Calinski–Harabasz", "Margines"],
        [
            ["4", "0,0492", "5,5247", "127,00", "0,0493"],
            ["6", "0,0431", "5,3616", "94,04", "0,0444"],
            ["8", "0,0373", "5,5496", "77,71", "0,0381"],
            ["12", "0,0355", "5,2845", "59,13", "0,0381"],
        ],
        [usable * 0.18, usable * 0.18, usable * 0.24, usable * 0.24, usable * 0.16],
    )
    paragraph(
        doc,
        "Żadnej z ocenionych metod nie przyjęto jako grupowania na kategorie, ponieważ grupy są słabo rozdzielone. "
        "Dalsza praca polega na wyborze innego sposobu podziału i sposobu nazywania kategorii.",
    )

    heading(doc, "Wyszukiwanie, zestawienia i odpowiedź")
    paragraph(
        doc,
        "Pytanie o treść jest przekształcane w wektor modelem BAAI/bge-m3, po czym wyszukiwane są najbliższe publikacje. "
        "Równolegle działa wyszukiwanie słowne BM25, które lepiej zachowuje dokładny tytuł, nazwisko oraz rzadki termin. "
        "Wyniki obu metod łączy się algorytmem RRF, bez porównywania punktacji pochodzących z różnych skal. Domyślnie "
        "zwracanych jest 10 publikacji. W interfejsie liczbę tę można ustawić w zakresie od 1 do 15 oraz zastosować filtr roku. "
        "Pod odpowiedzią podawane są tytuł, rok i DOI, jeżeli identyfikator występuje w rekordzie.",
    )
    paragraph(
        doc,
        "Liczebności wyznaczane są w bazie SQLite, ponieważ sam wektor nie określa liczby publikacji danego kierunku "
        "w kolejnych latach. Do analizy trendu przyjmowane są lata z przedziału 1900–2026. Rok spoza tego przedziału "
        "pozostaje w bazie, lecz nie wchodzi do szeregu. Wzorzec rozwoju porównuje pierwszy i ostatni punkt szeregu: "
        "zmiana powyżej 10% oznacza wzrost, spadek większy niż 10% oznacza spadek, a wartość pośrednia oznacza zbliżony poziom. "
        "Jeżeli szereg obejmuje tylko jeden rok, podawana jest liczebność za ten rok i wynik nie jest określany jako trend wieloletni. "
        "Aplikacja przedstawia ponadto najliczniejsze kierunki, profil autora, współautorów oraz autorów wskazanego kierunku. "
        "Brak osoby w zbiorze jest komunikowany wprost.",
    )
    paragraph(
        doc,
        "Odpowiedź formułuje lokalny model językowy uruchomiony na komputerze autorów. Obecnie podłączony jest model "
        "llama3.2:3b, ale wybór nie jest zakończony. W testach są także Qwen3 4B i Qwen3 8B. Zostanie pozostawiony "
        "najlepszy model, który opiera odpowiedź na przekazanych rekordach i może działać na komputerze autorów. "
        "Model otrzymuje już obliczone zestawienia oraz znalezione publikacje, dlatego nie generuje tytułów, lat ani "
        "nazwisk spoza przekazanych danych. Odpowiedź jest udzielana w języku pytania.",
    )
    add_table(
        doc,
        ["Parametr", "Wartość"],
        [
            ["Model", "obecnie llama3.2:3b; w testach także Qwen3 4B i Qwen3 8B"],
            ["Środowisko", "lokalnie, na komputerze autorów"],
            ["Temperatura", "0,2"],
            ["Kontekst", "2048 tokenów"],
            ["Długość odpowiedzi", "do 512 tokenów"],
            ["Czas oczekiwania", "90 sekund"],
            ["Brak odpowiedzi modelu", "zdanie składane z uzyskanych wyników"],
        ],
        [usable * 0.36, usable * 0.64],
    )
    paragraph(
        doc,
        "Użytkownik może prowadzić kilka rozmów i wracać do każdej z nich. Przy tworzeniu nowej rozmowy wskazuje, "
        "czy ma ona otrzymać historię innej rozmowy. Pytanie doprecyzowujące, na przykład o autorstwo wskazanej pracy, "
        "odnosi się do publikacji albo osoby występującej w tej historii. Jeżeli odniesienia nie da się ustalić, "
        "użytkownik jest proszony o doprecyzowanie. Pusta wypowiedź, powitanie oraz pytanie niezwiązane z publikacjami "
        "nie uruchamiają wyszukiwania. Przy liczebności kierunków oraz szeregu lat interfejs prezentuje również wykres.",
    )
    paragraph(
        doc,
        "Poprawność kodu sprawdzana jest lokalnie, bez użycia kontenerów. Testy obejmują wyznaczanie klucza autora, "
        "składanie tekstu z abstraktu polskiego i angielskiego, rozpoznawanie rodzaju pytania, opis wzrostu i spadku "
        "oraz ograniczenie lat do przedziału 1900–2026. Przygotowano także plik pytań dla małego zbioru próbnego. "
        "Ocenę podziału na grupy wykonano na próbce 5040 publikacji. Wyniki obu metod były słabe, dlatego podział nie "
        "został przyjęty. Ocena wyszukiwania na pełnym indeksie pozostaje do wykonania.",
    )

    heading(doc, "Dalsze prace")
    paragraph(
        doc,
        "Obliczone wektory modelu BAAI/bge-m3 pozostają bez zmian i nie będą wyznaczane ponownie. Do dokończenia "
        "pozostały prace opisane poniżej.",
    )
    paragraph(
        doc,
        "Nadal opracowywana jest metoda grupowania na kategorie. Po jej ustaleniu podział zostanie policzony "
        "na zapisanych wektorach, bez ponownego uruchamiania obliczeń na platformie Kaggle.",
    )
    paragraph(
        doc,
        "Dla pełnego zbioru zostaną przygotowane pytania w języku polskim i angielskim, ze wskazaniem publikacji, "
        "które powinny pojawić się w wyniku. Porównane zostaną wyszukiwanie słowne, wyszukiwanie wektorowe oraz ich "
        "połączenie, stosowane obecnie w aplikacji. Osobno sprawdzone zostanie pytanie w języku polskim kierowane do "
        "abstraktu angielskiego, ponieważ pod ten przypadek wybrano model BAAI/bge-m3.",
    )
    paragraph(
        doc,
        "Wartości liczbowe z odpowiedzi zostaną zestawione z zapytaniem wykonanym bezpośrednio na danych: liczba "
        "publikacji w kierunku, ranking kierunków oraz lata wchodzące do szeregu. Obecnie odpowiedzi formułuje model "
        "llama3.2:3b. Na tym samym zestawie pytań jest on porównywany z modelami Qwen3 4B i Qwen3 8B. Pozostawiony "
        "zostanie najlepszy model, który opiera odpowiedź na przekazanych rekordach i może być używany na komputerze autorów.",
    )
    paragraph(
        doc,
        "Na pełnym zbiorze zmierzone zostaną czas uruchomienia, zużycie pamięci oraz czas odpowiedzi na pytanie o treść, "
        "o trend i o autora. Pomiar zostanie wykonany na komputerze autorów, bez kart graficznych użytych na platformie Kaggle. "
        "Celem jest sprawdzenie, czy rozmowę można prowadzić bez długiej przerwy między kolejnymi odpowiedziami.",
    )
    add_table(
        doc,
        ["Zadanie", "Stan", "Uwaga"],
        [
            ["Wczytanie pełnego pliku", "zrealizowane", "621 515 rekordów w bazie SQLite"],
            ["Wektory BAAI/bge-m3 na platformie Kaggle", "zrealizowane", "dwie karty T4, około 1 godziny i 49 minut"],
            ["Baza Chroma", "zrealizowana", "wektory wstawione bez ponownego obliczania"],
            ["Grupowanie na kategorie", "w trakcie", "obie próby na próbce 5040 dały słaby podział i nie zostały przyjęte"],
            ["Wyszukiwanie i interfejs rozmowy", "wdrożone", "porównanie trzech wariantów pozostaje do wykonania"],
            ["Porównanie modeli językowych", "w trakcie", "obecnie llama3.2:3b; w testach także Qwen3 4B i Qwen3 8B"],
            ["Czas uruchomienia i zużycie pamięci", "do wykonania", "pomiar na komputerze autorów"],
        ],
        [usable * 0.36, usable * 0.20, usable * 0.44],
    )

    paragraph(doc, "Podpis promotora (akceptacja etapu 3): ................................................", justify=False, before=12)
    paragraph(doc, "Data: ................................................", justify=False, before=6)

    path.parent.mkdir(parents=True, exist_ok=True)
    doc.save(path)


if __name__ == "__main__":
    targets = [
        Path(r"C:\Users\matja\Downloads\Lab 3 (19.11.2026)\Agent do odpowiadania na pytania dotyczące trendów i zależności w publikacjach naukowych.docx"),
        Path(__file__).resolve().parents[1] / "docs" / "Etap 3 - Agent do odpowiadania na pytania dotyczące trendów i zależności w publikacjach naukowych.docx",
    ]
    for target in targets:
        try:
            build(target)
        except PermissionError:
            print(f"LOCKED {target}")
            continue
        print(target)
