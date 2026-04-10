import requests
import re
import sys
import argparse
import random
import difflib
import pandas as pd
from openpyxl import load_workbook

DATA_SH = "DATA"
SRCH_SH = "SEARCH"

def search_gutenberg(search=None, author_year_start=None, author_year_end=None,
                     copyright=None, ids=None, languages=None,
                     mime_type=None, sort=None, topic=None):
    """
    Query the Gutendex /books API and return raw results list.

    Parameters mirror the Gutendex API:
      search            - words matched against title and author names
      author_year_start - books with an author alive at or after this year
      author_year_end   - books with an author alive at or before this year
      copyright         - 'true', 'false', or 'null' (comma-separated combos ok)
      ids               - comma-separated Gutenberg ID numbers, e.g. '11,12,13'
      languages         - comma-separated 2-char codes, e.g. 'en' or 'fr,fi'
      mime_type         - MIME type prefix filter, e.g. 'text/plain'
      sort              - 'ascending', 'descending', or 'popular' (default)
      topic             - key-phrase matched against bookshelves and subjects
    """
    params = {}
    if search            is not None: params['search']            = search
    if author_year_start is not None: params['author_year_start'] = author_year_start
    if author_year_end   is not None: params['author_year_end']   = author_year_end
    if copyright         is not None: params['copyright']         = copyright
    if ids               is not None: params['ids']               = ids
    if languages         is not None: params['languages']         = languages
    if mime_type         is not None: params['mime_type']         = mime_type
    if sort              is not None: params['sort']              = sort
    if topic             is not None: params['topic']             = topic

    try:
        response = requests.get("https://gutendex.com/books/", params=params)
        response.raise_for_status()
        return response.json().get('results', [])
    except Exception as e:
        print(f"Error querying Gutendex: {e}"); sys.exit(1)


def get_gutenberg(search_query, **kwargs):
    """
    Resolve and download a Gutenberg book.
    Returns (raw_text, title).
    """
    results = search_gutenberg(search=search_query, **kwargs)
    if not results:
        print("No results found."); sys.exit(1)

    def score(book):
        return difflib.SequenceMatcher(None, search_query.lower(), book['title'].lower()).ratio()

    candidates = [
        b for b in results
        if any('text/plain' in m and u.endswith('.txt') for m, u in b.get('formats', {}).items())
    ]
    if not candidates:
        print("No plain-text versions found in results."); sys.exit(1)

    candidates.sort(key=score, reverse=True)

    CONFIDENCE = 0.5
    ambiguous = (score(candidates[0]) < CONFIDENCE or
                 (len(candidates) > 1 and abs(score(candidates[0]) - score(candidates[1])) < 0.1))

    if ambiguous:
        print("Multiple possible matches — please choose:")
        for i, b in enumerate(candidates[:5], 1):
            authors = ", ".join(a['name'] for a in b.get('authors', []))
            print(f"  {i}. {b['title']} — {authors} (score: {score(b):.2f})")
        try:
            choice = int(input("Enter number (or 0 to abort): "))
        except (ValueError, EOFError):
            choice = 0
        if choice < 1 or choice > len(candidates[:5]):
            print("Aborted."); sys.exit(0)
        top_match = candidates[choice - 1]
    else:
        top_match = candidates[0]

    title = top_match['title']
    text_url = next(
        (u for m, u in top_match.get('formats', {}).items() if 'text/plain' in m and u.endswith('.txt')),
        None
    )
    if not text_url:
        print(f"Could not find a plain text version for '{title}'."); sys.exit(1)

    try:
        text_res = requests.get(text_url)
        for enc in ('utf-8-sig', 'latin-1'):
            try:
                raw_text = text_res.content.decode(enc); break
            except UnicodeDecodeError:
                continue
        else:
            raw_text = text_res.content.decode('latin-1', errors='replace')
        return raw_text, title
    except Exception as e:
        print(f"Error fetching book: {e}"); sys.exit(1)


def clean_gutenberg(raw_text, title):
    """
    Strip Gutenberg boilerplate and image references from raw_text.
    Returns clean body text.
    """
    t = re.escape(title.upper())
    start_marker = rf'\*\*\* START OF THE PROJECT GUTENBERG EBOOK "?{t}"? \*\*\*'
    end_marker   = rf'\*\*\* END OF THE PROJECT GUTENBERG EBOOK "?{t}"? \*\*\*'
    match = re.search(rf"{start_marker}(.*?){end_marker}", raw_text, re.IGNORECASE | re.DOTALL)
    clean_text = match.group(1).strip() if match else raw_text
    return re.sub(r"\w+\.(?:jpg|jpeg|png|gif)\s*\(\d+[KM]\)\s*\n+\s*Full Size", "", clean_text, flags=re.IGNORECASE)

def create_oracle_files(text, search_query, rows=1000):
    safe_name = search_query.replace(' ', '_')
    raw_out, txt_out, xls_out = f"{safe_name}pg.txt", f"{safe_name}oracle.txt", f"{safe_name}oracle.xlsx"
   
    # Use ! for the XLSX internal format (Calc translates this to . automatically)
    sep = "!"

    # Save Raw Text
    with open(raw_out, 'w', encoding='utf-8') as f:
        f.write(text)

    # Process Snippets
    text_flat = " ".join(text.replace('\t', ' ').splitlines())
    all_snippets = re.findall(r'\b[^\s,.!?]+(?: [^\s,.!?]+){1,3} [^\s,.!?]+[,.!?]?', text_flat)
    clean_snippets = [s.strip().lower() for s in all_snippets if 3 <= len(s.split()) <= 5]
    random.shuffle(clean_snippets)
   
    # Create TXT Oracle
    sel = clean_snippets[:rows*2] if len(clean_snippets) >= rows*2 else random.choices(clean_snippets, k=rows*2)
    with open(txt_out, 'w', encoding='utf-8') as out:
        out.write(f"{'LEFT SNIPPET':<45} | {'ROW':^5} | {'RIGHT SNIPPET'}\n" + "-"*80 + "\n")
        for i in range(rows):
            out.write(f"{sel[i]:<45} | {i+1:>5} | {sel[i+rows]}\n")

    # Prepare DataFrames
    df_master = pd.DataFrame({
        'Snippet': clean_snippets,
        'SHUFFLE': [f'=RAND()' for _ in clean_snippets]
    })
   
    df_search = pd.DataFrame({
        'Label': ['Search Word:', 'Random Result:', 'Jump Link:', 'Match Count:'],
        'Value': ['the', '', '', '']
    })

    with pd.ExcelWriter(xls_out, engine='openpyxl') as writer:
        df_master.to_excel(writer, sheet_name=DATA_SH, index=False)
        df_search.to_excel(writer, sheet_name=SRCH_SH, index=False, header=False)

    # Apply Formulas
    wb = load_workbook(xls_out)
    ws_data, ws_search = wb[DATA_SH], wb[SRCH_SH]
    last_row = len(clean_snippets) + 1
   
    # SEARCH word reference (Direct, Uppercase)
    search_ref = f'{SRCH_SH}{sep}$B$1'
   
    # Helper Column C on DATA sheet (Match index)
    # We use commas here because openpyxl/Excel XML expects them;
    # LibreOffice will localize them to semicolons on its own.
    for r in range(2, last_row + 1):
        ws_data[f'C{r}'] = f'=IF(ISNUMBER(SEARCH({search_ref}, A{r})), ROW(), "")'
   
    # We "pull" columns A and C from DATA into hidden columns on SEARCH (Columns Y and Z)
    # This keeps the references local so the importer doesn't mangle them.
    for r in range(1, last_row + 1):
        ws_search[f'Y{r}'] = f'={DATA_SH}{sep}A{r}'
        ws_search[f'Z{r}'] = f'={DATA_SH}{sep}C{r}'

    # B2: Random Match Result
    ws_search['B2'] = (f'=IFERROR(INDEX($Y$1:$Y${last_row}, '
                       f'SMALL($Z$2:$Z${last_row}, '
                       f'RANDBETWEEN(1, MAX(1, COUNT($Z$2:$Z${last_row}))))), '
                       f'"No matches found")')
   
    # B3: Internal Hyperlink
    ws_search['B3'] = (f'=IF(B2="No matches found", "---", '
                       f'HYPERLINK("#" & "{DATA_SH}" & "{sep}A" & '
                       f'MATCH(B2, $Y$1:$Y${last_row}, 0), "➜ CLICK TO JUMP"))')
   
    # B4: Total Matches
    ws_search['B4'] = f'=COUNT($Z$2:$Z${last_row})'

    wb.save(xls_out)
    print(f"Success! Generated {xls_out}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Download a Gutenberg book and build oracle files.")
    parser.add_argument("query", help="Title / author search terms")
    parser.add_argument("--languages",         metavar="CODES",  help="Comma-separated 2-char language codes, e.g. 'en' or 'fr,fi'")
    parser.add_argument("--topic",             metavar="PHRASE", help="Key-phrase matched against bookshelves and subjects")
    parser.add_argument("--author-year-start", metavar="YEAR",   type=int, help="Author alive at or after this year")
    parser.add_argument("--author-year-end",   metavar="YEAR",   type=int, help="Author alive at or before this year")
    parser.add_argument("--copyright",         metavar="STATUS", help="'true', 'false', or 'null'")
    parser.add_argument("--ids",               metavar="IDS",    help="Comma-separated Gutenberg IDs, e.g. '11,12,13'")
    parser.add_argument("--sort",              choices=["popular", "ascending", "descending"], default=None)
    parser.add_argument("--rows",              type=int, default=1000, help="Number of oracle rows (default 1000)")
    args = parser.parse_args()

    kwargs = {k: v for k, v in {
        'languages':         args.languages,
        'topic':             args.topic,
        'author_year_start': args.author_year_start,
        'author_year_end':   args.author_year_end,
        'copyright':         args.copyright,
        'ids':               args.ids,
        'sort':              args.sort,
    }.items() if v is not None}

    raw_text, title = get_gutenberg(args.query, **kwargs)
    text = clean_gutenberg(raw_text, title)
    create_oracle_files(text, args.query, rows=args.rows)