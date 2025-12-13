from app import app, parse_date
import pytest

from app import find_columns

import pandas as pd
from io import StringIO, BytesIO
import re

SAMPLE_CSV = """date,quantity,price,product
02/01/2020,100,10,ABC
15/02/2020,50,12,ABC
01/06/2020,-120,15,ABC
05/12/2020,-30,20,ABC
"""


def test_find_columns():
    df = pd.read_csv(StringIO(SAMPLE_CSV))
    cols = find_columns(df)
    assert cols['date'] in df.columns
    assert cols['quantity'] in df.columns
    assert cols['price'] in df.columns


def test_end_to_end_gain():
    # We'll call the Flask app routes with a test client
    client = app.test_client()
    data = {
        'file': (BytesIO(SAMPLE_CSV.encode('utf-8')), 'sample_transactions.csv')
    }
    resp = client.post('/upload', data=data, content_type='multipart/form-data')
    assert resp.status_code == 200
    # Now we need to emulate selecting columns
    # Upload route saved csv to uploads/<id>.csv in app.config['UPLOAD_FOLDER']
    # We'll open uploads and find the file
    import os
    # Extract csv_path hidden input from the upload response HTML
    html = resp.data.decode('utf-8')
    import re
    m = re.search(r'name="csv_path" value="([^"]+)"', html)
    assert m, 'csv_path hidden input not found in response'
    csv_path = m.group(1)
    # Verify header contains product column
    with open(csv_path, 'r', encoding='utf-8') as fh:
        hdr = fh.readline().strip()
    assert 'product' in hdr

    resp = client.post('/calculate', data={
        'csv_path': csv_path,
        'date_col': 'date',
        'qty_col': 'quantity',
        'price_col': 'price',
        'product_col': 'product'
    }, follow_redirects=True)
    assert resp.status_code == 200
    # Expect product ABC matrix to appear and quantities 100, 20, 30 from FIFO
    assert b'Product: ABC' in resp.data
    assert b'100' in resp.data
    assert b'20' in resp.data
    assert b'30' in resp.data
    # Dates should be displayed in ISO yyyy-mm-dd
    assert b'2020-01-02' in resp.data
    assert b'2020-02-15' in resp.data
    assert b'2020-06-01' in resp.data
    assert b'2020-12-05' in resp.data
    # Check headers include quantities e.g. 'qty:' in sell header and buy header
    assert b'qty:' in resp.data


def test_product_normalization_same_group():
    SAMPLE = """date,quantity,price,product
02/01/2020,100,10, ABC
15/02/2020,-50,15,abc
"""
    client = app.test_client()
    data = {'file': (BytesIO(SAMPLE.encode('utf-8')), 's.csv')}
    resp = client.post('/upload', data=data, content_type='multipart/form-data')
    html = resp.data.decode('utf-8')
    import re
    m = re.search(r'name="csv_path" value="([^"]+)"', html)
    csv_path = m.group(1)
    resp = client.post('/calculate', data={'csv_path': csv_path, 'date_col': 'date', 'qty_col': 'quantity', 'price_col': 'price', 'product_col': 'product'}, follow_redirects=True)
    assert resp.status_code == 200
    # Both rows should be in the same product report
    assert b'Product: ABC' in resp.data
    # Matrix should include quantity 100 and 50
    assert b'100' in resp.data
    assert b'50' in resp.data
    # sale profit for this small sample will be shown; exact value asserted elsewhere


def test_logging_file_written():
    SAMPLE = """date,quantity,price,product
02/01/2020,100,10,ABC
15/02/2020,-50,15,ABC
"""
    client = app.test_client()
    data = {'file': (BytesIO(SAMPLE.encode('utf-8')), 'logtest.csv')}
    resp = client.post('/upload', data=data, content_type='multipart/form-data')
    html = resp.data.decode('utf-8')
    import re
    m = re.search(r'name="csv_path" value="([^"]+)"', html)
    csv_path = m.group(1)
    # remove any old log file if present
    import os
    base = os.path.splitext(os.path.basename(csv_path))[0]
    log_path = os.path.join('logs', f"{base}.log")
    if os.path.exists(log_path):
        os.remove(log_path)

    resp = client.post('/calculate', data={'csv_path': csv_path, 'date_col': 'date', 'qty_col': 'quantity', 'price_col': 'price', 'product_col': 'product'}, follow_redirects=True)
    assert resp.status_code == 200
    assert os.path.exists(log_path)
    with open(log_path, 'r', encoding='utf-8') as fh:
        content = fh.read()
    assert 'Product: ABC' in content
    assert 'BUY id=0' in content
    assert 'SELL id=0' in content
    assert 'MATCH' in content or 'UNMATCHED' in content


def test_quantity_commas_parsed():
    SAMPLE = """date,quantity,price,product
02/01/2020,"2,000",10,ABC
10/02/2020,"-2,000",15,ABC
"""
    client = app.test_client()
    data = {'file': (BytesIO(SAMPLE.encode('utf-8')), 'commas.csv')}
    resp = client.post('/upload', data=data, content_type='multipart/form-data')
    html = resp.data.decode('utf-8')
    import re
    m = re.search(r'name="csv_path" value="([^"]+)"', html)
    csv_path = m.group(1)
    resp = client.post('/calculate', data={'csv_path': csv_path, 'date_col': 'date', 'qty_col': 'quantity', 'price_col': 'price', 'product_col': 'product'}, follow_redirects=True)
    assert resp.status_code == 200
    # Confirm that the match quantity appears (2000) in the matrix
    assert b'2000' in resp.data


def test_price_commas_parsed():
    # Buy 100 @ "1,234.56" and sell 100 @ "1,300.00" -> profit per share 65.44 -> total 6544.00
    SAMPLE = """date,quantity,price,product
02/01/2020,100,"1,234.56",ABC
10/02/2020,-100,"1,300.00",ABC
"""
    client = app.test_client()
    data = {'file': (BytesIO(SAMPLE.encode('utf-8')), 'price_commas.csv')}
    resp = client.post('/upload', data=data, content_type='multipart/form-data')
    html = resp.data.decode('utf-8')
    import re
    m = re.search(r'name="csv_path" value="([^"]+)"', html)
    csv_path = m.group(1)
    resp = client.post('/calculate', data={'csv_path': csv_path, 'date_col': 'date', 'qty_col': 'quantity', 'price_col': 'price', 'product_col': 'product'}, follow_redirects=True)
    assert resp.status_code == 200
    # Total realized profit should include 6544.00
    assert b'6544.00' in resp.data


def test_summary_table():
    client = app.test_client()
    data = {
        'file': (BytesIO(SAMPLE_CSV.encode('utf-8')), 'summary.csv')
    }
    resp = client.post('/upload', data=data, content_type='multipart/form-data')
    assert resp.status_code == 200
    html = resp.data.decode('utf-8')
    import re
    m = re.search(r'name="csv_path" value="([^"]+)"', html)
    assert m
    csv_path = m.group(1)
    resp = client.post('/calculate', data={
        'csv_path': csv_path,
        'date_col': 'date',
        'qty_col': 'quantity',
        'price_col': 'price',
        'product_col': 'product'
    }, follow_redirects=True)
    assert resp.status_code == 200
    data = resp.data
    # Summary header
    assert b'Summary By Product' in data
    # Year column and row
    assert b'2020' in data
    # ABC profit for 2020 should be 800.00
    assert b'800.00' in data
    # counts
    assert b'2' in data  # both buys and sells counts appear
    # dates
    assert b'2020-01-02' in data
    assert b'2020-12-05' in data
    # remaining qty 0
    assert b'0' in data


def test_total_column_detection_and_calculation():
    # CSV with a 'total' column (transaction total), not unit price
    SAMPLE_TOTAL = """date,quantity,total,product
02/01/2020,100,1000,ABC
10/02/2020,-100,-1500,ABC
"""
    # find_columns should select the 'total' column as the price suggestion
    import pandas as pd
    from io import StringIO
    df = pd.read_csv(StringIO(SAMPLE_TOTAL))
    cols = find_columns(df)
    assert cols['price'] in df.columns
    assert 'total' in cols['price'].lower()

    # Now run through upload+calculate using the total column
    client = app.test_client()
    data = {'file': (BytesIO(SAMPLE_TOTAL.encode('utf-8')), 'total.csv')}
    resp = client.post('/upload', data=data, content_type='multipart/form-data')
    assert resp.status_code == 200
    html = resp.data.decode('utf-8')
    import re
    m = re.search(r'name="csv_path" value="([^"]+)"', html)
    assert m
    csv_path = m.group(1)
    resp = client.post('/calculate', data={
        'csv_path': csv_path,
        'date_col': 'date',
        'qty_col': 'quantity',
        'price_col': 'total',
        'product_col': 'product'
    }, follow_redirects=True)
    assert resp.status_code == 200
    # unit prices become 1000/100=10 buy, 1500/100=15 sell -> profit (15-10)*100 = 500
    assert b'500.00' in resp.data


def test_date_time_combination_fifo():
    SAMPLE = """date,time,quantity,price,product
02/01/2020,09:00,100,10,ABC
02/01/2020,15:00,50,12,ABC
02/01/2020,16:00,-120,15,ABC
"""
    client = app.test_client()
    data = {'file': (BytesIO(SAMPLE.encode('utf-8')), 'time.csv')}
    resp = client.post('/upload', data=data, content_type='multipart/form-data')
    assert resp.status_code == 200
    html = resp.data.decode('utf-8')
    import re
    m = re.search(r'name="csv_path" value="([^"]+)"', html)
    assert m
    csv_path = m.group(1)
    # now call /calculate with time_col included
    resp = client.post('/calculate', data={
        'csv_path': csv_path,
        'date_col': 'date',
        'time_col': 'time',
        'qty_col': 'quantity',
        'price_col': 'price',
        'product_col': 'product'
    }, follow_redirects=True)
    assert resp.status_code == 200
    # check matches 100 and 20
    assert b'100' in resp.data
    assert b'20' in resp.data


def test_date_format_no_t_or_seconds_in_html_and_excel():
    SAMPLE = """date,time,quantity,price,product
02/01/2020,09:00:00,100,10,ABC
02/01/2020,15:30:00,50,12,ABC
02/01/2020,16:45:00,-120,15,ABC
"""
    client = app.test_client()
    data = {'file': (BytesIO(SAMPLE.encode('utf-8')), 'time2.csv')}
    resp = client.post('/upload', data=data, content_type='multipart/form-data')
    assert resp.status_code == 200
    html = resp.data.decode('utf-8')
    import re
    m = re.search(r'name="csv_path" value="([^"]+)"', html)
    assert m
    csv_path = m.group(1)
    resp = client.post('/calculate', data={
        'csv_path': csv_path,
        'date_col': 'date',
        'time_col': 'time',
        'qty_col': 'quantity',
        'price_col': 'price',
        'product_col': 'product'
    }, follow_redirects=True)
    assert resp.status_code == 200
    body = resp.data.decode('utf-8')
    # Should show date+time like '2020-01-02 09:00' and not use 'T' or include seconds
    assert '2020-01-02 09:00' in body
    assert '2020-01-02 15:30' in body
    assert re.search(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}', body) is None
    assert re.search(r'\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}', body) is None

    # Check Excel Summary sheet value formatting
    import os
    base = os.path.splitext(os.path.basename(csv_path))[0]
    xlsx_path = os.path.join('uploads', f"{base}.xlsx")
    import pandas as pd
    summary_df = pd.read_excel(xlsx_path, sheet_name='Summary')
    first_tx = str(summary_df.loc[0, 'First Transaction'])
    assert 'T' not in first_tx
    assert re.search(r':\d{2}:\d{2}', first_tx) is None


def test_irregular_flag_shown_in_summary():
    SAMPLE = """date,quantity,price,product
02/01/2020,100,0,ABC
10/02/2020,-100,15,ABC
"""
    client = app.test_client()
    data = {'file': (BytesIO(SAMPLE.encode('utf-8')), 'irregular.csv')}
    resp = client.post('/upload', data=data, content_type='multipart/form-data')
    assert resp.status_code == 200
    html = resp.data.decode('utf-8')
    import re
    m = re.search(r'name="csv_path" value="([^"]+)"', html)
    assert m
    csv_path = m.group(1)
    resp = client.post('/calculate', data={
        'csv_path': csv_path,
        'date_col': 'date',
        'qty_col': 'quantity',
        'price_col': 'price',
        'product_col': 'product'
    }, follow_redirects=True)
    assert resp.status_code == 200
    # summary should show an asterisk next to product ABC
    assert b'ABC*' in resp.data


def test_excel_workbook_generated_and_contains_sheets():
    # Use SAMPLE_CSV from earlier
    client = app.test_client()
    data = {'file': (BytesIO(SAMPLE_CSV.encode('utf-8')), 'wb.csv')}
    resp = client.post('/upload', data=data, content_type='multipart/form-data')
    assert resp.status_code == 200
    html = resp.data.decode('utf-8')
    import re
    m = re.search(r'name="csv_path" value="([^"]+)"', html)
    assert m
    csv_path = m.group(1)
    resp = client.post('/calculate', data={
        'csv_path': csv_path,
        'date_col': 'date',
        'qty_col': 'quantity',
        'price_col': 'price',
        'product_col': 'product'
    }, follow_redirects=True)
    assert resp.status_code == 200
    # Determine workbook name and path
    import os
    base = os.path.splitext(os.path.basename(csv_path))[0]
    xlsx_path = os.path.join('uploads', f"{base}.xlsx")
    assert os.path.exists(xlsx_path)
    # Check that workbook has 'Summary' and 'ABC' sheets
    import pandas as pd
    xl = pd.ExcelFile(xlsx_path)
    assert 'Summary' in xl.sheet_names
    assert 'ABC' in xl.sheet_names
    # Verify headings present on ABC sheet
    import openpyxl
    wb = openpyxl.load_workbook(xlsx_path)
    ws = wb['ABC']
    abc_df = pd.read_excel(xlsx_path, sheet_name='ABC', header=None)
    # Top rows should contain sell dates and first column should contain buy dates
    assert abc_df.iloc[0, 3] == '2020-06-01'
    assert abc_df.iloc[0, 4] == '2020-12-05'
    assert abc_df.iloc[3, 0] == '2020-01-02'
    assert abc_df.iloc[4, 0] == '2020-02-15'
    # matrix body contains matched quantities
    assert int(abc_df.iloc[3, 3]) == 100
    assert int(abc_df.iloc[4, 3]) == 20
    assert int(abc_df.iloc[4, 4]) == 30
    # Blank row before profit, then profit row beneath matrix: expected per-column profits
    # For first sell (price 15): 100*(15-10) + 20*(15-12) = 560.0
    # For second sell (price 20): 30*(20-12) = 240.0
    assert abc_df.iloc[6, 0] == 'Column Profit'
    assert float(abc_df.iloc[6, 3]) == pytest.approx(560.0)
    assert float(abc_df.iloc[6, 4]) == pytest.approx(240.0)
    # Excel formatting: headings present and clearly distinct
    assert abc_df.iloc[2, 0] == 'date (purchases)'
    assert abc_df.iloc[2, 1] == 'quantity (purchases)'
    assert abc_df.iloc[0, 2] == 'date (sales)'
    assert abc_df.iloc[1, 2] == 'quantity (sales)'
    assert abc_df.iloc[2, 2] == 'price (sales)'
    # Purchases/Sales labels with arrows
    assert abc_df.iloc[0, 1] == 'Purchases →'
    assert abc_df.iloc[1, 0] == '← Sales'
    # Zero cells should be blank (NaN when read via pandas)
    import pandas as pd
    assert pd.isna(abc_df.iloc[3, 4])


def test_download_link_always_present():
    client = app.test_client()
    data = {'file': (BytesIO(SAMPLE_CSV.encode('utf-8')), 'wb2.csv')}
    resp = client.post('/upload', data=data, content_type='multipart/form-data')
    assert resp.status_code == 200
    html = resp.data.decode('utf-8')
    m = re.search(r'name="csv_path" value="([^"]+)"', html)
    assert m
    csv_path = m.group(1)
    resp = client.post('/calculate', data={
        'csv_path': csv_path,
        'date_col': 'date',
        'qty_col': 'quantity',
        'price_col': 'price',
        'product_col': 'product'
    }, follow_redirects=True)
    assert resp.status_code == 200
    assert b'Download Excel workbook' in resp.data
