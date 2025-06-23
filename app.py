from flask import Flask, render_template, request, redirect, url_for, session
from werkzeug.utils import secure_filename
from datetime import datetime
import os
import pandas as pd

app = Flask(__name__)

UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'xlsx'}

app = Flask(__name__)
app.secret_key = 'supersecretkey'  # Needed for session
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def read_excel_with_dynamic_header(filepath):
    all_sheets = pd.read_excel(filepath, sheet_name=None, header=None)

    # Try to find the most likely sheet
    selected_sheet_name = None
    for name in all_sheets:
        if "sz" in name.lower() or "separa" in name.lower():
            selected_sheet_name = name
            break
    if not selected_sheet_name:
        selected_sheet_name = list(all_sheets.keys())[0]  # fallback to first

    df_raw = pd.read_excel(filepath, sheet_name=selected_sheet_name, header=None)

    # Scan rows to find one that contains any variation of "rujukan"
    header_row_index = None
    for i, row in df_raw.iterrows():
        row_str = row.astype(str).str.upper().str.replace('\xa0', ' ', regex=False).str.strip()
        if any('RUJUKAN' in cell for cell in row_str):
            header_row_index = i
            break

    if header_row_index is None:
        raise ValueError("Could not find a row containing 'RUJUKAN'.")

    # Load properly with detected header row
    df = pd.read_excel(filepath, sheet_name=selected_sheet_name, header=header_row_index)
    df.columns = df.columns.str.replace('\xa0', ' ', regex=True).str.strip().str.upper()

    return df

@app.route('/', methods=['GET', 'POST'])
def upload():
    upload_dir = app.config['UPLOAD_FOLDER']

    # Get file info: filename + timestamp
    files = []
    for fname in os.listdir(upload_dir):
        if fname.endswith('.xlsx'):
            path = os.path.join(upload_dir, fname)
            timestamp = os.path.getmtime(path)
            files.append({
                'name': fname,
                'time': datetime.fromtimestamp(timestamp)
            })

    # Sort by most recent (newest first)
    files.sort(key=lambda f: f['time'], reverse=True)

    # Upload handling remains unchanged
    if request.method == 'POST':
        # User chose from dropdown
        if 'use_existing' in request.form:
            selected = request.form['use_existing']
            session['excel_path'] = os.path.join(upload_dir, selected)
            return redirect(url_for('search'))

        # User uploaded new file
        file = request.files.get('excel_file')
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            filepath = os.path.join(upload_dir, filename)
            file.save(filepath)

            session['excel_path'] = filepath
            return redirect(url_for('search'))

        return render_template('upload.html', error="Please upload a valid .xlsx file.", files=files)

    return render_template('upload.html', files=files)

@app.route('/search', methods=['GET', 'POST'])
def search():
    result = None
    filepath = session.get('excel_path')

    if not filepath or not os.path.exists(filepath):
        return redirect(url_for('upload'))

    if request.method == 'POST':
        ref_no = request.form['ref_no'].strip()

        try:
            df = read_excel_with_dynamic_header(filepath)
            match = df[df['NO RUJUKAN'].astype(str) == ref_no]

            if not match.empty:
                result = {
                    'rak': match.iloc[0].get('NO. RAK', 'N/A'),
                    'tajuk': match.iloc[0].get('TAJUK FAIL', 'N/A')
                }
            else:
                result = 'not_found'

        except Exception as e:
            result = f'error: {str(e)}'

    return render_template('search.html', result=result)

@app.route('/delete/<filename>', methods=['POST'])
def delete_file(filename):
    filename = secure_filename(filename)
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    if os.path.exists(filepath):
        os.remove(filepath)
    return redirect(url_for('upload'))

if __name__ == '__main__':
    app.run(debug=True)