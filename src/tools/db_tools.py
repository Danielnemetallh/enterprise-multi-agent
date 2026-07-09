"""
Enterprise Multi-Agent System — Mock Database Tools
====================================================
SQLite-Datenbank mit realitätsnahen Testdaten für alle 3 Agenten.

Tabellen:
  - customers         → Stammdaten (Name, Status, Vertragstyp)
  - products          → Produktkatalog mit Preisen
  - competitor_prices → Konkurrenz-Preise (für Agent 2: Scraping-Simulation)
  - support_tickets   → Eingehende Kundenanfragen (für Agent 1: Triage)
  - orders            → Bestellhistorie

Erzeugt: data/mock_customers.db
"""

import sqlite3
import os
import logging
from datetime import datetime, timedelta
from random import randint, choice, uniform
from faker import Faker

logger = logging.getLogger(__name__)

fake = Faker("de_DE")

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "data", "mock_customers.db")
DB_PATH = os.path.abspath(DB_PATH)


# ─────────────────────────────── SCHEMA ───────────────────────────────

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS customers (
    id          INTEGER PRIMARY KEY,
    name        TEXT NOT NULL,
    email       TEXT NOT NULL,
    phone       TEXT,
    status      TEXT NOT NULL CHECK(status IN ('aktiv', 'gekündigt', 'inaktiv')),
    vertragstyp TEXT NOT NULL CHECK(vertragstyp IN ('Premium', 'Business', 'Basic')),
    beitritt    TEXT NOT NULL,
    kundenseit  INTEGER DEFAULT 1
);

CREATE TABLE IF NOT EXISTS products (
    id          INTEGER PRIMARY KEY,
    name        TEXT NOT NULL,
    kategorie   TEXT NOT NULL,
    preis       REAL NOT NULL,
    beschreibung TEXT
);

CREATE TABLE IF NOT EXISTS competitor_prices (
    id          INTEGER PRIMARY KEY,
    produkt     TEXT NOT NULL,
    anbieter    TEXT NOT NULL,
    preis       REAL NOT NULL,
    stand       TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS support_tickets (
    id          INTEGER PRIMARY KEY,
    kunden_id   INTEGER NOT NULL,
    typ         TEXT NOT NULL CHECK(typ IN ('beschwerde', 'kuendigung', 'preisanfrage', 'sonstiges')),
    betreff     TEXT NOT NULL,
    nachricht   TEXT NOT NULL,
    status      TEXT NOT NULL DEFAULT 'offen' CHECK(status IN ('offen', 'in_bearbeitung', 'erledigt')),
    erstellt    TEXT NOT NULL,
    FOREIGN KEY (kunden_id) REFERENCES customers(id)
);

CREATE TABLE IF NOT EXISTS orders (
    id          INTEGER PRIMARY KEY,
    kunden_id   INTEGER NOT NULL,
    produkt_id  INTEGER NOT NULL,
    menge       INTEGER NOT NULL,
    gesamtpreis REAL NOT NULL,
    datum       TEXT NOT NULL,
    FOREIGN KEY (kunden_id) REFERENCES customers(id),
    FOREIGN KEY (produkt_id) REFERENCES products(id)
);
"""

INDEXES_SQL = [
    "CREATE INDEX IF NOT EXISTS idx_tickets_kunde ON support_tickets(kunden_id);",
    "CREATE INDEX IF NOT EXISTS idx_tickets_typ ON support_tickets(typ);",
    "CREATE INDEX IF NOT EXISTS idx_orders_kunde ON orders(kunden_id);",
    "CREATE INDEX IF NOT EXISTS idx_customers_status ON customers(status);",
]


# ─────────────────── REALISTISCHE TICKET-TEXTE ───────────────────

BESCHWERDE_TEXTE = {
    "Konkurrenz ist günstiger!": [
        "Ich habe festgestellt, dass CloudPerfect für genau denselben Cloud-Speicher nur 9,99€ verlangt. Wir zahlen bei euch 29,99€. Das ist fast das Dreifache! Könnt ihr da preislich mitgehen oder müssen wir wechseln?",
        "ApexCloud bietet ein vergleichbares Produkt für 14,99€ an. Ich würde gerne bei euch bleiben, aber der Preisunterschied ist einfach zu groß. Gibt es ein Rabattangebot für Bestandskunden?",
        "NetForge hat mir ein Angebot für 50 Benutzer zum halben Preis gemacht. Ich hätte gerne ein Gegenangebot von euch, sonst muss ich leider kündigen.",
    ],
    "Langsamer Support": [
        "Unser Ticket #1234 ist seit 3 Tagen unbeantwortet. Wir haben einen Premium-Vertrag mit 24h-SLA! Das ist enttäuschend für den Preis.",
        "Der Support hat auf meine dringende Anfrage erst nach 5 Tagen reagiert. So kann das nicht weitergehen, wir brauchen verlässlichen Support.",
        "Ich warte seit einer Woche auf Rückmeldung zu einem kritischen API-Problem. Für einen Business-Vertrag ist das inakzeptabel.",
    ],
    "Feature fehlt": [
        "Wir brauchen dringend eine Zwei-Faktor-Authentifizierung. Das ist heutzutage Standard und in eurem Produkt fehlt es komplett.",
        "Die API-Dokumentation ist unvollständig. Der Endpunkt /v2/users ist nicht dokumentiert, taucht aber in euren Beispielen auf.",
        "Warum gibt es keine Batch-Verarbeitung? Wir müssen hunderte Datensätze einzeln importieren, das kostet unheimlich viel Zeit.",
    ],
    "Server-Ausfall letzte Woche": [
        "Letzten Dienstag war unser Zugang für 4 Stunden nicht erreichbar. Wir konnten keine Transaktionen durchführen. Das hat uns Umsatz gekostet. Ich erwarte eine Gutschrift.",
        "Innerhalb eines Monats gab es drei Ausfälle. Das ist weit unter der versprochenen 99,9% Verfügbarkeit. Bitte um Stellungnahme und Kompensation.",
    ],
}

KUENDIGUNG_TEXTE = {
    "Kündigung meines Vertrags": [
        "Hiermit kündige ich meinen Premium-Vertrag fristgerecht zum nächstmöglichen Zeitpunkt. Bitte bestätigen Sie die Kündigung und senden Sie mir die Schlussrechnung zu.",
        "Ich möchte meinen Vertrag aus betrieblichen Gründen zum 31.12. kündigen. Der Service war gut, aber wir stellen unser Geschäftsmodell um.",
    ],
    "Bitte um Vertragsbeendigung": [
        "Bitte beenden Sie meinen Vertrag sofort. Ich bin mit der Leistung nicht zufrieden. Eine Kündigungsfrist sollte aufgrund der Schlechtleistung nicht gelten.",
    ],
}

PREISANFRAGE_TEXTE = {
    "Preis für Cloud-Speicher Pro?": [
        "Können Sie mir bitte ein Angebot für Cloud-Speicher Pro für 10 Benutzer machen? Wir brauchen mindestens 2TB Speicher. Gibt es Rabatt bei Jahreszahlung?",
        "Was kostet Cloud-Speicher Pro im Jahresabo bei 5 Benutzern? Und wie sieht es mit einem Rabatt für Bildungseinrichtungen aus?",
    ],
    "Angebot für Enterprise": [
        "Wir sind ein Unternehmen mit 200 Mitarbeitern und interessieren uns für euer Enterprise-Paket. Bitte senden Sie uns ein individuelles Angebot mit Volumen-Rabatten zu.",
        "Wir planen die Migration von 50 Benutzern auf eure Plattform. Können wir vorab einen Testmonat zum reduzierten Preis bekommen?",
    ],
    "Rabatt auf Jahresabo?": [
        "Gibt es aktuell eine Rabattaktion für Jahresabos? Ich möchte meinen Basic-Tarif auf Premium upgraden, aber 29,99€ sind mir monatlich zu viel.",
    ],
    "Preisvergleich Konkurrenz": [
        "Ich habe ein Angebot von DataSphere AG für 19,99€ pro Monat für ein vergleichbares Produkt. Könnt ihr das matchen oder sogar unterbieten?",
    ],
}

SONSTIGES_TEXTE = {
    "Frage zur Rechnung": [
        "Ich habe eine doppelte Rechnung für Mai erhalten. Bitte prüfen und die Zahlung stornieren.",
        "Die Rechnung vom 15. wurde bereits bezahlt, aber ich habe eine Mahnung bekommen. Können Sie das klären?",
    ],
    "Zugangsdaten verloren": [
        "Ich kann mich nicht mehr einloggen. Der Passwort-Reset funktioniert nicht. Bitte helfen Sie mir, meinen Account wiederherzustellen.",
    ],
    "Mitarbeiter hinzufügen": [
        "Ich möchte einen neuen Mitarbeiter zu unserem Team hinzufügen. Wie kann ich ihn einladen und welche Kosten kommen auf uns zu?",
    ],
    "API-Dokumentation": [
        "In der API-Dokumentation fehlt der Endpunkt für Bulk-Updates. Gibt es eine aktualisierte Version?",
        "Können Sie mir ein Beispiel für die OAuth2-Integration mit eurer API schicken?",
    ],
}

def generate_meaningful_text(betreff: str, typ: str) -> str:
    """Wählt einen passenden, realistischen Text zum Ticket-Betreff."""
    pool = {
        "beschwerde": BESCHWERDE_TEXTE,
        "kuendigung": KUENDIGUNG_TEXTE,
        "preisanfrage": PREISANFRAGE_TEXTE,
        "sonstiges": SONSTIGES_TEXTE,
    }.get(typ, {})
    
    texts = pool.get(betreff, [fake.paragraph(nb_sentences=3)])
    return choice(texts)


# ─────────────────────────────── MOCK DATA ───────────────────────────────

def generate_mock_data():
    data = {}

    # --- Customers (50) ---
    customers = []
    statuses = ["aktiv"] * 35 + ["gekündigt"] * 10 + ["inaktiv"] * 5
    vertraege = ["Premium"] * 10 + ["Business"] * 20 + ["Basic"] * 20

    for i in range(1, 51):
        beitritt = fake.date_between(start_date="-5y", end_date="-30d")
        customers.append((
            i, fake.name(), fake.email(), fake.phone_number(),
            choice(statuses), choice(vertraege),
            beitritt.isoformat(), randint(1, 8)
        ))
    data["customers"] = customers

    # --- Products (10) ---
    products = [
        (1, "Cloud-Speicher Basic",  "SaaS",   9.99,  "100 GB Speicher, 2 Benutzer"),
        (2, "Cloud-Speicher Pro",    "SaaS",  29.99,  "1 TB Speicher, 10 Benutzer"),
        (3, "Cloud-Speicher Enterpr.","SaaS",  99.99,  "Unlimited Speicher, API-Zugriff"),
        (4, "API-Gateway Standard",  "API",   49.99,  "10k Requests/Tag"),
        (5, "API-Gateway Unlimited", "API",  149.99,  "Unlimited Requests"),
        (6, "KI-Chatbot Basic",      "AI",    19.99,  "500 Konversationen/Monat"),
        (7, "KI-Chatbot Pro",        "AI",    79.99,  "5k Konversationen, Custom-Intents"),
        (8, "Monitoring Lite",       "Infra", 14.99,  "3 Server, Basis-Alarme"),
        (9, "Monitoring Enterprise", "Infra", 59.99,  "Unlimited Server, SLA 99.9%"),
        (10,"VPN-Service Business",  "Network",39.99, "50 Benutzer, 5 Standorte"),
    ]
    data["products"] = products

    # --- Competitor Prices (30) ---
    competitors = ["CloudPerfect GmbH", "DataSphere AG", "NetForge", "SkyCompute", "ApexCloud"]
    comp_prices = []
    for pid, pname, _, base_price, _ in products:
        for c in competitors:
            if uniform(0, 1) > 0.4:
                offset = uniform(-0.3, 0.3)
                cprice = round(base_price * (1 + offset), 2)
                comp_prices.append((
                    len(comp_prices) + 1, pname, c,
                    max(0.99, cprice),
                    (datetime.now() - timedelta(days=randint(0, 30))).isoformat()
                ))
    data["competitor_prices"] = comp_prices

    # --- Support Tickets (30) — mit realistischen Texten ---
    typen_pool = ["beschwerde"] * 8 + ["kuendigung"] * 4 + ["preisanfrage"] * 10 + ["sonstiges"] * 8
    status_pool = ["offen"] * 15 + ["in_bearbeitung"] * 10 + ["erledigt"] * 5

    tickets = []
    for i in range(1, 31):
        typ = choice(typen_pool)

        if typ == "beschwerde":
            betreff = choice(list(BESCHWERDE_TEXTE.keys()))
        elif typ == "kuendigung":
            betreff = choice(list(KUENDIGUNG_TEXTE.keys()))
        elif typ == "preisanfrage":
            betreff = choice(list(PREISANFRAGE_TEXTE.keys()))
        else:
            betreff = choice(list(SONSTIGES_TEXTE.keys()))

        nachricht = generate_meaningful_text(betreff, typ)

        tickets.append((
            i, randint(1, 50), typ, betreff, nachricht,
            choice(status_pool),
            fake.date_between(start_date="-60d", end_date="today").isoformat()
        ))
    data["support_tickets"] = tickets

    # --- Orders (80) ---
    orders = []
    for i in range(1, 81):
        kunde = randint(1, 50)
        produkt = randint(1, 10)
        menge = randint(1, 5)
        preis = products[produkt - 1][3]
        orders.append((
            i, kunde, produkt, menge,
            round(menge * preis, 2),
            fake.date_between(start_date="-3y", end_date="today").isoformat()
        ))
    data["orders"] = orders

    return data


# ─────────────────────────────── DB ERZEUGEN ───────────────────────────────

def create_database(force=False):
    exists = os.path.exists(DB_PATH)
    if exists and not force:
        logger.info(f"DB existiert bereits: {DB_PATH}")
        return False

    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    cur.executescript(SCHEMA_SQL)
    for idx in INDEXES_SQL:
        cur.execute(idx)

    data = generate_mock_data()

    cur.executemany("INSERT INTO customers VALUES (?,?,?,?,?,?,?,?)", data["customers"])
    cur.executemany("INSERT INTO products VALUES (?,?,?,?,?)", data["products"])
    cur.executemany("INSERT INTO competitor_prices VALUES (?,?,?,?,?)", data["competitor_prices"])
    cur.executemany("INSERT INTO support_tickets VALUES (?,?,?,?,?,?,?)", data["support_tickets"])
    cur.executemany("INSERT INTO orders VALUES (?,?,?,?,?,?)", data["orders"])

    conn.commit()
    conn.close()
    logger.info(f"Mock-DB erstellt: {DB_PATH}")
    logger.info(f"  {len(data['customers'])} Kunden, {len(data['products'])} Produkte")
    logger.info(f"  {len(data['competitor_prices'])} Konkurrenz-Preise")
    logger.info(f"  {len(data['support_tickets'])} Support-Tickets, {len(data['orders'])} Bestellungen")
    return True


# ─────────────────────── QUERIES FÜR AGENTEN ───────────────────────

def ensure_db():
    """Erstellt die DB automatisch, falls sie nicht existiert."""
    if not os.path.exists(DB_PATH):
        logger.warning(f"DB nicht gefunden, erstelle neue unter {DB_PATH}")
        create_database(force=True)
        return True
    return False


def get_conn():
    """Öffnet eine neue SQLite-Verbindung. Erstellt DB bei Bedarf."""
    ensure_db()
    return sqlite3.connect(DB_PATH)


class db_connection:
    """Context-Manager für DB-Verbindungen — schließt automatisch."""

    def __enter__(self):
        ensure_db()
        self.conn = sqlite3.connect(DB_PATH)
        return self.conn

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.conn.close()


def query_customer(kunden_id: int) -> dict:
    try:
        with db_connection() as conn:
            cur = conn.cursor()
            cur.execute("SELECT * FROM customers WHERE id = ?", (kunden_id,))
            row = cur.fetchone()
        if row:
            return {
                "id": row[0], "name": row[1], "email": row[2],
                "phone": row[3], "status": row[4], "vertragstyp": row[5],
                "beitritt": row[6], "kundenseit": row[7],
            }
        return {"error": "Kunde nicht gefunden"}
    except sqlite3.DatabaseError as e:
        logger.error(f"DB-Fehler bei query_customer({kunden_id}): {e}")
        return {"error": f"Datenbank-Fehler: {e}"}


def query_competitor_prices(produkt_name: str) -> list:
    try:
        with db_connection() as conn:
            cur = conn.cursor()
            cur.execute(
                "SELECT anbieter, preis, stand FROM competitor_prices WHERE produkt LIKE ?",
                (f"%{produkt_name}%",)
            )
            rows = cur.fetchall()
        return [{"anbieter": r[0], "preis": r[1], "stand": r[2]} for r in rows]
    except sqlite3.DatabaseError as e:
        logger.error(f"DB-Fehler bei query_competitor_prices: {e}")
        return []


def query_open_tickets(limit: int = 30) -> list:
    try:
        with db_connection() as conn:
            cur = conn.cursor()
            cur.execute("""
                SELECT t.id, t.kunden_id, t.typ, t.betreff, t.nachricht, c.name, c.email
                FROM support_tickets t
                JOIN customers c ON t.kunden_id = c.id
                WHERE t.status != 'erledigt'
                LIMIT ?
            """, (limit,))
            rows = cur.fetchall()
        return [{
            "id": r[0], "kunden_id": r[1], "typ": r[2], "betreff": r[3],
            "nachricht": r[4], "kunde": r[5], "email": r[6]
        } for r in rows]
    except sqlite3.DatabaseError as e:
        logger.error(f"DB-Fehler bei query_open_tickets: {e}")
        return []


def query_kunden_historie(kunden_id: int) -> dict:
    try:
        with db_connection() as conn:
            cur = conn.cursor()
            cur.execute("""
                SELECT p.name, o.menge, o.gesamtpreis, o.datum
                FROM orders o
                JOIN products p ON o.produkt_id = p.id
                WHERE o.kunden_id = ?
                ORDER BY o.datum DESC
                LIMIT 10
            """, (kunden_id,))
            orders = [{"produkt": r[0], "menge": r[1], "preis": r[2], "datum": r[3]} for r in cur.fetchall()]
            cur.execute("""
                SELECT typ, betreff, status, erstellt
                FROM support_tickets
                WHERE kunden_id = ?
                ORDER BY erstellt DESC
                LIMIT 5
            """, (kunden_id,))
            tickets = [{"typ": r[0], "betreff": r[1], "status": r[2], "datum": r[3]} for r in cur.fetchall()]
        return {"orders": orders, "tickets": tickets}
    except sqlite3.DatabaseError as e:
        logger.error(f"DB-Fehler bei query_kunden_historie({kunden_id}): {e}")
        return {"orders": [], "tickets": []}


def mark_ticket_done(ticket_id: int) -> None:
    """Markiert ein Ticket nach der Verarbeitung als erledigt."""
    try:
        with db_connection() as conn:
            conn.execute("UPDATE support_tickets SET status = 'erledigt' WHERE id = ?", (ticket_id,))
        logger.info(f"Ticket #{ticket_id} als erledigt markiert")
    except sqlite3.DatabaseError as e:
        logger.error(f"DB-Fehler bei mark_ticket_done({ticket_id}): {e}")


if __name__ == "__main__":
    from src.tools.logger import setup_logging
    setup_logging()

    import sys
    force = "--force" in sys.argv
    create_database(force=force)
