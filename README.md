# WatchBot — UK Pre-Owned Watch Market Search

Searches 16 UK pre-owned watch marketplaces daily for specific references. Sends an HTML email summary highlighting new listings and exact reference matches. Runs via GitHub Actions — no server required.

## Watches monitored

| Brand | Model | Reference |
|-------|-------|-----------|
| Cartier | Tank Louis Cartier | WGTA0091 |
| Omega | Specialities CK 859 | 511.12.39.21.99.002 |
| A. Lange & Söhne | Lange 1 | 101.032 (box & papers preferred) |
| Parmigiani Fleurier | Tonda PF GMT Rattrapante | PFC905-1020001-100182 |

## Sites searched

Chrono24 UK · eBay UK (UK sellers only) · Watchfinder · Subdial · Chronext · The Watch Agency · Xupes · WatchBox UK · The Watch Company · Jura Watches · Watch Club · WatchCollectors · Onaro · A Collected Man · Fellows Auctions · Sotheby's

## Setup

### 1. Fork / clone this repository

### 2. Set GitHub Actions secrets

Go to **Settings → Secrets and variables → Actions** and add:

| Secret | Value |
|--------|-------|
| `SMTP_USER` | Your Gmail address |
| `SMTP_PASS` | Gmail [App Password](https://support.google.com/accounts/answer/185833) (not your account password) |
| `NOTIFY_EMAIL` | Address to receive daily reports |

### 3. Enable GitHub Actions

The workflow runs daily at 08:00 UTC. Trigger it manually via **Actions → Daily Watch Search → Run workflow** to test immediately.

### 4. View reports

Each run uploads the HTML report as an artifact. Download it from the Actions run page, or receive it by email.

---

## Adding or changing watches

Edit `config/watches.yaml`. Each entry:

```yaml
watches:
  - brand: Rolex
    model: Submariner Date
    reference: "126610LN"
    aliases:
      - "126610 LN"
      - "126610-LN"
    prefer_full_set: false   # set true to badge "Full Set ✓" on matching listings
```

**Tip — verify a reference before adding:**

```bash
# By brand and reference
python run.py verify --brand "Rolex" --ref "126610LN"

# By retail URL (resolves to manufacturer reference automatically)
python run.py verify --url "https://www.harrods.com/en-gb/p/..."
```

---

## Local usage

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
playwright install chromium

cp .env.example .env   # fill in SMTP_USER, SMTP_PASS, NOTIFY_EMAIL

python run.py search --dry-run          # run without sending email or writing state
python run.py search --ref "101.032"    # search one watch only
python run.py search                    # full run
```

---

## How matching works

A listing is included **only** if its text contains the exact reference number (or an explicitly configured alias), after normalising away dots, hyphens, and spaces. Partial matches and similar-reference results are discarded. The reference `101.032` will never match `191.032` or `116.032`.

## Report format

- **★ Exact Ref Match + NEW** — amber row: new listing with confirmed reference
- **NEW** — green row: new listing (reference in title/description)
- **Previously seen** — collapsed; expand to review
- **Full Set ✓** — purple badge when box & papers detected and `prefer_full_set: true`
- **Auction** — pink badge; shows estimate range and end date instead of price
