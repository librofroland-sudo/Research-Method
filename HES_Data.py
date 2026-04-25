import pandas as pd
import glob
import os
import re
from pathlib import Path

BASE_DIR = r"F:/Nottingham/spring/Research Methods/NHS Hospital Admissions/total/HES_Data/final/"

def clean_code(code):
    if pd.isna(code):
        return ''
    code = str(code).strip()
    code = re.sub(r'^[‡\s]+', '', code)
    return code.strip().upper()

def get_chapter(code, desc):
    code = str(code).upper()
    desc = str(desc).lower()
    if code.startswith('U00') or code.startswith('U80'):
        return 'COVID (Provisional)'
    elif code.startswith('A') or code.startswith('B'):
        return 'Infectious Diseases'
    elif code.startswith('C') or (code.startswith('D') and len(code) >= 3 and code[1:3].isdigit() and int(code[1:3]) <= 48):
        return 'Neoplasms & Benign'
    elif code.startswith('F'):
        return 'Mental & Behavioural'
    elif code.startswith('I'):
        return 'Circulatory System'
    elif code.startswith('J'):
        return 'Respiratory System'
    elif code.startswith('K'):
        return 'Digestive System'
    elif code.startswith('M'):
        return 'Musculoskeletal'
    elif code.startswith('S') or code.startswith('T'):
        return 'Injuries & External'
    elif code.startswith('O') or 'pregnancy' in desc or 'labour' in desc:
        return 'Pregnancy & Childbirth'
    else:
        return 'Other'

def find_column_index(df, keywords, start_row=0, max_search=5):
    for row in range(start_row, min(start_row + max_search, len(df))):
        for col in range(df.shape[1]):
            cell = str(df.iloc[row, col]).lower()
            for kw in keywords:
                if kw in cell:
                    return col
    return None

def process_file(filepath):
    year = os.path.basename(filepath).split('-tab')[0].split('sum-')[-1]
    print(f"  Processing: {year}")

    df = pd.read_excel(filepath, sheet_name=0, header=None)
    header_row = next((i for i in range(5) if 'primary diagnosis' in str(df.iloc[i, 0]).lower()), 0)

    fce_col = find_column_index(df, ['finished consultant', 'finished admission', 'fce'], header_row) or 2
    adm_col = find_column_index(df, ['admissions'], header_row)
    em_col = find_column_index(df, ['emergency'], header_row)

    records = []
    for i in range(header_row + 1, len(df)):
        code = clean_code(df.iloc[i, 0])
        if not code or 'total' in code.lower():
            continue
        desc = str(df.iloc[i, 1]).strip() if pd.notna(df.iloc[i, 1]) else ''
        chapter = get_chapter(code, desc)
        try:
            fce = float(df.iloc[i, fce_col]) if pd.notna(df.iloc[i, fce_col]) else 0
            adm = float(df.iloc[i, adm_col]) if adm_col and pd.notna(df.iloc[i, adm_col]) else 0
            em = float(df.iloc[i, em_col]) if em_col and pd.notna(df.iloc[i, em_col]) else 0
        except:
            continue
        records.append({
            'Year': year,
            'Diagnosis_Code': code,
            'Description': desc[:80],
            'Chapter': chapter,
            'FCE': int(round(fce)),
            'Admissions': int(round(adm)),
            'Emergency': int(round(em))
        })
    return pd.DataFrame(records)


if __name__ == "__main__":
    files = sorted(glob.glob(os.path.join(BASE_DIR, "hosp-epis-stat-admi-prim-diag-sum-*-tab.xlsx")))
    if not files:
        print("No files found")
        exit()

    print(f"Found {len(files)} files\n")
    all_data = [process_file(f) for f in files]
    final = pd.concat(all_data, ignore_index=True)

    # Calculate Baseline_2019 (match by first 3 digits of code)
    print("Calculating Baseline_2019 (matching by first 3 characters of code)...")

    # Create 3-character prefix
    final['Code_Prefix'] = final['Diagnosis_Code'].str[:3]

    # Find sum of FCE for each Code_Prefix in 2019-20
    baseline_df = final[final['Year'] == '2019-20'].groupby('Code_Prefix')['FCE'].sum().reset_index()
    baseline_df = baseline_df.rename(columns={'FCE': 'Baseline_2019'})

    # Merge
    final = final.merge(baseline_df, on='Code_Prefix', how='left')

    # Calculate Pct_Change_2019
    final['Pct_Change_2019'] = final.apply(
        lambda x: round((x['FCE'] - x['Baseline_2019']) / x['Baseline_2019'] * 100, 1)
        if pd.notna(x['Baseline_2019']) and x['Baseline_2019'] > 0 else None, axis=1
    )

    final['Emergency_Percent'] = (final['Emergency'] / final['Admissions'] * 100).round(2)

    final = final.sort_values(['Year', 'Chapter', 'FCE'], ascending=[True, True, False]).reset_index(drop=True)

    output_path = os.path.join(BASE_DIR, "HES_2018-2024_Prefix_Match.csv")
    final.to_csv(output_path, index=False, encoding='utf-8-sig')

    print(f"\nCompleted! Total {len(final)} rows")
    print(f"Saved to: {output_path}")

    missing = final['Baseline_2019'].isna().sum()
    print(f"Rows missing Baseline: {missing}")

    print("\nPreview of first 15 rows:")
    print(final[['Year', 'Diagnosis_Code', 'Code_Prefix', 'FCE', 'Baseline_2019', 'Pct_Change_2019']].head(15).to_string())